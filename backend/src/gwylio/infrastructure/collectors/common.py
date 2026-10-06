"""Helpers every real collector shares: safe URLs, plain text, dates, JSON access and hits.

Collectors read text they did not write, so everything here is forgiving: a
missing field reads as empty, a date that will not parse reads as ``None``, a
URL with no host gives no hit rather than an exception. Titles, snippets and
warnings go through ``CleanText.scrub`` because publishers use dashes; URLs
are stored raw, so an en or em dash in one is percent-encoded instead.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime
from typing import Final

from gwylio.collection.model import Query, RawHit
from gwylio.shared.values import CleanText, IsoDate, KebabId
from gwylio.shared.vocabulary import Discipline

__all__ = [
    "SNIPPET_LIMIT",
    "HitBuilder",
    "as_dict",
    "as_list",
    "as_str",
    "parse_date",
    "plain_text",
    "query_phrases",
    "safe_url",
    "warn",
]

SNIPPET_LIMIT: Final[int] = 500
"""Snippets longer than this are cut at a word boundary and end with three dots."""
_DASHES: Final[dict[str, str]] = {chr(0x2013): "%E2%80%93", chr(0x2014): "%E2%80%94"}
_TAG_RE: Final[re.Pattern[str]] = re.compile(r"<[^>]*>")
_SPACE_RE: Final[re.Pattern[str]] = re.compile(r"\s+")
_QUOTED_RE: Final[re.Pattern[str]] = re.compile(r'"([^"]+)"')
_OR_RE: Final[re.Pattern[str]] = re.compile(r"\s+OR\s+")
_ISO_PREFIX_RE: Final[re.Pattern[str]] = re.compile(r"\d{4}-\d{2}-\d{2}")
_WRITTEN_FORMATS: Final[tuple[str, ...]] = ("%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y")


def safe_url(url: str) -> str:
    """The URL trimmed, with any en or em dash percent-encoded (the database refuses them)."""
    text = url.strip()
    for dash, encoded in _DASHES.items():
        text = text.replace(dash, encoded)
    return text


def plain_text(markup: str, limit: int | None = None) -> str:
    """Markup reduced to one line of plain text: tags removed, entities decoded, spaces collapsed.

    With ``limit``, text longer than that is cut at the last space before it
    and ends with three dots.
    """
    # Tags out, entities decoded, then tags out again: feeds often escape their HTML twice.
    text = _TAG_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", markup)))
    text = _SPACE_RE.sub(" ", text).strip()
    if limit is not None and len(text) > limit:
        cut = text[:limit]
        space = cut.rfind(" ")
        text = (cut[:space] if space > limit // 2 else cut).rstrip(" ,;:.") + "..."
    return text


def warn(text: str) -> CleanText:
    """A warning line, scrubbed of dashes because it may quote a server or an exception."""
    return CleanText.scrub(_SPACE_RE.sub(" ", text))


def query_phrases(text: str) -> tuple[str, ...]:
    """The phrases of an OR-joined query text, lower-cased: quoted phrases, else the OR parts.

    ``"nature recovery" OR "rewilding"`` gives ``("nature recovery", "rewilding")``;
    unquoted text with no ``OR`` gives the whole text as one phrase.
    """
    quoted = [phrase.strip() for phrase in _QUOTED_RE.findall(text)]
    parts = quoted or [part.strip().strip('"') for part in _OR_RE.split(text)]
    seen: dict[str, None] = {}
    for part in parts:
        phrase = " ".join(part.casefold().split())
        if phrase:
            seen.setdefault(phrase, None)
    return tuple(seen)


def parse_date(text: str | None) -> IsoDate | None:
    """A calendar date from ISO 8601, RFC 822 or ``September 12, 2026``; ``None`` otherwise."""
    if not text:
        return None
    value = text.strip()
    if _ISO_PREFIX_RE.match(value):
        try:
            return IsoDate(date.fromisoformat(value[:10]))
        except ValueError:
            return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        parsed = None
    if parsed is not None:
        return IsoDate(parsed.date())
    for pattern in _WRITTEN_FORMATS:
        try:
            return IsoDate(datetime.strptime(value, pattern).replace(tzinfo=UTC).date())
        except ValueError:
            continue
    return None


def as_dict(value: object) -> dict[str, object]:
    """``value`` when it is a JSON object, else an empty one."""
    if isinstance(value, dict):
        return {str(key): item for key, item in value.items()}
    return {}


def as_list(value: object) -> list[object]:
    """``value`` when it is a JSON array, else an empty one."""
    return list(value) if isinstance(value, list) else []


def as_str(value: object) -> str:
    """``value`` when it is a string, else the empty string."""
    return value if isinstance(value, str) else ""


@dataclass(frozen=True, slots=True)
class HitBuilder:
    """Builds the raw hits of one collector call, all carrying the query's id and discipline."""

    query: Query
    discipline: Discipline
    fetched_at: datetime

    def build(
        self,
        url: str,
        title: str,
        snippet: str = "",
        published_on: IsoDate | None = None,
        source_id: KebabId | None = None,
        warnings: list[CleanText] | None = None,
    ) -> RawHit | None:
        """A hit, or ``None`` (with a warning when ``warnings`` is given) for an unusable URL."""
        link = safe_url(url)
        if not link:
            return None
        try:
            return RawHit(
                url=link,
                title=CleanText.scrub(plain_text(title)),
                snippet=CleanText.scrub(plain_text(snippet, SNIPPET_LIMIT)),
                published_on=published_on,
                discipline=self.discipline,
                query_id=self.query.id,
                source_id=source_id,
                fetched_at=self.fetched_at,
            )
        except ValueError as error:
            if warnings is not None:
                warnings.append(
                    warn(f"query {self.query.id}: skipped a result with an unusable URL: {error}")
                )
            return None
