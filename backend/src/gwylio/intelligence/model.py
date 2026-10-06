"""The Intelligence context: the register of intelligence reports.

Pure, frozen domain objects with no input or output. An ``IntelligenceReport``
is the register entry: one external development, graded with the Admiralty
system, assessed against one or more requirements and tagged with topics,
hazards and places. Every change returns a new report with an entry appended
to its history; nothing is ever removed. ``appearances`` and
``distinct_sources`` are not fields: the service derives them from the
sightings named in ``sighting_ids``.

Cross-context identifiers (requirements, sources, actors, lanes, catalogue
ids) arrive as plain ``KebabId`` values, so this context never imports
Reference, Direction or Collection.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Final

from gwylio.shared.errors import DomainError
from gwylio.shared.values import CanonicalUrl, CleanText, IsoDate, KebabId, RunId
from gwylio.shared.vocabulary import (
    Bucket,
    Credibility,
    Direction,
    IndicatorState,
    Level,
    Reliability,
    ReportType,
    TimeHorizon,
)

__all__ = [
    "Assessment",
    "Bucket",
    "Credibility",
    "Direction",
    "Grading",
    "HistoryEntry",
    "HistoryKind",
    "IllegalTransition",
    "IndicatorState",
    "IntelligenceReport",
    "Level",
    "Reliability",
    "ReportType",
    "Scores",
    "TimeHorizon",
]

_GRADING_RE: Final[re.Pattern[str]] = re.compile(r"([A-F])([1-6])")


class IllegalTransition(DomainError):  # noqa: N818, the name the brief and the domain use
    """An event that the lifecycle does not allow from the report's current state."""


class HistoryKind(StrEnum):
    """What one history entry records."""

    CREATED = "created"
    SIGHTED = "sighted"
    STATE_CHANGED = "state_changed"
    VERIFIED = "verified"
    UPDATED = "updated"
    IMPORTED = "imported"
    FADED = "faded"
    REVIVED = "revived"


@dataclass(frozen=True, slots=True)
class Grading:
    """The Admiralty grading of one report: the source's reliability and the report's credibility.

    Renders as the letter and the digit together, such as ``B2``.
    """

    reliability: Reliability
    credibility: Credibility

    def __str__(self) -> str:
        return f"{self.reliability.value}{int(self.credibility)}"

    @classmethod
    def parse(cls, text: str) -> Grading:
        """The grading written as text, such as ``B2``; raises ``ValueError`` on anything else."""
        match = _GRADING_RE.fullmatch(text)
        if match is None:
            raise ValueError(
                f"not a grading: {text!r}; expected a letter A to F and a digit 1 to 6"
            )
        return cls(Reliability(match.group(1)), Credibility(int(match.group(2))))


@dataclass(frozen=True, slots=True)
class Assessment:
    """Which way a report bears on one requirement."""

    requirement_id: KebabId
    direction: Direction


@dataclass(frozen=True, slots=True)
class Scores:
    """The analyst's scores for a report, each on a short closed scale."""

    evidence: Level
    novelty: Level
    confidence: Level
    potential_impact: Level
    time_horizon: TimeHorizon


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    """One append-only line of a report's history: when, what kind of change, and why."""

    on: IsoDate
    kind: HistoryKind
    change: CleanText

    def __post_init__(self) -> None:
        if not self.change.strip():
            raise ValueError("a history entry needs a change text")


def _no_repeats(name: str, report_id: str, values: tuple[str, ...]) -> None:
    repeated = sorted({value for value in values if values.count(value) > 1})
    if repeated:
        raise DomainError(
            f"report '{report_id}' repeats {', '.join(repeated)} in {name}",
            scope="report",
            location=name,
        )


