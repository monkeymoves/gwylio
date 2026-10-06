"""CleanText.scrub for external text, and the RunId value object."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from gwylio.shared.values import CleanText, RunId

EN = chr(0x2013)
EM = chr(0x2014)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (f"Corporate plan 2024{EN}25", "Corporate plan 2024 to 25"),
        (f"pages 10 {EN} 12", "pages 10 to 12"),
        (f"Drought declared {EM} rivers at risk", "Drought declared, rivers at risk"),
        (f"Wales {EN} news", "Wales, news"),
        (f"well{EM}being", "well-being"),
        (f"{EM} leading dash", "- leading dash"),
        ("no dashes at all", "no dashes at all"),
        ("  padded  ", "padded"),
    ],
)
def test_scrub_replaces_dashes_in_external_text(raw: str, expected: str) -> None:
    cleaned = CleanText.scrub(raw)
    assert isinstance(cleaned, CleanText)
    assert cleaned == expected


@given(st.text())
def test_scrub_never_fails_and_never_leaves_a_dash(raw: str) -> None:
    cleaned = CleanText.scrub(raw)
    assert EN not in cleaned
    assert EM not in cleaned


def test_scrub_refuses_non_strings() -> None:
    with pytest.raises(TypeError):
        CleanText.scrub(12)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", ["20261006T0215Z-3f9a", "19991231T2359Z-0000"])
def test_run_id_accepts_minute_and_hex(value: str) -> None:
    assert RunId(value) == value
    assert repr(RunId(value)) == f"RunId('{value}')"


@pytest.mark.parametrize(
    "value",
    ["20261006T0215Z-3F9A", "20261006T0215-3f9a", "20261006t0215z-3f9a", "20261006T0215Z", ""],
)
def test_run_id_refuses_anything_else(value: str) -> None:
    with pytest.raises(ValueError, match="not a run id"):
        RunId(value)


def test_run_ids_sort_by_start_time() -> None:
    assert sorted([RunId("20261106T0000Z-0000"), RunId("20261006T2359Z-ffff")]) == [
        "20261006T2359Z-ffff",
        "20261106T0000Z-0000",
    ]
