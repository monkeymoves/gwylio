"""Scanability and the coverage status rule: the single place a blind spot is told apart from quiet.

A requirement with no active reports means two very different things. If
public sources can see it (high or medium scanability), silence is a finding:
the requirement is quiet. If they cannot (low or no scanability), silence is
not evidence: the requirement is a blind spot. A blind spot is never rendered
as quiet, and every caller asks ``coverage_status`` rather than deciding for
itself.

``Scanability`` belongs to the Direction context's language (a requirement's
scanability is configuration) and ``coverage_status`` to Direction's picture,
but Evaluation (the coverage audit) and Dissemination (the products) apply the
same rule. The dependency rule lets a context import only ``gwylio.shared``, so
both live here, in the shared kernel, and ``gwylio.direction`` re-exports them.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

__all__ = ["COVERED_MIN_REPORTS", "CoverageStatus", "Scanability", "coverage_status"]

COVERED_MIN_REPORTS: Final[int] = 3
"""The number of active reports at which a requirement counts as covered."""


class Scanability(StrEnum):
    """How far public, indexed sources can see a requirement at all."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"

    @property
    def meaning(self) -> str:
        """One sentence on what this value means for the scan."""
        return _SCANABILITY_MEANINGS[self]

    @property
    def sees_movement(self) -> bool:
        """True when public sources would show movement if there were any (high or medium)."""
        return self in (Scanability.HIGH, Scanability.MEDIUM)


_SCANABILITY_MEANINGS: Final[dict[Scanability, str]] = {
    Scanability.HIGH: "Public sources see the drivers and the evidence well.",
    Scanability.MEDIUM: "Public sources see the drivers, but the evidence only at release.",
    Scanability.LOW: "Evidence is mostly internal; public sources see it only in known windows.",
    Scanability.NONE: "Evidence is wholly internal; no public source will ever report on it.",
}


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
        if not scanability.sees_movement:
            return CoverageStatus.BLIND_SPOT
        return CoverageStatus.QUIET
    if active_report_count < COVERED_MIN_REPORTS:
        return CoverageStatus.THIN
    return CoverageStatus.COVERED
