"""The indications and warnings lifecycle as a transition table.

``transition(report, event, context)`` returns the report after one event, or
raises ``IllegalTransition``. The rules, in the order they are checked:

- ``Sighted`` always links the sighting to the report. Then:
  - on a faded report it revives the report to tracking (``revived`` entry);
  - on a matured or parked report it changes nothing else: matured and parked
    record sightings and ignore them;
  - on an emerging or tracking report whose distinct sources (after this
    sighting) reach three, it reinforces the report;
  - on an emerging report sighted in a run strictly later than the run that
    created it (or, for a report created outside a run, than its first
    sighting's run), it moves the report to tracking;
  - a sighting in a run that already sighted the report is linked and
    changes nothing else, not even the history (index echo), unless it brings
    a source not counted before that takes the distinct sources to three:
    distinct sources are independent evidence whichever run they arrive in.
  A sighting in a new run appends a ``sighted`` entry; a state change appends
  its own entry after it.
- ``MarkMatured`` and ``MarkParked`` are analyst events, legal from an active
  state (emerging, tracking, reinforced) only.
- ``Fade`` is the sweep's event, legal from an active state only.
- ``ConfirmIndependently`` sets the independent confirmation flag; it moves
  an emerging or tracking report to reinforced and is recorded on a
  reinforced one; it is illegal on matured, parked and faded reports.
- ``Verify`` is legal in every state: it sets ``last_verified`` and records
  the note.

Nothing is deleted, and every event that changes a report appends history.
The counts in the context are derived by the service from the sightings
(distinct runs and distinct source ids, never raw sightings).
"""

from __future__ import annotations

from dataclasses import dataclass

from gwylio.intelligence.model import (
    HistoryKind,
    IllegalTransition,
    IndicatorState,
    IntelligenceReport,
)
from gwylio.shared.values import CleanText, IsoDate, KebabId

__all__ = [
    "REINFORCING_SOURCES",
    "ConfirmIndependently",
    "Event",
    "Fade",
    "MarkMatured",
    "MarkParked",
    "Sighted",
    "SightingContext",
    "Verify",
    "transition",
]

REINFORCING_SOURCES = 3
"""Distinct source ids that reinforce a report."""


@dataclass(frozen=True, slots=True)
class Sighted:
    """A sighting from a scan run linked to the report (by promotion or reinforcement)."""

    run_id: str
    source_id: str | None
    on: IsoDate
    sighting_id: KebabId


@dataclass(frozen=True, slots=True)
class MarkMatured:
    """The analyst says the development is settled context."""

    on: IsoDate
    change: CleanText


@dataclass(frozen=True, slots=True)
class MarkParked:
    """The analyst sets the report aside."""

    on: IsoDate
    change: CleanText


@dataclass(frozen=True, slots=True)
class Fade:
    """The sweep found no sighting in the two most recent complete runs."""

    on: IsoDate
    change: CleanText


@dataclass(frozen=True, slots=True)
class ConfirmIndependently:
    """The analyst confirmed the report from an independent source."""

    on: IsoDate
    change: CleanText


@dataclass(frozen=True, slots=True)
class Verify:
    """The analyst checked the report's claims against the world."""

    on: IsoDate
    note: CleanText


Event = Sighted | MarkMatured | MarkParked | Fade | ConfirmIndependently | Verify


@dataclass(frozen=True, slots=True)
class SightingContext:
    """What the sightings say once this sighting is counted.

    ``appearances_after`` counts distinct runs, ``distinct_sources_after``
    distinct non-null source ids. ``is_later_run`` is true when this sighting's
    run started strictly after the report's anchor run; ``is_new_run`` when no
    earlier sighting of the report came from this run.
    """

    appearances_after: int
    distinct_sources_after: int
    is_later_run: bool
    is_new_run: bool


def _illegal(report: IntelligenceReport, event: Event) -> IllegalTransition:
    name = type(event).__name__
    return IllegalTransition(
        f"report '{report.id}' is {report.state.value}; {name} is not allowed from that state",
        scope="report",
        location="state",
    )


def _sighted(
    report: IntelligenceReport, event: Sighted, context: SightingContext | None
) -> IntelligenceReport:
    if context is None:
        raise ValueError("a Sighted event needs a SightingContext")
    linked = report.with_sighting(event.sighting_id)
    source = event.source_id or "an unwatched source"
    if context.is_new_run:
        linked = linked.with_history(
            event.on,
            HistoryKind.SIGHTED,
            f"sighted in run {event.run_id} by {source}; {context.appearances_after} "
            f"run{'s' if context.appearances_after != 1 else ''}, "
            f"{context.distinct_sources_after} distinct source"
            f"{'s' if context.distinct_sources_after != 1 else ''}",
        )
    state = report.state
    if state is IndicatorState.FADED:
        return linked.with_state(
            IndicatorState.TRACKING,
            event.on,
            HistoryKind.REVIVED,
            f"faded to tracking: sighted again in run {event.run_id}",
        )
    if state in (IndicatorState.MATURED, IndicatorState.PARKED):
        return linked
    if state in (IndicatorState.EMERGING, IndicatorState.TRACKING) and (
        context.distinct_sources_after >= REINFORCING_SOURCES
    ):
        return linked.with_state(
            IndicatorState.REINFORCED,
            event.on,
            HistoryKind.STATE_CHANGED,
            f"{state.value} to reinforced: {context.distinct_sources_after} distinct sources",
        )
    if state is IndicatorState.EMERGING and context.is_later_run and context.is_new_run:
        return linked.with_state(
            IndicatorState.TRACKING,
            event.on,
            HistoryKind.STATE_CHANGED,
            f"emerging to tracking: sighted in run {event.run_id}, later than the run that "
            "found it",
        )
    return linked


def transition(
    report: IntelligenceReport, event: Event, context: SightingContext | None = None
) -> IntelligenceReport:
    """The report after ``event``; raises ``IllegalTransition`` when the table forbids it."""
    state = report.state
    if isinstance(event, Sighted):
        return _sighted(report, event, context)
    if isinstance(event, Verify):
        return report.verified(event.on, event.note)
    if isinstance(event, MarkMatured | MarkParked | Fade):
        if not state.active:
            raise _illegal(report, event)
        if isinstance(event, MarkMatured):
            target, kind = IndicatorState.MATURED, HistoryKind.STATE_CHANGED
        elif isinstance(event, MarkParked):
            target, kind = IndicatorState.PARKED, HistoryKind.STATE_CHANGED
        else:
            target, kind = IndicatorState.FADED, HistoryKind.FADED
        return report.with_state(
            target, event.on, kind, f"{state.value} to {target.value}: {event.change}"
        )
    if isinstance(event, ConfirmIndependently):
        if not state.active:
            raise _illegal(report, event)
        flagged = report.with_independent_confirmation()
        if state is IndicatorState.REINFORCED:
            return flagged.with_history(
                event.on,
                HistoryKind.UPDATED,
                f"independent confirmation recorded: {event.change}",
            )
        return flagged.with_state(
            IndicatorState.REINFORCED,
            event.on,
            HistoryKind.STATE_CHANGED,
            f"{state.value} to reinforced: independently confirmed: {event.change}",
        )
    raise TypeError(f"unknown lifecycle event {type(event).__name__}")  # pragma: no cover
