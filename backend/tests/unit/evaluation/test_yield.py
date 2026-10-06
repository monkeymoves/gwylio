"""Yield per source: every reading reached by a constructed case."""

from __future__ import annotations

from gwylio.evaluation.yield_ import (
    HIGH_VOLUME_CANDIDATES,
    CandidateFacts,
    SightingFacts,
    SourceFacts,
    YieldReading,
    compute_yield,
)
from gwylio.shared.vocabulary import DispositionOutcome

R1, R2, R3 = "20260901T0900Z-0000", "20261001T0900Z-0000", "20261101T0900Z-0000"


def sightings_for(source: str, run: str, candidates: list[str]) -> list[SightingFacts]:
    return [SightingFacts(f"s-{source}-{run}-{c}", run, c, source) for c in candidates]


def build() -> tuple[list[SourceFacts], list[SightingFacts], list[CandidateFacts]]:
    sources = [
        SourceFacts("earner", "Earner", True),
        SourceFacts("noisy", "Noisy", True),
        SourceFacts("small", "Small", True),
        SourceFacts("silent", "Silent", True),
        SourceFacts("parked", "Parked", False),
    ]
    noisy = [f"n{i}" for i in range(HIGH_VOLUME_CANDIDATES)]
    sightings = [
        *sightings_for("earner", R1, ["e1", "e2"]),
        *sightings_for("earner", R2, ["e3"]),
        *sightings_for("earner", R3, ["e1"]),
        *sightings_for("noisy", R2, noisy),
        *sightings_for("small", R1, ["m1"]),
        SightingFacts("s-anon", R1, "x1", None),
    ]
    candidates = [
        CandidateFacts("e1", R1, "earner"),
        CandidateFacts("e2", R1, "earner"),
        CandidateFacts("e3", R2, "earner"),
        *(CandidateFacts(c, R2, "noisy") for c in noisy),
        CandidateFacts("m1", R1, "small"),
        CandidateFacts("x1", R1, None),
    ]
    return sources, sightings, candidates


def test_each_reading_is_reached() -> None:
    sources, sightings, candidates = build()
    dispositions = {
        "e1": DispositionOutcome.PROMOTED,
        "e2": DispositionOutcome.REJECTED,
        "e3": DispositionOutcome.PROMOTED,
        "n0": DispositionOutcome.REJECTED,
        "x1": DispositionOutcome.PROMOTED,
    }
    result = {y.source_id: y for y in compute_yield(sources, sightings, candidates, dispositions)}
    assert [y for y in result] == ["earner", "noisy", "small", "silent", "parked"]
    earner = result["earner"]
    assert earner.reading is YieldReading.EARNING_ITS_PLACE
    assert (earner.raw_hits, earner.unique_candidates, earner.promoted) == (4, 3, 2)
    assert earner.promotion_rate == 2 / 3
    assert earner.last_run_with_hits == R3
    assert earner.last_productive_run == R2
    noisy = result["noisy"]
    assert noisy.reading is YieldReading.HIGH_VOLUME_NO_PROMOTIONS
    assert noisy.unique_candidates == HIGH_VOLUME_CANDIDATES and noisy.promotion_rate == 0
    assert noisy.last_productive_run is None
    small = result["small"]
    assert small.reading is YieldReading.LOW_VOLUME
    assert (small.raw_hits, small.unique_candidates, small.last_run_with_hits) == (1, 1, R1)
    silent = result["silent"]
    assert silent.reading is YieldReading.SILENT
    assert silent.raw_hits == 0 and silent.promotion_rate is None
    assert silent.last_run_with_hits is None and silent.last_productive_run is None


def test_silent_sources_are_listed_and_only_active_ones_read_silent() -> None:
    sources, sightings, candidates = build()
    result = compute_yield(sources, sightings, candidates, {})
    silent = [y.source_id for y in result if y.reading is YieldReading.SILENT]
    assert silent == ["silent"]
    parked = next(y for y in result if y.source_id == "parked")
    assert parked.reading is YieldReading.LOW_VOLUME and not parked.active


def test_one_fewer_than_the_threshold_is_low_volume() -> None:
    sources = [SourceFacts("s", "S", True)]
    ids = [f"c{i}" for i in range(HIGH_VOLUME_CANDIDATES - 1)]
    sightings = sightings_for("s", R1, ids)
    candidates = [CandidateFacts(c, R1, "s") for c in ids]
    [only] = compute_yield(sources, sightings, candidates, {})
    assert only.reading is YieldReading.LOW_VOLUME


def test_every_reading_has_a_meaning() -> None:
    assert all(reading.meaning.endswith(".") for reading in YieldReading)
    assert [r.value for r in YieldReading] == [
        "earning_its_place",
        "high_volume_no_promotions",
        "low_volume",
        "silent",
    ]
