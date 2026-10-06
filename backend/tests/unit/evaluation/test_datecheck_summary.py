"""The date check summary: counts by kind for the snapshot."""

from __future__ import annotations

import pytest

from gwylio.evaluation.datecheck import summarise_findings

KINDS = ["passed_horizon", "future_language", "stale_verification", "never_verified"]


def test_counts_every_kind_in_order_and_the_reports_flagged() -> None:
    summary = summarise_findings(
        [("a", "never_verified"), ("a", "future_language"), ("b", "never_verified")], KINDS
    )
    assert summary.counts == (
        ("passed_horizon", 0),
        ("future_language", 1),
        ("stale_verification", 0),
        ("never_verified", 2),
    )
    assert summary.total == 3
    assert summary.reports_flagged == 2
    assert summary.count("never_verified") == 2


def test_an_unknown_kind_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown date check kinds: rot"):
        summarise_findings([("a", "rot")], KINDS)
