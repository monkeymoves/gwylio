"""Submission and sweep file names, the replay order and the sweep file contract."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from gwylio.processing.ingest import (
    SweepFile,
    dumps_sweep,
    loads_sweep,
    next_submission_stem,
    next_sweep_stem,
    replay_order,
)


def test_submission_stems_count_up_per_run_or_per_day() -> None:
    existing = ["20261006T0215Z-3f9a__1", "20261006T0215Z-3f9a__2", "legacy__2026-07-25"]
    assert next_submission_stem("20261006T0215Z-3f9a", "2026-10-06", existing) == (
        "20261006T0215Z-3f9a__3"
    )
    assert next_submission_stem("20261007T0215Z-0000", "2026-10-07", existing) == (
        "20261007T0215Z-0000__1"
    )
    assert next_submission_stem(None, "2026-10-06", ["direct__2026-10-06__1"]) == (
        "direct__2026-10-06__2"
    )
    assert next_sweep_stem("2026-10-06", ["2026-10-06__1", "2026-10-05__4"]) == "2026-10-06__2"


def test_replay_order_sorts_submissions_and_places_each_sweep() -> None:
    steps = replay_order(
        [("2026-10-02", "b__1"), ("2026-07-25", "legacy__2026-07-25"), ("2026-10-02", "a__1")],
        [(3, "2026-10-03__1"), (1, "2026-09-01__1"), (0, "2026-07-01__1")],
    )
    assert steps == [
        ("sweep", "2026-07-01__1"),
        ("submission", "legacy__2026-07-25"),
        ("sweep", "2026-09-01__1"),
        ("submission", "a__1"),
        ("submission", "b__1"),
        ("sweep", "2026-10-03__1"),
    ]
    with pytest.raises(ValueError, match="ran after 2 submissions, but only 1 exist"):
        replay_order([("2026-10-02", "a__1")], [(2, "2026-10-03__1")])


def test_a_sweep_file_round_trips_and_needs_a_fade() -> None:
    document = SweepFile(
        format="gwylio.sweep/1",
        on="2026-10-06",
        after_submissions=2,
        faded=[{"report_id": "quiet", "change": "no sighting"}],  # type: ignore[list-item]
    )
    assert loads_sweep(dumps_sweep(document)) == document
    with pytest.raises(ValidationError):
        loads_sweep(
            '{"format": "gwylio.sweep/1", "on": "2026-10-06", "after_submissions": 0, "faded": []}'
        )
