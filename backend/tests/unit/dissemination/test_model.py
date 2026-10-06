"""Products, periods, tables and the Markdown they render to."""

from __future__ import annotations

from datetime import date

import pytest

from gwylio.dissemination.model import (
    TACTICAL_MESSAGE,
    Level,
    NotImplementedInV1,
    Period,
    Product,
    ProductLevel,
    Section,
    Table,
    product_id,
    product_stem,
    to_markdown,
)
from gwylio.dissemination.render_tactical import render_tactical
from gwylio.shared.values import CleanText, IsoDate, KebabId

TODAY = date(2026, 10, 6)


def test_periods_default_to_the_month_or_year_holding_today() -> None:
    month = Period.for_level(Level.OPERATIONAL, None, TODAY)
    assert (str(month.start), str(month.end), month.label) == (
        "2026-10-01",
        "2026-10-31",
        "2026-10",
    )
    assert month.is_month
    year = Period.for_level(Level.STRATEGIC, None, TODAY)
    assert (str(year.start), str(year.end), year.label) == ("2026-01-01", "2026-12-31", "2026")
    assert not year.is_month


def test_periods_parse_their_own_shape_only() -> None:
    assert str(Period.for_level(Level.OPERATIONAL, "2028-02", TODAY).end) == "2028-02-29"
    assert Period.for_level(Level.STRATEGIC, "2025", TODAY).label == "2025"
    with pytest.raises(ValueError, match="YYYY-MM"):
        Period.for_level(Level.OPERATIONAL, "2026", TODAY)
    with pytest.raises(ValueError, match="a year"):
        Period.for_level(Level.STRATEGIC, "2026-10", TODAY)
    with pytest.raises(ValueError, match="no month"):
        Period.for_level(Level.OPERATIONAL, "2026-13", TODAY)


def test_period_contains_both_ends() -> None:
    month = Period.month(2026, 10)
    assert month.contains(IsoDate("2026-10-01")) and month.contains(IsoDate("2026-10-31"))
    assert not month.contains(IsoDate("2026-11-01"))


def test_product_ids_and_stems() -> None:
    month = Period.month(2026, 10)
    assert product_id(Level.OPERATIONAL, month, "nrw", True) == "operational-2026-10"
    assert product_id(Level.STRATEGIC, Period.year(2026), "other", False) == "strategic-2026-other"
    assert product_stem(Level.OPERATIONAL, month, "nrw", True) == "operational_2026-10"
    assert product_stem(Level.OPERATIONAL, month, "other", False) == "operational_2026-10_other"
    assert Level is ProductLevel


def test_tables_must_be_rectangular_and_sections_have_headings() -> None:
    with pytest.raises(ValueError, match="row 0 has 1 cells"):
        Table((CleanText("a"), CleanText("b")), ((CleanText("1"),),))
    with pytest.raises(ValueError, match="heading"):
        Section(CleanText(" "))
    with pytest.raises(ValueError, match="depth"):
        Section(CleanText("x"), depth=4)


def product(**changes: object) -> Product:
    base: dict[str, object] = {
        "id": KebabId("operational-2026-10"),
        "level": Level.OPERATIONAL,
        "requirement_set_id": KebabId("nrw"),
        "period": Period.month(2026, 10),
        "generated_on": IsoDate("2026-10-06"),
        "title": CleanText("Title"),
        "lead": (CleanText("Lead one."),),
        "sections": (
            Section(
                CleanText("First"),
                body=(CleanText("Para."),),
                bullets=(CleanText("one"), CleanText("two  spaced")),
                tables=(
                    Table((CleanText("A"), CleanText("B")), ((CleanText("x|y"), CleanText("2")),)),
                ),
            ),
            Section(CleanText("Sub"), depth=3),
        ),
        "report_ids": (KebabId("a"), KebabId("b")),
        "method_note": CleanText("Note."),
    }
    base.update(changes)
    return Product(**base)  # type: ignore[arg-type]


def test_markdown_is_deterministic_with_pipes_escaped() -> None:
    text = to_markdown(product())
    assert text == (
        "# Title\n\nLead one.\n\n## First\n\nPara.\n\n| A | B |\n|---|---|\n| x\\|y | 2 |\n\n"
        "- one\n- two spaced\n\n### Sub\n"
    )
    assert to_markdown(product()) == text


def test_a_product_lists_each_report_once_in_order() -> None:
    with pytest.raises(ValueError, match="twice"):
        product(report_ids=(KebabId("a"), KebabId("a")))
    with pytest.raises(ValueError, match="in order"):
        product(report_ids=(KebabId("b"), KebabId("a")))


def test_tactical_raises_not_implemented_in_v1() -> None:
    with pytest.raises(NotImplementedInV1) as caught:
        render_tactical()
    assert caught.value.message == TACTICAL_MESSAGE
    assert TACTICAL_MESSAGE == "tactical alerts are a designed seam, not built in v1"
