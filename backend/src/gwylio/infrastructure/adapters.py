"""Adapt the stored register and the configuration into Evaluation and Dissemination inputs.

The Evaluation and Dissemination contexts import only ``gwylio.shared`` and
themselves, so this module is where their plain inputs are built: it reads
the repositories and the loaded configuration, resolves what the register
stores only by id (a requirement's set and scanability, a hazard's family, a
lane's lens), and hands the facts in. The arithmetic stays in Evaluation; the
words stay in Dissemination's copy. The audit, the yield table and both
products read the same facts from here, so their numbers reconcile.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from gwylio.direction.model import GroupKind, RequirementSet
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
from gwylio.dissemination.model import Level, Period, Product, product_stem
from gwylio.dissemination.render_intsum import render_intsum
from gwylio.dissemination.render_strategic import render_strategic
from gwylio.dissemination.render_tactical import render_tactical
from gwylio.evaluation.coverage import (
    AxisFacts,
    CoverageMatrix,
    CredibilityCount,
    NodeFacts,
    ReportFacts,
    RequirementFacts,
    RequirementSetFacts,
    credibility_distribution,
    non_government_share,
    requirement_by_lane,
    taxonomy_by_count,
)
from gwylio.evaluation.datecheck import DateCheckSummary, summarise_findings
from gwylio.evaluation.funnel import FunnelCounts, FunnelTrend, RunFunnel
from gwylio.evaluation.yield_ import (
    CandidateFacts,
    SightingFacts,
    SourceFacts,
    SourceYield,
    compute_yield,
)
from gwylio.infrastructure.config.loaders import LoadedConfig
from gwylio.infrastructure.sqlite.db import Database
from gwylio.infrastructure.sqlite.repositories import (
    SqliteCandidateRepository,
    SqliteReportRepository,
    SqliteScanRunRepository,
    SqliteSightingLookup,
    SqliteSubmissionRepository,
)
from gwylio.intelligence.datecheck import DateCheckFinding, FindingKind, date_check
from gwylio.intelligence.model import IntelligenceReport
from gwylio.shared.coverage import CoverageStatus
from gwylio.shared.values import IsoDate
from gwylio.shared.vocabulary import DispositionOutcome

__all__ = [
    "CoverageAudit",
    "audit",
    "date_findings",
    "datecheck_summary",
    "funnel_trend",
    "product_inputs",
    "render_product",
    "report_facts",
    "requirement_set_facts",
    "run_dispositions",
    "source_yield",
]


# Evaluation inputs.


def requirement_set_facts(requirement_set: RequirementSet) -> RequirementSetFacts:
    """A requirement set as the coverage audit reads it."""
    return RequirementSetFacts(
        id=str(requirement_set.id),
        requirements=tuple(
            RequirementFacts(
                id=str(r.id),
                code=r.code,
                short=str(r.short),
                scanability=r.scanability,
                expected_coverage=tuple(str(node) for node in r.expected_coverage),
            )
            for r in requirement_set.requirements
        ),
    )


def report_facts(
    reports: Sequence[IntelligenceReport], config: LoadedConfig
) -> tuple[ReportFacts, ...]:
    """The reports as the coverage audit reads them: lens and hazard families resolved."""
    catalogue = config.catalogue
    return tuple(
        ReportFacts(
            id=str(report.id),
            state=report.state,
            requirement_ids=tuple(str(r) for r in report.requirement_ids),
            source_id=report.source_id,
            actor_id=report.actor_id,
            lane=str(report.lane),
            lens=catalogue.lane(report.lane).lens.value,
            credibility=report.grading.credibility,
            created_run_id=report.created_run_id,
            created_on=str(report.created_on),
            hazard_families=tuple(
                sorted({str(catalogue.hazard(h).family) for h in report.hazards})
            ),
        )
        for report in reports
    )


@dataclass(frozen=True, slots=True)
class CoverageAudit:
    """Both coverage matrices for one requirement set, and the credibility spread."""

    requirement_set: RequirementSet
    lanes: CoverageMatrix
    taxonomy: tuple[tuple[AxisFacts, CoverageMatrix], ...]
    credibility: tuple[CredibilityCount, ...]


def _assessed_on(
    reports: Sequence[IntelligenceReport], requirement_set: RequirementSet
) -> list[IntelligenceReport]:
    ids = requirement_set.requirement_ids()
    return [r for r in reports if any(a.requirement_id in ids for a in r.assessments)]


def _audit(
    config: LoadedConfig, requirement_set: RequirementSet, reports: Sequence[IntelligenceReport]
) -> CoverageAudit:
    catalogue = config.catalogue
    facts = report_facts(reports, config)
    set_facts = requirement_set_facts(requirement_set)
    lanes = requirement_by_lane(
        set_facts,
        facts,
        {str(s.id): str(s.lane) for s in config.sources},
        lanes=[str(lane.id) for lane in catalogue.lanes],
        actors={str(a.id): str(a.lane) for a in catalogue.actors},
    )
    axes = tuple(
        AxisFacts(
            str(axis.id),
            str(axis.name),
            tuple(NodeFacts(str(n.id), str(n.name)) for n in axis.nodes),
        )
        for axis in catalogue.taxonomy.axes
    )
    in_set = report_facts(_assessed_on(reports, requirement_set), config)
    return CoverageAudit(
        requirement_set=requirement_set,
        lanes=lanes,
        taxonomy=tuple((axis, taxonomy_by_count(axis, set_facts, facts)) for axis in axes),
        credibility=credibility_distribution(r for r in in_set if r.state.active),
    )


def audit(db: Database, config: LoadedConfig, set_id: str) -> CoverageAudit:
    """The coverage audit of one requirement set over the stored register."""
    return _audit(config, config.requirement_set(set_id), SqliteReportRepository(db).list())


def funnel_trend(db: Database) -> FunnelTrend:
    """Every stored run's funnel, oldest first."""
    return FunnelTrend(
        RunFunnel(
            run_id=str(run.id),
            started_at=run.started_at,
            funnel=FunnelCounts(
                raw=run.funnel.raw,
                dropped_own=run.funnel.dropped_own,
                dropped_negative=run.funnel.dropped_negative,
                dropped_unrelated=run.funnel.dropped_unrelated,
                passed=run.funnel.passed,
                unique=run.funnel.unique,
                seen_before=run.funnel.seen_before,
                new=run.funnel.new,
                reinforcements=run.funnel.reinforcements,
            ),
            requests_made=run.requests_made,
            budget_exhausted=run.budget_exhausted,
        )
        for run in SqliteScanRunRepository(db).all()
    )


