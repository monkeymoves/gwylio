"""Funnel trend series and disposition summary arithmetic."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from gwylio.evaluation.funnel import FUNNEL_FIELDS, FunnelCounts, FunnelTrend, RunFunnel
from gwylio.shared.vocabulary import DispositionOutcome as O


def run(run_id: str, day: int, raw: int, new: int, requests: int = 10) -> RunFunnel:
    return RunFunnel(
        run_id=run_id,
        started_at=datetime(2026, 10, day, 9, 0, tzinfo=UTC),
        funnel=FunnelCounts(raw=raw, passed=raw, unique=new + 1, seen_before=1, new=new),
        requests_made=requests,
        budget_exhausted=False,
    )


TREND = FunnelTrend([run("b", 2, 30, 4, 12), run("a", 1, 20, 5, 8), run("c", 3, 0, 0, 1)])


def test_runs_are_ordered_by_start_and_latest_is_the_last() -> None:
    assert [r.run_id for r in TREND.runs] == ["a", "b", "c"]
    latest = TREND.latest()
    assert latest is not None and latest.run_id == "c"
    assert FunnelTrend([]).latest() is None


def test_series_and_totals() -> None:
    assert TREND.series("raw") == (("a", 20), ("b", 30), ("c", 0))
    assert TREND.series("new") == (("a", 5), ("b", 4), ("c", 0))
    assert TREND.series("requests_made") == (("a", 8), ("b", 12), ("c", 1))
    assert TREND.total("raw") == 50
    assert [r.run_id for r in TREND.last(2).runs] == ["b", "c"]
    assert TREND.last(0).runs == ()
    assert set(FUNNEL_FIELDS) >= {"raw", "unique", "new", "reinforcements"}
    with pytest.raises(ValueError, match="unknown funnel field"):
        TREND.series("promoted")


def test_disposition_summary_counts_every_outcome_and_the_promotion_rate() -> None:
    summary = TREND.disposition_summary("a", [O.PROMOTED, O.PROMOTED, O.REJECTED, O.DEFERRED])
    assert summary.counts == (
        (O.PROMOTED, 2),
        (O.REJECTED, 1),
        (O.DUPLICATE, 0),
        (O.DEFERRED, 1),
        (O.REINFORCEMENT, 0),
    )
    assert summary.promoted == 2
    assert summary.new == 5
    assert summary.disposed == 3
    assert summary.undisposed == 2
    assert summary.promotion_rate == pytest.approx(0.4)


def test_a_run_with_no_new_candidates_has_no_promotion_rate() -> None:
    summary = TREND.disposition_summary("c", [])
    assert summary.promotion_rate is None
    assert summary.undisposed == 0


def test_undisposed_never_goes_below_zero() -> None:
    summary = TREND.disposition_summary("b", [O.REJECTED] * 6)
    assert summary.undisposed == 0


def test_bad_inputs_are_refused() -> None:
    with pytest.raises(KeyError):
        TREND.disposition_summary("zzz", [])
    with pytest.raises(ValueError, match="once"):
        FunnelTrend([run("a", 1, 1, 1), run("a", 2, 1, 1)])
    with pytest.raises(ValueError, match="non-negative"):
        FunnelCounts(raw=-1)
