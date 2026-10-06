"""The coverage status rule: the single place a blind spot is told apart from quiet.

A requirement with no active reports means two very different things. If
public sources can see it (high or medium scanability), silence is a finding:
the requirement is quiet. If they cannot (low or no scanability), silence is
not evidence: the requirement is a blind spot. A blind spot is never rendered
as quiet, and every caller asks this function rather than deciding for itself.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from gwylio.direction.model import Scanability

__all__ = ["COVERED_MIN_REPORTS", "CoverageStatus", "coverage_status"]

COVERED_MIN_REPORTS: Final[int] = 3
"""The number of active reports at which a requirement counts as covered."""


class CoverageStatus(StrEnum):
    """The state of one requirement in the picture."""

    COVERED = "covered"
    THIN = "thin"
    QUIET = "quiet"
    BLIND_SPOT = "blind_spot"

    @property
    def meaning(self) -> str:
        """One sentence on what this status means in the picture."""
        return _COVERAGE_MEANINGS[self]


_COVERAGE_MEANINGS: Final[dict[CoverageStatus, str]] = {
    CoverageStatus.COVERED: "Three or more active reports.",
    CoverageStatus.THIN: "One or two active reports.",
    CoverageStatus.QUIET: "No active reports, and public sources could see movement if there "
    "were any.",
    CoverageStatus.BLIND_SPOT: "No active reports, and public sources cannot see this requirement: "
    "absence is not evidence, so never call it quiet.",
}


def coverage_status(scanability: Scanability, active_report_count: int) -> CoverageStatus:
    """The coverage status of a requirement with this scanability and report count.

    No reports and low or no scanability is a blind spot; no reports and high or
    medium scanability is quiet; one or two reports is thin; three or more is
    covered. Raises ``ValueError`` on a negative count.
    """
    if isinstance(active_report_count, bool) or not isinstance(active_report_count, int):
        raise TypeError("active_report_count must be an int")
    if active_report_count < 0:
        raise ValueError(f"active_report_count cannot be negative, got {active_report_count}")
    if active_report_count == 0:
        if scanability in (Scanability.LOW, Scanability.NONE):
            return CoverageStatus.BLIND_SPOT
        return CoverageStatus.QUIET
    if active_report_count < COVERED_MIN_REPORTS:
        return CoverageStatus.THIN
    return CoverageStatus.COVERED
