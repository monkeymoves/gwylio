"""Closed vocabularies that more than one context uses.

``Discipline``, ``Reliability``, ``CandidateStatus`` and ``MatchedBy`` belong
to the Collection context's language, but Processing (the candidates file),
Intelligence (grading, reinforcements) and Evaluation (yield per discipline)
need them too. The dependency rule lets a
context import only ``gwylio.shared``, so they live here, in the shared
kernel, and ``gwylio.collection.model`` re-exports them.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

__all__ = ["CandidateStatus", "Discipline", "MatchedBy", "Reliability"]


class Discipline(StrEnum):
    """The kind of collection a collector performs."""

    OSINT_WEB = "osint_web"
    OSINT_FEED = "osint_feed"
    OSINT_SITE = "osint_site"
    OSINT_ACADEMIC = "osint_academic"
    GEOINT = "geoint"
    SENSOR = "sensor"

    @property
    def reserved(self) -> bool:
        """True for disciplines named for later work that no collector serves yet."""
        return self in _RESERVED

    @property
    def meaning(self) -> str:
        """One sentence on what this discipline collects."""
        return _DISCIPLINE_MEANINGS[self]


_RESERVED: Final[frozenset[Discipline]] = frozenset({Discipline.GEOINT, Discipline.SENSOR})
_DISCIPLINE_MEANINGS: Final[dict[Discipline, str]] = {
    Discipline.OSINT_WEB: "Open web search with a query text.",
    Discipline.OSINT_FEED: "Items read from the feeds of watched sources, matched to a query.",
    Discipline.OSINT_SITE: "Web search restricted to the domains of named watched sources.",
    Discipline.OSINT_ACADEMIC: "Scholarly indexes searched with a query text.",
    Discipline.GEOINT: "Reserved: geospatial intelligence, not collected in version 1.",
    Discipline.SENSOR: "Reserved: sensor and monitoring data, not collected in version 1.",
}


class Reliability(StrEnum):
    """The Admiralty reliability of a source, A (best) to F (cannot be judged).

    Reliability belongs to the source, never to one report: the analyst judges
    credibility (1 to 6) per report, and the two together make the grading.
    """

    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"

    @property
    def label(self) -> str:
        """The standard Admiralty wording for this letter."""
        return _RELIABILITY_LABELS[self]


_RELIABILITY_LABELS: Final[dict[Reliability, str]] = {
    Reliability.A: "completely reliable",
    Reliability.B: "usually reliable",
    Reliability.C: "fairly reliable",
    Reliability.D: "not usually reliable",
    Reliability.E: "unreliable",
    Reliability.F: "cannot be judged",
}


class CandidateStatus(StrEnum):
    """What the collector knew about a candidate's canonical URL when it found it."""

    NEW = "new"
    SEEN_BEFORE = "seen_before"
    REINFORCEMENT = "reinforcement"

    @property
    def meaning(self) -> str:
        """One sentence on what this status means."""
        return _CANDIDATE_STATUS_MEANINGS[self]


_CANDIDATE_STATUS_MEANINGS: Final[dict[CandidateStatus, str]] = {
    CandidateStatus.NEW: "No earlier run recorded the URL and it matches no report.",
    CandidateStatus.SEEN_BEFORE: "An earlier run recorded the URL; it matches no report.",
    CandidateStatus.REINFORCEMENT: "The URL, or failing that the exact title, matches a report.",
}


class MatchedBy(StrEnum):
    """How a candidate was matched to an existing intelligence report."""

    URL = "url"
    TITLE = "title"
