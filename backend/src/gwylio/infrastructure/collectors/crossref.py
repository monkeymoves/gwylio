"""Scholarly works from Crossref: the other half of the ``osint_academic`` discipline.

Enabled only when ``GWYLIO_ACADEMIC=1`` (or an explicit ``--discipline
osint_academic``). One request per query: ``GET https://api.crossref.org/works``
with ``query``, ``filter=from-pub-date:<a year ago>``, ``rows=15`` and
``mailto``; the shared client's User-Agent carries the same contact address,
as Crossref's etiquette asks. Each item becomes a ``RawHit`` on its DOI URL,
with the abstract (JATS markup stripped), or failing that the journal title,
as the snippet. A published date with no day is left out rather than guessed.

Note: the academic indexes ignore geography. They match keywords loosely, so
a query ending "Wales" returns global papers that seldom mention Wales. The
collector does not try to fix that; the relevance gate does the filtering.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from typing import Final

from gwylio.collection.model import Query, RawHit, Source
from gwylio.collection.ports import CollectResult
from gwylio.infrastructure.collectors.common import HitBuilder, as_dict, as_list, as_str, warn
from gwylio.infrastructure.collectors.openalex import LOOKBACK_DAYS
from gwylio.infrastructure.http.client import HttpClient, HttpError
from gwylio.shared.clock import Clock, SystemClock
from gwylio.shared.values import CleanText, IsoDate
from gwylio.shared.vocabulary import Discipline

__all__ = ["CROSSREF_URL", "ROWS", "CrossrefCollector", "crossref_date"]

CROSSREF_URL: Final[str] = "https://api.crossref.org/works"
ROWS: Final[int] = 15
_DATE_FIELDS: Final[tuple[str, ...]] = (
    "published",
    "published-online",
    "published-print",
    "issued",
)


def crossref_date(item: dict[str, object]) -> IsoDate | None:
    """The first full ``date-parts`` among the published dates, or ``None``."""
    for name in _DATE_FIELDS:
        parts = as_list(as_dict(item.get(name)).get("date-parts"))
        first = as_list(parts[0]) if parts else []
        numbers = [part for part in first[:3] if isinstance(part, int)]
        if len(numbers) == 3:
            try:
                return IsoDate(date(numbers[0], numbers[1], numbers[2]))
            except ValueError:
                continue
    return None


def _first_str(value: object) -> str:
    return next((as_str(item) for item in as_list(value) if as_str(item)), "")


class CrossrefCollector:
    """``osint_academic`` through Crossref: one search per query."""

    name: Final[str] = "Crossref"

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
            return CollectResult(warnings=(warn(f"Crossref query {query.id}: no budget left"),))
        before = self._http.requests_made
        since = self._clock.today() - timedelta(days=LOOKBACK_DAYS)
        try:
            body = self._http.get_json(
                CROSSREF_URL,
                params={
                    "query": str(query.text),
                    "filter": f"from-pub-date:{since.isoformat()}",
                    "rows": ROWS,
                    "mailto": self._mailto,
                },
            )
        except HttpError as error:
            return CollectResult(
                requests_used=self._http.requests_made - before,
                warnings=(warn(f"Crossref query {query.id} failed: {error}"),),
            )
        warnings: list[CleanText] = []
        builder = HitBuilder(query, self.discipline, self._clock.now())
        hits: list[RawHit] = []
        message = as_dict(as_dict(body).get("message"))
        for item in (as_dict(entry) for entry in as_list(message.get("items"))):
            doi = as_str(item.get("DOI")).strip()
            url = f"https://doi.org/{doi}" if doi else as_str(item.get("URL"))
            hit = builder.build(
                url,
                _first_str(item.get("title")),
                as_str(item.get("abstract")) or _first_str(item.get("container-title")),
                crossref_date(item),
                None,
                warnings,
            )
            if hit is not None:
                hits.append(hit)
        return CollectResult(tuple(hits), self._http.requests_made - before, tuple(warnings))