@dataclass(frozen=True, slots=True)
class IntelligenceReport:
    """One register entry. Frozen: every change returns a new report with history appended.

    ``lane`` is where the report was found: the source's lane when the source is
    watched, otherwise the lane the analyst gave. ``created_run_id`` is the run
    whose candidate was promoted, or ``None`` for a report added outside a run
    (the legacy import, a direct analyst addition).
    """

    id: KebabId
    title: CleanText
    url: str
    canonical_url: CanonicalUrl
    source_id: KebabId | None
    source_name: CleanText
    actor_id: KebabId | None
    lane: KebabId
    report_type: ReportType
    grading: Grading
    assessments: tuple[Assessment, ...]
    topics: tuple[KebabId, ...]
    hazards: tuple[KebabId, ...]
    places: tuple[KebabId, ...]
    scores: Scores
    state: IndicatorState
    bucket: Bucket
    event_horizon: IsoDate | None
    last_verified: IsoDate | None
    summary: CleanText
    notes: CleanText
    owner: CleanText | None
    created_on: IsoDate
    created_run_id: RunId | None
    independent_confirmation: bool = False
    history: tuple[HistoryEntry, ...] = ()
    sighting_ids: tuple[KebabId, ...] = ()

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise DomainError(f"report '{self.id}' needs a title", scope="report", location="title")
        if not self.source_name.strip():
            raise DomainError(
                f"report '{self.id}' needs a source name", scope="report", location="source_name"
            )
        if CanonicalUrl(self.url) != self.canonical_url:
            raise DomainError(
                f"report '{self.id}' url does not canonicalise to its canonical_url",
                scope="report",
                location="url",
            )
        if not self.assessments:
            raise DomainError(
                f"report '{self.id}' needs at least one assessment",
                scope="report",
                location="assessments",
            )
        _no_repeats("assessments", self.id, tuple(a.requirement_id for a in self.assessments))
        _no_repeats("topics", self.id, self.topics)
        _no_repeats("hazards", self.id, self.hazards)
        _no_repeats("places", self.id, self.places)
        _no_repeats("sighting_ids", self.id, self.sighting_ids)
        if not self.history:
            raise DomainError(
                f"report '{self.id}' needs at least one history entry",
                scope="report",
                location="history",
            )
        if self.owner is not None and not self.owner.strip():
            raise DomainError(
                f"report '{self.id}' has an empty owner; use null for no owner",
                scope="report",
                location="owner",
            )

    @property
    def requirement_ids(self) -> tuple[KebabId, ...]:
        """The requirements this report is assessed against, in order."""
        return tuple(a.requirement_id for a in self.assessments)

    def with_history(self, on: IsoDate, kind: HistoryKind, change: str) -> IntelligenceReport:
        """This report with one history entry appended."""
        entry = HistoryEntry(on, kind, CleanText(change))
        return replace(self, history=(*self.history, entry))

    def with_state(
        self, state: IndicatorState, on: IsoDate, kind: HistoryKind, change: str
    ) -> IntelligenceReport:
        """This report in ``state``, with a history entry saying why."""
        return replace(self, state=state).with_history(on, kind, change)

    def with_sighting(self, sighting_id: KebabId) -> IntelligenceReport:
        """This report with one more sighting linked. The lifecycle decides the history."""
        if sighting_id in self.sighting_ids:
            raise DomainError(
                f"report '{self.id}' already has sighting '{sighting_id}'",
                scope="report",
                location="sighting_ids",
            )
        return replace(self, sighting_ids=(*self.sighting_ids, sighting_id))

    def with_independent_confirmation(self) -> IntelligenceReport:
        """This report flagged as independently confirmed (no history; the lifecycle adds it)."""
        return replace(self, independent_confirmation=True)

    def verified(self, on: IsoDate, note: str) -> IntelligenceReport:
        """This report verified against the world on ``on``."""
        return replace(self, last_verified=on).with_history(on, HistoryKind.VERIFIED, note)

    def updated(
        self,
        on: IsoDate,
        change: str,
        *,
        title: CleanText | None = None,
        summary: CleanText | None = None,
        notes: CleanText | None = None,
        bucket: Bucket | None = None,
        owner: CleanText | None = None,
        clear_owner: bool = False,
        event_horizon: IsoDate | None = None,
        clear_event_horizon: bool = False,
    ) -> IntelligenceReport:
        """This report with the analyst's editable fields changed and an ``updated`` entry.

        Only the fields named here are editable; ``None`` leaves a field as it
        is, and the ``clear_`` flags set the two optional fields to nothing.
        """
        if owner is not None and clear_owner:
            raise ValueError("set the owner or clear it, not both")
        if event_horizon is not None and clear_event_horizon:
            raise ValueError("set the event horizon or clear it, not both")
        changed = replace(
            self,
            title=self.title if title is None else title,
            summary=self.summary if summary is None else summary,
            notes=self.notes if notes is None else notes,
            bucket=self.bucket if bucket is None else bucket,
            owner=None if clear_owner else (self.owner if owner is None else owner),
            event_horizon=None
            if clear_event_horizon
            else (self.event_horizon if event_horizon is None else event_horizon),
        )
        return changed.with_history(on, HistoryKind.UPDATED, change)

    def last_history_on(self) -> IsoDate:
        """The latest date in the history."""
        return max(entry.on for entry in self.history)
