"""The Brave web and site collectors against their cassettes."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
import respx

from gwylio.collection.model import Discipline, Query
from gwylio.infrastructure.collectors.brave_site import (
    MAX_QUERY_CHARS,
    MAX_QUERY_WORDS,
    BraveSiteCollector,
    site_queries,
    site_query,
)
from gwylio.infrastructure.collectors.brave_web import (
    BRAVE_WEB_URL,
    BraveSearch,
    BraveWebCollector,
)
from gwylio.infrastructure.http.client import HttpClient
from gwylio.shared.clock import FixedClock
from gwylio.shared.values import IsoDate, KebabId
from tests.integration.collectors.cassettes import request_params, response
from tests.support import query, source

pytestmark = pytest.mark.integration

NOW = datetime(2026, 10, 6, 2, 15, tzinfo=UTC)
CLOCK = FixedClock(NOW)
KEY = "test-key-not-real"


def web_query() -> Query:
    return query("web-habitat-01", text="habitat restoration Wales")


def test_web_maps_the_cassette_to_raw_hits(http: HttpClient, mocked: respx.MockRouter) -> None:
    route = mocked.get(BRAVE_WEB_URL).mock(return_value=response("brave_web", "web_search.json"))
    collector = BraveWebCollector(BraveSearch(http, KEY), CLOCK)
    result = collector.collect(query("web-habitat-01", text="habitat restoration Wales"), (), 5)

    sent = route.calls.last.request
    assert dict(sent.url.params) == request_params("brave_web", "web_search.json")
    assert sent.headers["X-Subscription-Token"] == KEY
    assert result.requests_used == 1
    assert result.warnings == ()
    assert len(result.hits) == 7
    first, second, third = result.hits[:3]
    assert first.url == "https://www.gov.wales/nature-recovery-action-plan-wales-2026-2030"
    assert first.title == "Nature Recovery Action Plan for Wales 2026 to 2030 | GOV.WALES"
    assert first.snippet == (
        "The Welsh Government sets out how habitat restoration will be funded through the "
        "Nature Networks Programme & the Sustainable Farming Scheme."
    )
    assert first.published_on == IsoDate("2026-09-15")
    assert first.discipline is Discipline.OSINT_WEB
    assert first.query_id == "web-habitat-01"
    assert first.source_id is None
    assert first.fetched_at == NOW
    assert second.title == (
        "Biodiversity targets inquiry, Climate Change, Environment and Infrastructure Committee"
    )
    assert second.published_on == IsoDate("2026-09-20")  # from "age", there being no page_age
    assert third.canonical_url.value == "bbc.co.uk/news/articles/c4g7wales2026"
    assert third.published_on == IsoDate("2026-09-28")
    last = result.hits[-1]
    assert last.url == (
        "https://nation.cymru/news/habitat%E2%80%93restoration-funding-boost-for-welsh-uplands/"
    )
    assert last.published_on is None  # "3 days ago" is not a date


def test_web_failure_is_a_warning_with_the_requests_counted(
    http: HttpClient, mocked: respx.MockRouter
) -> None:
    mocked.get(BRAVE_WEB_URL).mock(return_value=httpx.Response(500))
    result = BraveWebCollector(BraveSearch(http, KEY), CLOCK).collect(web_query(), (), 10)
    assert result.hits == ()
    assert result.requests_used == 4
    assert len(result.warnings) == 1
    assert "web query web-habitat-01 failed: HTTP 500" in result.warnings[0]


def test_a_refused_key_stops_web_and_site_after_one_warning(
    http: HttpClient, mocked: respx.MockRouter
) -> None:
    route = mocked.get(BRAVE_WEB_URL).mock(return_value=httpx.Response(401))
    search = BraveSearch(http, KEY)
    web = BraveWebCollector(search, CLOCK)
    site = BraveSiteCollector(search, CLOCK)
    first = web.collect(web_query(), (), 10)
    assert first.requests_used == 1
    assert "refused the API key (HTTP 401)" in first.warnings[0]
    assert web.collect(web_query(), (), 10) == type(first)()
    senedd = (source("senedd-cymru", "senedd.wales", lane="senedd"),)
    site_query_ = query(
        "site-x", discipline=Discipline.OSINT_SITE, lane="senedd", site_source_ids=("senedd-cymru",)
    )
    assert site.collect(site_query_, senedd, 10).requests_used == 0
    assert route.call_count == 1


def test_web_with_no_budget_makes_no_request(http: HttpClient, mocked: respx.MockRouter) -> None:
    route = mocked.get(BRAVE_WEB_URL)
    result = BraveWebCollector(BraveSearch(http, KEY), CLOCK).collect(web_query(), (), 0)
    assert result.requests_used == 0
    assert route.call_count == 0
    assert "no request budget left" in result.warnings[0]


def test_brave_search_needs_a_key(http: HttpClient) -> None:
    with pytest.raises(ValueError):
        BraveSearch(http, "  ")


SENEDD = (
    source("senedd-cymru", "senedd.wales", lane="senedd"),
    source("senedd-research", "research.senedd.wales", lane="senedd"),
)
SITE_QUERY = query(
    "site-nature-senedd",
    discipline=Discipline.OSINT_SITE,
    lane="senedd",
    text='"nature recovery" OR "biodiversity targets"',
    site_source_ids=("senedd-cymru", "senedd-research"),
)


def test_site_joins_the_domains_in_one_request_and_names_each_hit_source(
    http: HttpClient, mocked: respx.MockRouter
) -> None:
    route = mocked.get(BRAVE_WEB_URL).mock(return_value=response("brave_site", "site_search.json"))
    result = BraveSiteCollector(BraveSearch(http, KEY), CLOCK).collect(SITE_QUERY, SENEDD, 10)
    assert route.call_count == 1
    assert dict(route.calls.last.request.url.params) == request_params(
        "brave_site", "site_search.json"
    )
    assert result.requests_used == 1
    assert result.warnings == ()
    research, inquiry, bill = result.hits
    assert research.source_id == KebabId("senedd-research")  # the longest matching domain
    assert research.title == "What next for nature recovery in Wales?"
    assert research.published_on == IsoDate("2026-09-01")
    assert research.discipline is Discipline.OSINT_SITE
    assert research.query_id == "site-nature-senedd"
    assert inquiry.source_id == KebabId("senedd-cymru")
    assert inquiry.snippet == "Terms of reference for the biodiversity targets inquiry."
    assert bill.title == (
        "Environment (Principles, Governance and Biodiversity Targets) (Wales) Bill"
    )
    assert bill.published_on == IsoDate("2026-07-14")


def test_site_query_shapes() -> None:
    assert site_query(["gov.wales"], '"a" OR "b"') == 'site:gov.wales ("a" OR "b")'
    assert site_query(["gov.wales", "senedd.wales"], '"a"') == (
        '(site:gov.wales OR site:senedd.wales) ("a")'
    )


def test_many_domains_split_within_brave_limits() -> None:
    domains = [f"partner{n}.example.org" for n in range(12)]
    text = " OR ".join(f'"phrase number {n}"' for n in range(6))
    searches = site_queries(domains, text)
    assert len(searches) > 1
    assert [d for chunk, _ in searches for d in chunk] == domains
    for _, q in searches:
        assert len(q) <= MAX_QUERY_CHARS
        assert len(q.split()) <= MAX_QUERY_WORDS
    assert site_queries(["gov.wales", "gov.wales"], '"a"') == [
        (("gov.wales",), 'site:gov.wales ("a")')
    ]


def test_site_stops_at_the_remaining_budget_and_warns(
    http: HttpClient, mocked: respx.MockRouter
) -> None:
    route = mocked.get(BRAVE_WEB_URL).mock(return_value=response("brave_site", "site_search.json"))
    partners = tuple(
        source(f"partner-{n}", f"partner{n}.example.org", lane="partnership-and-civil-society")
        for n in range(12)
    )
    many = query(
        "site-many",
        discipline=Discipline.OSINT_SITE,
        lane="partnership-and-civil-society",
        text=" OR ".join(f'"phrase number {n}"' for n in range(6)),
        site_source_ids=tuple(p.id for p in partners),
    )
    needed = len(site_queries([p.domain for p in partners], str(many.text)))
    assert needed >= 2
    result = BraveSiteCollector(BraveSearch(http, KEY), CLOCK).collect(many, partners, 1)
    assert route.call_count == 1
    assert result.requests_used == 1
    assert len(result.warnings) == 1
    assert "stopped at the request budget (1 left); not searched: " in result.warnings[0]
    assert "partner11.example.org" in result.warnings[0]


def test_site_with_no_sources_warns(http: HttpClient) -> None:
    result = BraveSiteCollector(BraveSearch(http, KEY), CLOCK).collect(SITE_QUERY, (), 10)
    assert result.requests_used == 0
    assert "no sources to search" in result.warnings[0]


def test_site_failure_on_one_chunk_is_a_warning(http: HttpClient, mocked: respx.MockRouter) -> None:
    mocked.get(BRAVE_WEB_URL).mock(return_value=httpx.Response(422))
    result = BraveSiteCollector(BraveSearch(http, KEY), CLOCK).collect(SITE_QUERY, SENEDD, 10)
    assert result.requests_used == 1
    assert (
        "site query site-nature-senedd failed on senedd.wales, research.senedd.wales"
        in (result.warnings[0])
    )
