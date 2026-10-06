"""Open web search through the Brave Search API: the ``osint_web`` collector.

One request per query: ``GET https://api.search.brave.com/res/v1/web/search``
with the ``X-Subscription-Token`` header and ``q``, ``count=20``,
``country=GB``, ``search_lang=en`` and ``safesearch=off``. Each of
``web.results[]`` becomes a ``RawHit``: its ``url``, its ``title``, its
``description`` as the snippet (Brave marks matches with ``<strong>``, which is
stripped) and its ``page_age``, or failing that its ``age``, as the published
date when either parses. The source is left for the scan to resolve by domain.

``BraveSearch`` holds the request and the mapping so the site collector
(``brave_site.py``) shares them. A refused key (HTTP 401 or 403) switches the
collector off for the rest of the run with one warning, rather than one
warning per query; any other failure is a warning for that query alone.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Final

from gwylio.collection.model import Query, RawHit, Source
from gwylio.collection.ports import CollectResult
from gwylio.infrastructure.collectors.common import (
    HitBuilder,
    as_dict,
    as_list,
    as_str,
    parse_date,
    warn,
)
from gwylio.infrastructure.http.client import HttpClient, HttpError
from gwylio.shared.clock import Clock, SystemClock
from gwylio.shared.values import CleanText, IsoDate, KebabId
from gwylio.shared.vocabulary import Discipline

__all__ = ["BRAVE_WEB_URL", "RESULT_COUNT", "BraveSearch", "BraveWebCollector", "brave_date"]

BRAVE_WEB_URL: Final[str] = "https://api.search.brave.com/res/v1/web/search"
RESULT_COUNT: Final[int] = 20
_REFUSED: Final[frozenset[int]] = frozenset({401, 403})


def brave_date(result: dict[str, object]) -> IsoDate | None:
    """The result's ``page_age`` as a date, else its ``age``, else ``None``."""
    return parse_date(as_str(result.get("page_age"))) or parse_date(as_str(result.get("age")))


class BraveSearch:
    """One Brave Search API web request and the mapping of its results to hits."""

    def __init__(self, http: HttpClient, api_key: str) -> None:
        if not api_key.strip():
            raise ValueError("the Brave Search API needs a key")
        self._http = http
        self._key = api_key.strip()
        self.refused: str | None = None
        """Why the API refused the key, once it has; the collectors then stop asking."""

    @property
    def http(self) -> HttpClient:
        """The client the requests go through."""
        return self._http

    def results(self, q: str) -> list[dict[str, object]]:
        """``web.results[]`` for one search; raises ``HttpError``."""
        try:
            body = self._http.get_json(
                BRAVE_WEB_URL,
                params={
                    "q": q,
                    "count": RESULT_COUNT,
                    "country": "GB",
                    "search_lang": "en",
                    "safesearch": "off",
                },
                headers={"X-Subscription-Token": self._key, "Accept": "application/json"},
            )
        except HttpError as error:
            if error.status in _REFUSED:
                self.refused = f"Brave Search refused the API key (HTTP {error.status})"
            raise
        return [as_dict(item) for item in as_list(as_dict(as_dict(body).get("web")).get("results"))]

    @staticmethod
    def hits(
        results: Sequence[dict[str, object]],
        builder: HitBuilder,
        warnings: list[CleanText],
        source_for: Callable[[str], KebabId | None] | None = None,
    ) -> list[RawHit]:
        """The results as raw hits, skipping any without a usable URL."""
        hits: list[RawHit] = []
        for result in results:
            url = as_str(result.get("url"))
            hit = builder.build(
                url,
                as_str(result.get("title")),
                as_str(result.get("description")),
                brave_date(result),
                None if source_for is None else source_for(url),
                warnings,
            )
            if hit is not None:
                hits.append(hit)
        return hits


class BraveWebCollector:
    """``osint_web``: one Brave web search per query."""

    def __init__(self, search: BraveSearch, clock: Clock | None = None) -> None:
        self._search = search
        self._clock = clock or SystemClock()

    @property
    def discipline(self) -> Discipline:
        return Discipline.OSINT_WEB

    def collect(
        self, query: Query, sources: Sequence[Source], remaining_budget: int
    ) -> CollectResult:
        if self._search.refused is not None:
            return CollectResult()
        if remaining_budget < 1:
            return CollectResult(warnings=(warn(f"query {query.id}: no request budget left"),))
        http = self._search.http
        before = http.requests_made
        warnings: list[CleanText] = []
        builder = HitBuilder(query, self.discipline, self._clock.now())
        try:
            results = self._search.results(str(query.text))
        except HttpError as error:
            if self._search.refused is not None:
                message = f"{self._search.refused}; Brave web and site queries skipped from here on"
            else:
                message = f"web query {query.id} failed: {error}"
            return CollectResult(
                requests_used=http.requests_made - before, warnings=(warn(message),)
            )
        hits = BraveSearch.hits(results, builder, warnings)
        return CollectResult(tuple(hits), http.requests_made - before, tuple(warnings))
