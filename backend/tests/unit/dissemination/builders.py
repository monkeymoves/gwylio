"""Hand-built inputs for the renderers: a small requirement set and a few reports."""

from __future__ import annotations

from collections.abc import Sequence

from gwylio.dissemination.copy import Copy, parse_copy
from gwylio.dissemination.inputs import (
    AssessmentView,
    FindingView,
    GroupView,
    HistoryView,
    LaneMatrixView,
    LaneRowView,
    MethodFacts,
    NodeCountsView,
    NodeRowView,
    ProductInputs,
    ReportView,
    RequirementSetView,
    RequirementView,
    RunView,
)
from gwylio.shared.coverage import CoverageStatus, Scanability
from gwylio.shared.values import IsoDate
from gwylio.shared.vocabulary import (
    Credibility,
    Direction,
    DispositionOutcome,
    IndicatorState,
)
from gwylio.shared.vocabulary import Level as ScoreLevel
from tests.support import PROJECT_ROOT


def shipped_copy() -> Copy:
    return parse_copy((PROJECT_ROOT / "config" / "copy.json").read_text(encoding="utf-8"))


SET = RequirementSetView(
    id="test-set",
    name="Test framework",
    version="1",
    requirements=(
        RequirementView(
            "si1",
            "SI1",
            "Resilient ecosystems in full",
            "Resilient ecosystems",
            Scanability.HIGH,
            "Drivers are external.",
        ),
        RequirementView(
            "si4", "SI4", "Pollution in full", "Pollution", Scanability.HIGH, "Published monthly."
        ),
        RequirementView(
            "si9",
            "SI9",
            "Partnerships in full",
            "Partnerships",
            Scanability.LOW,
            "Evidence is internal.",
        ),
        RequirementView(
            "si12",
            "SI12",
            "Engagement in full",
            "Engagement",
            Scanability.NONE,
            "Staff survey only.",
        ),
    ),
    groups=(
        GroupView("nature", "wbo", "Nature is Recovering", ("si1",)),
        GroupView("pollution", "wbo", "Pollution is Minimised", ("si4",)),
        GroupView("i1", "impact", "Impact one", ("si1", "si4")),
    ),
)


def view(
    report_id: str,
    assessments: Sequence[tuple[str, Direction]],
    *,
    title: str | None = None,
    state: IndicatorState = IndicatorState.EMERGING,
    created_on: str = "2026-10-02",
    history: Sequence[tuple[str, str]] = (),
    impact: ScoreLevel = ScoreLevel.MEDIUM,
    grading: str = "B2",
    lens: str = "government",
) -> ReportView:
    return ReportView(
        id=report_id,
        title=title or f"Title of {report_id}",
        grading=grading,
        credibility=Credibility(int(grading[1])),
        state=state,
        lens=lens,
        assessments=tuple(AssessmentView(r, d) for r, d in assessments),
        potential_impact=impact,
        created_on=IsoDate(created_on),
        history=(
            HistoryView(IsoDate(created_on), "created"),
            *(HistoryView(IsoDate(on), kind) for on, kind in history),
        ),
    )


T, N, B, S = Direction.THREATENS, Direction.NEUTRAL, Direction.INFORMS_BASELINE, Direction.SUPPORTS

REPORTS = (
    view("a-support", [("si1", S)], impact=ScoreLevel.HIGH),
    view("b-threat", [("si1", T)], grading="C3"),
    view("c-baseline", [("si1", B), ("si4", S)]),
    view("d-twoway", [("si1", N)], impact=ScoreLevel.LOW),
    view("e-old", [("si4", T)], created_on="2026-08-01", history=[("2026-10-03", "verified")]),
    view("f-quiet", [("si4", S)], created_on="2026-08-01", state=IndicatorState.MATURED),
    view("g-outside", [("si9", T)], created_on="2026-10-05"),
)

LANE_MATRIX = LaneMatrixView(
    columns=("Welsh Government", "Independent media"),
    rows=(
        LaneRowView("SI1 Resilient ecosystems", (3, 1, 0), 4, CoverageStatus.COVERED),
        LaneRowView("SI4 Pollution", (1, 0, 0), 1, CoverageStatus.THIN),
        LaneRowView("SI9 Partnerships", (1, 0, 0), 1, CoverageStatus.THIN),
        LaneRowView("SI12 Engagement", (0, 0, 0), 0, CoverageStatus.BLIND_SPOT),
    ),
)
NODES = (
    NodeCountsView(
        "SoNaRR ecosystems",
        (
            NodeRowView("Marine", 1, 4, CoverageStatus.COVERED),
            NodeRowView("Urban", 0, 0, CoverageStatus.BLIND_SPOT),
        ),
    ),
)
RUN = RunView("20261001T0900Z-0000", IsoDate("2026-10-01"), "2026.10.0", 30, 17, 5, 2, 148, False)


def method(*, runs: bool = True, promotions: int = 5) -> MethodFacts:
    return MethodFacts(
        runs=(RUN,) if runs else (),
        dispositions=tuple(
            (o, {DispositionOutcome.PROMOTED: 4, DispositionOutcome.REJECTED: 1}.get(o, 0))
            for o in DispositionOutcome
        ),
        undisposed=0,
        promotions=promotions,
        non_government=1 if promotions else 0,
        credibility=tuple(
            (
                c,
                4
                if c is Credibility.PROBABLY_TRUE
                else (1 if c is Credibility.POSSIBLY_TRUE else 0),
            )
            for c in Credibility
        ),
        instrument_versions=("2026.10.0",) if runs else (),
        current_instrument_version="2026.10.0",
        blind_spots=("SI12 Engagement",),
    )


def inputs(
    reports: Sequence[ReportView] = REPORTS,
    findings: Sequence[FindingView] = (),
    *,
    runs: bool = True,
) -> ProductInputs:
    return ProductInputs(
        requirement_set=SET,
        reports=tuple(reports),
        findings=tuple(findings),
        method=method(runs=runs),
        lane_matrix=LANE_MATRIX,
        node_counts=NODES,
        active_counts=(("si1", 4), ("si4", 1), ("si9", 1), ("si12", 0)),
    )
