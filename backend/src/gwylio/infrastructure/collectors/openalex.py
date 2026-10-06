"""Scholarly works from OpenAlex: one half of the ``osint_academic`` discipline.

Enabled only when ``GWYLIO_ACADEMIC=1`` (or an explicit ``--discipline
osint_academic``). One request per query: ``GET https://api.openalex.org/works``
with ``search``, ``filter=from_publication_date:<a year ago>``, ``per_page=15``
and ``mailto`` (the polite pool). Each result becomes a ``RawHit`` on its DOI
URL (its landing page or OpenAlex id when it has no DOI), with the abstract,
rebuilt from OpenAlex's inverted index, as the snippet.

Note: the academic indexes ignore geography. They match keywords loosely, so
"ecosystem resilience assessment Wales" returns global papers that seldom
mention Wales. The collector does not try to fix that; the relevance gate
does the filtering, and an academic pass that yields nothing is the gate
working, not the collector failing.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
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
from gwylio.shared.values import CleanText
from gwylio.shared.vocabulary import Discipline

__all__ = ["LOOKBACK_DAYS", "OPENALEX_URL", "PER_PAGE", "OpenAlexCollector", "rebuild_abstract"]

OPENALEX_URL: Final[str] = "https://api.openalex.org/works"
PER_PAGE: Final[int] = 15
LOOKBACK_DAYS: Final[int] = 365
"""Works published in the last year: "from a year ago" for both academic indexes."""


def rebuild_abstract(inverted: object) -> str:
    """OpenAlex's ``abstract_inverted_index`` (word to positions) back into text."""
    positions: dict[int, str] = {}
    for word, places in as_dict(inverted).items():
        for place in as_list(places):
            if isinstance(place, int):
                positions[place] = word
    return " ".join(positions[index] for index in sorted(positions))


class OpenAlexCollector:
    """``osint_academic`` through OpenAlex: one search per query."""

    name: Final[str] = "OpenAlex"

    def __init__(self, http: HttpClient, mailto: str, clock: Clock | None = None) -> None:
        self._http = http
        self._mailto = mailto
        self._clock = clock or SystemClock()

    @property
    def discipline(self) -> Discipline:
        return Discipline.OSINT_ACADEMIC

    def collect(
        self, query: Query, sources: Sequence[Source], remaining_budget: int
    ) -> CollectResult:
        if remaining_budget < 1:
            return CollectResult(warnings=(warn(f"OpenAlex query {query.id}: no budget left"),))
        before = self._http.requests_made
        since = self._clock.today() - timedelta(days=LOOKBACK_DAYS)
        try:
            body = self._http.get_json(
                OPENALEX_URL,
                params={
                    "search": str(query.text),
                    "filter": f"from_publication_date:{since.isoformat()}",
                    "per_page": PER_PAGE,
                    "mailto": self._mailto,
                },
            )
        except HttpError as error:
            return CollectResult(
                requests_used=self._http.requests_made - before,
                warnings=(warn(f"OpenAlex query {query.id} failed: {error}"),),
            )
        warnings: list[CleanText] = []
        builder = HitBuilder(query, self.discipline, self._clock.now())
        hits: list[RawHit] = []
        for result in (as_dict(item) for item in as_list(as_dict(body).get("results"))):
            location = as_dict(result.get("primary_location"))
            url = (
                as_str(result.get("doi"))
                or as_str(location.get("landing_page_url"))
                or as_str(result.get("id"))
            )
            title = as_str(result.get("display_name")) or as_str(result.get("title"))
            hit = builder.build(
                url,
                title,
                rebuild_abstract(result.get("abstract_inverted_index")),
                parse_date(as_str(result.get("publication_date"))),
                None,
                warnings,
            )
            if hit is not None:
                hits.append(hit)
        return CollectResult(tuple(hits), self._http.requests_made - before, tuple(warnings))
