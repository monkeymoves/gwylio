"""Collection model: sources, queries, the instrument hash, the funnel and the scan run."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta

import pytest

from gwylio.collection.model import (
    Candidate,
    Discipline,
    Funnel,
    FunnelMismatch,
    QueryInstrument,
    RawHit,
    RunImmutable,
    RunStatus,
    ScanRun,
    SourceStatus,
    derive_candidate_id,
    derive_sighting_id,
    find_source_problems,
    make_run_id,
    run_short,
)
from gwylio.shared.errors import DuplicateId, UnknownReference
from gwylio.shared.values import CanonicalUrl, CleanText, KebabId, RunId
from tests.support import hit, instrument, query, source

STARTED = datetime(2026, 10, 6, 2, 15, 42, tzinfo=UTC)
RUN = RunId("20261006T0215Z-3f9a")


# Identifiers


def test_run_id_is_the_utc_minute_and_four_hex() -> None:
    assert make_run_id(STARTED, "3f9a") == "20261006T0215Z-3f9a"
    with pytest.raises(ValueError, match="four lower-case hex"):
        make_run_id(STARTED, "3F9A")
    with pytest.raises(ValueError, match="timezone-aware"):
        make_run_id(datetime(2026, 10, 6), "3f9a")


def test_candidate_and_sighting_ids_are_kebab_and_derived_from_the_run() -> None:
    url = CanonicalUrl("https://gov.wales/a")
    first = derive_candidate_id(RUN, url)
    assert first.startswith("c-20261006t0215z-3f9a-")
    assert len(first.rsplit("-", 1)[1]) == 6
    assert derive_candidate_id(RUN, url) == first
    assert derive_candidate_id(RUN, url, attempt=1) != first
    assert derive_sighting_id(RUN, 7) == "s-20261006t0215z-3f9a-000007"
    assert run_short(RUN) == "20261006t0215z-3f9a"
    with pytest.raises(ValueError, match="counts from 1"):
        derive_sighting_id(RUN, 0)


# Sources


def test_source_domain_must_be_a_bare_host() -> None:
    with pytest.raises(ValueError, match="bare lower-case host"):
        source("welsh-government", "www.gov.wales")
    with pytest.raises(ValueError, match="bare lower-case host"):
        source("welsh-government", "gov.wales/news")


def test_feed_source_needs_an_http_feed_url() -> None:
    with pytest.raises(ValueError, match="needs a feed_url"):
        source("audit-wales", "audit.wales", discipline=Discipline.OSINT_FEED)
    with pytest.raises(ValueError, match="http or https"):
        source("audit-wales", "audit.wales", feed_url="ftp://audit.wales/rss.xml")
    feed = source(
        "audit-wales",
        "audit.wales",
        discipline=Discipline.OSINT_FEED,
        feed_url="https://www.audit.wales/rss.xml",
    )
    assert feed.active


def test_parked_source_is_not_active() -> None:
    assert not source("openalex", "api.openalex.org", status=SourceStatus.PARKED).active


def test_source_problems_cover_duplicates_and_unknown_references() -> None:
    sources = [
        source("welsh-government", "gov.wales"),
        source("welsh-government", "statswales.gov.wales"),
        source("stats", "gov.wales", lane="nowhere"),
    ]
    problems = find_source_problems(
        sources, lane_ids={"welsh-government"}, actor_ids={"someone-else"}
    )
    kinds = [(type(p), p.location) for p in problems]
    assert (DuplicateId, "sources[1].id") in kinds
    assert (DuplicateId, "sources[2].domain") in kinds
    assert (UnknownReference, "sources[2].lane") in kinds
    assert (UnknownReference, "sources[0].actor") in kinds
    assert all(p.scope == "sources" for p in problems)


# Queries and the instrument


def test_site_queries_and_only_site_queries_name_sources() -> None:
    with pytest.raises(ValueError, match="must name at least one source"):
        query("s1", discipline=Discipline.OSINT_SITE)
    with pytest.raises(ValueError, match="only osint_site queries"):
        query("w1", site_source_ids=("welsh-government",))
    with pytest.raises(ValueError, match="repeats a value"):
        query("w1", topic_hints=("peatland", "peatland"))
    with pytest.raises(ValueError, match="empty negative term"):
        query("w1", negative_terms=(" ",))


def test_instrument_hash_is_stable_and_covers_every_field() -> None:
    base = instrument(query("q1"), query("q2", text="river pollution Wales"))
    assert base.content_hash.startswith("sha256:")
    assert len(base.content_hash) == len("sha256:") + 64
    assert base.verify_hash()
    assert instrument(query("q1"), query("q2", text="river pollution Wales")) == base
    variants = [
        instrument(query("q1"), query("q2", text="river pollution in Wales")),
        instrument(query("q2", text="river pollution Wales"), query("q1")),
        instrument(query("q1"), query("q2", text="river pollution Wales"), budget=149),
        instrument(query("q1"), query("q2", text="river pollution Wales"), negatives=()),
        instrument(query("q1"), query("q2", text="river pollution Wales"), version="2026.10.1"),
        instrument(
            query("q1", topic_hints=("peatland",)), query("q2", text="river pollution Wales")
        ),
    ]
    assert len({v.content_hash for v in variants} | {base.content_hash}) == len(variants) + 1


def test_verify_hash_fails_when_the_content_changes() -> None:
    base = instrument(query("q1"))
    tampered = QueryInstrument(
        base.version, base.content_hash, base.global_negative_terms, 3, base.queries
    )
    assert not tampered.verify_hash()
    assert tampered.expected_hash() != base.content_hash


def test_compute_hash_matches_build() -> None:
    queries = (query("q1"),)
    built = QueryInstrument.build(CleanText("2026.10.0"), (), 5, queries)
    assert built.content_hash == QueryInstrument.compute_hash("2026.10.0", [], 5, queries)


def test_instrument_refuses_a_zero_budget_and_looks_up_queries() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        instrument(query("q1"), budget=0)
    inst = instrument(query("q1"), query("f1", discipline=Discipline.OSINT_FEED))
    assert inst.query("q1").id == "q1"
    with pytest.raises(UnknownReference):
        inst.query("missing")
    assert [q.id for q in inst.queries_for([Discipline.OSINT_FEED])] == ["f1"]
    assert inst.negative_terms_for(query("q9", negative_terms=("us epa",))) == (
        "new south wales",
        "us epa",
    )


def _instrument_problems(inst: QueryInstrument) -> list[tuple[str, str]]:
    sources = {
        "gov-wales": source("gov-wales", "gov.wales", lane="welsh-government"),
        "off-site": source("off-site", "off.wales", site_pass=False),
        "senedd": source("senedd", "senedd.wales", lane="senedd"),
    }
    problems = inst.find_problems(
        lane_ids={"welsh-government", "senedd", "governance-capacity"},
        requirement_ids={"si1"},
        topic_ids={"peatland"},
        sources=sources,
    )
    return [(p.location, p.message) for p in problems]


def test_instrument_problems_name_every_broken_reference() -> None:
    inst = instrument(
        query("q1", lane="nowhere", requirement_hints=("si99",), topic_hints=("tundra",)),
        query("q1"),
        query(
            "s1",
            discipline=Discipline.OSINT_SITE,
            site_source_ids=("gov-wales", "missing", "off-site", "senedd"),
        ),
        query("f1", discipline=Discipline.OSINT_FEED, lane="governance-capacity"),
    )
    found = dict(_instrument_problems(inst))
    assert "unknown lane 'nowhere'" in found["queries[0].lane"]
    assert "unknown requirement 'si99'" in found["queries[0].requirement_hints[0]"]
    assert "unknown topic 'tundra'" in found["queries[0].topic_hints[0]"]
    assert "used twice" in found["queries[1].id"]
    assert "unknown source 'missing'" in found["queries[2].site_source_ids[1]"]
    assert "site_pass is off" in found["queries[2].site_source_ids[2]"]
    assert "from lane 'senedd'" in found["queries[2].site_source_ids[3]"]
    assert "has no feed sources" in found["queries[3].lane"]
    assert "queries[2].site_source_ids[0]" not in found


def test_instrument_problems_report_a_stale_hash_and_validate_raises() -> None:
    base = instrument(query("q1"))
    stale = replace(base, content_hash="sha256:" + "0" * 64)
    [(location, message)] = _instrument_problems(stale)
    assert location == "content_hash"
    assert base.content_hash in message
    with pytest.raises(Exception, match="content_hash"):
        stale.validate(
            lane_ids={"welsh-government"}, requirement_ids=set(), topic_ids=set(), sources={}
        )
    base.validate(lane_ids={"welsh-government"}, requirement_ids=set(), topic_ids=set(), sources={})


# Hits and candidates


def test_raw_hit_canonicalises_and_needs_an_aware_time() -> None:
    raw = hit("https://www.gov.wales/a/?utm_source=x")
    assert raw.canonical_url.value == "gov.wales/a"
    assert raw.with_source(KebabId("gov-wales")).source_id == "gov-wales"
    with pytest.raises(ValueError, match="timezone-aware"):
        replace(raw, fetched_at=datetime(2026, 10, 6))
    with pytest.raises(FrozenInstanceError):
        raw.title = CleanText("x")  # type: ignore[misc]


def test_candidate_url_must_match_its_canonical_url() -> None:
    with pytest.raises(ValueError, match="does not canonicalise"):
        Candidate(
            id=KebabId("c-x-000000"),
            run_id=RUN,
            canonical_url=CanonicalUrl("gov.wales/a"),
            url="https://gov.wales/b",
            title=CleanText("t"),
            snippet=CleanText(""),
            published_on=None,
            first_seen_run_id=RUN,
            trusted=True,
            source_id=None,
            lane=KebabId("welsh-government"),
            discipline=Discipline.OSINT_WEB,
            query_id=KebabId("q1"),
        )


# The funnel


def test_a_consistent_funnel_checks() -> None:
    Funnel(10, 1, 2, 3, 4, 3, 1, 1, 1).check()
    Funnel().check()


@pytest.mark.parametrize(
    ("funnel", "fragment"),
    [
        (Funnel(10, 1, 2, 3, 5, 3, 1, 1, 1), "raw 10 != dropped_own 1"),
        (Funnel(10, 1, 2, 3, 4, 3, 1, 1, 0), "unique 3 != new 1"),
        (Funnel(4, 0, 0, 0, 4, 5, 5, 0, 0), "more than passed"),
        (Funnel(4, 0, 0, 0, 4, 0, 0, 0, 0), "at least one candidate"),
        (Funnel(-1, 0, 0, 0, -1, 0, 0, 0, 0), "raw is negative"),
    ],
)
def test_a_hand_broken_funnel_fails(funnel: Funnel, fragment: str) -> None:
    with pytest.raises(FunnelMismatch, match=fragment):
        funnel.check()


# The scan run


def started_run(budget: int = 5) -> ScanRun:
    return ScanRun.start(
        RUN, STARTED, instrument(query("q1"), budget=budget), [Discipline.OSINT_WEB]
    )


def test_a_run_accumulates_then_completes() -> None:
    run = started_run().add_hits(3, 1).add_hits(2, 2)
    assert (run.funnel.raw, run.requests_made, run.status) == (5, 3, RunStatus.RUNNING)
    assert run.request_budget == 5
    done = run.complete(STARTED + timedelta(minutes=2), Funnel(5, 1, 1, 0, 3, 2, 0, 2, 0))
    assert done.status is RunStatus.COMPLETE
    assert done.finished


def test_adding_hits_to_a_complete_run_raises() -> None:
    done = started_run().add_hits(1, 1).complete(STARTED, Funnel(1, 0, 0, 0, 1, 1, 0, 1, 0))
    with pytest.raises(RunImmutable, match="cannot add hits"):
        done.add_hits(1, 1)
    with pytest.raises(RunImmutable):
        done.add_note(CleanText("late"))
    with pytest.raises(RunImmutable):
        done.exhaust_budget(CleanText("late"))
    with pytest.raises(RunImmutable):
        done.complete(STARTED, done.funnel)
    with pytest.raises(FrozenInstanceError):
        done.requests_made = 0  # type: ignore[misc]


def test_an_aborted_run_is_immutable_too() -> None:
    aborted = started_run().abort(STARTED, CleanText("aborted: network"))
    assert aborted.status is RunStatus.ABORTED
    assert aborted.notes == ("aborted: network",)
    with pytest.raises(RunImmutable):
        aborted.add_hits(1, 1)


def test_completing_with_a_mismatched_or_broken_funnel_raises() -> None:
    run = started_run().add_hits(2, 1)
    with pytest.raises(FunnelMismatch, match="recorded 2"):
        run.complete(STARTED, Funnel(3, 0, 0, 0, 3, 1, 0, 1, 0))
    with pytest.raises(FunnelMismatch):
        run.complete(STARTED, Funnel(2, 0, 0, 0, 2, 1, 0, 0, 0))


def test_run_construction_rules() -> None:
    run = started_run()
    with pytest.raises(ValueError, match="finish before it starts"):
        replace(run, status=RunStatus.COMPLETE, finished_at=STARTED - timedelta(seconds=1))
    with pytest.raises(ValueError, match="running run has no finished_at"):
        replace(run, finished_at=STARTED)
    with pytest.raises(ValueError, match="request_budget"):
        replace(run, request_budget=0)
    with pytest.raises(ValueError, match="cannot be negative"):
        run.add_hits(-1, 0)


def test_exhausting_the_budget_records_a_note() -> None:
    run = started_run().exhaust_budget(CleanText("request budget of 5 reached"))
    assert run.budget_exhausted
    assert run.notes == ("request budget of 5 reached",)
    assert isinstance(run.add_note(CleanText("x")).notes[-1], str)


def test_hit_requires_a_url_with_a_host() -> None:
    with pytest.raises(ValueError):
        RawHit(
            url="https://",
            title=CleanText("t"),
            snippet=CleanText(""),
            published_on=None,
            discipline=Discipline.OSINT_WEB,
            query_id=KebabId("q1"),
            source_id=None,
            fetched_at=STARTED,
        )