def run_dispositions(db: Database) -> dict[str, list[DispositionOutcome]]:
    """Each run's candidates' latest outcomes (deferred only when nothing later), by run id."""
    outcomes = SqliteSubmissionRepository(db).latest_outcomes()
    by_run: dict[str, list[DispositionOutcome]] = {}
    for candidate in SqliteCandidateRepository(db).all_candidates():
        outcome = outcomes.get(str(candidate.id))
        if outcome is not None:
            by_run.setdefault(str(candidate.run_id), []).append(outcome)
    return by_run


def source_yield(db: Database, config: LoadedConfig) -> tuple[SourceYield, ...]:
    """The yield of every watched source, in watchlist order."""
    outcomes = SqliteSubmissionRepository(db).latest_outcomes()
    return compute_yield(
        sources=(SourceFacts(str(s.id), str(s.name), s.active) for s in config.sources),
        sightings=(
            SightingFacts(str(f.sighting_id), str(f.run_id), str(f.candidate_id), f.source_id)
            for f in SqliteSightingLookup(db).all_sightings()
        ),
        candidates=(
            CandidateFacts(str(c.id), str(c.run_id), c.source_id)
            for c in SqliteCandidateRepository(db).all_candidates()
        ),
        dispositions={
            candidate: outcome
            for candidate, outcome in outcomes.items()
            if outcome is not DispositionOutcome.DEFERRED
        },
    )


def date_findings(
    reports: Sequence[IntelligenceReport], config: LoadedConfig, today: date | IsoDate
) -> list[DateCheckFinding]:
    """The date check over these reports with the configured rules."""
    rules = config.datecheck
    return date_check(reports, today, rules.future_phrases, stale_after_days=rules.stale_after_days)


def datecheck_summary(findings: Sequence[DateCheckFinding]) -> DateCheckSummary:
    """The findings counted by kind, every kind listed."""
    return summarise_findings(
        ((str(f.report_id), f.kind.value) for f in findings), [k.value for k in FindingKind]
    )


# Dissemination inputs.


def _set_view(requirement_set: RequirementSet) -> RequirementSetView:
    return RequirementSetView(
        id=str(requirement_set.id),
        name=str(requirement_set.name),
        version=str(requirement_set.version),
        requirements=tuple(
            RequirementView(
                id=str(r.id),
                code=r.code,
                name=str(r.name),
                short=str(r.short),
                scanability=r.scanability,
                scanability_note=str(r.scanability_note),
            )
            for r in requirement_set.requirements
        ),
        groups=tuple(
            GroupView(
                id=str(g.id),
                kind="wbo" if g.kind is GroupKind.WBO else "impact",
                name=str(g.name),
                members=tuple(str(m) for m in g.members),
            )
            for g in requirement_set.groups
        ),
    )


