"""The Intelligence context's ports: what it needs from the outside world.

Every port is a ``Protocol`` that infrastructure satisfies structurally. The
facts the register needs from Collection (sightings, the runs they came from,
the watchlist's grades) arrive as the small frozen records defined here, so
this context never imports Collection.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from gwylio.intelligence.model import IntelligenceReport
from gwylio.shared.values import CanonicalUrl, CleanText, IsoDate, KebabId, RunId
from gwylio.shared.vocabulary import DispositionOutcome, Reliability

__all__ = [
    "DispositionRecord",
    "ReportRepository",
    "RunFact",
    "SightingFact",
    "SightingLookup",
    "SourceDirectory",
    "SourceInfo",
    "SubmissionRecord",
    "SubmissionRepository",
]


@dataclass(frozen=True, slots=True)
class SightingFact:
    """One stored sighting, with when its run started: what lifecycle maths counts."""

    sighting_id: KebabId
    run_id: RunId
    run_started_at: datetime
    candidate_id: KebabId
    source_id: KebabId | None

    @property
    def run_order(self) -> tuple[datetime, str]:
        """How runs sort: by start instant, then by id."""
        return (self.run_started_at, str(self.run_id))


@dataclass(frozen=True, slots=True)
class RunFact:
    """One finished scan run, as the sweep sees it."""

    run_id: RunId
    started_at: datetime
    complete: bool
    raw_hits: int

    @property
    def order(self) -> tuple[datetime, str]:
        """How runs sort: by start instant, then by id."""
        return (self.started_at, str(self.run_id))


@dataclass(frozen=True, slots=True)
class SourceInfo:
    """What the register takes from a watched source: its grade, lane and actor."""

    source_id: KebabId
    name: CleanText
    reliability: Reliability
    lane: KebabId
    actor_id: KebabId


@dataclass(frozen=True, slots=True)
class SubmissionRecord:
    """One ingested submission file. ``id`` is the file name without ``.json``."""

    id: str
    run_id: RunId | None
    analyst: CleanText
    rubric_version: CleanText
    received_on: IsoDate
    method_note: CleanText


@dataclass(frozen=True, slots=True)
class DispositionRecord:
    """The fate one submission gave one candidate."""

    candidate_id: KebabId
    outcome: DispositionOutcome
    reason: CleanText
    report_id: KebabId | None


class ReportRepository(Protocol):
    """The register as stored."""

    def get(self, report_id: str) -> IntelligenceReport | None:
        """The report with this id, or ``None``."""
        ...

    def list(self) -> tuple[IntelligenceReport, ...]:
        """Every report, by id."""
        ...

    def list_active(self) -> tuple[IntelligenceReport, ...]:
        """Every report in an active state (emerging, tracking, reinforced), by id."""
        ...

    def save(self, report: IntelligenceReport) -> None:
        """Store the report, replacing a stored report with the same id."""
        ...

    def by_canonical_url(self, canonical_url: CanonicalUrl) -> IntelligenceReport | None:
        """The report whose canonical URL is this (the first by id when several share it)."""
        ...

    def by_normalised_title(self, normalised_title: str) -> IntelligenceReport | None:
        """The report whose normalised title is exactly this (the first by id), or ``None``."""
        ...


class SubmissionRepository(Protocol):
    """Every ingested submission and the dispositions it recorded."""

    def record(
        self, submission: SubmissionRecord, dispositions: Sequence[DispositionRecord]
    ) -> None:
        """Store a submission and its dispositions; refuse an id already stored."""
        ...

    def get(self, submission_id: str) -> SubmissionRecord | None:
        """The submission with this id, or ``None``."""
        ...

    def all(self) -> tuple[SubmissionRecord, ...]:
        """Every submission, in the order it was ingested."""
        ...

    def dispositions_for_candidate(
        self, candidate_id: str
    ) -> tuple[tuple[str, DispositionRecord], ...]:
        """Every earlier disposition of this candidate, with the submission id that gave it."""
        ...


class SightingLookup(Protocol):
    """The collection facts lifecycle maths needs, read from the collection tables."""

    def sightings_of_candidate(self, candidate_id: str) -> tuple[SightingFact, ...]:
        """Every sighting of the candidate, by sighting id."""
        ...

    def sightings(self, sighting_ids: Sequence[str]) -> tuple[SightingFact, ...]:
        """The named sightings, in the order given; unknown ids are left out."""
        ...

    def run(self, run_id: str) -> RunFact | None:
        """The stored run, or ``None``."""
        ...

    def runs(self) -> tuple[RunFact, ...]:
        """Every stored run, oldest first."""
        ...

    def report_of_sighting(self, sighting_id: str) -> str | None:
        """The report a sighting is already linked to, or ``None``."""
        ...


class SourceDirectory(Protocol):
    """The watchlist, as the register needs it."""

    def get(self, source_id: str) -> SourceInfo | None:
        """The watched source with this id, or ``None``."""
        ...
