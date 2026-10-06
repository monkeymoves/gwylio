"""The shipped sources, instrument and gating rules say what they should."""

from __future__ import annotations

from collections import Counter

import pytest

from gwylio.collection.model import Discipline, Reliability, Source, SourceStatus
from gwylio.infrastructure.config.loaders import LoadedConfig

pytestmark = pytest.mark.integration


def test_the_instrument_hash_verifies(shipped_config: LoadedConfig) -> None:
    instrument = shipped_config.instrument
    assert instrument.verify_hash()
    assert instrument.version == "2026.10.0"
    assert instrument.max_requests_per_run == 150


def test_the_instrument_transcribes_every_old_query(shipped_config: LoadedConfig) -> None:
    counts = Counter(q.discipline for q in shipped_config.instrument.queries)
    assert counts == {
        Discipline.OSINT_WEB: 78,
        Discipline.OSINT_SITE: 56,
        Discipline.OSINT_FEED: 14,
        Discipline.OSINT_ACADEMIC: 14,
    }
    assert len(shipped_config.instrument.global_negative_terms) == 12


def test_every_site_query_names_existing_site_pass_sources_of_its_lane(
    shipped_config: LoadedConfig,
) -> None:
    sources = {s.id: s for s in shipped_config.sources}
    site_queries = [
        q for q in shipped_config.instrument.queries if q.discipline is Discipline.OSINT_SITE
    ]
    assert site_queries
    for query in site_queries:
        assert query.site_source_ids, query.id
        for source_id in query.site_source_ids:
            source = sources[source_id]
            assert source.site_pass and source.trusted and source.active, (query.id, source_id)
            assert source.lane == query.lane, (query.id, source_id)


def test_every_feed_query_has_an_active_feed_in_its_lane(shipped_config: LoadedConfig) -> None:
    feed_lanes = {
        s.lane for s in shipped_config.sources if s.discipline is Discipline.OSINT_FEED and s.active
    }
    for query in shipped_config.instrument.queries:
        if query.discipline is Discipline.OSINT_FEED:
            assert query.lane in feed_lanes, query.id


def test_default_disciplines_fit_the_budget_at_one_request_per_query(
    shipped_config: LoadedConfig,
) -> None:
    instrument = shipped_config.instrument
    default = instrument.queries_for(
        [Discipline.OSINT_WEB, Discipline.OSINT_SITE, Discipline.OSINT_FEED]
    )
    assert len(default) == 148
    assert len(default) <= instrument.max_requests_per_run
    assert len(instrument.queries) > instrument.max_requests_per_run


def test_the_watchlist_transcribes_the_old_sources(shipped_config: LoadedConfig) -> None:
    sources: dict[str, Source] = {s.id: s for s in shipped_config.sources}
    assert len(sources) == 43
    assert Counter(s.status for s in sources.values()) == {
        SourceStatus.ACTIVE: 41,
        SourceStatus.PARKED: 2,
    }
    assert {s.id for s in sources.values() if s.status is SourceStatus.PARKED} == {
        "openalex",
        "crossref",
    }
    assert Counter(s.discipline for s in sources.values()) == {
        Discipline.OSINT_SITE: 39,
        Discipline.OSINT_FEED: 2,
        Discipline.OSINT_ACADEMIC: 2,
    }
    assert {s.id for s in sources.values() if s.reliability is Reliability.A} == {
        "uk-legislation",
        "statswales",
        "ons",
    }
    assert {s.id for s in sources.values() if s.reliability is Reliability.D} == {
        "river-action",
        "fish-legal",
        "leigh-day",
        "surfers-against-sewage",
    }
    assert sources["audit-wales"].lane == "governance-capacity"
    assert sources["nation-cymru"].lane == "independent-media"
    assert sources["climate-change-committee"].feed_url == "https://www.theccc.org.uk/feed/"


def test_every_source_names_a_known_actor_and_lane(shipped_config: LoadedConfig) -> None:
    catalogue = shipped_config.catalogue
    for source in shipped_config.sources:
        assert source.actor in catalogue.actor_ids(), source.id
        assert source.lane in catalogue.lane_ids(), source.id


def test_gating_rules_cover_own_domains_and_place_tokens(shipped_config: LoadedConfig) -> None:
    gating = shipped_config.gating
    assert gating.is_own_domain("naturalresources.wales")
    assert gating.is_own_domain("cyfoethnaturiol.cymru")
    assert not gating.is_own_domain("gov.wales")
    for token in ("wales", "welsh", "cymru", "cymraeg", "senedd", "dee", "teifi", "gogledd cymru"):
        assert token in gating.relevance_tokens, token
    assert not any(gating.is_own_domain(source.domain) for source in shipped_config.sources)
