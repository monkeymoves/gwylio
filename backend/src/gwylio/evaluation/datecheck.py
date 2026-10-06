"""A summary of the date check for the picture: how many findings of each kind.

The date check itself belongs to the Intelligence context
(``gwylio.intelligence.datecheck``). Evaluation only counts what it found, so
the snapshot and the products can say how much of the register needs a look.
The infrastructure layer hands the findings in as ``(report id, kind)`` pairs
and the kinds in the order to report them.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

__all__ = ["DateCheckSummary", "summarise_findings"]


@dataclass(frozen=True, slots=True)
class DateCheckSummary:
    """Findings counted by kind (every kind listed, zeros included) and reports flagged."""

    counts: tuple[tuple[str, int], ...]
    reports_flagged: int

    @property
    def total(self) -> int:
        """Every finding."""
        return sum(count for _, count in self.counts)

    def count(self, kind: str) -> int:
        """The findings of one kind."""
        return dict(self.counts).get(kind, 0)


def summarise_findings(
    findings: Iterable[tuple[str, str]], kinds: Sequence[str]
) -> DateCheckSummary:
    """Count ``(report id, kind)`` findings per kind, in the order ``kinds`` gives.

    Raises ``ValueError`` for a finding whose kind is not listed.
    """
    listed = list(findings)
    unknown = sorted({kind for _, kind in listed} - set(kinds))
    if unknown:
        raise ValueError(f"unknown date check kinds: {', '.join(unknown)}")
    tally = Counter(kind for _, kind in listed)
    return DateCheckSummary(
        counts=tuple((kind, tally[kind]) for kind in kinds),
        reports_flagged=len({report_id for report_id, _ in listed}),
    )
