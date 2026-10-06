"""The date check: each finding kind fires when it should and only then."""

from __future__ import annotations

from datetime import date

import pytest

from gwylio.intelligence.datecheck import (
    DateCheckFinding,
    FindingKind,
    Severity,
    date_check,
    phrase_pattern,
)
from gwylio.intelligence.model import HistoryEntry, HistoryKind, IndicatorState
from gwylio.shared.values import CleanText, IsoDate
from tests.unit.intelligence.fakes import report

TODAY = IsoDate("2026-10-06")
PHRASES = (
    "upcoming",
    "forthcoming",
    "will be published",
    "due to",
    "expected to",
    "consultation closes",
    "later this year",
    "next year",
    "imminent",
    "about to",
)


def kinds(findings: list[DateCheckFinding]) -> list[tuple[str, FindingKind]]:
    return [(f.report_id, f.kind) for f in findings]


def created(on: str) -> tuple[HistoryEntry, ...]:
    return (HistoryEntry(IsoDate(on), HistoryKind.CREATED, CleanText("created")),)


def test_a_clean_recent_report_has_no_findings() -> None:
    assert date_check([report(last_verified="2026-10-01")], TODAY, PHRASES) == []


def test_passed_horizon_fires_and_is_an_action() -> None:
    [finding] = date_check(
        [report(event_horizon="2026-09-30", last_verified="2026-10-01")], TODAY, PHRASES
    )
    assert finding.kind is FindingKind.PASSED_HORIZON
    assert finding.severity is Severity.ACT
    assert finding.detail.startswith("event horizon 2026-09-30 passed 6 days ago")


def test_a_horizon_today_or_later_has_not_passed() -> None:
    for horizon in ("2026-10-06", "2027-01-01"):
        stale = report(event_horizon=horizon, last_verified="2026-10-01")
        assert date_check([stale], TODAY, PHRASES) == []


def test_a_passed_horizon_with_a_later_look_is_not_flagged() -> None:
    history = (
        *created("2026-09-01"),
        HistoryEntry(IsoDate("2026-09-30"), HistoryKind.UPDATED, CleanText("closed; result due")),
    )
    looked = report(event_horizon="2026-09-30", last_verified="2026-10-01", history=history)
    assert date_check([looked], TODAY, PHRASES) == []


def test_a_sighting_after_the_horizon_is_not_a_look() -> None:
    history = (
        *created("2026-09-01"),
        HistoryEntry(IsoDate("2026-10-02"), HistoryKind.SIGHTED, CleanText("sighted in run x")),
        HistoryEntry(IsoDate("2026-10-02"), HistoryKind.STATE_CHANGED, CleanText("to tracking")),
    )
    sighted = report(event_horizon="2026-09-30", last_verified="2026-09-02", history=history)
    assert kinds(date_check([sighted], TODAY, PHRASES)) == [
        ("drought-2026", FindingKind.PASSED_HORIZON)
    ]


@pytest.mark.parametrize("field", ["title", "summary", "notes"])
def test_future_language_fires_per_field(field: str) -> None:
    text = {"title": "A plan", "summary": "A plan.", "notes": ""}
    text[field] = "Results are Forthcoming, and the consultation   closes soon"
    flagged = report(last_verified="2026-10-01", **text)  # type: ignore[arg-type]
    [finding] = date_check([flagged], TODAY, PHRASES)
    assert finding.kind is FindingKind.FUTURE_LANGUAGE
    assert finding.severity is Severity.WARN
    assert finding.detail == (
        f"{field} uses future-framed language: 'consultation closes', 'forthcoming'"
    )


def test_future_language_matches_whole_words_only() -> None:
    quiet = report(summary="An imminently overdue release; the upcomingness of it all.")
    assert date_check([quiet], TODAY, PHRASES) == []
    assert phrase_pattern([]) is None
    assert phrase_pattern(["  "]) is None


def test_stale_and_never_verified() -> None:
    old = report("old", last_verified="2026-08-21")
    edge = report("edge", last_verified="2026-08-22")
    never = report("never", last_verified=None)
    findings = date_check([old, edge, never], TODAY, PHRASES)
    assert kinds(findings) == [
        ("old", FindingKind.STALE_VERIFICATION),
        ("never", FindingKind.NEVER_VERIFIED),
    ]
    assert findings[0].detail == "last verified 2026-08-21, 46 days ago (more than 45)"
    assert findings[1].severity is Severity.ACT
    assert date_check([old], TODAY, PHRASES, stale_after_days=60) == []


def test_faded_and_parked_reports_are_not_checked_but_matured_ones_are() -> None:
    reports = [
        report(state, state=state, last_verified=None, created_on="2025-12-01")
        for state in IndicatorState
        if state is not IndicatorState.EMERGING
    ]
    flagged = {f.report_id for f in date_check(reports, TODAY, PHRASES)}
    assert flagged == {"tracking", "reinforced", "matured"}


def test_findings_sort_by_kind_then_report_and_take_a_plain_date() -> None:
    reports = [
        report("b", last_verified=None),
        report(
            "a", event_horizon="2026-01-01", created_on="2025-12-01", last_verified="2026-08-01"
        ),
    ]
    findings = date_check(reports, date(2026, 10, 6), PHRASES)
    assert kinds(findings) == [
        ("a", FindingKind.PASSED_HORIZON),
        ("a", FindingKind.STALE_VERIFICATION),
        ("b", FindingKind.NEVER_VERIFIED),
    ]
