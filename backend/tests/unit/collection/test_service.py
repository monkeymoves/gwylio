"""RunScan and Probe on small instruments with scripted collectors."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from gwylio.collection.model import (
    Discipline,
    Query,
    RawHit,
    RunStatus,
    Source,
    SourceStatus,
)
from gwylio.collection.ports import CollectResult
from gwylio.collection.service import PROBE_QUERY_ID, Probe, RunScan, ScanAborted
from gwylio.infrastructure.collectors.fake import FakeCollector
from gwylio.infrastructure.ids import FixedIdGenerator
from gwylio.infrastructure.memory import (
    MemoryCandidateRepository,
    MemoryInstrumentRepository,
    MemoryScanRunRepository,
    NullKnownReports,
)
from gwylio.shared.clock import FixedClock
from gwylio.shared.errors import DomainError
from gwylio.shared.values import CleanText
from tests.support import hit, instrument, query, rules, source

CLOCK = FixedClock(datetime(2026, 10, 6, 2, 15, 42, tzinfo=UTC))
WEB = Discipline.OSINT_WEB
SITE = Discipline.OSINT_SITE
FEED = Discipline.OSINT_FEED


@dataclass
class Harness:
    collectors: dict[Discipline, object]
    instruments: MemoryInstrumentRepository = field(default_factory=MemoryInstrumentRepository)
    runs: MemoryScanRunRepository = field(default_factory=MemoryScanRunRepository)
    candidates: MemoryCandidateRepository = field(default_factory=MemoryCandidateRepository)

    def scan(self, suffix: str = "3f9a") -> RunScan:
        return RunScan(
            collectors=self.collectors,  # type: ignore[arg-type]
            instruments=self.instruments,
            runs=self.runs,
            candidates=self.candidates,
            known=NullKnownReports(),
            rules=rules(),
            clock=CLOCK,
            ids=FixedIdGenerator(suffix),
        )


def web_hits(*query_ids: str) -> list[RawHit]:
    return [hit(f"https://gov.wales/{q}", f"Result for {q}", query_id=q) for q in query_ids]


def test_budget_stops_dispatch_and_names_the_unrun_queries() -> None:
    inst = instrument(*(query(f"q{n}") for n in range(1, 6)), budget=3)
    collector = FakeCollector(WEB, web_hits("q1", "q2", "q3", "q4", "q5"))
    harness = Harness({WEB: collector})
    result = harness.scan().execute(inst, [source("gov-wales", "gov.wales")], [WEB])
    run = result.run
    assert run.status is RunStatus.COMPLETE
    assert run.budget_exhausted
    assert run.requests_made == 3
    assert run.notes == ("request budget of 3 reached after 3 requests; 2 queries not run: q4, q5",)
    assert [call[0] for call in collector.calls] == ["q1", "q2", "q3"]
    assert [call[2] for call in collector.calls] == [3, 2, 1]
    assert run.funnel.raw == 3
    assert len(result.candidates) == 3


def test_a_run_that_spends_exactly_its_budget_is_not_exhausted() -> None:
    inst = instrument(query("q1"), query("q2"), budget=2)
    result = Harness({WEB: FakeCollector(WEB, web_hits("q1"))}).scan().execute(inst, [], [WEB])
    assert result.run.requests_made == 2
    assert not result.run.budget_exhausted


def test_a_run_is_stored_with_its_candidates_and_sightings() -> None:
    inst = instrument(query("q1"), query("q2"))
    hits = [
        hit("https://www.gov.wales/a?utm_source=x", "A", query_id="q1"),
        hit("https://gov.wales/a", "A again", query_id="q2"),
        hit("https://example.com/b", "Nothing relevant", query_id="q2"),
    ]
    harness = Harness({WEB: FakeCollector(WEB, hits)})
    result = harness.scan().execute(inst, [source("gov-wales", "gov.wales")], [WEB])
    run = result.run
    assert run.id == "20261006T0215Z-3f9a"
    assert harness.runs.get(run.id) == run
    assert harness.instruments.get("2026.10.0") == inst
    [candidate] = harness.candidates.candidates_for_run(run.id)
    assert candidate == result.candidates[0]
    assert candidate.source_id == "gov-wales"
    assert candidate.trusted
    assert candidate.first_seen_run_id == run.id
    assert [s.id for s in harness.candidates.sightings_for_run(run.id)] == [
        "s-20261006t0215z-3f9a-000001",
        "s-20261006t0215z-3f9a-000002",
    ]
    assert [s.query_id for s in result.sightings] == ["q1", "q2"]
    assert (run.funnel.raw, run.funnel.dropped_unrelated, run.funnel.passed) == (3, 1, 2)
    run.funnel.check()


def test_a_second_run_marks_urls_seen_before() -> None:
    inst = instrument(query("q1"))
    harness = Harness({WEB: FakeCollector(WEB, web_hits("q1"))})
    first = harness.scan().execute(inst, [], [WEB])
    later = RunScan(
        collectors={WEB: FakeCollector(WEB, web_hits("q1"))},
        instruments=harness.instruments,
        runs=harness.runs,
        candidates=harness.candidates,
        known=NullKnownReports(),
        rules=rules(),
        clock=FixedClock(datetime(2026, 11, 6, 2, 15, tzinfo=UTC)),
        ids=FixedIdGenerator("bbbb"),
    )
    second = later.execute(inst, [], [WEB])
    [candidate] = second.candidates
    assert candidate.first_seen_run_id == first.run.id
    assert second.status_of(candidate).value == "seen_before"
    assert (second.run.funnel.seen_before, second.run.funnel.new) == (1, 0)


def test_site_queries_use_named_active_sources_and_feeds_use_the_lane() -> None:
    sources = [
        source("gov-wales", "gov.wales"),
        source("stats", "statswales.gov.wales", status=SourceStatus.PARKED),
        source(
            "audit-wales",
            "audit.wales",
            lane="governance-capacity",
            discipline=FEED,
            feed_url="https://www.audit.wales/rss.xml",
        ),
        source(
            "old-feed",
            "old.wales",
            lane="governance-capacity",
            discipline=FEED,
            feed_url="https://old.wales/rss",
            status=SourceStatus.RETIRED,
        ),
    ]
    inst = instrument(
        query("s1", discipline=SITE, site_source_ids=("gov-wales", "stats")),
        query("s2", discipline=SITE, site_source_ids=("stats",)),
        query("f1", discipline=FEED, lane="governance-capacity"),
        query("f2", discipline=FEED, lane="senedd"),
    )
    site, feed = FakeCollector(SITE, []), FakeCollector(FEED, [])
    result = Harness({SITE: site, FEED: feed}).scan().execute(inst, sources, [SITE, FEED])
    assert site.calls == [("s1", ("gov-wales",), 150)]
    assert feed.calls == [("f1", ("audit-wales",), 149)]
    assert result.warnings == (
        "query s2 skipped: no active sources to run on",
        "query f2 skipped: no active sources to run on",
    )
    assert result.run.requests_made == 2
    assert result.run.disciplines == (FEED, SITE)


def test_hit_source_comes_from_the_collector_or_an_exact_domain_match() -> None:
    sources = [source("gov-wales", "gov.wales"), source("senedd", "senedd.wales", lane="senedd")]
    hits = [
        hit("https://gov.wales/a", query_id="q1"),
        hit("https://business.senedd.wales/x", "Senedd item", query_id="q1"),
        hit("https://senedd.wales/y", query_id="q1", source_id="gov-wales"),
        hit("https://senedd.wales/z", query_id="q1", source_id="nobody"),
    ]
    result = (
        Harness({WEB: FakeCollector(WEB, hits)})
        .scan()
        .execute(instrument(query("q1")), sources, [WEB])
    )
    by_url = {c.canonical_url.value: c for c in result.candidates}
    assert by_url["gov.wales/a"].source_id == "gov-wales"
    assert by_url["business.senedd.wales/x"].source_id is None
    assert by_url["business.senedd.wales/x"].lane == "welsh-government"
    assert by_url["senedd.wales/y"].source_id == "gov-wales"
    assert by_url["senedd.wales/z"].source_id == "senedd"
    assert by_url["senedd.wales/z"].lane == "senedd"
    assert result.warnings == (
        "hit https://senedd.wales/z names unknown source nobody; matched by domain instead",
    )


def test_hints_are_the_union_over_every_sighting_query() -> None:
    inst = instrument(
        query("q1", requirement_hints=("si4",), topic_hints=("pollution",)),
        query("q2", requirement_hints=("si1", "si4"), topic_hints=("nature",)),
    )
    hits = [hit("https://gov.wales/a", query_id="q1"), hit("https://gov.wales/a", query_id="q2")]
    [candidate] = (
        Harness({WEB: FakeCollector(WEB, hits)}).scan().execute(inst, [], [WEB]).candidates
    )
    assert candidate.requirement_hints == ("si4", "si1")
    assert candidate.topic_hints == ("pollution", "nature")
    assert candidate.query_id == "q1"


class Broken:
    discipline = WEB

    def collect(
        self, query: Query, sources: Sequence[Source], remaining_budget: int
    ) -> CollectResult:
        raise ConnectionError("network down")


def test_a_collector_failure_stores_an_aborted_run() -> None:
    harness = Harness({WEB: Broken()})
    with pytest.raises(ScanAborted, match="network down") as caught:
        harness.scan().execute(instrument(query("q1")), [], [WEB])
    run = caught.value.run
    assert run.status is RunStatus.ABORTED
    assert run.notes == ("aborted: ConnectionError: network down",)
    assert harness.runs.get(run.id) == run
    assert harness.candidates.candidates_for_run(run.id) == ()


class Greedy:
    discipline = WEB

    def collect(
        self, query: Query, sources: Sequence[Source], remaining_budget: int
    ) -> CollectResult:
        return CollectResult(hits=(hit("https://gov.wales/a", query_id=query.id),), requests_used=5)


def test_a_collector_overspending_is_warned_about_and_counted() -> None:
    result = (
        Harness({WEB: Greedy()})
        .scan()
        .execute(instrument(query("q1"), query("q2"), budget=3), [], [WEB])
    )
    assert result.run.requests_made == 5
    assert result.run.budget_exhausted
    assert "used 5 requests with only 3 left" in result.warnings[0]


class Confused:
    discipline = WEB

    def collect(
        self, query: Query, sources: Sequence[Source], remaining_budget: int
    ) -> CollectResult:
        return CollectResult(hits=(hit("https://gov.wales/a", query_id="other"),), requests_used=1)


def test_a_hit_for_the_wrong_query_aborts_the_run() -> None:
    with pytest.raises(ScanAborted, match="hit for query other"):
        Harness({WEB: Confused()}).scan().execute(instrument(query("q1")), [], [WEB])


def test_scan_refuses_missing_collectors_and_empty_disciplines() -> None:
    scan = Harness({WEB: FakeCollector(WEB, [])}).scan()
    with pytest.raises(ValueError, match="no collector for osint_feed"):
        scan.execute(instrument(query("q1")), [], [WEB, FEED])
    with pytest.raises(ValueError, match="at least one discipline"):
        scan.execute(instrument(query("q1")), [], [])
    with pytest.raises(ValueError, match="serves osint_web"):
        Harness({FEED: FakeCollector(WEB, [])}).scan()


def test_a_changed_instrument_under_an_old_version_is_refused() -> None:
    harness = Harness({WEB: FakeCollector(WEB, [])})
    harness.scan().execute(instrument(query("q1")), [], [WEB])
    with pytest.raises(DomainError, match="needs a new version"):
        harness.scan("0001").execute(instrument(query("q1"), query("q2")), [], [WEB])
    bumped = instrument(query("q1"), query("q2"), version="2026.10.1")
    harness.scan("0002").execute(bumped, [], [WEB])
    harness.scan("0003").execute(bumped, [], [WEB])
    assert len(harness.runs.all()) == 3


def test_an_instrument_with_a_stale_hash_is_refused() -> None:
    from dataclasses import replace

    stale = replace(instrument(query("q1")), content_hash="sha256:" + "0" * 64)
    with pytest.raises(DomainError, match="does not verify"):
        Harness({WEB: FakeCollector(WEB, [])}).scan().execute(stale, [], [WEB])


def test_probe_returns_hits_and_stores_nothing() -> None:
    scripted = [hit("https://gov.wales/a", query_id=PROBE_QUERY_ID)]
    collector = FakeCollector(WEB, scripted)
    result = Probe({WEB: collector}).run("nature recovery Wales", WEB)
    assert [h.url for h in result.hits] == ["https://gov.wales/a"]
    assert result.requests_used == 1
    assert result.query.id == "probe"
    assert collector.calls == [("probe", (), 1)]


def test_probe_site_sources_and_refusals() -> None:
    collector = FakeCollector(SITE, [])
    gov = source("gov-wales", "gov.wales")
    result = Probe({SITE: collector}).run("rewilding", SITE, sources=[gov], budget=2)
    assert result.query.site_source_ids == ("gov-wales",)
    assert collector.calls == [("probe", ("gov-wales",), 2)]
    with pytest.raises(ValueError, match="no collector"):
        Probe({}).run("x", WEB)
    with pytest.raises(ValueError, match="at least one request"):
        Probe({WEB: FakeCollector(WEB, [])}).run("x", WEB, budget=0)


def test_fake_collector_with_no_budget_makes_no_request() -> None:
    result = FakeCollector(WEB, web_hits("q1")).collect(query("q1"), [], 0)
    assert (result.hits, result.requests_used) == ((), 0)
    assert result.warnings == (CleanText("query q1: no budget left"),)
    with pytest.raises(ValueError):
        CollectResult(requests_used=-1)
