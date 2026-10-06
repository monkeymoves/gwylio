"""The date check: which reports may have rotted since they were written.

A claim that was true when written can stop being true without anyone
noticing (rot). ``date_check`` is a pure function of the reports, today's date
and the configured future-framed phrases; it informs, it never blocks. It
looks only at reports still in the picture (every state but faded and
parked):

- ``passed_horizon`` (act): the event horizon is before today and no history
  entry that records someone looking (created, imported, updated or
  verified) is dated on or after it, so nobody has looked since the event was
  due. A sighting, or the lifecycle change it causes, is the collector
  re-finding a page, not a look;
- ``future_language`` (warn): the title, summary or notes contain a
  future-framed phrase such as "forthcoming", which reads wrong once the
  future arrives;
- ``stale_verification`` (warn): ``last_verified`` is more than 45 days ago;
- ``never_verified`` (act): ``last_verified`` is missing.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Final

from gwylio.intelligence.model import HistoryKind, IntelligenceReport
from gwylio.shared.values import CleanText, IsoDate, KebabId

__all__ = [
    "LOOKS",
    "STALE_AFTER_DAYS",
    "DateCheckFinding",
    "FindingKind",
    "Severity",
    "date_check",
    "phrase_pattern",
]

STALE_AFTER_DAYS: Final[int] = 45
"""A verification older than this many days is stale."""

LOOKS: Final[frozenset[HistoryKind]] = frozenset(
    {HistoryKind.CREATED, HistoryKind.IMPORTED, HistoryKind.UPDATED, HistoryKind.VERIFIED}
)
"""History kinds that record a person looking at the report, which clear a passed horizon."""


class FindingKind(StrEnum):
    """What the date check found wrong with a report."""

    PASSED_HORIZON = "passed_horizon"
    FUTURE_LANGUAGE = "future_language"
    STALE_VERIFICATION = "stale_verification"
    NEVER_VERIFIED = "never_verified"

    @property
    def meaning(self) -> str:
        """One sentence on what this kind of finding means."""
        return _KIND_MEANINGS[self]


_KIND_MEANINGS: Final[dict[FindingKind, str]] = {
    FindingKind.PASSED_HORIZON: (
        "The event horizon has passed and nobody has updated or verified the report since."
    ),
    FindingKind.FUTURE_LANGUAGE: (
        "The title, summary or notes use future-framed language that rots once the date passes."
    ),
    FindingKind.STALE_VERIFICATION: "The report was last verified more than 45 days ago.",
    FindingKind.NEVER_VERIFIED: "The report has never been verified against its source.",
}


class Severity(StrEnum):
    """How urgent a finding is: ``act`` before the report is quoted again, ``warn`` to check."""

    WARN = "warn"
    ACT = "act"


@dataclass(frozen=True, slots=True)
class DateCheckFinding:
    """One reason to look at one report again."""

    report_id: KebabId
    kind: FindingKind
    detail: CleanText
    severity: Severity


def phrase_pattern(phrases: Iterable[str]) -> re.Pattern[str] | None:
    """One case-insensitive pattern matching any phrase as whole words, or ``None`` for none."""
    cleaned = sorted({" ".join(p.casefold().split()) for p in phrases if p.strip()}, key=len)
    if not cleaned:
        return None
    alternatives = "|".join(
        r"\s+".join(re.escape(word) for word in phrase.split()) for phrase in reversed(cleaned)
    )
    return re.compile(rf"\b(?:{alternatives})\b", re.IGNORECASE)


def _as_date(today: IsoDate | date) -> date:
    return today.value if isinstance(today, IsoDate) else today


def date_check(
    reports: Iterable[IntelligenceReport],
    today: IsoDate | date,
    phrases: Sequence[str],
    *,
    stale_after_days: int = STALE_AFTER_DAYS,
) -> list[DateCheckFinding]:
    """Every finding for the reports still in the picture, by kind then report id."""
    now = _as_date(today)
    pattern = phrase_pattern(phrases)
    findings: list[DateCheckFinding] = []
    for report in reports:
        if not report.state.live:
            continue
        horizon = report.event_horizon
        if (
            horizon is not None
            and horizon.value < now
            and not any(entry.on >= horizon and entry.kind in LOOKS for entry in report.history)
        ):
            days = (now - horizon.value).days
            findings.append(
                DateCheckFinding(
                    report.id,
                    FindingKind.PASSED_HORIZON,
                    CleanText(
                        f"event horizon {horizon} passed {days} day"
                        f"{'s' if days != 1 else ''} ago and nobody has updated or verified the "
                        "report since"
                    ),
                    Severity.ACT,
                )
            )
        if pattern is not None:
            for name, text in (
                ("title", report.title),
                ("summary", report.summary),
                ("notes", report.notes),
            ):
                found = sorted(
                    {" ".join(m.group(0).casefold().split()) for m in pattern.finditer(text)}
                )
                if found:
                    findings.append(
                        DateCheckFinding(
                            report.id,
                            FindingKind.FUTURE_LANGUAGE,
                            CleanText(
                                f"{name} uses future-framed language: "
                                + ", ".join(f"'{phrase}'" for phrase in found)
                            ),
                            Severity.WARN,
                        )
                    )
        verified = report.last_verified
        if verified is None:
            findings.append(
                DateCheckFinding(
                    report.id,
                    FindingKind.NEVER_VERIFIED,
                    CleanText("never verified against its source"),
                    Severity.ACT,
                )
            )
        elif (now - verified.value).days > stale_after_days:
            age = (now - verified.value).days
            findings.append(
                DateCheckFinding(
                    report.id,
                    FindingKind.STALE_VERIFICATION,
                    CleanText(
                        f"last verified {verified}, {age} days ago (more than {stale_after_days})"
                    ),
                    Severity.WARN,
                )
            )
    order = list(FindingKind)
    return sorted(findings, key=lambda f: (order.index(f.kind), f.report_id, f.detail))
