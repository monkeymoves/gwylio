"""The coverage audit: requirements by lane, taxonomy by count, and the credibility spread."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from gwylio.evaluation.coverage import (
    UNATTRIBUTED,
    AxisFacts,
    NodeFacts,
    ReportFacts,
    RequirementFacts,
    RequirementSetFacts,
    cell_status,
    credibility_distribution,
    lane_of,
    lens_counts,
    non_government_share,
    requirement_by_lane,
    taxonomy_by_count,
)
from gwylio.shared.coverage import CoverageStatus, Scanability
from gwylio.shared.vocabulary import Credibility, IndicatorState

COVERED, THIN = CoverageStatus.COVERED, CoverageStatus.THIN
QUIET, BLIND = CoverageStatus.QUIET, CoverageStatus.BLIND_SPOT
LANES = ("welsh-government", "independent-media", "legal-and-campaign")
SOURCES = {"gov": "welsh-government", "news": "independent-media"}
ACTORS = {"river-action": "legal-and-campaign"}


def req(code: str, scanability: Scanability, coverage: tuple[str, ...] = ()) -> RequirementFacts:
    return RequirementFacts(code.lower(), code, f"Short {code}", scanability, coverage)


SET = RequirementSetFacts(
    "test-set",
    (
        req("SI1", Scanability.HIGH, ("marine", "freshwaters")),
        req("SI2", Scanability.MEDIUM, ("freshwaters",)),
        req("SI9", Scanability.LOW),
        req("SI12", Scanability.NONE),
    ),
)
SONARR = AxisFacts(
    "sonarr",
    "SoNaRR",
    (
        NodeFacts("marine", "Marine"),
        NodeFacts("freshwaters", "Freshwaters"),
        NodeFacts("urban", "Urban"),
    ),
)
HAZARDS = AxisFacts("hazards", "Hazard families", (NodeFacts("wildfire", "Wildfire"),))


def report(
    report_id: str,
    requirements: Sequence[str],
    *,
    source: str | None = None,
    actor: str | None = None,
    lane: str | None = "welsh-government",
    lens: str = "government",
    state: IndicatorState = IndicatorState.EMERGING,
    credibility: Credibility = Credibility.PROBABLY_TRUE,
    run: str | None = None,
    families: tuple[str, ...] = (),
) -> ReportFacts:
    return ReportFacts(
        id=report_id,
        state=state,
        requirement_ids=tuple(requirements),
        source_id=source,
        actor_id=actor,
        lane=lane,
        lens=lens,
        credibility=credibility,
        created_run_id=run,
        created_on="2026-10-01",
        hazard_families=families,
    )


def test_a_none_scanability_requirement_with_no_reports_is_a_blind_spot() -> None:
    matrix = requirement_by_lane(SET, [], SOURCES, lanes=LANES)
    assert matrix.row("si12").status is BLIND
    assert matrix.row("si9").status is BLIND
    assert {cell.status for cell in matrix.row("si12").cells} == {BLIND}


def test_a_high_scanability_requirement_with_no_reports_is_quiet() -> None:
    matrix = requirement_by_lane(SET, [], SOURCES, lanes=LANES)
    assert matrix.row("si1").status is QUIET
    assert matrix.row("si2").status is QUIET
    assert {cell.status for cell in matrix.row("si1").cells} == {QUIET}


def test_counts_reconcile_with_a_hand_built_report_set() -> None:
    reports = [
        report("a", ["si1"], source="gov"),
        report(
            "b", ["si1", "si2"], source="news", lane="independent-media", lens="partnership_society"
        ),
        report("c", ["si1"], source=None, actor="river-action", lane="independent-media"),
        report("d", ["si1"], source=None, actor=None, lane="welsh-government"),
        report("e", ["si2"], source=None, actor=None, lane=None),
        report("f", ["si9"], source="gov"),
        report("g", ["si1"], source="gov", state=IndicatorState.MATURED),
        report("h", ["si1"], source="gov", state=IndicatorState.FADED),
        report("i", ["si1"], source="gov", state=IndicatorState.PARKED),
        report("j", ["si1", "other-set-req"], source="gov", state=IndicatorState.TRACKING),
    ]
    matrix = requirement_by_lane(SET, reports, SOURCES, lanes=LANES, actors=ACTORS)
    assert matrix.columns == (*LANES, UNATTRIBUTED)
    si1 = matrix.row("si1")
    counts = {cell.column_id: cell.count for cell in si1.cells}
    # a, d and j by source or own lane; b by its source; c by its actor's lane.
    assert counts == {
        "welsh-government": 3,
        "independent-media": 1,
        "legal-and-campaign": 1,
        UNATTRIBUTED: 0,
    }
    assert si1.total == 5 and si1.status is COVERED
    si2 = matrix.row("si2")
    assert {c.column_id: c.count for c in si2.cells if c.count} == {
        "independent-media": 1,
        UNATTRIBUTED: 1,
    }
    assert si2.total == 2 and si2.status is THIN
    assert matrix.row("si9").total == 1 and matrix.row("si9").status is THIN
    assert matrix.row("si12").status is BLIND
    assert matrix.column_total("welsh-government") == 4
    assert matrix.column_total(UNATTRIBUTED) == 1
    assert matrix.report_ids == ("a", "b", "c", "d", "e", "f", "j")
    assert sum(row.total for row in matrix.rows) == sum(
        matrix.column_total(column) for column in matrix.columns
    )


def test_cell_statuses_follow_the_count_and_the_row() -> None:
    assert cell_status(3, QUIET) is COVERED
    assert cell_status(1, BLIND) is THIN
    assert cell_status(0, QUIET) is QUIET
    assert cell_status(0, COVERED) is QUIET
    assert cell_status(0, BLIND) is BLIND
    reports = [report(f"r{i}", ["si1"], source="gov") for i in range(3)]
    row = requirement_by_lane(SET, reports, SOURCES, lanes=LANES).row("si1")
    assert [cell.status for cell in row.cells] == [COVERED, QUIET, QUIET, QUIET]


def test_lane_of_prefers_source_then_actor_then_own_lane() -> None:
    assert lane_of(report("a", [], source="news", actor="river-action"), SOURCES, ACTORS) == (
        "independent-media"
    )
    assert lane_of(report("a", [], source="unknown", actor="river-action"), SOURCES, ACTORS) == (
        "legal-and-campaign"
    )
    assert lane_of(report("a", [], lane="senedd"), SOURCES, ACTORS) == "senedd"
    assert lane_of(report("a", [], lane=None), SOURCES, ACTORS) == UNATTRIBUTED


def test_a_lane_outside_the_columns_counts_as_unattributed() -> None:
    matrix = requirement_by_lane(SET, [report("a", ["si1"], lane="senedd")], SOURCES, lanes=LANES)
    assert matrix.cell("si1", UNATTRIBUTED).count == 1


def test_a_node_no_requirement_expects_is_a_blind_spot_at_zero() -> None:
    matrix = taxonomy_by_count(SONARR, SET, [])
    assert matrix.row("urban").expected == 0
    assert matrix.row("urban").status is BLIND
    assert matrix.row("marine").expected == 1 and matrix.row("marine").status is QUIET
    assert matrix.row("freshwaters").expected == 2
    hazards = taxonomy_by_count(HAZARDS, SET, [])
    assert hazards.row("wildfire").status is BLIND


def test_taxonomy_counts_reports_by_expected_coverage_and_hazard_family() -> None:
    reports = [
        report("a", ["si1"]),
        report("b", ["si2"]),
        report("c", ["si9"], families=("wildfire",)),
        report("d", ["si2"], state=IndicatorState.FADED),
    ]
    sonarr = taxonomy_by_count(SONARR, SET, reports)
    assert {row.row_id: row.total for row in sonarr.rows} == {
        "marine": 1,
        "freshwaters": 2,
        "urban": 0,
    }
    assert sonarr.row("freshwaters").status is THIN
    assert sonarr.row("urban").status is BLIND
    hazards = taxonomy_by_count(HAZARDS, SET, reports)
    assert hazards.row("wildfire").total == 1
    assert hazards.row("wildfire").status is THIN, "a report makes an unexpected node thin"
    assert sonarr.report_ids == ("a", "b")


def test_credibility_distribution_lists_every_digit_and_filters_by_run() -> None:
    reports = [
        report("a", ["si1"], credibility=Credibility.CONFIRMED, run="r1"),
        report("b", ["si1"], credibility=Credibility.POSSIBLY_TRUE, run="r1"),
        report("c", ["si1"], credibility=Credibility.POSSIBLY_TRUE, run="r2"),
        report("d", ["si1"], credibility=Credibility.POSSIBLY_TRUE, run=None),
    ]
    every = credibility_distribution(reports)
    assert [(int(c.credibility), c.count) for c in every] == [
        (1, 1),
        (2, 0),
        (3, 3),
        (4, 0),
        (5, 0),
        (6, 0),
    ]
    run = credibility_distribution(reports, "r1")
    assert [c.count for c in run] == [1, 0, 1, 0, 0, 0]
    assert sum(c.count for c in credibility_distribution([], "r1")) == 0


def test_non_government_share_and_lens_counts() -> None:
    reports = [
        report("a", ["si1"]),
        report("b", ["si1"], lens="partnership_society"),
        report("c", ["si1"], lens="international"),
    ]
    assert non_government_share(reports) == (2, 3)
    assert non_government_share([]) == (0, 0)
    assert lens_counts(reports) == {"government": 1, "international": 1, "partnership_society": 1}


@pytest.mark.parametrize("scanability", list(Scanability))
def test_a_row_status_never_reads_quiet_when_public_sources_cannot_see(
    scanability: Scanability,
) -> None:
    single = RequirementSetFacts("s", (req("SI1", scanability),))
    status = requirement_by_lane(single, [], {}, lanes=LANES).row("si1").status
    assert status is (QUIET if scanability.sees_movement else BLIND)
