"""The strategic renderer over hand-built inputs."""

from __future__ import annotations

from gwylio.dissemination.model import Level, Period, Product, to_markdown
from gwylio.dissemination.render_strategic import render_strategic
from gwylio.shared.values import IsoDate
from tests.unit.dissemination.builders import inputs, shipped_copy

PERIOD = Period.year(2026)
TODAY = IsoDate("2026-10-06")


def render() -> Product:
    return render_strategic(inputs(), PERIOD, TODAY, shipped_copy())


def section(product: Product, heading: str) -> list[str]:
    for s in product.sections:
        if s.heading == heading:
            return [*s.body, *s.bullets]
    raise AssertionError(f"no section {heading!r}")


def test_the_standing_picture_per_requirement() -> None:
    product = render()
    assert product.level is Level.STRATEGIC and product.id == "strategic-2026"
    si1 = section(product, "SI1 Resilient ecosystems in full")
    assert si1[0] == "Coverage status: covered, from 4 active reports."
    assert si1[1] == ("By direction: threatens 1, two-way 1, informs the baseline 1, supports 1.")
    assert si1[2] == "By state: emerging 4."
    assert si1[3] == "Grading spread: B2 3, C3 1."
    assert si1[4] == "Scanability: high. Drivers are external."
    top = si1[-3:]
    assert top[0].startswith(
        "B2 Title of a-support [SI1 supports] (emerging, potential impact high)"
    )
    assert top[1].startswith("C3 Title of b-threat"), "threats first among equals"
    si4 = section(product, "SI4 Pollution in full")
    assert "Matured reports kept as settled context, not counted above: 1." in si4


def test_a_blind_spot_requirement_carries_the_standing_sentence() -> None:
    si12 = section(render(), "SI12 Engagement in full")
    assert si12[0] == "Coverage status: blind spot, from 0 active reports."
    assert any(line.startswith("A blind spot is not quiet.") for line in si12)


def test_questions_are_phrased_from_the_copy_template() -> None:
    product = render()
    nature = section(product, "Nature is Recovering (SI1)")
    assert nature == [
        "What would change for SI1 if this holds: Title of b-threat?",
        "What would change for SI1 if this holds: Title of d-twoway?",
    ]
    pollution = section(product, "Pollution is Minimised (SI4)")
    assert pollution == ["What would change for SI4 if this holds: Title of e-old?"]


def test_an_objective_with_nothing_threatening_says_so() -> None:
    copy = shipped_copy()
    calm = inputs(reports=[r for r in inputs().reports if r.id in {"a-support", "f-quiet"}])
    product = render_strategic(calm, PERIOD, TODAY, copy)
    assert section(product, "Nature is Recovering (SI1)") == [copy.strategic.questions_none]


def test_coverage_tables_are_present() -> None:
    text = to_markdown(render())
    assert "### Requirements by lane\n" in text
    assert "| Requirement | Welsh Government | Independent media | Total | Status |" in text
    assert "| SI12 Engagement | 0 | 0 | 0 | blind spot |" in text
    assert "### Taxonomy: SoNaRR ecosystems\n" in text
    assert "| Urban | 0 | 0 | blind spot |" in text
    assert "Unattributed" not in text


def test_the_question_template_swap_changes_every_question() -> None:
    copy = shipped_copy()
    swapped = copy.model_copy(
        update={
            "strategic": copy.strategic.model_copy(
                update={"question": "Suppose {title} holds: what moves for {codes}?"}
            )
        }
    )
    product = render_strategic(inputs(), PERIOD, TODAY, swapped)
    assert section(product, "Nature is Recovering (SI1)")[0] == (
        "Suppose Title of b-threat holds: what moves for SI1?"
    )
