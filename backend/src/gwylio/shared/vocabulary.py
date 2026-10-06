"""Closed vocabularies that more than one context uses.

``Discipline``, ``Reliability``, ``CandidateStatus`` and ``MatchedBy`` belong
to the Collection context's language, but Processing (the candidates file),
Intelligence (grading, reinforcements) and Evaluation (yield per discipline)
need them too. The dependency rule lets a
context import only ``gwylio.shared``, so they live here, in the shared
kernel, and ``gwylio.collection.model`` re-exports them.

The Intelligence context's closed values (``ReportType``, ``Direction``,
``IndicatorState``, ``Bucket``, ``Level``, ``TimeHorizon``, ``Credibility``)
and the Processing context's ``DispositionOutcome`` live here for the same
reason: the submission contract in Processing names them, the register in
Intelligence enforces them, and Evaluation and Dissemination read them.
``gwylio.intelligence.model`` re-exports them.
"""

from __future__ import annotations

from enum import IntEnum, StrEnum
from typing import Final

__all__ = [
    "Bucket",
    "CandidateStatus",
    "Credibility",
    "Direction",
    "Discipline",
    "DispositionOutcome",
    "IndicatorState",
    "Level",
    "MatchedBy",
    "Reliability",
    "ReportType",
    "TimeHorizon",
]


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


# The Intelligence context's closed values.


class ReportType(StrEnum):
    """What kind of development an intelligence report describes."""

    POLICY = "policy"
    LEGISLATION = "legislation"
    RESEARCH = "research"
    DATA_RELEASE = "data_release"
    FUNDING = "funding"
    PARTNERSHIP = "partnership"
    INTERNATIONAL = "international"
    LEGAL = "legal"
    ENVIRONMENTAL = "environmental"
    MARKET = "market"
    INCIDENT = "incident"


class Direction(StrEnum):
    """Which way a report bears on one requirement."""

    SUPPORTS = "supports"
    THREATENS = "threatens"
    NEUTRAL = "neutral"
    INFORMS_BASELINE = "informs_baseline"

    @property
    def meaning(self) -> str:
        """One sentence on what this direction means."""
        return _DIRECTION_MEANINGS[self]


_DIRECTION_MEANINGS: Final[dict[Direction, str]] = {
    Direction.SUPPORTS: "Makes progress on the requirement more likely or easier.",
    Direction.THREATENS: "Makes progress on the requirement less likely or harder.",
    Direction.NEUTRAL: "Bears on the requirement with no clear direction, or both ways at once.",
    Direction.INFORMS_BASELINE: "Changes what we know about where the requirement stands now.",
}


class IndicatorState(StrEnum):
    """Where a report is in the indications and warnings lifecycle."""

    EMERGING = "emerging"
    TRACKING = "tracking"
    REINFORCED = "reinforced"
    MATURED = "matured"
    FADED = "faded"
    PARKED = "parked"

    @property
    def active(self) -> bool:
        """True for the states the lifecycle still moves: emerging, tracking and reinforced."""
        return self in _ACTIVE_STATES

    @property
    def live(self) -> bool:
        """True for every state still in the picture: the active ones and matured."""
        return self in _ACTIVE_STATES or self is IndicatorState.MATURED

    @property
    def meaning(self) -> str:
        """One sentence on what this state means and how a report reaches it."""
        return _STATE_MEANINGS[self]


_ACTIVE_STATES: Final[frozenset[IndicatorState]] = frozenset(
    {IndicatorState.EMERGING, IndicatorState.TRACKING, IndicatorState.REINFORCED}
)
_STATE_MEANINGS: Final[dict[IndicatorState, str]] = {
    IndicatorState.EMERGING: "New to the register, seen in one run only.",
    IndicatorState.TRACKING: "Seen again in a strictly later run than the one that found it.",
    IndicatorState.REINFORCED: (
        "Seen by three distinct sources, or independently confirmed by the analyst."
    ),
    IndicatorState.MATURED: "Settled context, set by the analyst; sightings are still recorded.",
    IndicatorState.FADED: (
        "Not seen in the two most recent complete runs; set by the sweep, revived by a sighting."
    ),
    IndicatorState.PARKED: "Set aside by the analyst; sightings are still recorded.",
}


class Bucket(StrEnum):
    """Where a report goes next."""

    BRIEF = "brief"
    FOLLOW_UP = "follow_up"
    WATCH = "watch"
    PARK = "park"


class Level(StrEnum):
    """A three-point score: low, medium or high."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TimeHorizon(StrEnum):
    """When a report's consequences are expected to land."""

    IMMEDIATE = "immediate"
    NEAR_TERM = "near_term"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"


class Credibility(IntEnum):
    """The Admiralty credibility of one report's information, 1 (best) to 6 (cannot be judged).

    The analyst judges credibility per report; the source's reliability is
    fixed by the watchlist. The two together make the grading, such as B2.
    """

    CONFIRMED = 1
    PROBABLY_TRUE = 2
    POSSIBLY_TRUE = 3
    DOUBTFUL = 4
    IMPROBABLE = 5
    CANNOT_BE_JUDGED = 6

    @property
    def label(self) -> str:
        """The standard Admiralty wording for this digit, such as ``probably true``."""
        return self.name.lower().replace("_", " ")


# The Processing context's closed values.


class DispositionOutcome(StrEnum):
    """The fate the analyst gives one candidate in a submission."""

    PROMOTED = "promoted"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"
    DEFERRED = "deferred"
    REINFORCEMENT = "reinforcement"

    @property
    def meaning(self) -> str:
        """One sentence on what this outcome means."""
        return _OUTCOME_MEANINGS[self]


_OUTCOME_MEANINGS: Final[dict[DispositionOutcome, str]] = {
    DispositionOutcome.PROMOTED: "Became a new intelligence report, named by report_id.",
    DispositionOutcome.REJECTED: "Fails the promotion test; the reason says which part.",
    DispositionOutcome.DUPLICATE: (
        "The same development as another candidate or report; report_id may name it."
    ),
    DispositionOutcome.DEFERRED: "Not judged yet; a later submission may dispose of it.",
    DispositionOutcome.REINFORCEMENT: (
        "A new sighting of an existing report, named by report_id and confirmed in reinforcements."
    ),
}
