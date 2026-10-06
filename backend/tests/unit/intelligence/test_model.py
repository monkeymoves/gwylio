"""Intelligence reports, grading and the shared closed values they use."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from gwylio.intelligence import model
from gwylio.intelligence.model import (
    Assessment,
    Grading,
    HistoryEntry,
    HistoryKind,
)
from gwylio.shared.errors import DomainError
from gwylio.shared.values import CanonicalUrl, CleanText, IsoDate, KebabId
from gwylio.shared.vocabulary import (
    Bucket,
    Credibility,
    Direction,
    DispositionOutcome,
    IndicatorState,
    Reliability,
)
from tests.unit.intelligence.fakes import report

ON = IsoDate("2026-10-02")


def test_grading_renders_and_parses_letter_and_digit() -> None:
    grading = Grading(Reliability.B, Credibility.PROBABLY_TRUE)
    assert str(grading) == "B2"
    assert Grading.parse("C3") == Grading(Reliability.C, Credibility.POSSIBLY_TRUE)
    for bad in ("G1", "A7", "b2", "A", "A10"):
        with pytest.raises(ValueError, match="not a grading"):
            Grading.parse(bad)


def test_credibility_digits_and_labels() -> None:
    assert [int(c) for c in Credibility] == [1, 2, 3, 4, 5, 6]
    assert [c.label for c in Credibility] == [
        "confirmed",
        "probably true",
        "possibly true",
        "doubtful",
        "improbable",
        "cannot be judged",
    ]


def test_states_split_into_active_and_live() -> None:
    assert {s for s in IndicatorState if s.active} == {
        IndicatorState.EMERGING,
        IndicatorState.TRACKING,
        IndicatorState.REINFORCED,
    }
    assert {s for s in IndicatorState if not s.live} == {
        IndicatorState.FADED,
        IndicatorState.PARKED,
    }
    assert all(s.meaning.endswith(".") for s in IndicatorState)
    assert all(d.meaning for d in Direction)
    assert all(o.meaning for o in DispositionOutcome)


def test_the_model_re_exports_the_shared_values() -> None:
    assert model.Reliability is Reliability
    assert model.IndicatorState is IndicatorState
    assert model.Bucket is Bucket


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"assessments": ()}, "at least one assessment"),
        ({"history": ()}, "at least one history entry"),
        ({"title": CleanText(" ")}, "needs a title"),
        ({"source_name": CleanText("")}, "needs a source name"),
        ({"canonical_url": CanonicalUrl("example.org/other")}, "does not canonicalise"),
        ({"topics": (KebabId("peatland"), KebabId("peatland"))}, "repeats peatland in topics"),
        (
            {
                "assessments": (
                    Assessment(KebabId("si1"), Direction.THREATENS),
                    Assessment(KebabId("si1"), Direction.SUPPORTS),
                )
            },
            "repeats si1 in assessments",
        ),
        ({"owner": CleanText(" ")}, "empty owner"),
    ],
)
def test_report_invariants_name_the_report(change: dict[str, Any], message: str) -> None:
    with pytest.raises(DomainError, match=message) as raised:
        replace(report(), **change)
    assert "drought-2026" in str(raised.value)


def test_history_entries_need_text_and_refuse_dashes() -> None:
    with pytest.raises(ValueError, match="needs a change text"):
        HistoryEntry(ON, HistoryKind.UPDATED, CleanText(" "))
    with pytest.raises(ValueError, match="EN DASH"):
        report().with_history(ON, HistoryKind.UPDATED, "a " + chr(0x2013) + " b")


def test_updates_change_only_named_fields_and_append_history() -> None:
    before = report(event_horizon="2026-12-01")
    after = before.updated(
        ON,
        "moved to brief",
        bucket=Bucket.BRIEF,
        owner=CleanText("Luke"),
        clear_event_horizon=True,
    )
    assert (after.bucket, after.owner, after.event_horizon) == (Bucket.BRIEF, "Luke", None)
    assert (after.title, after.summary, after.state) == (before.title, before.summary, before.state)
    assert after.history[-1] == HistoryEntry(ON, HistoryKind.UPDATED, CleanText("moved to brief"))
    assert after.history[:-1] == before.history
    with pytest.raises(ValueError, match="not both"):
        before.updated(ON, "x", owner=CleanText("A"), clear_owner=True)


def test_a_sighting_is_linked_once() -> None:
    linked = report().with_sighting(KebabId("s-1"))
    with pytest.raises(DomainError, match="already has sighting 's-1'"):
        linked.with_sighting(KebabId("s-1"))


def test_match_key_ignores_the_case_of_percent_escapes() -> None:
    lower = CanonicalUrl("https://gov.wales/plan-2026%e2%80%9327")
    upper = CanonicalUrl("https://www.gov.wales/plan-2026%E2%80%9327/")
    assert lower != upper
    assert lower.match_key == upper.match_key == "gov.wales/plan-2026%E2%80%9327"
