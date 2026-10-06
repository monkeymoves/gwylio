"""Items from the feeds of watched sources: the ``osint_feed`` collector.

For each active feed source in the query's lane (the scan chooses them), the
collector fetches the feed, parses RSS 2.0, RSS 1.0 or Atom with the standard
library's ``xml.etree``, and keeps an item only when one of the query's
phrases appears, case-insensitively, in its title or summary. Feeds are a
firehose of whatever a body publishes (Audit Wales covers schools and health
too) and their domains are trusted, so without this filter every item would
pass the relevance gate on its domain alone.

Each feed is fetched at most once per run: the instrument has a feed query
per cluster and lane, and they all read the same few feeds, so a fetch is
cached for the life of the collector (one scan run) and later queries cost
no requests. A feed that cannot be fetched or parsed yields zero hits and one
warning naming the source; it never raises. Each hit records its source id.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final
from urllib.parse import urljoin

from gwylio.collection.model import Query, RawHit, Source
from gwylio.collection.ports import CollectResult
from gwylio.infrastructure.collectors.common import (
    HitBuilder,
    parse_date,
    plain_text,
    query_phrases,
    warn,
)
from gwylio.infrastructure.http.client import HttpClient, HttpError
from gwylio.shared.clock import Clock, SystemClock
from gwylio.shared.values import CleanText, IsoDate
from gwylio.shared.vocabulary import Discipline

__all__ = ["FeedCollector", "FeedError", "FeedItem", "item_matches", "parse_feed"]

_ATOM: Final[str] = "{http://www.w3.org/2005/Atom}"
_RSS1: Final[str] = "{http://purl.org/rss/1.0/}"
_RDF: Final[str] = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}RDF"
_CONTENT: Final[str] = "{http://purl.org/rss/1.0/modules/content/}encoded"
_DC_DATE: Final[str] = "{http://purl.org/dc/elements/1.1/}date"
_SNIFF: Final[int] = 4096


class FeedError(ValueError):
    """A feed body that is not well-formed RSS or Atom."""


@dataclass(frozen=True, slots=True)
class FeedItem:
    """One feed item as plain text: title, absolute link, summary and published date."""

    title: str
    link: str
    summary: str
    published_on: IsoDate | None


def _text(element: ET.Element | None) -> str:
    return "" if element is None else "".join(element.itertext()).strip()


def _first(element: ET.Element, *tags: str) -> str:
    for tag in tags:
        value = _text(element.find(tag))
        if value:
            return value
    return ""


def _rss_item(item: ET.Element, ns: str, base_url: str) -> FeedItem | None:
    link = _first(item, f"{ns}link")
    if not link:
        guid = item.find(f"{ns}guid")
        permalink = guid is not None and guid.get("isPermaLink", "true").lower() != "false"
        candidate = _text(guid)
        if permalink and candidate.startswith(("http://", "https://")):
            link = candidate
    if not link:
        return None
    return FeedItem(
        title=plain_text(_first(item, f"{ns}title")),
        link=urljoin(base_url, link.strip()),
        summary=plain_text(_first(item, f"{ns}description", _CONTENT)),
        published_on=parse_date(_first(item, f"{ns}pubDate", _DC_DATE)),
    )


def _atom_link(entry: ET.Element) -> str:
    links = entry.findall(f"{_ATOM}link")
    for link in links:
        if link.get("rel", "alternate") == "alternate" and link.get("href"):
            return link.get("href", "")
    return next((link.get("href", "") for link in links if link.get("href")), "")


def _atom_entry(entry: ET.Element, base_url: str) -> FeedItem | None:
    link = _atom_link(entry)
    if not link:
        return None
    return FeedItem(
        title=plain_text(_first(entry, f"{_ATOM}title")),
        link=urljoin(base_url, link.strip()),
        summary=plain_text(_first(entry, f"{_ATOM}summary", f"{_ATOM}content")),
        published_on=parse_date(_first(entry, f"{_ATOM}published", f"{_ATOM}updated")),
    )


def parse_feed(body: bytes | str, base_url: str) -> tuple[FeedItem, ...]:
    """The items of an RSS 2.0, RSS 1.0 or Atom feed, in feed order; ``FeedError`` otherwise.

    A document type declaration that defines entities is refused outright:
    a feed has no need of one, and refusing it closes the door on entity
    expansion attacks.
    """
    head = body[:_SNIFF] if isinstance(body, bytes) else body[:_SNIFF].encode("utf-8", "replace")
    if b"<!ENTITY" in head.upper():
        raise FeedError("the feed declares XML entities, which a feed never needs")
    try:
        root = ET.fromstring(body)
    except ET.ParseError as error:
        raise FeedError(f"not well-formed XML: {error}") from error
    items: Iterable[FeedItem | None]
    if root.tag == "rss":
        items = (_rss_item(item, "", base_url) for item in root.iter("item"))
    elif root.tag == f"{_ATOM}feed":
        items = (_atom_entry(entry, base_url) for entry in root.iter(f"{_ATOM}entry"))
    elif root.tag == _RDF:
        items = (_rss_item(item, _RSS1, base_url) for item in root.iter(f"{_RSS1}item"))
    else:
        raise FeedError(f"not an RSS or Atom feed (the root element is <{root.tag}>)")
    return tuple(item for item in items if item is not None)


def item_matches(item: FeedItem, phrases: Sequence[str]) -> bool:
    """True when any phrase appears, case-insensitively, in the item's title or summary."""
    text = f"{item.title}\n{item.summary}".casefold()
    return any(phrase in text for phrase in phrases)


