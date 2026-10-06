"""In-memory repositories keep the rules persistence must keep; id generators."""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from gwylio.collection.model import Discipline, Funnel, Reinforcement, ScanRun, Sighting
from gwylio.infrastructure.ids import FixedIdGenerator, RandomIdGenerator
from gwylio.infrastructure.memory import (
    MemoryCandidateRepository,
    MemoryInstrumentRepository,
    MemoryScanRunRepository,
    MemorySourceRepository,
    NullKnownReports,
    StaticKnownReports,
)
from gwylio.shared.errors import DomainError, DuplicateId, UnknownReference
from gwylio.shared.values import RUN_ID_PATTERN, CanonicalUrl, CleanText, KebabId, RunId
from gwylio.shared.vocabulary import MatchedBy
from tests.support import earlier_candidate, instrument, query, source

STARTED = datetime(2026, 10, 6, 2, 15, tzinfo=UTC)
LATER = RunId("20261106T0215Z-bbbb")


def test_source_repository() -> None:
    repository = MemorySourceRepository([source("gov-wales", "gov.wales")])
    repository.add(source("senedd", "senedd.wales"))
    assert [s.id for s in repository.all()] == ["gov-wales", "senedd"]
    assert repository.get("senedd") is not None
    assert repository.get("nobody") is None
    with pytest.raises(DuplicateId):
        repository.add(source("senedd", "other.wales"))


def test_instrument_repository_keeps_a_version_fixed() -> None:
    repository = MemoryInstrumentRepository()
    first = instrument(query("q1"))
    repository.add(first)
    repository.add(first)
    assert repository.get("2026.10.0") == first
    with pytest.raises(DomainError, match="different hash"):
        repository.add(instrument(query("q2")))


def test_run_repository_stores_finished_runs_once_in_time_order() -> None:
    repository = MemoryScanRunRepository()
    inst = instrument(query("q1"))
    running = ScanRun.start(LATER, datetime(2026, 11, 6, tzinfo=UTC), inst, [Discipline.OSINT_WEB])
    with pytest.raises(DomainError, match="still running"):
        repository.add(running)
    later = running.complete(datetime(2026, 11, 6, 1, tzinfo=UTC), Funnel())
    earlier = replace(
        later,
        id=RunId("20261006T0215Z-aaaa"),
        started_at=STARTED,
        finished_at=STARTED,
    )
    repository.add(later)
    repository.add(earlier)
    assert [r.id for r in repository.all()] == ["20261006T0215Z-aaaa", LATER]
    with pytest.raises(DomainError, match="cannot change"):
        repository.add(later)


def test_candidate_repository_uniqueness_and_seen_index() -> None:
    repository = MemoryCandidateRepository()
    first = earlier_candidate()
    repository.add_candidates([first])
    with pytest.raises(DuplicateId, match="already stored"):
        repository.add_candidates([first])
    with pytest.raises(DuplicateId, match="already has a candidate"):
        repository.add_candidates([replace(first, id=KebabId("c-other"))])
    again = replace(first, id=KebabId("c-later"), run_id=LATER)
    repository.add_candidates([again])
    assert repository.canonical_urls_before(LATER) == {first.canonical_url.value: first.run_id}
    assert repository.canonical_urls_before(first.run_id) == {
        first.canonical_url.value: first.first_seen_run_id
    }
    assert repository.canonical_urls_before("20991231T2359Z-ffff") == {
        first.canonical_url.value: first.run_id
    }

    sighting = Sighting(KebabId("s-1"), LATER, again.id, None, KebabId("q1"), Discipline.OSINT_WEB)
    repository.add_sightings([sighting])
    assert repository.sightings_for_run(LATER) == (sighting,)
    with pytest.raises(DuplicateId):
        repository.add_sightings([sighting])
    with pytest.raises(UnknownReference):
        repository.add_sightings(
            [replace(sighting, id=KebabId("s-2"), candidate_id=KebabId("c-x"))]
        )

    reinforcement = Reinforcement(again.id, KebabId("drought-2026"), MatchedBy.URL)
    repository.add_reinforcements([reinforcement])
    assert repository.reinforcements_for_run(LATER) == (reinforcement,)
    assert repository.reinforcements_for_run(first.run_id) == ()
    with pytest.raises(UnknownReference):
        repository.add_reinforcements([Reinforcement(KebabId("c-x"), KebabId("r"), MatchedBy.URL)])
    assert repository.candidates_for_run(LATER) == (again,)


def test_known_reports() -> None:
    null = NullKnownReports()
    assert null.report_id_for_url(CanonicalUrl("gov.wales")) is None
    assert null.report_id_for_title("x") is None
    static = StaticKnownReports(
        by_url={"https://www.gov.wales/a/": "r1"}, by_title={"A  Title": "r2"}
    )
    assert static.report_id_for_url(CanonicalUrl("gov.wales/a")) == "r1"
    assert static.report_id_for_title("a title") == "r2"


def test_id_generators() -> None:
    random_id = RandomIdGenerator().run_id(STARTED)
    assert re.fullmatch(RUN_ID_PATTERN, random_id)
    assert random_id.startswith("20261006T0215Z-")
    fixed = FixedIdGenerator("3f9a")
    assert fixed.run_id(STARTED) == "20261006T0215Z-3f9a"
    url = CanonicalUrl("gov.wales/a")
    assert fixed.candidate_id(
        RunId("20261006T0215Z-3f9a"), url, 0
    ) == RandomIdGenerator().candidate_id(RunId("20261006T0215Z-3f9a"), url, 0)
    assert fixed.sighting_id(RunId("20261006T0215Z-3f9a"), 1) == "s-20261006t0215z-3f9a-000001"
    assert CleanText("x") == "x"
