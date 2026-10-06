"""The feed collector against RSS 2.0, Atom, malformed and missing feeds."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
import respx

from gwylio.collection.model import Discipline
from gwylio.infrastructure.collectors.feed import FeedCollector, FeedError, parse_feed
from gwylio.infrastructure.http.client import HttpClient
from gwylio.shared.clock import FixedClock
from gwylio.shared.values import IsoDate, KebabId
from tests.integration.collectors.cassettes import response
from tests.support import query, source

pytestmark = pytest.mark.integration

RIGHT_QUOTE = chr(0x2019)
CLOCK = FixedClock(datetime(2026, 10, 6, 2, 15, tzinfo=UTC))
CCC_FEED = "https://www.theccc.org.uk/feed/"
AUDIT_FEED = "https://www.audit.wales/rss.xml"
CCC = source(
    "climate-change-committee",
    "theccc.org.uk",
    lane="uk-government-and-regulators",
    discipline=Discipline.OSINT_FEED,
    feed_url=CCC_FEED,
)
AUDIT = source(
    "audit-wales",
    "audit.wales",
    lane="governance-capacity",
    discipline=Discipline.OSINT_FEED,
    feed_url=AUDIT_FEED,
)


def feed_query(query_id: str, text: str, lane: str = "uk-government-and-regulators"):
    return query(query_id, discipline=Discipline.OSINT_FEED, lane=lane, text=text)


def test_rss_items_matching_a_phrase_become_hits(
    http: HttpClient, mocked: respx.MockRouter
) -> None:
    mocked.get(CCC_FEED).mock(return_value=response("feed", "rss_ccc.json"))
    collector = FeedCollector(http, CLOCK)
    result = collector.collect(
        feed_query("feed-ccc", '"wales" OR "seventh carbon budget"'), (CCC,), 5
    )
    assert result.requests_used == 1
    assert result.warnings == ()
    wales, budget = result.hits
    assert wales.url == (
        "https://www.theccc.org.uk/publication/progress-in-reducing-emissions-in-wales-2026/"
    )
    assert wales.title == "Progress in reducing emissions in Wales: 2026 report to the Senedd"
    assert wales.snippet == (
        "Our latest assessment of Wales" + RIGHT_QUOTE + "s progress, emissions fell 3% in 2025 & "
        "land use remains off track."
    )
    assert wales.published_on == IsoDate("2026-09-24")
    assert wales.source_id == KebabId("climate-change-committee")
    assert wales.discipline is Discipline.OSINT_FEED
    assert wales.query_id == "feed-ccc"
    assert budget.title == "The Seventh Carbon Budget: one year on"
    assert budget.snippet == "A look back at the Seventh Carbon Budget advice."
    assert budget.published_on == IsoDate("2026-09-07")
    assert collector.summary() == "feeds: 1 of 1 responded"


def test_the_keyword_filter_keeps_and_drops(http: HttpClient, mocked: respx.MockRouter) -> None:
    mocked.get(CCC_FEED).mock(return_value=response("feed", "rss_ccc.json"))
    collector = FeedCollector(http, CLOCK)
    northern = collector.collect(feed_query("feed-a", '"NORTHERN IRELAND"'), (CCC,), 5)
    assert [hit.title for hit in northern.hits] == [
        "Adapting to climate change in Northern Ireland"
    ]
    assert northern.hits[0].published_on == IsoDate("2026-08-20")  # from dc:date
    nothing = collector.collect(feed_query("feed-b", '"peat" OR "hydrogen"'), (CCC,), 5)
    assert nothing.hits == ()
    analysis = collector.collect(feed_query("feed-c", "analysis team"), (CCC,), 5)
    assert [hit.title for hit in analysis.hits] == ["Job vacancy: Senior Analyst"]


def test_atom_entries_become_hits(http: HttpClient, mocked: respx.MockRouter) -> None:
    mocked.get(AUDIT_FEED).mock(return_value=response("feed", "atom_audit_wales.json"))
    result = FeedCollector(http, CLOCK).collect(
        feed_query("feed-audit", '"flood" OR "natural resources"', "governance-capacity"),
        (AUDIT,),
        5,
    )
    flood, resources = result.hits
    assert flood.url == "https://www.audit.wales/publication/flood-risk-management-follow-up-review"
    assert flood.title == "Flood risk management in Wales: follow-up review"
    assert flood.snippet == (
        "We followed up our 2024 review of how councils and partners manage flood risk."
    )
    assert flood.published_on == IsoDate("2026-09-10")
    assert flood.source_id == KebabId("audit-wales")
    assert resources.url == (
        "https://www.audit.wales/publication/sustainable-development-natural-resources"
    )
    assert resources.published_on == IsoDate("2026-08-01")  # updated, there being no published
    assert resources.snippet.startswith("How public bodies apply")


def test_each_feed_is_fetched_once_per_run(http: HttpClient, mocked: respx.MockRouter) -> None:
    route = mocked.get(CCC_FEED).mock(return_value=response("feed", "rss_ccc.json"))
    collector = FeedCollector(http, CLOCK)
    first = collector.collect(feed_query("feed-1", '"wales"'), (CCC,), 5)
    second = collector.collect(feed_query("feed-2", '"seventh carbon budget"'), (CCC,), 5)
    assert route.call_count == 1
    assert (first.requests_used, second.requests_used) == (1, 0)
    assert len(first.hits) == len(second.hits) == 1
    assert second.hits[0].query_id == "feed-2"


def test_a_malformed_feed_gives_no_hits_and_one_warning(
    http: HttpClient, mocked: respx.MockRouter
) -> None:
    mocked.get(AUDIT_FEED).mock(return_value=response("feed", "malformed.json"))
    collector = FeedCollector(http, CLOCK)
    text = '"flood"'
    result = collector.collect(feed_query("feed-x", text, "governance-capacity"), (AUDIT,), 5)
    assert result.hits == ()
    assert result.requests_used == 1
    assert len(result.warnings) == 1
    assert result.warnings[0].startswith("feed audit-wales (https://www.audit.wales/rss.xml)")
    assert "not well-formed XML" in result.warnings[0]
    again = collector.collect(feed_query("feed-y", text, "governance-capacity"), (AUDIT,), 5)
    assert again == type(again)()  # the failure is cached: no request, no repeated warning
    assert collector.summary() == "feeds: 0 of 1 responded; failed: audit-wales"


def test_a_404_feed_gives_no_hits_and_one_warning(
    http: HttpClient, mocked: respx.MockRouter
) -> None:
    mocked.get(CCC_FEED).mock(return_value=httpx.Response(404))
    mocked.get(AUDIT_FEED).mock(return_value=response("feed", "atom_audit_wales.json"))
    collector = FeedCollector(http, CLOCK)
    both = (CCC, AUDIT)
    result = collector.collect(feed_query("feed-z", '"flood"'), both, 5)
    assert result.requests_used == 2
    assert len(result.warnings) == 1
    assert "feed climate-change-committee" in result.warnings[0]
    assert "HTTP 404" in result.warnings[0]
    assert [hit.source_id for hit in result.hits] == ["audit-wales"]


def test_an_unreachable_feed_never_raises(http: HttpClient, mocked: respx.MockRouter) -> None:
    mocked.get(CCC_FEED).mock(side_effect=httpx.ProxyError("CONNECT tunnel failed, response 403"))
    result = FeedCollector(http, CLOCK).collect(feed_query("feed-z", '"wales"'), (CCC,), 5)
    assert result.hits == ()
    assert result.requests_used == 1
    assert "ProxyError" in result.warnings[0]


def test_the_budget_stops_further_fetches(http: HttpClient, mocked: respx.MockRouter) -> None:
    ccc = mocked.get(CCC_FEED).mock(return_value=response("feed", "rss_ccc.json"))
    audit = mocked.get(AUDIT_FEED).mock(return_value=response("feed", "atom_audit_wales.json"))
    result = FeedCollector(http, CLOCK).collect(feed_query("feed-z", '"flood"'), (CCC, AUDIT), 1)
    assert (ccc.call_count, audit.call_count) == (1, 0)
    assert result.requests_used == 1
    assert "stopped at the request budget; feed audit-wales not fetched" in result.warnings[0]


def test_parse_feed_refuses_what_is_not_a_feed() -> None:
    with pytest.raises(FeedError, match="root element is <html>"):
        parse_feed(b"<html><body>Moved</body></html>", CCC_FEED)
    with pytest.raises(FeedError, match="entities"):
        parse_feed(
            b'<?xml version="1.0"?><!DOCTYPE rss [<!ENTITY a "aaaa">]><rss><channel/></rss>',
            CCC_FEED,
        )


def test_parse_feed_reads_rss_1_and_skips_items_without_links() -> None:
    body = (
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
        'xmlns="http://purl.org/rss/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/">'
        "<item><title>Drought in Wales</title><link>https://example.org/drought</link>"
        "<dc:date>2026-08-01</dc:date></item>"
        "<item><title>No link here</title></item>"
        "</rdf:RDF>"
    )
    items = parse_feed(body, "https://example.org/feed")
    assert [(i.title, i.link, str(i.published_on)) for i in items] == [
        ("Drought in Wales", "https://example.org/drought", "2026-08-01")
    ]
    guid = (
        "<rss><channel><item><title>T</title>"
        "<guid>https://example.org/permalink</guid></item>"
        '<item><title>U</title><guid isPermaLink="false">https://example.org/x</guid></item>'
        "</channel></rss>"
    )
    assert [i.link for i in parse_feed(guid, "https://example.org/")] == [
        "https://example.org/permalink"
    ]