@dataclass(frozen=True, slots=True)
class _Fetched:
    items: tuple[FeedItem, ...]
    fetched_at: datetime


class FeedCollector:
    """``osint_feed``: matching items from each source's feed, each feed fetched once per run."""

    def __init__(self, http: HttpClient, clock: Clock | None = None) -> None:
        self._http = http
        self._clock = clock or SystemClock()
        self._cache: dict[str, _Fetched | None] = {}
        self.responded: dict[str, int] = {}
        """Source id to the number of items its feed carried, for each feed that answered."""
        self.failed: dict[str, str] = {}
        """Source id to why its feed failed, for each feed that did not."""

    @property
    def discipline(self) -> Discipline:
        return Discipline.OSINT_FEED

    def summary(self) -> str:
        """One line on how the feeds fared in this run."""
        total = len(self.responded) + len(self.failed)
        line = f"feeds: {len(self.responded)} of {total} responded"
        if self.failed:
            line += f"; failed: {', '.join(sorted(self.failed))}"
        return line

    def _fetch(self, source: Source, url: str, warnings: list[CleanText]) -> _Fetched | None:
        fetched_at = self._clock.now()
        try:
            items = parse_feed(self._http.get_bytes(url), url)
        except (HttpError, FeedError) as error:
            reason = str(error)
            self.failed[source.id] = reason
            warnings.append(warn(f"feed {source.id} ({url}) gave nothing: {reason}"))
            return None
        self.responded[source.id] = len(items)
        return _Fetched(items, fetched_at)

    def collect(
        self, query: Query, sources: Sequence[Source], remaining_budget: int
    ) -> CollectResult:
        before = self._http.requests_made
        phrases = query_phrases(str(query.text))
        warnings: list[CleanText] = []
        hits: list[RawHit] = []
        for source in sources:
            url = source.feed_url
            if url is None:
                warnings.append(warn(f"feed query {query.id}: source {source.id} has no feed"))
                continue
            if url not in self._cache:
                if self._http.requests_made - before >= remaining_budget:
                    warnings.append(
                        warn(
                            f"feed query {query.id} stopped at the request budget; feed "
                            f"{source.id} not fetched"
                        )
                    )
                    continue
                self._cache[url] = self._fetch(source, url, warnings)
            fetched = self._cache[url]
            if fetched is None:
                continue
            builder = HitBuilder(query, self.discipline, fetched.fetched_at)
            for item in fetched.items:
                if not item_matches(item, phrases):
                    continue
                hit = builder.build(
                    item.link, item.title, item.summary, item.published_on, source.id, warnings
                )
                if hit is not None:
                    hits.append(hit)
        return CollectResult(tuple(hits), self._http.requests_made - before, tuple(warnings))
