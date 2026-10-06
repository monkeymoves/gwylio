"""The coverage status rule, as the Direction context names it.

The rule itself lives in ``gwylio.shared.coverage`` so that the Evaluation and
Dissemination contexts can apply it without importing Direction; this module
re-exports it so Direction's language stays whole. A requirement with no
active reports and low or no scanability is a blind spot, never quiet.
"""

from __future__ import annotations

from gwylio.shared.coverage import COVERED_MIN_REPORTS, CoverageStatus, coverage_status

__all__ = ["COVERED_MIN_REPORTS", "CoverageStatus", "coverage_status"]
