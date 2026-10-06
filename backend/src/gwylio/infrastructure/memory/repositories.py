"""Dictionary-backed repositories for every Collection port, and two ``KnownReports``."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from gwylio.collection.dedup import normalise_title
from gwylio.collection.model import (
    Candidate,
    QueryInstrument,
    Reinforcement,
    RunId,
    RunImmutable,
    ScanRun,
    Sighting,
    Source,
)
from gwylio.shared.errors import DomainError, DuplicateId, UnknownReference
from gwylio.shared.values import CanonicalUrl

__all__ = [
    "MemoryCandidateRepository",
    "MemoryInstrumentRepository",
    "MemoryScanRunRepository",
    "MemorySourceRepository",
    "NullKnownReports",
    "StaticKnownReports",
]


class MemorySourceRepository:
    """The watchlist, in insertion order."""

    def __init__(self, sources: Sequence[Source] = ()) -> None:
        self._sources: dict[str, Source] = {}
        for source in sources:
            self.add(source)

    def add(self, source: Source) -> None:
        if source.id in self._sources:
            raise DuplicateId(f"source '{source.id}' is already stored", scope="sources")
        self._sources[source.id] = source

    def get(self, source_id: str) -> Source | None:
        return self._sources.get(source_id)

    def all(self) -> tuple[Source, ...]:
        return tuple(self._sources.values())


class MemoryInstrumentRepository:
    """Instrument versions; a stored version never changes."""

    def __init__(self) -> None:
        self._versions: dict[str, QueryInstrument] = {}

    def add(self, instrument: QueryInstrument) -> None:
        stored = self._versions.get(instrument.version)
        if stored is not None:
            if stored.content_hash == instrument.content_hash:
                return
            raise DomainError(
                f"instrument version {instrument.version} is already stored with a different hash",
                scope="instrument",
            )
        self._versions[instrument.version] = instrument

    def get(self, version: str) -> QueryInstrument | None:
        return self._versions.get(version)


class MemoryScanRunRepository:
    """Finished runs, oldest first."""

    def __init__(self) -> None:
        self._runs: dict[str, ScanRun] = {}

    def add(self, run: ScanRun) -> None:
        if not run.finished:
            raise DomainError(f"run {run.id} is still running; store it when it finishes")
        if run.id in self._runs:
            raise RunImmutable(f"run {run.id} is already stored and cannot change")
        self._runs[run.id] = run

    def get(self, run_id: str) -> ScanRun | None:
        return self._runs.get(run_id)

    def all(self) -> tuple[ScanRun, ...]:
        return tuple(sorted(self._runs.values(), key=lambda run: (run.started_at, run.id)))


class MemoryCandidateRepository:
    """Candidates, sightings and reinforcements, with the uniqueness rules persistence keeps."""

    def __init__(self) -> None:
        self._candidates: dict[str, Candidate] = {}
        self._urls_by_run: dict[tuple[str, str], str] = {}
        self._sightings: dict[str, Sighting] = {}
        self._reinforcements: list[Reinforcement] = []

    def add_candidates(self, candidates: Sequence[Candidate]) -> None:
        for candidate in candidates:
            if candidate.id in self._candidates:
                raise DuplicateId(f"candidate '{candidate.id}' is already stored")
            key = (candidate.run_id, candidate.canonical_url.value)
            if key in self._urls_by_run:
                raise DuplicateId(
                    f"run {candidate.run_id} already has a candidate for "
                    f"{candidate.canonical_url.value}"
                )
            self._candidates[candidate.id] = candidate
            self._urls_by_run[key] = candidate.id

    def add_sightings(self, sightings: Sequence[Sighting]) -> None:
        for sighting in sightings:
            if sighting.id in self._sightings:
                raise DuplicateId(f"sighting '{sighting.id}' is already stored")
            if sighting.candidate_id not in self._candidates:
                raise UnknownReference(f"sighting of unknown candidate '{sighting.candidate_id}'")
            self._sightings[sighting.id] = sighting

    def add_reinforcements(self, reinforcements: Sequence[Reinforcement]) -> None:
        for reinforcement in reinforcements:
            if reinforcement.candidate_id not in self._candidates:
                raise UnknownReference(
                    f"reinforcement of unknown candidate '{reinforcement.candidate_id}'"
                )
            self._reinforcements.append(reinforcement)

    def candidates_for_run(self, run_id: str) -> tuple[Candidate, ...]:
        return tuple(c for c in self._candidates.values() if c.run_id == run_id)

    def sightings_for_run(self, run_id: str) -> tuple[Sighting, ...]:
        return tuple(s for s in self._sightings.values() if s.run_id == run_id)

    def reinforcements_for_run(self, run_id: str) -> tuple[Reinforcement, ...]:
        ours = {c.id for c in self.candidates_for_run(run_id)}
        return tuple(r for r in self._reinforcements if r.candidate_id in ours)

    def canonical_urls_before(self, run_id: str) -> Mapping[str, RunId]:
        first_seen: dict[str, RunId] = {}
        for candidate in self._candidates.values():
            if candidate.run_id == run_id:
                continue
            url = candidate.canonical_url.value
            earlier = first_seen.get(url)
            if earlier is None or candidate.first_seen_run_id < earlier:
                first_seen[url] = candidate.first_seen_run_id
        return first_seen


class NullKnownReports:
    """A register with no reports, until the Intelligence context arrives."""

    def report_id_for_url(self, canonical_url: CanonicalUrl) -> str | None:
        return None

    def report_id_for_title(self, normalised_title: str) -> str | None:
        return None


class StaticKnownReports:
    """A fixed register: report ids by evidence URL and by title, for tests."""

    def __init__(
        self,
        by_url: Mapping[str, str] | None = None,
        by_title: Mapping[str, str] | None = None,
    ) -> None:
        self._by_url = {CanonicalUrl(url).value: report for url, report in (by_url or {}).items()}
        self._by_title = {
            normalise_title(title): report for title, report in (by_title or {}).items()
        }

    def report_id_for_url(self, canonical_url: CanonicalUrl) -> str | None:
        return self._by_url.get(canonical_url.value)

    def report_id_for_title(self, normalised_title: str) -> str | None:
        return self._by_title.get(normalised_title)
