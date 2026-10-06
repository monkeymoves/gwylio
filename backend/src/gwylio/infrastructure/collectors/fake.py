"""A scripted collector for tests and ``gwylio collect --dry-run``.

``FakeCollector`` returns the scripted hits whose ``query_id`` is the query
it is asked to run, and reports one request per call. ``load_fake_hits``
reads the scripted hits from a JSON fixture such as
``backend/tests/fixtures/fake_hits.json``.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from datetime import datetime
from pathlib import Path
from typing import Annotated

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field

from gwylio.collection.model import Query, RawHit, Source
from gwylio.collection.ports import CollectResult
from gwylio.shared.values import KEBAB_PATTERN, CleanText, IsoDate, KebabId
from gwylio.shared.vocabulary import Discipline

__all__ = ["FakeCollector", "FakeHitsFile", "load_fake_hits"]

Prose = Annotated[str, AfterValidator(CleanText)]


class FakeHitConfig(BaseModel):
    """One scripted hit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    url: str = Field(min_length=1)
    title: Prose
    snippet: Prose = ""
    published_on: str | None = Field(default=None, pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    discipline: Discipline
    query_id: str = Field(pattern=KEBAB_PATTERN)
    source_id: str | None = Field(default=None, pattern=KEBAB_PATTERN)
    note: Prose | None = Field(default=None, description="Why this hit is in the fixture.")


class FakeHitsFile(BaseModel):
    """A fixture of scripted hits."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    notes: Prose | None = None
    fetched_at: AwareDatetime
    hits: list[FakeHitConfig]


def _hit(config: FakeHitConfig, fetched_at: datetime) -> RawHit:
    return RawHit(
        url=config.url,
        title=CleanText(config.title),
        snippet=CleanText(config.snippet),
        published_on=None if config.published_on is None else IsoDate(config.published_on),
        discipline=config.discipline,
        query_id=KebabId(config.query_id),
        source_id=None if config.source_id is None else KebabId(config.source_id),
        fetched_at=fetched_at,
    )


def load_fake_hits(path: Path) -> tuple[RawHit, ...]:
    """The scripted hits in a fixture file, in file order."""
    parsed = FakeHitsFile.model_validate(json.loads(path.read_text(encoding="utf-8")))
    return tuple(_hit(config, parsed.fetched_at) for config in parsed.hits)


class FakeCollector:
    """Returns the scripted hits for each query it runs, one request per call."""

    def __init__(self, discipline: Discipline, hits: Iterable[RawHit]) -> None:
        self._discipline = discipline
        self._hits = tuple(hit for hit in hits if hit.discipline is discipline)
        self.calls: list[tuple[str, tuple[str, ...], int]] = []

    @property
    def discipline(self) -> Discipline:
        return self._discipline

    def collect(
        self, query: Query, sources: Sequence[Source], remaining_budget: int
    ) -> CollectResult:
        self.calls.append((query.id, tuple(source.id for source in sources), remaining_budget))
        if remaining_budget < 1:
            return CollectResult(warnings=(CleanText(f"query {query.id}: no budget left"),))
        hits = tuple(hit for hit in self._hits if hit.query_id == query.id)
        return CollectResult(hits=hits, requests_used=1)
