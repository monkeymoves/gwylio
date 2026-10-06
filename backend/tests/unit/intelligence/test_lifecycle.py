"""The lifecycle transition table: every state by every event."""

from __future__ import annotations

import pytest

from gwylio.intelligence.lifecycle import (
    ConfirmIndependently,
    Event,
    Fade,
    MarkMatured,
    MarkParked,
    Sighted,
    SightingContext,
    Verify,
    transition,
)
from gwylio.intelligence.model import HistoryKind, IllegalTransition, IndicatorState
from gwylio.shared.values import CleanText, IsoDate, KebabId
from tests.unit.intelligence.fakes import report, run_id

ON = IsoDate("2026-10-02")
WHY = CleanText("a reason")

E, T, R, M, F, P = (
    IndicatorState.EMERGING,
    IndicatorState.TRACKING,
    IndicatorState.REINFORCED,
    IndicatorState.MATURED,
    IndicatorState.FADED,
    IndicatorState.PARKED,
)
X = IllegalTransition

LATER = SightingContext(
    appearances_after=2, distinct_sources_after=2, is_later_run=True, is_new_run=True
)
ECHO = SightingContext(
    appearances_after=1, distinct_sources_after=1, is_later_run=False, is_new_run=False
)
THIRD = SightingContext(
    appearances_after=2, distinct_sources_after=3, is_later_run=True, is_new_run=True
)

EVENTS: dict[str, tuple[Event, SightingContext | None]] = {
    "sighted_later_run": (Sighted(run_id(2), "bbc-wales", ON, KebabId("s-new")), LATER),
    "sighted_same_run_echo": (Sighted(run_id(1), "nation-cymru", ON, KebabId("s-new")), ECHO),
    "sighted_third_source": (Sighted(run_id(2), "bto", ON, KebabId("s-new")), THIRD),
    "mark_matured": (MarkMatured(ON, WHY), None),
    "mark_parked": (MarkParked(ON, WHY), None),
    "fade": (Fade(ON, WHY), None),
    "confirm_independently": (ConfirmIndependently(ON, WHY), None),
    "verify": (Verify(ON, WHY), None),
}

# state: (later, echo, third, matured, parked, fade, confirm, verify)
TABLE: dict[IndicatorState, tuple[IndicatorState | type[IllegalTransition], ...]] = {
    E: (T, E, R, M, P, F, R, E),
    T: (T, T, R, M, P, F, R, T),
    R: (R, R, R, M, P, F, R, R),
    M: (M, M, M, X, X, X, X, M),
    F: (T, T, T, X, X, X, X, F),
    P: (P, P, P, X, X, X, X, P),
}

CASES = [
    (state, name, expected)
    for state, row in TABLE.items()
    for name, expected in zip(EVENTS, row, strict=True)
]


def test_the_table_covers_every_state_and_every_event() -> None:
    assert set(TABLE) == set(IndicatorState)
    assert len(CASES) == len(IndicatorState) * len(EVENTS) == 48


@pytest.mark.parametrize(
    ("state", "event_name", "expected"), CASES, ids=[f"{s.value}-{n}" for s, n, _ in CASES]
)
def test_every_state_by_every_event(
    state: IndicatorState, event_name: str, expected: IndicatorState | type[IllegalTransition]
) -> None:
    before = report(state=state, sightings=("s-first",))
    event, context = EVENTS[event_name]
    if expected is IllegalTransition:
        with pytest.raises(IllegalTransition, match=f"is {state.value}"):
            transition(before, event, context)
        return
    after = transition(before, event, context)
    assert after.state is expected
    if isinstance(event, Sighted):
        assert after.sighting_ids == (*before.sighting_ids, event.sighting_id)
    if event_name != "sighted_same_run_echo":
        assert len(after.history) > len(before.history), "every change appends history"
    assert after.history[: len(before.history)] == before.history, "history is append-only"


def test_a_second_sighting_in_the_same_run_changes_nothing_but_is_recorded() -> None:
    before = report(state=E, sightings=("s-first",))
    event, context = EVENTS["sighted_same_run_echo"]
    after = transition(before, event, context)
    assert after.state is E
    assert after.history == before.history
    assert after.sighting_ids == ("s-first", "s-new")


def test_three_distinct_sources_reinforce_but_three_sightings_from_one_do_not() -> None:
    one_source = report(state=E, sightings=())
    for index in range(3):
        context = SightingContext(
            appearances_after=1,
            distinct_sources_after=1,
            is_later_run=False,
            is_new_run=index == 0,
        )
        one_source = transition(
            one_source,
            Sighted(run_id(1), "nation-cymru", ON, KebabId(f"s-{index}")),
            context,
        )
    assert one_source.state is E
    three_sources = report(state=E, sightings=())
    for index, source in enumerate(("nation-cymru", "bbc-wales", "bto")):
        context = SightingContext(
            appearances_after=1,
            distinct_sources_after=index + 1,
            is_later_run=False,
            is_new_run=index == 0,
        )
        three_sources = transition(
            three_sources, Sighted(run_id(1), source, ON, KebabId(f"s-{index}")), context
        )
    assert three_sources.state is R
    assert three_sources.history[-1].change == "emerging to reinforced: 3 distinct sources"


def test_a_faded_report_revives_to_tracking_with_a_revived_entry() -> None:
    faded = report(state=F, sightings=("s-first",))
    event, context = EVENTS["sighted_later_run"]
    revived = transition(faded, event, context)
    assert revived.state is T
    assert [h.kind for h in revived.history[-2:]] == [HistoryKind.SIGHTED, HistoryKind.REVIVED]
    assert revived.history[-1].change == f"faded to tracking: sighted again in run {run_id(2)}"


def test_tracking_needs_a_strictly_later_run() -> None:
    first = SightingContext(
        appearances_after=1, distinct_sources_after=1, is_later_run=False, is_new_run=True
    )
    still = transition(report(state=E), Sighted(run_id(1), None, ON, KebabId("s-1")), first)
    assert still.state is E
    assert still.history[-1].kind is HistoryKind.SIGHTED
    assert "an unwatched source" in still.history[-1].change


def test_analyst_events_record_their_reason_and_verify_sets_the_date() -> None:
    matured = transition(report(state=T), MarkMatured(ON, CleanText("settled context")))
    assert matured.history[-1].change == "tracking to matured: settled context"
    assert matured.history[-1].kind is HistoryKind.STATE_CHANGED
    faded = transition(report(state=R), Fade(ON, CleanText("quiet")))
    assert faded.history[-1].kind is HistoryKind.FADED
    verified = transition(report(state=P, last_verified=None), Verify(ON, CleanText("checked")))
    assert verified.last_verified == ON
    assert verified.history[-1].kind is HistoryKind.VERIFIED


def test_independent_confirmation_sets_the_flag_and_is_recorded_on_a_reinforced_report() -> None:
    confirmed = transition(report(state=E), ConfirmIndependently(ON, WHY))
    assert confirmed.independent_confirmation
    assert confirmed.state is R
    again = transition(confirmed, ConfirmIndependently(ON, WHY))
    assert again.state is R
    assert again.history[-1].kind is HistoryKind.UPDATED


def test_a_sighting_needs_its_context() -> None:
    with pytest.raises(ValueError, match="needs a SightingContext"):
        transition(report(), Sighted(run_id(2), None, ON, KebabId("s-x")))
