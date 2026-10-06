"""Which real collector serves each discipline in this environment, and why one is missing.

``build_collectors`` returns the collectors that can run here:

- ``osint_web`` and ``osint_site`` (Brave Search) only with a Brave key;
- ``osint_feed`` always (feeds need no key);
- ``osint_academic`` (OpenAlex then Crossref, as one collector) only when
  the academic indexes are switched on.

The fake collector is never in this registry: it belongs to tests,
``collect --dry-run`` and ``collect --fake``. Every collector shares the one
``HttpClient``, so the request count and the per-host rate limits cover the
whole run. Build a fresh registry for each run: the feed collector caches
each feed for the life of the run.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Final, Protocol

from gwylio.collection.model import Query, RawHit, Source
from gwylio.collection.ports import Collector, CollectResult
from gwylio.infrastructure.collectors.brave_site import BraveSiteCollector
from gwylio.infrastructure.collectors.brave_web import BraveSearch, BraveWebCollector
from gwylio.infrastructure.collectors.common import warn
from gwylio.infrastructure.collectors.crossref import CrossrefCollector
from gwylio.infrastructure.collectors.feed import FeedCollector
from gwylio.infrastructure.collectors.openalex import OpenAlexCollector
from gwylio.infrastructure.config.settings import Settings
from gwylio.infrastructure.http.client import HttpClient
from gwylio.shared.clock import Clock
from gwylio.shared.values import CleanText
from gwylio.shared.vocabulary import Discipline

__all__ = [
    "AcademicCollector",
    "NamedCollector",
    "build_collectors",
    "describe_collector",
    "missing_disciplines",
]

NO_BRAVE_KEY: Final[str] = (
    "no Brave Search API key; set GWYLIO_BRAVE_API_KEY or BRAVE_API_KEY, or put "
    "BRAVE_API_KEY=<key> in search_keys.txt at the project root"
)
ACADEMIC_OFF: Final[str] = (
    "the academic indexes are off; set GWYLIO_ACADEMIC=1 or pass --discipline osint_academic"
)
_REASONS: Final[dict[Discipline, str]] = {
    Discipline.OSINT_WEB: NO_BRAVE_KEY,
    Discipline.OSINT_SITE: NO_BRAVE_KEY,
    Discipline.OSINT_ACADEMIC: ACADEMIC_OFF,
    Discipline.GEOINT: "reserved; no collector serves it in version 1",
    Discipline.SENSOR: "reserved; no collector serves it in version 1",
}
_DESCRIPTIONS: Final[dict[Discipline, str]] = {
    Discipline.OSINT_WEB: "Brave web search",
    Discipline.OSINT_SITE: "Brave site search",
    Discipline.OSINT_FEED: "RSS and Atom feeds",
    Discipline.OSINT_ACADEMIC: "OpenAlex and Crossref",
}


class NamedCollector(Collector, Protocol):
    """A collector with a display name, for the parts of a combined collector."""

    @property
    def name(self) -> str:
        """The index's name, for warnings."""
        ...


class AcademicCollector:
    """``osint_academic``: each query runs on every academic index in turn, within the budget."""

    def __init__(self, parts: Sequence[NamedCollector]) -> None:
        if not parts:
            raise ValueError("the academic collector needs at least one index")
        for part in parts:
            if part.discipline is not Discipline.OSINT_ACADEMIC:
                raise ValueError(f"{part.name} serves {part.discipline.value}, not osint_academic")
        self._parts = tuple(parts)

    @property
    def discipline(self) -> Discipline:
        return Discipline.OSINT_ACADEMIC

    def collect(
        self, query: Query, sources: Sequence[Source], remaining_budget: int
    ) -> CollectResult:
        hits: list[RawHit] = []
        warnings: list[CleanText] = []
        used = 0
        for index, part in enumerate(self._parts):
            left = remaining_budget - used
            if left < 1:
                names = ", ".join(p.name for p in self._parts[index:])
                warnings.append(
                    warn(
                        f"academic query {query.id} stopped at the request budget; {names} skipped"
                    )
                )
                break
            result = part.collect(query, sources, left)
            hits.extend(result.hits)
            warnings.extend(result.warnings)
            used += result.requests_used
        return CollectResult(tuple(hits), used, tuple(warnings))


def build_collectors(
    settings: Settings, http: HttpClient, clock: Clock | None = None
) -> dict[Discipline, Collector]:
    """The real collectors available with these settings, sharing ``http``."""
    collectors: dict[Discipline, Collector] = {}
    if settings.brave_api_key is not None:
        search = BraveSearch(http, settings.brave_api_key.get_secret_value())
        collectors[Discipline.OSINT_WEB] = BraveWebCollector(search, clock)
        collectors[Discipline.OSINT_SITE] = BraveSiteCollector(search, clock)
    collectors[Discipline.OSINT_FEED] = FeedCollector(http, clock)
    if settings.academic_enabled:
        collectors[Discipline.OSINT_ACADEMIC] = AcademicCollector(
            (
                OpenAlexCollector(http, settings.contact_email, clock),
                CrossrefCollector(http, settings.contact_email, clock),
            )
        )
    return {d: collectors[d] for d in Discipline if d in collectors}


def missing_disciplines(
    requested: Iterable[Discipline],
    available: Mapping[Discipline, Collector] | Iterable[Discipline],
) -> list[str]:
    """``<discipline>: <reason>`` for each requested discipline no collector serves here."""
    have = frozenset(available)
    return [
        f"{d.value}: {_REASONS.get(d, 'no collector is registered for it')}"
        for d in dict.fromkeys(requested)
        if d not in have
    ]


def describe_collector(discipline: Discipline) -> str:
    """What serves a discipline, in a few words, for the command line."""
    return _DESCRIPTIONS.get(discipline, discipline.value)
