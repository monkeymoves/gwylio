"""Yield per source: is each watched source earning its place on the watchlist?

Pure functions over plain inputs. The infrastructure layer reads the
watchlist, the stored sightings and candidates, and each candidate's final
disposition, and hands them in as the small records below.

For each source:

- ``raw_hits`` counts its stored sightings: the hits it returned that passed
  the gates (a dropped hit is counted in its run's funnel, never per source);
- ``unique_candidates`` counts the distinct candidates it sighted;
- ``promoted`` counts those candidates whose final disposition is
  ``promoted``, and ``promotion_rate`` is promoted over unique candidates;
- ``last_run_with_hits`` and ``last_productive_run`` name the latest run in
  which it sighted anything, and in which it sighted a candidate that was
  promoted.

The reading, checked in this order: ``earning_its_place`` (promoted at least
once); ``silent`` (an active source with no hit in any run);
``high_volume_no_promotions`` (20 or more candidates, none promoted);
``low_volume`` (fewer than 20, none promoted). Run ids sort by the minute the
run started, so the latest run is the greatest id.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from gwylio.shared.vocabulary import DispositionOutcome

__all__ = [
    "HIGH_VOLUME_CANDIDATES",
    "CandidateFacts",
    "SightingFacts",
    "SourceFacts",
    "SourceYield",
    "YieldReading",
    "compute_yield",
]

HIGH_VOLUME_CANDIDATES: Final[int] = 20
"""Candidates at which a source with no promotions reads as high volume rather than low."""


class YieldReading(StrEnum):
    """What a source's yield says about its place on the watchlist."""

    EARNING_ITS_PLACE = "earning_its_place"
    HIGH_VOLUME_NO_PROMOTIONS = "high_volume_no_promotions"
    LOW_VOLUME = "low_volume"
    SILENT = "silent"

    @property
    def meaning(self) -> str:
        """One sentence on what this reading means."""
        return _READING_MEANINGS[self]


_READING_MEANINGS: Final[dict[YieldReading, str]] = {
    YieldReading.EARNING_ITS_PLACE: "At least one of its candidates was promoted to a report.",
    YieldReading.HIGH_VOLUME_NO_PROMOTIONS: (
        "Twenty or more candidates and no promotion: noise to tune out or a query to tighten."
    ),
    YieldReading.LOW_VOLUME: "Fewer than twenty candidates and no promotion yet.",
    YieldReading.SILENT: "An active source that has not returned a hit in any run.",
}


@dataclass(frozen=True, slots=True)
class SourceFacts:
    """One watchlist entry, as the yield needs it."""

    source_id: str
    name: str
    active: bool


@dataclass(frozen=True, slots=True)
class SightingFacts:
    """One stored sighting: which run, which candidate, which source."""

    sighting_id: str
    run_id: str
    candidate_id: str
    source_id: str | None


@dataclass(frozen=True, slots=True)
class CandidateFacts:
    """One stored candidate and the run that found it."""

    candidate_id: str
    run_id: str
    source_id: str | None


@dataclass(frozen=True, slots=True)
class SourceYield:
    """How productive one source has been across every stored run."""

    source_id: str
    name: str
    active: bool
    raw_hits: int
    unique_candidates: int
    promoted: int
    last_run_with_hits: str | None
    last_productive_run: str | None
    reading: YieldReading

    @property
    def promotion_rate(self) -> float | None:
        """Promoted over unique candidates, or ``None`` when the source found none."""
        return None if self.unique_candidates == 0 else self.promoted / self.unique_candidates


def _reading(active: bool, hits: int, candidates: int, promoted: int) -> YieldReading:
    if promoted > 0:
        return YieldReading.EARNING_ITS_PLACE
    if active and hits == 0:
        return YieldReading.SILENT
    if candidates >= HIGH_VOLUME_CANDIDATES:
        return YieldReading.HIGH_VOLUME_NO_PROMOTIONS
    return YieldReading.LOW_VOLUME


def compute_yield(
    sources: Iterable[SourceFacts],
    sightings: Iterable[SightingFacts],
    candidates: Iterable[CandidateFacts],
    dispositions: Mapping[str, DispositionOutcome],
) -> tuple[SourceYield, ...]:
    """The yield of every source, in watchlist order.

    ``dispositions`` maps a candidate id to its final outcome (the latest that
    is not deferred); a candidate with none is not yet judged. Sightings name
    their run; ``candidates`` supply the run of a candidate when a sighting's
    run is needed for the last productive run.
    """
    run_of = {candidate.candidate_id: candidate.run_id for candidate in candidates}
    hits: dict[str, int] = {}
    seen: dict[str, set[str]] = {}
    last_hit: dict[str, str] = {}
    for sighting in sightings:
        if sighting.source_id is None:
            continue
        source_id = sighting.source_id
        hits[source_id] = hits.get(source_id, 0) + 1
        seen.setdefault(source_id, set()).add(sighting.candidate_id)
        if sighting.run_id > last_hit.get(source_id, ""):
            last_hit[source_id] = sighting.run_id
    result: list[SourceYield] = []
    for source in sources:
        found = seen.get(source.source_id, set())
        promoted_ids = {c for c in found if dispositions.get(c) is DispositionOutcome.PROMOTED}
        productive = max((run_of.get(c, "") for c in promoted_ids), default="")
        count = hits.get(source.source_id, 0)
        result.append(
            SourceYield(
                source_id=source.source_id,
                name=source.name,
                active=source.active,
                raw_hits=count,
                unique_candidates=len(found),
                promoted=len(promoted_ids),
                last_run_with_hits=last_hit.get(source.source_id),
                last_productive_run=productive or None,
                reading=_reading(source.active, count, len(found), len(promoted_ids)),
            )
        )
    return tuple(result)
