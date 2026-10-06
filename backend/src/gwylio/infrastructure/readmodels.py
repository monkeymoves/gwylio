"""Build the read models the snapshot and the read API serve, from the database and config.

``ReadModels`` reads the stored register, runs, submissions and products
once (lazily, per instance) and answers one method per document. The
evaluation numbers come from ``gwylio.infrastructure.adapters`` (the same
functions behind ``gwylio audit``, ``gwylio yield`` and the products), so
the site, the API, the command line and the products reconcile.

Everything that depends on time takes it from the injected ``Clock``: the
``generated_at`` stamp and the date the date check runs on. Two builds with
the same clock over the same database are equal.

``filter_reports`` is the single definition of the report filters: the API
applies it, and the front end applies the same rules client side over
``reports.json``.
"""

from __future__ import annotations

import enum
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date
from functools import cached_property
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Final, TypeVar

from gwylio.api.schemas import (
    AssessmentDetail,
    AssessmentLine,
    Coverage,
    CoverageAxisView,
    CoverageCellView,
    CoverageColumn,
    CoverageMatrixView,
    CoverageRowView,
    CredibilityBar,
    DateCheck,
    DateCheckCounts,
    DateCheckGroup,
    DateCheckLine,
    DirectionCounts,
    DisciplineCount,
    DispositionCounts,
    DispositionView,
    Enums,
    EnumValue,
    FindingLine,
    FunnelPoint,
    GroupTile,
    GroupView,
    HazardRef,
    HistoryLine,
    LegendEntry,
    Meta,
    MetaCounts,
    NamedRef,
    Picture,
    ProductDetail,
    ProductSummary,
    ReadingCounts,
    ReportDetail,
    ReportSummary,
    RequirementSetDetail,
    RequirementSetSummary,
    RequirementTile,
    RequirementView,
    RunDetail,
    RunSummary,
    ScoresView,
    SightingLine,
    SourceCount,
    SourcesHealth,
    SourceSummary,
    StateCounts,
    StatusCounts,
)
from gwylio.collection.model import (
    Candidate,
    RunStatus,
    ScanRun,
    Sighting,
    Source,
    SourceStatus,
)
from gwylio.direction.model import GroupKind, Requirement, RequirementSet
from gwylio.dissemination.model import ProductLevel, to_markdown
from gwylio.dissemination.product_file import product_document
from gwylio.evaluation.coverage import UNATTRIBUTED, CoverageMatrix, CredibilityCount
from gwylio.evaluation.coverage import credibility_distribution as credibility_spread
from gwylio.evaluation.funnel import FunnelTrend, RunFunnel
from gwylio.evaluation.yield_ import SourceYield, YieldReading
from gwylio.infrastructure.adapters import (
    audit,
    date_findings,
    funnel_trend,
    report_facts,
    run_dispositions,
    source_yield,
)
from gwylio.infrastructure.config.loaders import LoadedConfig
from gwylio.infrastructure.config.settings import CANDIDATES_SUBDIR, PRODUCTS_SUBDIR
from gwylio.infrastructure.handoff.candidates_file import (
    CandidatesFileError,
    read_candidates_file,
)
from gwylio.infrastructure.sqlite.db import Database
from gwylio.infrastructure.sqlite.repositories import (
    SqliteCandidateRepository,
    SqliteProductRepository,
    SqliteReportRepository,
    SqliteScanRunRepository,
    SqliteSightingLookup,
    SqliteSubmissionRepository,
    StoredProduct,
    format_timestamp,
)
from gwylio.intelligence.datecheck import DateCheckFinding, FindingKind, Severity
from gwylio.intelligence.model import HistoryKind, IntelligenceReport
from gwylio.intelligence.ports import SightingFact, SubmissionRecord
from gwylio.intelligence.service import derived_counts
from gwylio.processing.candidates_file import FunnelCounts
from gwylio.processing.submission import RUBRIC_VERSION
from gwylio.reference.model import Lens
from gwylio.shared.clock import Clock
from gwylio.shared.coverage import CoverageStatus, Scanability
from gwylio.shared.errors import DomainError
from gwylio.shared.values import IsoDate
from gwylio.shared.vocabulary import (
    Bucket,
    Credibility,
    Direction,
    Discipline,
    DispositionOutcome,
    IndicatorState,
    Level,
    Reliability,
    ReportType,
    TimeHorizon,
)

__all__ = [
    "FINDING_SEVERITY",
    "HEALTH_WINDOW",
    "NotFound",
    "ReadModels",
    "ReportFilter",
    "app_version",
    "filter_reports",
]

HEALTH_WINDOW: Final[int] = 12
"""How many of the most recent runs the sources health trend shows."""

FINDING_SEVERITY: Final[dict[FindingKind, Severity]] = {
    FindingKind.PASSED_HORIZON: Severity.ACT,
    FindingKind.FUTURE_LANGUAGE: Severity.WARN,
    FindingKind.STALE_VERIFICATION: Severity.WARN,
    FindingKind.NEVER_VERIFIED: Severity.ACT,
}
"""The severity the date check gives each kind of finding, for groups with none in them."""

