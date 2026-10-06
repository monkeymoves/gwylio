"""Web search restricted to watched domains through the Brave Search API: ``osint_site``.

A site query names its sources; their domains are OR-joined into the search,
``(site:gov.wales OR site:senedd.wales) ("phrase" OR "phrase")``, with a lone
domain written ``site:gov.wales ("phrase" OR ...)``. Brave accepts at most 400
characters and 50 words in ``q``, so a query naming many sources (the
partnership lane names twelve) is split into as few requests as fit; most
site queries cost one request.

The collector honours the remaining budget: when the requests a query needs
would exceed it, it runs what fits and warns naming the domains not searched.
Each hit carries the id of the named source whose domain (or a parent of the
hit's host) it came from.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from gwylio.collection.model import Query, RawHit, Source
from gwylio.collection.ports import CollectResult
from gwylio.infrastructure.collectors.brave_web import BraveSearch
from gwylio.infrastructure.collectors.common import HitBuilder, warn
from gwylio.infrastructure.http.client import HttpError
from gwylio.shared.clock import Clock, SystemClock
from gwylio.shared.values import CanonicalUrl, CleanText, KebabId
from gwylio.shared.vocabulary import Discipline

__all__ = ["MAX_QUERY_CHARS", "MAX_QUERY_WORDS", "BraveSiteCollector", "site_queries", "site_query"]

MAX_QUERY_CHARS: Final[int] = 400
MAX_QUERY_WORDS: Final[int] = 50


def site_query(domains: Sequence[str], text: str) -> str:
    """The Brave ``q`` for ``text`` on ``domains``."""
    sites = " OR ".join(f"site:{domain}" for domain in domains)
    if len(domains) > 1:
        sites = f"({sites})"
    return f"{sites} ({text})"


def _fits(q: str) -> bool:
    return len(q) <= MAX_QUERY_CHARS and len(q.split()) <= MAX_QUERY_WORDS


def site_queries(domains: Sequence[str], text: str) -> list[tuple[tuple[str, ...], str]]:
    """The fewest searches covering ``domains`` within Brave's limits, in domain order.

    A domain that does not fit even alone is still searched alone: the text is
    the instrument's, and Brave reports a query it refuses.
    """
    chunks: list[tuple[str, ...]] = []
    current: list[str] = []
    for domain in dict.fromkeys(domains):
        if current and not _fits(site_query([*current, domain], text)):
            chunks.append(tuple(current))
            current = []
        current.append(domain)
    if current:
        chunks.append(tuple(current))
    return [(chunk, site_query(chunk, text)) for chunk in chunks]


def _source_for(url: str, sources: Sequence[Source]) -> KebabId | None:
    """The named source whose domain is the URL's host or a parent of it, longest first."""
    try:
        host = CanonicalUrl(url).host
    except ValueError:
        return None
    matches = [s for s in sources if host == s.domain or host.endswith("." + s.domain)]
    if not matches:
        return None
    return max(matches, key=lambda s: len(s.domain)).id


class BraveSiteCollector:
    """``osint_site``: Brave searches restricted to the domains a query names."""

    def __init__(self, search: BraveSearch, clock: Clock | None = None) -> None:
        self._search = search
        self._clock = clock or SystemClock()

    @property
    def discipline(self) -> Discipline:
        return Discipline.OSINT_SITE

    def collect(
        self, query: Query, sources: Sequence[Source], remaining_budget: int
    ) -> CollectResult:
        if self._search.refused is not None:
            return CollectResult()
        if not sources:
            return CollectResult(warnings=(warn(f"site query {query.id}: no sources to search"),))
        http = self._search.http
        before = http.requests_made
        warnings: list[CleanText] = []
        hits: list[RawHit] = []
        builder = HitBuilder(query, self.discipline, self._clock.now())
        searches = site_queries([source.domain for source in sources], str(query.text))
        for index, (domains, q) in enumerate(searches):
            if http.requests_made - before >= remaining_budget:
                skipped = [domain for chunk, _ in searches[index:] for domain in chunk]
                warnings.append(
                    warn(
                        f"site query {query.id} stopped at the request budget ({remaining_budget} "
                        f"left); not searched: {', '.join(skipped)}"
                    )
                )
                break
            try:
                results = self._search.results(q)
            except HttpError as error:
                if self._search.refused is not None:
                    warnings.append(
                        warn(f"{self._search.refused}; Brave site queries skipped from here on")
                    )
                    break
                warnings.append(
                    warn(f"site query {query.id} failed on {', '.join(domains)}: {error}")
                )
                continue
            hits.extend(
                BraveSearch.hits(results, builder, warnings, lambda url: _source_for(url, sources))
            )
        return CollectResult(tuple(hits), http.requests_made - before, tuple(warnings))