def _report_view(report: IntelligenceReport, config: LoadedConfig) -> ReportView:
    return ReportView(
        id=str(report.id),
        title=str(report.title),
        grading=str(report.grading),
        credibility=report.grading.credibility,
        state=report.state,
        lens=config.catalogue.lane(report.lane).lens.value,
        assessments=tuple(
            AssessmentView(str(a.requirement_id), a.direction) for a in report.assessments
        ),
        potential_impact=report.scores.potential_impact,
        created_on=report.created_on,
        history=tuple(HistoryView(h.on, h.kind.value) for h in report.history),
    )


def _lane_view(config: LoadedConfig, matrix: CoverageMatrix) -> LaneMatrixView:
    names = {str(lane.id): str(lane.name) for lane in config.catalogue.lanes}
    lanes = matrix.columns[:-1]
    return LaneMatrixView(
        columns=tuple(names.get(lane, lane) for lane in lanes),
        rows=tuple(
            LaneRowView(row.label, tuple(c.count for c in row.cells), row.total, row.status)
            for row in matrix.rows
        ),
    )


def _method(
    db: Database,
    config: LoadedConfig,
    period: Period,
    created: Sequence[ReportFacts],
    coverage: CoverageAudit,
) -> MethodFacts:
    trend = funnel_trend(db)
    runs = [run for run in trend.runs if period.contains(IsoDate(run.started_at.date()))]
    per_run = run_dispositions(db)
    totals: Counter[DispositionOutcome] = Counter()
    undisposed = 0
    for run in runs:
        summary = trend.disposition_summary(run.run_id, per_run.get(run.run_id, []))
        totals.update(dict(summary.counts))
        undisposed += summary.undisposed
    stored = {str(r.id): r for r in SqliteScanRunRepository(db).all()}
    non_government, promotions = non_government_share(created)
    return MethodFacts(
        runs=tuple(
            RunView(
                run_id=run.run_id,
                started_on=IsoDate(run.started_at.date()),
                instrument_version=str(stored[run.run_id].instrument_version),
                raw=run.funnel.raw,
                unique=run.funnel.unique,
                new=run.funnel.new,
                reinforcements=run.funnel.reinforcements,
                requests_made=run.requests_made,
                budget_exhausted=run.budget_exhausted,
            )
            for run in runs
        ),
        dispositions=tuple((outcome, totals[outcome]) for outcome in DispositionOutcome),
        undisposed=undisposed,
        promotions=promotions,
        non_government=non_government,
        credibility=tuple((c.credibility, c.count) for c in credibility_distribution(created)),
        instrument_versions=tuple(
            sorted({str(stored[run.run_id].instrument_version) for run in runs})
        ),
        current_instrument_version=str(config.instrument.version),
        blind_spots=tuple(
            row.label for row in coverage.lanes.rows if row.status is CoverageStatus.BLIND_SPOT
        ),
    )


def product_inputs(
    db: Database, config: LoadedConfig, set_id: str, period: Period, today: date | IsoDate
) -> ProductInputs:
    """Everything a renderer reads for one requirement set and period, as of ``today``."""
    requirement_set = config.requirement_set(set_id)
    everything = SqliteReportRepository(db).list()
    reports = _assessed_on(everything, requirement_set)
    coverage = _audit(config, requirement_set, everything)
    created = [r for r in report_facts(reports, config) if period.contains(IsoDate(r.created_on))]
    return ProductInputs(
        requirement_set=_set_view(requirement_set),
        reports=tuple(_report_view(r, config) for r in reports),
        findings=tuple(
            FindingView(str(f.report_id), f.kind.value, str(f.detail))
            for f in date_findings(reports, config, today)
        ),
        method=_method(db, config, period, created, coverage),
        lane_matrix=_lane_view(config, coverage.lanes),
        node_counts=tuple(
            NodeCountsView(
                axis.name,
                tuple(
                    NodeRowView(row.label, row.expected or 0, row.total, row.status)
                    for row in matrix.rows
                ),
            )
            for axis, matrix in coverage.taxonomy
        ),
        active_counts=tuple((row.row_id, row.total) for row in coverage.lanes.rows),
        default_set=requirement_set.id == config.requirement_sets[0].id,
    )


def render_product(
    db: Database,
    config: LoadedConfig,
    level: Level,
    period: Period,
    today: date,
    set_id: str,
) -> tuple[Product, str]:
    """Render one product and the file stem it is written under.

    Raises ``NotImplementedInV1`` for the tactical level, before reading anything.
    """
    if level is Level.TACTICAL:
        render_tactical()
    inputs = product_inputs(db, config, set_id, period, today)
    on = IsoDate(today)
    render = render_strategic if level is Level.STRATEGIC else render_intsum
    product = render(inputs, period, on, config.copy)
    return product, product_stem(level, period, set_id, inputs.default_set)