_RATE_PLACES: Final[int] = 4
_E = TypeVar("_E", bound=enum.Enum)


class NotFound(LookupError):  # noqa: N818, the read API's word for a 404
    """No document with that id: the API answers 404."""

    def __init__(self, what: str, item_id: str) -> None:
        super().__init__(f"no {what} '{item_id}'")
        self.message = f"no {what} '{item_id}'"


def app_version() -> str:
    """The installed version of the ``gwylio`` distribution."""
    try:
        return version("gwylio")
    except PackageNotFoundError:  # pragma: no cover, only when run from a bare checkout
        return "0.0.0+unknown"


def _instant(clock: Clock) -> str:
    return clock.now().astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _day(value: IsoDate | None) -> str | None:
    return None if value is None else str(value)


def _rate(value: float | None) -> float | None:
    return None if value is None else round(value, _RATE_PLACES)


def _words(value: str) -> str:
    return value.replace("_", " ")


def _latest(values: Iterable[IsoDate | None]) -> str | None:
    present = [value for value in values if value is not None]
    return str(max(present)) if present else None


def _directions(counts: Counter[Direction]) -> DirectionCounts:
    return DirectionCounts(**{d.value: counts[d] for d in Direction})


def _states(counts: Counter[IndicatorState]) -> StateCounts:
    return StateCounts(**{s.value: counts[s] for s in IndicatorState})


# The report filters.


@dataclass(frozen=True, slots=True)
class ReportFilter:
    """The filters on the report list; ``None`` means "any".

    ``direction`` narrows to reports with an assessment in that direction; when
    ``requirement`` or ``set_id`` is also given, that same assessment must be on
    the requirement or in the set. ``since`` keeps reports whose latest history
    entry is on or after it. ``q`` matches title or summary, ignoring case.
    """

    set_id: str | None = None
    requirement: str | None = None
    direction: Direction | None = None
    state: IndicatorState | None = None
    bucket: Bucket | None = None
    lane: str | None = None
    hazard: str | None = None
    place: str | None = None
    topic: str | None = None
    since: date | None = None
    q: str | None = None
    reliability: Reliability | None = None
    credibility: Credibility | None = None


def _matches(report: ReportSummary, f: ReportFilter) -> bool:
    checks: list[bool] = []
    if f.set_id is not None:
        checks.append(f.set_id in report.set_ids)
    if f.requirement is not None:
        checks.append(f.requirement in report.requirement_ids)
    if f.direction is not None:
        checks.append(
            any(
                a.direction is f.direction
                and (f.requirement is None or a.requirement_id == f.requirement)
                and (f.set_id is None or a.set_id == f.set_id)
                for a in report.assessments
            )
        )
    for wanted, actual in (
        (f.state, report.state),
        (f.bucket, report.bucket),
        (f.lane, report.lane),
        (f.reliability, report.reliability),
        (f.credibility, report.credibility),
    ):
        if wanted is not None:
            checks.append(actual == wanted)
    for wanted_tag, tags in ((f.hazard, report.hazards), (f.place, report.places)):
        if wanted_tag is not None:
            checks.append(wanted_tag in tags)
    if f.topic is not None:
        checks.append(f.topic in report.topics)
    if f.since is not None:
        checks.append(report.last_changed >= f.since.isoformat())
    if f.q is not None and f.q.strip():
        needle = " ".join(f.q.casefold().split())
        checks.append(needle in report.title.casefold() or needle in report.summary.casefold())
    return all(checks)


def filter_reports(reports: Iterable[ReportSummary], f: ReportFilter) -> list[ReportSummary]:
    """The reports that pass every filter in ``f``, in the order given."""
    return [report for report in reports if _matches(report, f)]


# The builder.


