"""Deduplication by canonical URL, and matching against what is already known.

The lesson from the earlier tool: distinct documents often share a generic
title ("Consultation display | Senedd"), so titles never decide whether two
hits are the same document. Only the canonical URL does. A title is used in
one place only: to match a candidate to an existing report when its URL does
not match any report.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from gwylio.collection.model import CandidateStatus, MatchedBy, RawHit, RunId
from gwylio.collection.ports import KnownReports
from gwylio.shared.values import CanonicalUrl, CleanText, IsoDate, KebabId

__all__ = [
    "CandidateDraft",
    "KnownMatch",
    "SeenIndex",
    "group_hits",
    "match_known",
    "normalise_title",
]


@dataclass(frozen=True, slots=True)
class CandidateDraft:
    """Every passed hit for one canonical URL in a run, before it becomes a candidate.

    The first hit gives the URL, the title, the source, the query and the
    discipline; the snippet is the longest any hit carried (the first on a
    tie); ``published_on`` is the earliest date any hit carried. Every hit
    becomes a sighting.
    """

    canonical_url: CanonicalUrl
    hits: tuple[RawHit, ...]

    def __post_init__(self) -> None:
        if not self.hits:
            raise ValueError("a draft needs at least one hit")
        if any(hit.canonical_url != self.canonical_url for hit in self.hits):
            raise ValueError("every hit in a draft must share its canonical URL")

    @property
    def first(self) -> RawHit:
        """The hit that found this URL first in the run."""
        return self.hits[0]

    @property
    def url(self) -> str:
        """The first hit's URL as the collector returned it."""
        return self.first.url

    @property
    def title(self) -> CleanText:
        """The first hit's title."""
        return self.first.title

    @property
    def snippet(self) -> CleanText:
        """The longest snippet, the first one on a tie."""
        best = self.first.snippet
        for hit in self.hits[1:]:
            if len(hit.snippet) > len(best):
                best = hit.snippet
        return best

    @property
    def published_on(self) -> IsoDate | None:
        """The earliest publication date any hit carried."""
        dates = [hit.published_on for hit in self.hits if hit.published_on is not None]
        return min(dates) if dates else None


def group_hits(passed_hits: Iterable[RawHit]) -> list[CandidateDraft]:
    """One draft per canonical URL, in the order each URL was first found."""
    groups: dict[CanonicalUrl, list[RawHit]] = {}
    for hit in passed_hits:
        groups.setdefault(hit.canonical_url, []).append(hit)
    return [CandidateDraft(url, tuple(hits)) for url, hits in groups.items()]


def normalise_title(title: str) -> str:
    """A title lower-cased with its whitespace collapsed, for exact title matching."""
    return " ".join(title.casefold().split())


class SeenIndex:
    """Which canonical URLs earlier runs recorded, and the run that first recorded each."""

    __slots__ = ("_first_seen",)

    def __init__(self, first_seen: Mapping[str, str] | None = None) -> None:
        self._first_seen = {url: RunId(run) for url, run in (first_seen or {}).items()}

    def first_seen_run(self, canonical_url: CanonicalUrl) -> RunId | None:
        """The run that first recorded this URL, or ``None`` if no earlier run did."""
        return self._first_seen.get(canonical_url.value)

    def __len__(self) -> int:
        return len(self._first_seen)


@dataclass(frozen=True, slots=True)
class KnownMatch:
    """A draft with what the collector knew about it."""

    draft: CandidateDraft
    status: CandidateStatus
    first_seen_run_id: RunId | None
    report_id: KebabId | None = None
    matched_by: MatchedBy | None = None


def match_known(
    drafts: Sequence[CandidateDraft], seen: SeenIndex, known: KnownReports
) -> list[KnownMatch]:
    """Mark each draft as a reinforcement, seen before, or new, in that order of precedence.

    A reinforcement's canonical URL matches a report, or, only when the URL
    matches none, its normalised title equals a report's normalised title.
    Seen before means an earlier run recorded the canonical URL. Everything
    else is new. ``first_seen_run_id`` is the earlier run when there was one.
    """
    matches: list[KnownMatch] = []
    for draft in drafts:
        first_seen = seen.first_seen_run(draft.canonical_url)
        report = known.report_id_for_url(draft.canonical_url)
        matched_by = MatchedBy.URL
        if report is None:
            report = known.report_id_for_title(normalise_title(draft.title))
            matched_by = MatchedBy.TITLE
        if report is not None:
            matches.append(
                KnownMatch(
                    draft, CandidateStatus.REINFORCEMENT, first_seen, KebabId(report), matched_by
                )
            )
        elif first_seen is not None:
            matches.append(KnownMatch(draft, CandidateStatus.SEEN_BEFORE, first_seen))
        else:
            matches.append(KnownMatch(draft, CandidateStatus.NEW, None))
    return matches
