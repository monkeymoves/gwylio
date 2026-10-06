"""Every SQLite repository round-trips its aggregate and keeps the in-memory refusals."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from gwylio.collection.model import (
    Candidate,
    Query,
    Reinforcement,
    RunImmutable,
    RunStatus,
    ScanRun,
    Sighting,
    Source,
    SourceStatus,
)
from gwylio.collection.ports import CollectResult
from gwylio.collection.service import RunResult, RunScan, ScanAborted
from gwylio.infrastructure.collectors.fake import FakeCollector, load_fake_hits
from gwylio.infrastructure.config.loaders import LoadedConfig
from gwylio.infrastructure.ids import FixedIdGenerator
from gwylio.infrastructure.memory import (
    MemoryCandidateRepository,
    MemoryInstrumentRepository,
    MemoryScanRunRepository,
    NullKnownReports,
    StaticKnownReports,
)
from gwylio.infrastructure.sqlite.db import Database
from gwylio.infrastructure.sqlite.repositories import (
    SqliteCandidateRepository,
    SqliteInstrumentRepository,
    SqliteReferenceRepository,
    SqliteRequirementSetRepository,
    SqliteScanRunRepository,
    SqliteSourceRepository,
    format_timestamp,
    parse_timestamp,
    save_config,
)
from gwylio.reference.model import Place, PlaceKind, ReferenceCatalogue
from gwylio.shared.clock import FixedClock
from gwylio.shared.errors import DomainError, DuplicateId, UnknownReference
from gwylio.shared.values import CanonicalUrl, CleanText, KebabId, RunId
from gwylio.shared.vocabulary import Discipline, MatchedBy
from tests.support import (
    ALL,
    CLOCK,
    DEFAULT,
    FAKE_HITS,
    add_reports,
    instrument,
    promotion,
    query,
    small_taxonomy,
    sqlite_scan,
)

pytestmark = pytest.mark.integration

LATER = FixedClock(datetime(2026, 11, 3, 2, 15, 7, 250000, tzinfo=UTC))
DROUGHT = "nation.cymru/news/drought-declared-across-south-west-wales"


def by_url(candidates: Sequence[Candidate]) -> list[Candidate]:
    return sorted(candidates, key=lambda c: c.canonical_url.value)


def by_id(sightings: Sequence[Sighting]) -> list[Sighting]:
    return sorted(sightings, key=lambda s: s.id)


# Timestamps.


def test_timestamps_are_stored_as_utc_text_with_microseconds() -> None:
    moment = datetime(2026, 10, 6, 3, 15, 42, 7, tzinfo=UTC)
    assert format_timestamp(moment) == "2026-10-06T03:15:42.000007Z"
    assert parse_timestamp(format_timestamp(moment)) == moment
    with pytest.raises(ValueError, match="timezone-aware"):
        format_timestamp(datetime(2026, 10, 6))


# Reference and direction.


def test_the_reference_catalogue_round_trips(db: Database, shipped_config: LoadedConfig) -> None:
    repository = SqliteReferenceRepository(db)
    assert repository.load() is None
    repository.save(shipped_config.catalogue)
    loaded = repository.load()
    assert loaded == shipped_config.catalogue
    assert loaded is not None
    assert [p.welsh_name for p in loaded.places] == [
        p.welsh_name for p in shipped_config.catalogue.places
    ]
    repository.save(shipped_config.catalogue)
    assert repository.load() == shipped_config.catalogue


def test_a_child_place_may_come_before_its_parent(db: Database) -> None:
    places = (
        Place(KebabId("dee"), CleanText("Dee"), PlaceKind.RIVER_BASIN, KebabId("wales")),
        Place(KebabId("wales"), CleanText("Wales"), PlaceKind.NATION, centroid=(52.3, -3.7)),
    )
    catalogue = ReferenceCatalogue(small_taxonomy(), (), (), places, (), ())
    repository = SqliteReferenceRepository(db)
    repository.save(catalogue)
    assert repository.load() == catalogue


def test_requirement_sets_round_trip(configured: Database, shipped_config: LoadedConfig) -> None:
    repository = SqliteRequirementSetRepository(configured)
    assert repository.all() == shipped_config.requirement_sets
    nrw = shipped_config.requirement_set("nrw-corporate-plan")
    assert repository.get("nrw-corporate-plan") == nrw
    assert repository.get("no-such-set") is None
    renamed = replace(nrw, version=CleanText("2026.11"))
    repository.save(renamed)
    assert repository.all() == (renamed,)


def test_sources_round_trip_and_refuse_a_repeated_id(
    configured: Database, shipped_config: LoadedConfig
) -> None:
    repository = SqliteSourceRepository(configured)
    assert repository.all() == shipped_config.sources
    first = shipped_config.sources[0]
    assert repository.get(first.id) == first
    assert repository.get("nobody") is None
    with pytest.raises(DuplicateId, match="already stored"):
        repository.add(first)
    extra = replace(first, id=KebabId("extra-source"), domain="extra.example.org")
    repository.add(extra)
    assert repository.all()[-1] == extra
    with pytest.raises(UnknownReference, match="lane or actor"):
        repository.add(replace(extra, id=KebabId("stray"), domain="x.org", lane=KebabId("nope")))
    with pytest.raises(DuplicateId, match="already watched"):
        repository.add(replace(extra, id=KebabId("twin")))


def test_the_instrument_round_trips_and_a_version_never_changes(
    configured: Database, shipped_config: LoadedConfig
) -> None:
    repository = SqliteInstrumentRepository(configured)
    assert repository.get(shipped_config.instrument.version) is None
    repository.add(shipped_config.instrument)
    repository.add(shipped_config.instrument)
    assert repository.get(shipped_config.instrument.version) == shipped_config.instrument
    assert repository.versions() == (shipped_config.instrument.version,)
    changed = instrument(query("web-x"), version=str(shipped_config.instrument.version))
    with pytest.raises(DomainError, match="different hash"):
        repository.add(changed)


def test_an_instrument_with_every_kind_of_query_round_trips(configured: Database) -> None:
    inst = instrument(
        query("w1", requirement_hints=("si1", "si4"), topic_hints=("peatland",)),
        query(
            "s1",
            discipline=Discipline.OSINT_SITE,
            negative_terms=("new south wales", "jobs"),
            site_source_ids=("senedd", "welsh-government"),
        ),
        budget=12,
        negatives=("australia", "cymru " + "fc"),
        version="2026.11.3",
    )
    repository = SqliteInstrumentRepository(configured)
    repository.add(inst)
    assert repository.get("2026.11.3") == inst


def test_the_whole_configuration_saves_twice_and_reads_back(
    db: Database, shipped_config: LoadedConfig
) -> None:
    save_config(db, shipped_config)
    save_config(db, shipped_config)
    assert SqliteReferenceRepository(db).load() == shipped_config.catalogue
    assert SqliteRequirementSetRepository(db).all() == shipped_config.requirement_sets
    assert SqliteSourceRepository(db).all() == shipped_config.sources


def test_a_source_a_stored_run_names_cannot_leave_the_configuration(
    configured: Database, shipped_config: LoadedConfig
) -> None:
    result = sqlite_scan(configured, shipped_config)
    named = {c.source_id for c in result.candidates if c.source_id is not None}
    gone = next(s for s in shipped_config.sources if s.id in named)
    without = replace(
        shipped_config, sources=tuple(s for s in shipped_config.sources if s.id != gone.id)
    )
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        save_config(configured, without)
    assert SqliteSourceRepository(configured).get(gone.id) == gone
    retired = replace(
        shipped_config,
        sources=tuple(
            replace(s, status=SourceStatus.RETIRED) if s.id == gone.id else s
            for s in shipped_config.sources
        ),
    )
    save_config(configured, retired)
    stored = SqliteSourceRepository(configured).get(gone.id)
    assert stored is not None
    assert stored.status is SourceStatus.RETIRED


# Scan runs.


def test_a_scan_round_trips_through_every_repository(
    configured: Database, shipped_config: LoadedConfig
) -> None:
    add_reports(configured, shipped_config)
    known = StaticKnownReports(by_url={DROUGHT: "drought-2026"})
    result = sqlite_scan(configured, shipped_config, ALL, known=known)
    runs = SqliteScanRunRepository(configured)
    candidates = SqliteCandidateRepository(configured)
    assert runs.get(result.run.id) == result.run
    assert runs.all() == (result.run,)
    assert result.run.budget_exhausted
    assert candidates.candidates_for_run(result.run.id) == tuple(by_url(result.candidates))
    assert candidates.sightings_for_run(result.run.id) == tuple(by_id(result.sightings))
    assert candidates.reinforcements_for_run(result.run.id) == result.reinforcements
    assert [r.matched_by for r in result.reinforcements] == [MatchedBy.URL]
    assert runs.get("20261006T0215Z-ffff") is None
    assert candidates.candidates_for_run("20261006T0215Z-ffff") == ()


def test_sqlite_and_memory_repositories_agree_over_two_runs(
    configured: Database, shipped_config: LoadedConfig
) -> None:
    memory_runs = MemoryScanRunRepository()
    memory_candidates = MemoryCandidateRepository()
    hits = load_fake_hits(FAKE_HITS)
    results: list[tuple[RunResult, RunResult]] = []
    for clock, suffix in ((CLOCK, "aaaa"), (LATER, "bbbb")):
        in_memory = RunScan(
            collectors={d: FakeCollector(d, hits) for d in DEFAULT},
            instruments=MemoryInstrumentRepository(),
            runs=memory_runs,
            candidates=memory_candidates,
            known=NullKnownReports(),
            rules=shipped_config.gating,
            clock=clock,
            ids=FixedIdGenerator(suffix),
        ).execute(shipped_config.instrument, shipped_config.sources, DEFAULT)
        stored = sqlite_scan(configured, shipped_config, clock=clock, suffix=suffix)
        results.append((in_memory, stored))
    for in_memory, stored in results:
        assert stored.run == in_memory.run
        assert by_url(stored.candidates) == by_url(in_memory.candidates)
        assert by_id(stored.sightings) == by_id(in_memory.sightings)
    second = results[1][1]
    assert second.run.funnel.seen_before == second.run.funnel.unique == 17
    assert SqliteScanRunRepository(configured).all() == memory_runs.all()
    later = RunId("20991231T2359Z-ffff")
    assert SqliteCandidateRepository(configured).canonical_urls_before(
        later
    ) == memory_candidates.canonical_urls_before(later)


def test_a_running_run_and_a_second_add_are_refused(
    configured: Database, shipped_config: LoadedConfig
) -> None:
    runs = SqliteScanRunRepository(configured)
    SqliteInstrumentRepository(configured).add(shipped_config.instrument)
    started = ScanRun.start(
        RunId("20261006T0215Z-3f9a"), CLOCK.now(), shipped_config.instrument, DEFAULT
    )
    with pytest.raises(DomainError, match="still running"):
        runs.add(started)
    aborted = started.abort(CLOCK.now(), CleanText("aborted: test"))
    runs.add(aborted)
    with pytest.raises(RunImmutable, match="cannot change"):
        runs.add(aborted)
    assert runs.get(aborted.id) == aborted


def test_a_run_of_an_unstored_instrument_is_refused(
    configured: Database, shipped_config: LoadedConfig
) -> None:
    started = ScanRun.start(
        RunId("20261006T0215Z-3f9a"), CLOCK.now(), shipped_config.instrument, DEFAULT
    )
    with pytest.raises(UnknownReference, match="not stored"):
        SqliteScanRunRepository(configured).add(started.abort(CLOCK.now(), CleanText("x")))


class Broken:
    discipline = Discipline.OSINT_WEB

    def collect(self, query: Query, sources: Sequence[Source], remaining: int) -> CollectResult:
        raise ConnectionError("network down")


def test_an_aborted_scan_is_stored_with_no_candidates(
    configured: Database, shipped_config: LoadedConfig
) -> None:
    scan = RunScan(
        collectors={Discipline.OSINT_WEB: Broken()},
        instruments=SqliteInstrumentRepository(configured),
        runs=SqliteScanRunRepository(configured),
        candidates=SqliteCandidateRepository(configured),
        known=NullKnownReports(),
        rules=shipped_config.gating,
        clock=CLOCK,
        ids=FixedIdGenerator("dead"),
    )
    with configured.transaction(), pytest.raises(ScanAborted) as caught:
        scan.execute(shipped_config.instrument, shipped_config.sources, [Discipline.OSINT_WEB])
    stored = SqliteScanRunRepository(configured).get(caught.value.run.id)
    assert stored == caught.value.run
    assert stored is not None
    assert stored.status is RunStatus.ABORTED
    assert SqliteCandidateRepository(configured).candidates_for_run(stored.id) == ()


# Candidates, sightings and reinforcements: the refusals the memory repository makes.


@pytest.fixture
def stored(configured: Database, shipped_config: LoadedConfig) -> RunResult:
    return sqlite_scan(configured, shipped_config)


def test_a_repeated_candidate_id_or_url_is_refused(configured: Database, stored: RunResult) -> None:
    candidates = SqliteCandidateRepository(configured)
    first = stored.candidates[0]
    with pytest.raises(DuplicateId, match="already stored"):
        candidates.add_candidates([first])
    with pytest.raises(DuplicateId, match="already has a candidate"):
        candidates.add_candidates([replace(first, id=KebabId("c-other"))])
    assert len(candidates.candidates_for_run(stored.run.id)) == len(stored.candidates)


def test_a_failed_batch_stores_none_of_its_candidates(
    configured: Database, stored: RunResult
) -> None:
    candidates = SqliteCandidateRepository(configured)
    first = stored.candidates[0]
    url = "https://gov.wales/fresh"
    fresh = replace(first, id=KebabId("c-fresh"), url=url, canonical_url=CanonicalUrl(url))
    with pytest.raises(DuplicateId):
        candidates.add_candidates([fresh, first])
    assert all(c.id != "c-fresh" for c in candidates.candidates_for_run(stored.run.id))


def test_a_candidate_must_name_stored_rows(configured: Database, stored: RunResult) -> None:
    first = stored.candidates[0]
    orphan = replace(first, id=KebabId("c-orphan"), run_id=RunId("20261006T0215Z-0000"))
    with pytest.raises(UnknownReference, match="not stored"):
        SqliteCandidateRepository(configured).add_candidates([orphan])


def test_sightings_and_reinforcements_need_a_known_candidate(
    configured: Database, shipped_config: LoadedConfig, stored: RunResult
) -> None:
    add_reports(configured, shipped_config, promotion("r-1"))
    candidates = SqliteCandidateRepository(configured)
    sighting = stored.sightings[0]
    with pytest.raises(UnknownReference, match="unknown candidate 'c-nobody'"):
        candidates.add_sightings(
            [replace(sighting, id=KebabId("s-x"), candidate_id=KebabId("c-nobody"))]
        )
    with pytest.raises(DuplicateId, match="already stored"):
        candidates.add_sightings([sighting])
    with pytest.raises(UnknownReference, match="unknown candidate 'c-nobody'"):
        candidates.add_reinforcements(
            [Reinforcement(KebabId("c-nobody"), KebabId("r-1"), MatchedBy.URL)]
        )
    reinforcement = Reinforcement(stored.candidates[0].id, KebabId("r-1"), MatchedBy.TITLE)
    candidates.add_reinforcements([reinforcement])
    with pytest.raises(DuplicateId, match="already reinforced"):
        candidates.add_reinforcements([reinforcement])
    assert candidates.reinforcements_for_run(stored.run.id) == (reinforcement,)
    with pytest.raises(UnknownReference, match="names report 'r-none', which is not stored"):
        candidates.add_reinforcements(
            [Reinforcement(stored.candidates[1].id, KebabId("r-none"), MatchedBy.URL)]
        )


def test_a_sighting_belongs_to_its_candidates_run(
    configured: Database, shipped_config: LoadedConfig, stored: RunResult
) -> None:
    later = sqlite_scan(configured, shipped_config, clock=LATER, suffix="bbbb")
    misplaced = replace(stored.sightings[0], id=KebabId("s-misplaced"), run_id=later.run.id)
    with pytest.raises(UnknownReference, match="other than its candidate's"):
        SqliteCandidateRepository(configured).add_sightings([misplaced])


# The seen index.


def test_the_seen_index_reports_earlier_runs_only(
    configured: Database, shipped_config: LoadedConfig
) -> None:
    candidates = SqliteCandidateRepository(configured)
    first = sqlite_scan(configured, shipped_config, (Discipline.OSINT_FEED,), suffix="aaaa")
    assert candidates.canonical_urls_before(first.run.id) == {}
    second = sqlite_scan(configured, shipped_config, clock=LATER, suffix="bbbb")
    feed_urls = {c.canonical_url.value for c in first.candidates}
    assert candidates.canonical_urls_before(second.run.id) == {
        url: first.run.id for url in feed_urls
    }
    before_first = candidates.canonical_urls_before(first.run.id)
    second_urls = {c.canonical_url.value for c in second.candidates}
    assert set(before_first) == second_urls
    assert all(
        before_first[url] == (first.run.id if url in feed_urls else second.run.id)
        for url in second_urls
    )
    statuses = {c.canonical_url.value: second.status_of(c) for c in second.candidates}
    assert {url for url, s in statuses.items() if s.value == "seen_before"} == feed_urls