class ReadModels:
    """Every read model over one database, one configuration and one clock."""

    def __init__(
        self,
        db: Database,
        config: LoadedConfig,
        *,
        clock: Clock,
        data_dir: Path | None = None,
        window: int = HEALTH_WINDOW,
    ) -> None:
        self._db = db
        self._config = config
        self._clock = clock
        self._data_dir = data_dir
        self._window = window

    # What is read once.

    @cached_property
    def today(self) -> IsoDate:
        """The date the date check and the picture are computed for."""
        return IsoDate(self._clock.today())

    @cached_property
    def _reports(self) -> tuple[IntelligenceReport, ...]:
        return SqliteReportRepository(self._db).list()

    @cached_property
    def _findings(self) -> list[DateCheckFinding]:
        return date_findings(self._reports, self._config, self.today)

    @cached_property
    def _findings_by_report(self) -> dict[str, list[DateCheckFinding]]:
        found: dict[str, list[DateCheckFinding]] = defaultdict(list)
        for finding in self._findings:
            found[str(finding.report_id)].append(finding)
        return found

    @cached_property
    def _runs(self) -> tuple[ScanRun, ...]:
        return SqliteScanRunRepository(self._db).all()

    @cached_property
    def _trend(self) -> FunnelTrend:
        return funnel_trend(self._db)

    @cached_property
    def _outcomes_by_run(self) -> dict[str, list[DispositionOutcome]]:
        return run_dispositions(self._db)

    @cached_property
    def _latest_outcomes(self) -> dict[str, DispositionOutcome]:
        return SqliteSubmissionRepository(self._db).latest_outcomes()

    @cached_property
    def _submissions(self) -> tuple[SubmissionRecord, ...]:
        return SqliteSubmissionRepository(self._db).all()

    @cached_property
    def _candidates(self) -> dict[str, Candidate]:
        return {str(c.id): c for c in SqliteCandidateRepository(self._db).all_candidates()}

    @cached_property
    def _sightings(self) -> dict[str, Sighting]:
        repository = SqliteCandidateRepository(self._db)
        return {
            str(s.id): s for run in self._runs for s in repository.sightings_for_run(str(run.id))
        }

    @cached_property
    def _sighting_facts(self) -> dict[str, SightingFact]:
        return {str(f.sighting_id): f for f in SqliteSightingLookup(self._db).all_sightings()}

    @cached_property
    def _products(self) -> tuple[StoredProduct, ...]:
        return SqliteProductRepository(self._db).all()

    @cached_property
    def _yields(self) -> dict[str, SourceYield]:
        return {y.source_id: y for y in source_yield(self._db, self._config)}

    @cached_property
    def _sources(self) -> dict[str, Source]:
        return {str(s.id): s for s in self._config.sources}

    @cached_property
    def _requirements(self) -> dict[str, tuple[RequirementSet, Requirement]]:
        found: dict[str, tuple[RequirementSet, Requirement]] = {}
        for requirement_set in self._config.requirement_sets:
            for requirement in requirement_set.requirements:
                found.setdefault(str(requirement.id), (requirement_set, requirement))
        return found

    def _requirement_set(self, set_id: str) -> RequirementSet:
        try:
            return self._config.requirement_set(set_id)
        except KeyError:
            raise NotFound("requirement set", set_id) from None

    @property
    def _default_set(self) -> RequirementSet:
        return self._config.requirement_sets[0]

    def _derived(self, report: IntelligenceReport) -> tuple[int, int]:
        facts = [self._sighting_facts[s] for s in report.sighting_ids if s in self._sighting_facts]
        return derived_counts(facts)

    def _lane_name(self, lane_id: str) -> str:
        try:
            return str(self._config.catalogue.lane(lane_id).name)
        except DomainError:
            return lane_id

    def _lens(self, lane_id: str) -> Lens:
        return self._config.catalogue.lane(lane_id).lens

    def _actor_name(self, actor_id: str | None) -> str | None:
        if actor_id is None:
            return None
        try:
            return str(self._config.catalogue.actor(actor_id).name)
        except DomainError:
            return None

    def _source_name(self, source_id: str | None) -> str | None:
        source = None if source_id is None else self._sources.get(source_id)
        return None if source is None else str(source.name)

    def _credibility_bars(self, counts: Iterable[CredibilityCount]) -> list[CredibilityBar]:
        labels = self._config.copy.common.credibility
        return [
            CredibilityBar(
                credibility=c.credibility, label=labels.label(int(c.credibility)), count=c.count
            )
            for c in counts
        ]

    # meta.json and enums.json

    def meta(self) -> Meta:
        """When and from what this snapshot was built, and how much it holds."""
        latest = self._runs[-1] if self._runs else None
        return Meta(
            generated_at=_instant(self._clock),
            today=str(self.today),
            app_version=app_version(),
            rubric_version=RUBRIC_VERSION,
            instrument_version=str(self._config.instrument.version),
            latest_run_id=None if latest is None else str(latest.id),
            latest_run_started_at=None if latest is None else format_timestamp(latest.started_at),
            default_requirement_set_id=str(self._default_set.id),
            requirement_set_ids=[str(rs.id) for rs in self._config.requirement_sets],
            counts=MetaCounts(
                reports=len(self._reports),
                reports_by_state=_states(Counter(r.state for r in self._reports)),
                runs=len(self._runs),
                sources=len(self._config.sources),
                active_sources=sum(1 for s in self._config.sources if s.active),
                submissions=len(self._submissions),
                products=len(self._products),
                requirement_sets=len(self._config.requirement_sets),
            ),
        )

    def enums(self) -> Enums:
        """Every closed vocabulary with its label and meaning, for legends and filters."""
        common = self._config.copy.common

        def values(
            members: Iterable[_E], label: Callable[[_E], str] | None = None
        ) -> list[EnumValue]:
            return [
                EnumValue(
                    value=str(m.value),
                    label=label(m) if label is not None else _words(str(m.value)),
                    meaning=getattr(m, "meaning", None),
                )
                for m in members
            ]

        return Enums(
            direction=values(Direction, lambda d: getattr(common.directions, d.value)),
            indicator_state=values(IndicatorState, lambda s: getattr(common.states, s.value)),
            bucket=values(Bucket),
            coverage_status=values(CoverageStatus, lambda c: getattr(common.statuses, c.value)),
            scanability=values(Scanability, lambda s: getattr(common.scanability, s.value)),
            reliability=values(Reliability, lambda r: r.label),
            credibility=values(Credibility, lambda c: common.credibility.label(int(c))),
            report_type=values(ReportType),
            score_level=values(Level),
            time_horizon=values(TimeHorizon),
            finding_kind=values(
                FindingKind, lambda k: getattr(self._config.copy.intsum, k.value).heading
            ),
            severity=values(Severity),
            yield_reading=values(YieldReading),
            disposition_outcome=values(DispositionOutcome),
            discipline=values(Discipline),
            source_status=values(SourceStatus),
            run_status=values(RunStatus),
            history_kind=values(HistoryKind),
            product_level=values(ProductLevel),
            group_kind=values(
                GroupKind,
                lambda g: "well-being objective (WBO)" if g is GroupKind.WBO else "impact",
            ),
            lens=values(Lens),
            blind_spot_rule=common.blind_spot_rule,
            undercount=common.undercount,
        )

    # Requirement sets.

    def requirement_sets(self) -> list[RequirementSetSummary]:
        """Every configured requirement set, the default first."""
        return [
            RequirementSetSummary(
                id=str(rs.id),
                name=str(rs.name),
                version=str(rs.version),
                source_doc=str(rs.source_doc),
                requirements=len(rs.requirements),
                impact_groups=len(rs.groups_of_kind(GroupKind.IMPACT)),
                wbo_groups=len(rs.groups_of_kind(GroupKind.WBO)),
                is_default=rs.id == self._default_set.id,
            )
            for rs in self._config.requirement_sets
        ]

    def requirement_set(self, set_id: str) -> RequirementSetDetail:
        """One requirement set with its requirements and groups."""
        rs = self._requirement_set(set_id)
        return RequirementSetDetail(
            id=str(rs.id),
            name=str(rs.name),
            version=str(rs.version),
            source_doc=str(rs.source_doc),
            is_default=rs.id == self._default_set.id,
            requirements=[
                RequirementView(
                    id=str(r.id),
                    code=r.code,
                    name=str(r.name),
                    short=str(r.short),
                    scanability=r.scanability,
                    scanability_note=str(r.scanability_note),
                    keywords=[str(k) for k in r.keywords],
                    expected_coverage=[str(n) for n in r.expected_coverage],
                    metric_sources=[str(m) for m in r.metric_sources],
                    development=r.development,
                    group_ids=[str(g.id) for g in rs.groups_of(r.id)],
                )
                for r in rs.requirements
            ],
            groups=[
                GroupView(
                    id=str(g.id),
                    kind=g.kind,
                    name=str(g.name),
                    statement=None if g.statement is None else str(g.statement),
                    note=None if g.note is None else str(g.note),
                    members=[str(m) for m in g.members],
                    related_groups=[str(r) for r in g.related_groups],
                )
                for g in rs.groups
            ],
        )

    # The picture.

    def _datecheck_counts(self, findings: Sequence[DateCheckFinding]) -> DateCheckCounts:
        tally = Counter(f.kind for f in findings)
        return DateCheckCounts(
            **{kind.value: tally[kind] for kind in FindingKind},
            total=len(findings),
            reports_flagged=len({f.report_id for f in findings}),
        )

    def picture(self, set_id: str) -> Picture:
        """One requirement set's picture: tiles per group and requirement, and the date check."""
        rs = self._requirement_set(set_id)
        rows = {row.row_id: row for row in audit(self._db, self._config, set_id).lanes.rows}
        ids = rs.requirement_ids()
        in_set = [r for r in self._reports if any(a.requirement_id in ids for a in r.assessments)]
        on: dict[str, list[tuple[IntelligenceReport, Direction]]] = defaultdict(list)
        for report in in_set:
            for a in report.assessments:
                on[str(a.requirement_id)].append((report, a.direction))
        tiles: list[RequirementTile] = []
        for r in rs.requirements:
            assessed = on[str(r.id)]
            active = [(report, d) for report, d in assessed if report.state.active]
            row = rows[str(r.id)]
            if row.total != len(active):  # pragma: no cover, the audit and the picture agree
                raise AssertionError(f"{r.id}: audit counts {row.total}, picture {len(active)}")
            live = [report for report, _ in assessed if report.state.live]
            tiles.append(
                RequirementTile(
                    requirement_id=str(r.id),
                    code=r.code,
                    short=str(r.short),
                    name=str(r.name),
                    scanability=r.scanability,
                    status=row.status,
                    active=len(active),
                    total=len(assessed),
                    directions=_directions(Counter(d for _, d in active)),
                    states=_states(Counter(report.state for report, _ in assessed)),
                    latest_event_horizon=_latest(report.event_horizon for report in live),
                    latest_verified=_latest(report.last_verified for report in live),
                    group_ids=[str(g.id) for g in rs.groups_of(r.id)],
                )
            )
        by_id = {tile.requirement_id: tile for tile in tiles}

        def group_tile(kind: GroupKind) -> list[GroupTile]:
            built: list[GroupTile] = []
            for g in rs.groups_of_kind(kind):
                members = {str(m) for m in g.members}
                reports = [
                    r for r in in_set if any(a.requirement_id in members for a in r.assessments)
                ]
                directions: Counter[Direction] = Counter()
                for report in reports:
                    if report.state.active:
                        directions.update(
                            {a.direction for a in report.assessments if a.requirement_id in members}
                        )
                statuses = Counter(by_id[m].status for m in g.members)
                live = [r for r in reports if r.state.live]
                built.append(
                    GroupTile(
                        group_id=str(g.id),
                        kind=g.kind,
                        name=str(g.name),
                        statement=None if g.statement is None else str(g.statement),
                        members=[str(m) for m in g.members],
                        active=sum(1 for r in reports if r.state.active),
                        total=len(reports),
                        directions=_directions(directions),
                        states=_states(Counter(r.state for r in reports)),
                        statuses=StatusCounts(**{s.value: statuses[s] for s in CoverageStatus}),
                        latest_event_horizon=_latest(r.event_horizon for r in live),
                        latest_verified=_latest(r.last_verified for r in live),
                    )
                )
            return built

        set_ids = {str(r.id) for r in in_set}
        return Picture(
            set_id=str(rs.id),
            set_name=str(rs.name),
            version=str(rs.version),
            today=str(self.today),
            wbo_groups=group_tile(GroupKind.WBO),
            impact_groups=group_tile(GroupKind.IMPACT),
            requirements=tiles,
            datecheck=self._datecheck_counts(
                [f for f in self._findings if str(f.report_id) in set_ids]
            ),
        )

    # Reports.

    def _assessment_place(self, requirement_id: str) -> tuple[str | None, Requirement | None]:
        found = self._requirements.get(requirement_id)
        return (None, None) if found is None else (str(found[0].id), found[1])

    def _summary(self, report: IntelligenceReport) -> ReportSummary:
        appearances, sources = self._derived(report)
        lines: list[AssessmentLine] = []
        for a in report.assessments:
            set_id, requirement = self._assessment_place(str(a.requirement_id))
            lines.append(
                AssessmentLine(
                    requirement_id=str(a.requirement_id),
                    code=None if requirement is None else requirement.code,
                    set_id=set_id,
                    direction=a.direction,
                )
            )
        present = {a.direction for a in report.assessments}
        return ReportSummary(
            id=str(report.id),
            title=str(report.title),
            url=report.url,
            grading=str(report.grading),
            reliability=report.grading.reliability,
            credibility=report.grading.credibility,
            report_type=report.report_type,
            state=report.state,
            bucket=report.bucket,
            directions=[d for d in Direction if d in present],
            assessments=lines,
            requirement_ids=[str(r) for r in report.requirement_ids],
            set_ids=sorted({line.set_id for line in lines if line.set_id is not None}),
            lane=str(report.lane),
            lane_name=self._lane_name(report.lane),
            source_id=report.source_id,
            source_name=str(report.source_name),
            topics=[str(t) for t in report.topics],
            hazards=[str(h) for h in report.hazards],
            places=[str(p) for p in report.places],
            summary=str(report.summary),
            created_on=str(report.created_on),
            last_changed=str(report.last_history_on()),
            last_verified=_day(report.last_verified),
            event_horizon=_day(report.event_horizon),
            appearances=appearances,
            distinct_sources=sources,
            flags=sorted(
                {f.kind for f in self._findings_by_report.get(str(report.id), [])},
                key=list(FindingKind).index,
            ),
        )

    def reports(self, report_filter: ReportFilter | None = None) -> list[ReportSummary]:
        """Every report by id, narrowed by ``report_filter`` when given."""
        summaries = [self._summary(report) for report in self._reports]
        return summaries if report_filter is None else filter_reports(summaries, report_filter)

    def report_ids(self) -> list[str]:
        """Every report id, in order."""
        return [str(report.id) for report in self._reports]

    def report(self, report_id: str) -> ReportDetail:
        """One report in full."""
        report = next((r for r in self._reports if r.id == report_id), None)
        if report is None:
            raise NotFound("report", report_id)
        summary = self._summary(report)
        catalogue = self._config.catalogue
        assessments: list[AssessmentDetail] = []
        for a in report.assessments:
            set_id, requirement = self._assessment_place(str(a.requirement_id))
            assessments.append(
                AssessmentDetail(
                    requirement_id=str(a.requirement_id),
                    code=None if requirement is None else requirement.code,
                    name=None if requirement is None else str(requirement.name),
                    set_id=set_id,
                    direction=a.direction,
                )
            )
        hazards: list[HazardRef] = []
        for hazard_id in report.hazards:
            hazard = catalogue.hazard(hazard_id)
            family = catalogue.taxonomy.require_node(hazard.family)
            hazards.append(
                HazardRef(
                    id=str(hazard.id),
                    name=str(hazard.name),
                    family=str(hazard.family),
                    family_name=str(family.name),
                )
            )
        sightings: list[SightingLine] = []
        for sighting_id in report.sighting_ids:
            fact = self._sighting_facts.get(str(sighting_id))
            if fact is None:
                continue
            sighting = self._sightings.get(str(sighting_id))
            candidate = self._candidates.get(str(fact.candidate_id))
            sightings.append(
                SightingLine(
                    sighting_id=str(sighting_id),
                    run_id=str(fact.run_id),
                    run_started_at=format_timestamp(fact.run_started_at),
                    candidate_id=str(fact.candidate_id),
                    url=None if candidate is None else candidate.url,
                    source_id=fact.source_id,
                    source_name=self._source_name(fact.source_id),
                    discipline=None if sighting is None else sighting.discipline,
                    query_id=None if sighting is None else str(sighting.query_id),
                )
            )
        labels = self._config.copy.common.credibility
        return ReportDetail(
            id=summary.id,
            title=summary.title,
            url=report.url,
            canonical_url=report.canonical_url.value,
            grading=summary.grading,
            reliability=summary.reliability,
            reliability_label=report.grading.reliability.label,
            credibility=summary.credibility,
            credibility_label=labels.label(int(report.grading.credibility)),
            report_type=report.report_type,
            state=report.state,
            bucket=report.bucket,
            lane=summary.lane,
            lane_name=summary.lane_name,
            lens=self._lens(report.lane),
            source_id=report.source_id,
            source_name=summary.source_name,
            actor_id=report.actor_id,
            actor_name=self._actor_name(report.actor_id),
            directions=summary.directions,
            assessments=assessments,
            requirement_ids=summary.requirement_ids,
            set_ids=summary.set_ids,
            topics=[NamedRef(id=str(t), name=str(catalogue.topic(t).name)) for t in report.topics],
            hazards=hazards,
            places=[NamedRef(id=str(p), name=str(catalogue.place(p).name)) for p in report.places],
            scores=ScoresView(
                evidence=report.scores.evidence,
                novelty=report.scores.novelty,
                confidence=report.scores.confidence,
                potential_impact=report.scores.potential_impact,
                time_horizon=report.scores.time_horizon,
            ),
            summary=summary.summary,
            notes=str(report.notes),
            owner=None if report.owner is None else str(report.owner),
            created_on=summary.created_on,
            created_run_id=report.created_run_id,
            last_changed=summary.last_changed,
            last_verified=summary.last_verified,
            event_horizon=summary.event_horizon,
            independent_confirmation=report.independent_confirmation,
            appearances=summary.appearances,
            distinct_sources=summary.distinct_sources,
            history=[
                HistoryLine(on=str(h.on), kind=h.kind, change=str(h.change)) for h in report.history
            ],
            sightings=sightings,
            findings=[
                FindingLine(kind=f.kind, severity=f.severity, detail=str(f.detail))
                for f in self._findings_by_report.get(str(report.id), [])
            ],
            cited_in=[
                str(stored.product.id)
                for stored in self._products
                if report.id in stored.product.report_ids
            ],
        )

    # Sources.

    def _source_summary(self, source: Source) -> SourceSummary:
        found = self._yields[str(source.id)]
        lane = str(source.lane)
        return SourceSummary(
            id=str(source.id),
            name=str(source.name),
            domain=source.domain,
            feed_url=source.feed_url,
            discipline=source.discipline,
            lane=lane,
            lane_name=self._lane_name(lane),
            lens=self._lens(lane),
            actor=str(source.actor),
            actor_name=self._actor_name(source.actor) or str(source.actor),
            reliability=source.reliability,
            reliability_label=source.reliability.label,
            trusted=source.trusted,
            site_pass=source.site_pass,
            status=source.status,
            added_on=str(source.added_on),
            notes=None if source.notes is None else str(source.notes),
            raw_hits=found.raw_hits,
            unique_candidates=found.unique_candidates,
            promoted=found.promoted,
            promotion_rate=_rate(found.promotion_rate),
            last_run_with_hits=found.last_run_with_hits,
            last_productive_run=found.last_productive_run,
            reading=found.reading,
        )

    def sources(self) -> list[SourceSummary]:
        """Every watched source with its yield, in watchlist order."""
        return [self._source_summary(source) for source in self._config.sources]

    def source(self, source_id: str) -> SourceSummary:
        """One watched source with its yield."""
        source = self._sources.get(source_id)
        if source is None:
            raise NotFound("source", source_id)
        return self._source_summary(source)

    def _funnel(self, run: RunFunnel) -> FunnelCounts:
        f = run.funnel
        return FunnelCounts(
            raw=f.raw,
            dropped_own=f.dropped_own,
            dropped_negative=f.dropped_negative,
            dropped_unrelated=f.dropped_unrelated,
            passed=f.passed,
            unique=f.unique,
            seen_before=f.seen_before,
            new=f.new,
            reinforcements=f.reinforcements,
        )

    def sources_health(self) -> SourcesHealth:
        """The funnel trend over the most recent runs, and the silent sources."""
        budgets = {str(run.id): run.request_budget for run in self._runs}
        readings = Counter(y.reading for y in self._yields.values())
        return SourcesHealth(
            window=self._window,
            runs_total=len(self._trend.runs),
            trend=[
                FunnelPoint(
                    run_id=run.run_id,
                    started_at=format_timestamp(run.started_at),
                    funnel=self._funnel(run),
                    requests_made=run.requests_made,
                    request_budget=budgets[run.run_id],
                    budget_exhausted=run.budget_exhausted,
                )
                for run in self._trend.last(self._window).runs
            ],
            sources=len(self._config.sources),
            active_sources=sum(1 for s in self._config.sources if s.active),
            readings=ReadingCounts(**{r.value: readings[r] for r in YieldReading}),
            silent_sources=[
                str(s.id)
                for s in self._config.sources
                if self._yields[str(s.id)].reading is YieldReading.SILENT
            ],
        )

    # Scan runs.

    def _run_parts(self, run: ScanRun) -> tuple[list[Candidate], DispositionView, list[str]]:
        candidates = [c for c in self._candidates.values() if c.run_id == run.id]
        summary = self._trend.disposition_summary(
            str(run.id), self._outcomes_by_run.get(str(run.id), [])
        )
        counts = dict(summary.counts)
        view = DispositionView(
            counts=DispositionCounts(**{o.value: counts[o] for o in DispositionOutcome}),
            new=summary.new,
            disposed=summary.disposed,
            undisposed=summary.undisposed,
            promotion_rate=_rate(summary.promotion_rate),
        )
        submissions = [s.id for s in self._submissions if s.run_id == run.id]
        return candidates, view, submissions

    def _run_summary(self, run: ScanRun) -> RunSummary:
        candidates, view, submissions = self._run_parts(run)
        return RunSummary(
            run_id=str(run.id),
            started_at=format_timestamp(run.started_at),
            finished_at=None if run.finished_at is None else format_timestamp(run.finished_at),
            status=run.status,
            instrument_version=str(run.instrument_version),
            disciplines=list(run.disciplines),
            funnel=self._funnel(self._trend_run(str(run.id))),
            requests_made=run.requests_made,
            request_budget=run.request_budget,
            budget_exhausted=run.budget_exhausted,
            candidates=len(candidates),
            promoted=view.counts.promoted,
            undisposed=view.undisposed,
            submissions=submissions,
        )

    def _trend_run(self, run_id: str) -> RunFunnel:
        return next(r for r in self._trend.runs if r.run_id == run_id)

    def runs(self) -> list[RunSummary]:
        """Every stored run, oldest first."""
        return [self._run_summary(run) for run in self._runs]

    def run_ids(self) -> list[str]:
        """Every stored run id, oldest first."""
        return [str(run.id) for run in self._runs]

    def _warnings(self, run_id: str) -> list[str]:
        if self._data_dir is None:
            return []
        path = self._data_dir / CANDIDATES_SUBDIR / f"{run_id}.json"
        if not path.is_file():
            return []
        try:
            return [str(w) for w in read_candidates_file(path).warnings]
        except CandidatesFileError:
            return []

    def run(self, run_id: str) -> RunDetail:
        """One run in full: funnel, shares by source and discipline, dispositions, grades."""
        run = next((r for r in self._runs if r.id == run_id), None)
        if run is None:
            raise NotFound("scan run", run_id)
        summary = self._run_summary(run)
        candidates, view, _ = self._run_parts(run)
        sightings = [s for s in self._sightings.values() if s.run_id == run.id]
        by_source_sightings = Counter(s.source_id for s in sightings)
        by_source_candidates = Counter(c.source_id for c in candidates)
        source_ids = sorted(
            set(by_source_sightings) | set(by_source_candidates),
            key=lambda s: (s is None, s or ""),
        )
        repository = SqliteCandidateRepository(self._db)
        created = [str(r.id) for r in self._reports if r.created_run_id == run.id]
        return RunDetail(
            **summary.model_dump(),
            instrument_hash=run.instrument_hash,
            reinforcements_recorded=len(repository.reinforcements_for_run(str(run.id))),
            notes=[str(note) for note in run.notes],
            warnings=self._warnings(str(run.id)),
            per_source=[
                SourceCount(
                    source_id=source_id,
                    source_name=self._source_name(source_id),
                    sightings=by_source_sightings[source_id],
                    candidates=by_source_candidates[source_id],
                )
                for source_id in source_ids
            ],
            per_discipline=[
                DisciplineCount(
                    discipline=d,
                    candidates=sum(1 for c in candidates if c.discipline is d),
                    sightings=sum(1 for s in sightings if s.discipline is d),
                )
                for d in run.disciplines
            ],
            dispositions=view,
            credibility=self._credibility_bars(
                credibility_spread(report_facts(self._reports, self._config), str(run.id))
            ),
            promoted_report_ids=created,
        )

    # Coverage.

    def _matrix(
        self, matrix: CoverageMatrix, names: dict[str, str], codes: dict[str, str]
    ) -> CoverageMatrixView:
        return CoverageMatrixView(
            columns=[CoverageColumn(id=c, name=names.get(c, c)) for c in matrix.columns],
            rows=[
                CoverageRowView(
                    row_id=row.row_id,
                    label=row.label,
                    code=codes.get(row.row_id),
                    cells=[
                        CoverageCellView(column_id=c.column_id, count=c.count, status=c.status)
                        for c in row.cells
                    ],
                    total=row.total,
                    status=row.status,
                    expected=row.expected,
                )
                for row in matrix.rows
            ],
            report_ids=list(matrix.report_ids),
        )

    def coverage(self, set_id: str) -> Coverage:
        """Both coverage matrices of one requirement set, with the legend."""
        rs = self._requirement_set(set_id)
        result = audit(self._db, self._config, set_id)
        common = self._config.copy.common
        lane_names = {str(lane.id): str(lane.name) for lane in self._config.catalogue.lanes}
        lane_names[UNATTRIBUTED] = common.unattributed
        codes = {str(r.id): r.code for r in rs.requirements}
        return Coverage(
            set_id=str(rs.id),
            set_name=str(rs.name),
            legend=[
                LegendEntry(
                    status=status,
                    label=getattr(common.statuses, status.value),
                    meaning=status.meaning,
                )
                for status in CoverageStatus
            ],
            lanes=self._matrix(result.lanes, lane_names, codes),
            taxonomy=[
                CoverageAxisView(
                    axis_id=axis.id,
                    axis_name=axis.name,
                    matrix=self._matrix(matrix, {"reports": common.header_reports}, {}),
                )
                for axis, matrix in result.taxonomy
            ],
            credibility=self._credibility_bars(result.credibility),
        )

    # The date check.

    def datecheck(self) -> DateCheck:
        """Every date check finding, grouped by kind; every kind listed."""
        titles = {str(r.id): r for r in self._reports}
        intsum = self._config.copy.intsum
        groups: list[DateCheckGroup] = []
        for kind in FindingKind:
            found = [f for f in self._findings if f.kind is kind]
            copy = getattr(intsum, kind.value)
            groups.append(
                DateCheckGroup(
                    kind=kind,
                    severity=FINDING_SEVERITY[kind],
                    label=copy.heading,
                    meaning=copy.meaning,
                    count=len(found),
                    findings=[
                        DateCheckLine(
                            report_id=str(f.report_id),
                            title=str(titles[str(f.report_id)].title),
                            state=titles[str(f.report_id)].state,
                            detail=str(f.detail),
                            severity=f.severity,
                        )
                        for f in found
                    ],
                )
            )
        return DateCheck(
            today=str(self.today),
            reports_checked=sum(1 for r in self._reports if r.state.live),
            total=len(self._findings),
            reports_flagged=len({f.report_id for f in self._findings}),
            groups=groups,
        )

    # Products.

    def products(self) -> list[ProductSummary]:
        """Every recorded product, by id."""
        return [
            ProductSummary(
                id=str(stored.product.id),
                level=stored.product.level,
                requirement_set_id=str(stored.product.requirement_set_id),
                period=product_document(stored.product, stored.markdown_file).period,
                generated_on=str(stored.product.generated_on),
                title=str(stored.product.title),
                report_count=len(stored.product.report_ids),
                section_headings=[str(s.heading) for s in stored.product.sections],
                markdown_file=stored.markdown_file,
            )
            for stored in self._products
        ]

    def product_ids(self) -> list[str]:
        """Every recorded product id, in order."""
        return [str(stored.product.id) for stored in self._products]

    def product(self, product_id: str) -> ProductDetail:
        """One product: its sections, as recorded, and its Markdown."""
        stored = next((p for p in self._products if p.product.id == product_id), None)
        if stored is None:
            raise NotFound("product", product_id)
        document = product_document(stored.product, stored.markdown_file)
        return ProductDetail(
            id=document.id,
            level=document.level,
            requirement_set_id=document.requirement_set_id,
            period=document.period,
            generated_on=document.generated_on,
            title=document.title,
            lead=document.lead,
            sections=document.sections,
            report_ids=document.report_ids,
            method_note=document.method_note,
            markdown_file=document.markdown_file,
            markdown_path=f"{PRODUCTS_SUBDIR}/{document.markdown_file}",
            body=str(to_markdown(stored.product)),
        )

    # Identifiers every list holds, for the snapshot.

    def requirement_set_ids(self) -> list[str]:
        """Every configured requirement set id, the default first."""
        return [str(rs.id) for rs in self._config.requirement_sets]
