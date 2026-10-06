"""The Collection context's ports: what it needs from the outside world.

Every port is a ``Protocol``, so infrastructure satisfies it structurally and
this context never imports infrastructure. In-memory implementations live in
``gwylio.infrastructure.memory``; SQLite ones arrive with persistence and real
collectors with the HTTP adapters.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from gwylio.collection.model import (
    Candidate,
    Query,
    QueryInstrument,
    RawHit,
    Reinforcement,
    RunId,
    ScanRun,
    Sighting,
    Source,
)
from gwylio.shared.values import CanonicalUrl, CleanText, KebabId
from gwylio.shared.vocabulary import Discipline

__all__ = [
    "CandidateRepository",
    "CollectResult",
    "Collector",
    "IdGenerator",
    "InstrumentRepository",
    "KnownReports",
    "ScanRunRepository",
    "SourceRepository",
]


@dataclass(frozen=True, slots=True)
class CollectResult:
    """What one collector call returned.

    ``requests_used`` counts the requests actually made, which must not exceed
    the remaining budget the collector was given. ``warnings`` carry soft
    failures (a feed that would not parse, a source that timed out) that the
    run reports without stopping.
    """

    hits: tuple[RawHit, ...] = ()
    requests_used: int = 0
    warnings: tuple[CleanText, ...] = ()

    def __post_init__(self) -> None:
        if self.requests_used < 0:
            raise ValueError("requests_used cannot be negative")


@runtime_checkable
class Collector(Protocol):
    """An adapter that performs one discipline of collection."""

    @property
    def discipline(self) -> Discipline:
        """The discipline this collector serves."""
        ...

    def collect(
        self, query: Query, sources: Sequence[Source], remaining_budget: int
    ) -> CollectResult:
        """Run one query against ``sources`` (empty for open web and academic queries).

        Must make no more than ``remaining_budget`` requests, and must set each
        hit's ``query_id`` to ``query.id`` and its ``discipline`` to this
        collector's discipline.
        """
        ...


class SourceRepository(Protocol):
    """The watchlist as stored."""

    def add(self, source: Source) -> None:
        """Store a new source; refuse an id that is already stored."""
        ...

    def get(self, source_id: str) -> Source | None:
        """The source with this id, or ``None``."""
        ...

    def all(self) -> tuple[Source, ...]:
        """Every stored source, in insertion order."""
        ...


class InstrumentRepository(Protocol):
    """Every instrument version a run has used. A version, once stored, never changes."""

    def add(self, instrument: QueryInstrument) -> None:
        """Store a new version; refuse a stored version whose hash differs."""
        ...

    def get(self, version: str) -> QueryInstrument | None:
        """The instrument with this version, or ``None``."""
        ...


class ScanRunRepository(Protocol):
    """Every finished scan run."""

    def add(self, run: ScanRun) -> None:
        """Store a finished run; refuse a running run and a run id already stored."""
        ...

    def get(self, run_id: str) -> ScanRun | None:
        """The run with this id, or ``None``."""
        ...

    def all(self) -> tuple[ScanRun, ...]:
        """Every stored run, oldest first."""
        ...


class CandidateRepository(Protocol):
    """Candidates, their sightings and the reinforcements found at collection."""

    def add_candidates(self, candidates: Sequence[Candidate]) -> None:
        """Store candidates; refuse a repeated id or a canonical URL repeated within a run."""
        ...

    def add_sightings(self, sightings: Sequence[Sighting]) -> None:
        """Store sightings; refuse a repeated id or a sighting of an unknown candidate."""
        ...

    def add_reinforcements(self, reinforcements: Sequence[Reinforcement]) -> None:
        """Store reinforcements; refuse one for an unknown candidate."""
        ...

    def candidates_for_run(self, run_id: str) -> tuple[Candidate, ...]:
        """The run's candidates in insertion order."""
        ...

    def sightings_for_run(self, run_id: str) -> tuple[Sighting, ...]:
        """The run's sightings in insertion order."""
        ...

    def reinforcements_for_run(self, run_id: str) -> tuple[Reinforcement, ...]:
        """The run's reinforcements in insertion order."""
        ...

    def canonical_urls_before(self, run_id: str) -> Mapping[str, RunId]:
        """Every canonical URL that a run other than ``run_id`` recorded.

        Maps the canonical URL string to the run that first recorded it. Runs
        are stored only when they finish, so every stored run is earlier than
        the run being collected. This is what the seen index is built from.
        """
        ...


class KnownReports(Protocol):
    """What the register knows, for spotting reinforcements at collection time."""

    def report_id_for_url(self, canonical_url: CanonicalUrl) -> str | None:
        """The report whose evidence has this canonical URL, or ``None``."""
        ...

    def report_id_for_title(self, normalised_title: str) -> str | None:
        """The report whose normalised title is exactly this, or ``None``."""
        ...


class IdGenerator(Protocol):
    """Where new identifiers come from, so tests can make them predictable."""

    def run_id(self, started_at: datetime) -> RunId:
        """A new run id for a run starting at ``started_at``."""
        ...

    def candidate_id(self, run_id: RunId, canonical_url: CanonicalUrl, attempt: int) -> KebabId:
        """The id for this URL's candidate in this run; ``attempt`` resolves a collision."""
        ...

    def sighting_id(self, run_id: RunId, index: int) -> KebabId:
        """The id of the ``index``th sighting of the run, counting from 1."""
        ...
