"""The INTSUM renderer over hand-built inputs."""

from __future__ import annotations

from gwylio.dissemination.inputs import FindingView
from gwylio.dissemination.model import Level, Period, Product, to_markdown
from gwylio.dissemination.render_intsum import render_intsum
from gwylio.shared.values import IsoDate
from tests.unit.dissemination.builders import inputs, shipped_copy

PERIOD = Period.month(2026, 10)
TODAY = IsoDate("2026-10-06")
DASHES = (chr(0x2013), chr(0x2014))


def render(**kwargs: object) -> Product:
    return render_intsum(inputs(**kwargs), PERIOD, TODAY, shipped_copy())  # type: ignore[arg-type]


def section(product: Product, heading: str) -> list[str]:
    for s in product.sections:
        if s.heading == heading:
            return [*s.body, *s.bullets]
    raise AssertionError(f"no section {heading!r}")


def test_summary_counts_the_period() -> None:
    product = render()
    assert product.level is Level.OPERATIONAL
    assert product.id == "operational-2026-10"
    summary = section(product, "Summary")
    assert summary[0] == "New reports created in the period: 5."
    assert summary[3] == "Reports verified against their source in the period: 1."
    assert summary[4] == (
        "Across the reports that moved, 3 assessments threaten a requirement, 1 cut both ways, "
        "1 inform the baseline and 2 support."
    )
    table = next(s for s in product.sections if s.heading == "Summary").tables[0]
    assert [str(c) for c in table.headers] == ["Measure", "Count"]
    assert ("New reports", "5") in [tuple(map(str, row)) for row in table.rows]


def test_threats_and_two_way_signals_come_before_supports_within_each_list() -> None:
    nature = section(render(), "Nature is Recovering (SI1)")
    order = [line.split(" [")[0].split(" ", 1)[1] for line in nature]
    assert order == [
        "Title of b-threat",
        "Title of d-twoway",
        "Title of c-baseline",
        "Title of a-support",
    ]
    assert nature[0] == "C3 Title of b-threat [SI1 threatens] (emerging)"
    pollution = section(render(), "Pollution is Minimised (SI4)")
    assert pollution[0].startswith("B2 Title of e-old [SI4 threatens]")
    assert pollution[-1].startswith("B2 Title of c-baseline [SI4 supports]")


def test_reports_outside_every_objective_get_their_own_list() -> None:
    outside = section(render(), "Outside the well-being objectives")
    assert outside == ["B2 Title of g-outside [SI9 threatens] (emerging)"]


def test_quiet_and_blind_spots_say_a_blind_spot_is_not_quiet() -> None:
    lines = section(render(), "Quiet and blind spots")
    assert lines[0].startswith("A blind spot is not quiet.")
    assert lines[2:] == [
        "SI12 Engagement: blind spot this period. Active reports in the register: 0. "
        "Scanability: none."
    ]


def test_verification_due_lists_findings_by_kind() -> None:
    findings = [
        FindingView("b-threat", "never_verified", "never verified against its source"),
        FindingView("a-support", "passed_horizon", "event horizon 2026-09-30 passed"),
    ]
    product = render(findings=findings)
    headings = [str(s.heading) for s in product.sections]
    assert headings.index("Passed event horizons") < headings.index("Never verified")
    assert section(product, "Never verified")[1] == (
        "Title of b-threat (b-threat): never verified against its source."
    )
    assert "b-threat" in product.report_ids


def test_nothing_to_verify_says_so() -> None:
    assert section(render(), "Verification due") == [
        "The date check found nothing to look at again."
    ]


def test_method_note_with_and_without_runs() -> None:
    note = section(render(), "Method note")
    assert note[0].startswith("Scan runs started in the period: 1.")
    assert "promoted 4, rejected 1" in note[1]
    assert "of which 1 (20 per cent) came from lanes outside government" in note[2]
    assert any("SI12 Engagement" in line for line in note)
    quiet = render(runs=False)
    assert section(quiet, "Method note")[0].startswith("No scan run started in the period")
    assert "2026.10.0" in quiet.method_note
    method = next(s for s in quiet.sections if s.heading == "Method note")
    assert [str(t.headers[0]) for t in method.tables] == ["Credibility"]


def test_copy_swap_changes_the_output() -> None:
    copy = shipped_copy()
    swapped = copy.model_copy(
        update={"intsum": copy.intsum.model_copy(update={"summary_heading": "At a glance"})}
    )
    before = to_markdown(render_intsum(inputs(), PERIOD, TODAY, copy))
    after = to_markdown(render_intsum(inputs(), PERIOD, TODAY, swapped))
    assert "## Summary\n" in before and "## At a glance\n" in after
    assert before.replace("## Summary\n", "## At a glance\n") == after


def test_no_dashes_and_deterministic_with_the_same_clock() -> None:
    first = to_markdown(render())
    second = to_markdown(render())
    assert first == second
    assert not any(dash in first for dash in DASHES)
    assert first.startswith("# Operational intelligence summary (INTSUM), October 2026\n")


def test_cited_reports_are_the_ones_that_moved() -> None:
    product = render()
    assert product.report_ids == (
        "a-support",
        "b-threat",
        "c-baseline",
        "d-twoway",
        "e-old",
        "g-outside",
    )
