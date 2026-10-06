"""The read models: what the published snapshot holds and what the read API serves.

Production is a static site reading JSON snapshots; the API is a local
development and analyst tool (ADR 0001). Both serve these Pydantic models,
built by ``gwylio.infrastructure.readmodels`` and serialised by one function
(``gwylio.infrastructure.snapshot.to_jsonable``), so a snapshot file and the
matching API response are the same JSON. A contract test proves it.

Conventions: dates are ``YYYY-MM-DD`` strings and instants ISO 8601 UTC
strings ending in ``Z``; enums are their string values (credibility is its
digit); every field is present in every document, ``null`` when empty, so
the generated TypeScript types have no optional fields. Every model has an
identifier title (its class name) so ``gwylio schema`` can generate a
TypeScript interface for it; names are unique across every registered
schema. Prose fields are ``CleanText``: no en or em dash.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from gwylio.collection.model import RunStatus, SourceStatus
from gwylio.direction.model import GroupKind
from gwylio.dissemination.model import ProductLevel
from gwylio.dissemination.product_file import PeriodModel, SectionModel
from gwylio.evaluation.yield_ import YieldReading
from gwylio.intelligence.datecheck import FindingKind, Severity
from gwylio.intelligence.model import HistoryKind
from gwylio.processing.candidates_file import FunnelCounts
from gwylio.reference.model import Lens
from gwylio.shared.coverage import CoverageStatus, Scanability
from gwylio.shared.values import CleanText
from gwylio.shared.vocabulary import (
    Bucket,
    Credibility,
    Direction,
    Discipline,
    IndicatorState,
    Level,
    Reliability,
    ReportType,
    TimeHorizon,
)

__all__ = [
    "READ_MODELS",
    "AssessmentDetail",
    "AssessmentLine",
    "Coverage",
    "CoverageAxisView",
    "CoverageCellView",
    "CoverageColumn",
    "CoverageMatrixView",
    "CoverageRowView",
    "CredibilityBar",
    "DateCheck",
    "DateCheckCounts",
    "DateCheckGroup",
    "DateCheckLine",
    "DirectionCounts",
    "DisciplineCount",
    "DispositionCounts",
    "DispositionView",
    "EnumValue",
    "Enums",
    "FindingLine",
    "FunnelPoint",
    "GroupTile",
    "GroupView",
    "HazardRef",
    "HistoryLine",
    "LegendEntry",
    "Meta",
    "MetaCounts",
    "NamedRef",
    "Picture",
    "ProductDetail",
    "ProductSummary",
    "ReadingCounts",
    "ReportDetail",
    "ReportSummary",
    "RequirementSetDetail",
    "RequirementSetSummary",
    "RequirementTile",
    "RequirementView",
    "RunDetail",
    "RunSummary",
    "ScoresView",
    "SightingLine",
    "SourceCount",
    "SourceSummary",
    "SourcesHealth",
    "StateCounts",
    "StatusCounts",
]

Text = Annotated[str, AfterValidator(CleanText)]
"""Prose or an identifier: validated into ``CleanText`` (no en or em dash)."""
Day = Annotated[str, Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$", description="YYYY-MM-DD.")]
Instant = Annotated[
    str, Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]+Z$", description="ISO 8601, UTC.")
]
Rate = Annotated[float, Field(ge=0, description="A share from 0 to 1, rounded to four places.")]


class _ReadModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# Small counts shared by several documents.


class DirectionCounts(_ReadModel):
    """Reports counted by the direction of their assessment."""

    supports: int
    threatens: int
    neutral: int
    informs_baseline: int


class StateCounts(_ReadModel):
    """Reports counted by indicator state."""

    emerging: int
    tracking: int
    reinforced: int
    matured: int
    faded: int
    parked: int


class StatusCounts(_ReadModel):
    """Requirements counted by coverage status."""

    covered: int
    thin: int
    quiet: int
    blind_spot: int


class DateCheckCounts(_ReadModel):
    """Date check findings counted by kind, their total, and the reports they flag."""

    passed_horizon: int
    future_language: int
    stale_verification: int
    never_verified: int
    total: int
    reports_flagged: int


class CredibilityBar(_ReadModel):
    """How many reports carry one credibility digit: one bar of the grade inflation check."""

    credibility: Credibility
    label: Text = Field(description="The Admiralty wording, such as probably true.")
    count: int


# meta.json and enums.json


class MetaCounts(_ReadModel):
    """How much the register and its machinery hold."""

    reports: int
    reports_by_state: StateCounts
    runs: int
    sources: int = Field(description="Every source on the watchlist.")
    active_sources: int
    submissions: int
    products: int
    requirement_sets: int


class Meta(_ReadModel):
    """meta.json, GET /api/v1/meta: when and from what the snapshot was built."""

    generated_at: Instant = Field(description="When the snapshot or response was built.")
    today: Day = Field(description="The date the date check and the picture were computed for.")
    app_version: Text
    rubric_version: Text
    instrument_version: Text = Field(description="The current instrument in config/.")
    latest_run_id: Text | None
    latest_run_started_at: Instant | None
    default_requirement_set_id: Text
    requirement_set_ids: list[Text]
    counts: MetaCounts


class EnumValue(_ReadModel):
    """One value of a closed vocabulary, with its label and what it means."""

    value: Text = Field(description="The stored value; credibility digits are written 1 to 6.")
    label: Text
    meaning: Text | None


class Enums(_ReadModel):
    """enums.json, GET /api/v1/meta/enums: every closed vocabulary, for legends and filters."""

    direction: list[EnumValue]
    indicator_state: list[EnumValue]
    bucket: list[EnumValue]
    coverage_status: list[EnumValue]
    scanability: list[EnumValue]
    reliability: list[EnumValue]
    credibility: list[EnumValue]
    report_type: list[EnumValue]
    score_level: list[EnumValue]
    time_horizon: list[EnumValue]
    finding_kind: list[EnumValue]
    severity: list[EnumValue]
    yield_reading: list[EnumValue]
    disposition_outcome: list[EnumValue]
    discipline: list[EnumValue]
    source_status: list[EnumValue]
    run_status: list[EnumValue]
    history_kind: list[EnumValue]
    product_level: list[EnumValue]
    group_kind: list[EnumValue]
    lens: list[EnumValue]
    blind_spot_rule: Text = Field(
        description="The standing sentence that a blind spot is not quiet."
    )
    undercount: Text = Field(description="The standing sentence that reports are not impact.")


# Requirement sets


class RequirementSetSummary(_ReadModel):
    """One entry of requirement_sets.json, GET /api/v1/requirement-sets."""

    id: Text
    name: Text
    version: Text
    source_doc: Text
    requirements: int
    impact_groups: int
    wbo_groups: int
    is_default: bool


class RequirementView(_ReadModel):
    """One requirement (a Priority Intelligence Requirement, such as an SI)."""

    id: Text
    code: Text
    name: Text
    short: Text
    scanability: Scanability
    scanability_note: Text
    keywords: list[Text]
    expected_coverage: list[Text] = Field(description="Taxonomy node ids.")
    metric_sources: list[Text]
    development: bool
    group_ids: list[Text] = Field(description="The groups (impacts, objectives) holding it.")


class GroupView(_ReadModel):
    """One group of requirements: an impact statement or a well-being objective (WBO)."""

    id: Text
    kind: GroupKind
    name: Text
    statement: Text | None
    note: Text | None
    members: list[Text]
    related_groups: list[Text]


class RequirementSetDetail(_ReadModel):
    """requirement_set_<id>.json, GET /api/v1/requirement-sets/{id}."""

    id: Text
    name: Text
    version: Text
    source_doc: Text
    is_default: bool
    requirements: list[RequirementView]
    groups: list[GroupView]


# The picture


class RequirementTile(_ReadModel):
    """One requirement on the picture: its reports by direction and state, and its status.

    ``active`` counts the active reports (emerging, tracking, reinforced)
    assessed on it, and ``directions`` splits them by the direction of that
    assessment, so the directions add up to ``active``. ``states`` counts
    every report assessed on it. The latest dates come from reports still in
    the picture (active or matured).
    """

    requirement_id: Text
    code: Text
    short: Text
    name: Text
    scanability: Scanability
    status: CoverageStatus
    active: int
    total: int
    directions: DirectionCounts
    states: StateCounts
    latest_event_horizon: Day | None
    latest_verified: Day | None
    group_ids: list[Text]


class GroupTile(_ReadModel):
    """One group on the picture, aggregated over its member requirements.

    ``active`` and ``total`` count distinct reports; ``directions`` counts
    distinct active reports with at least one assessment in that direction on
    a member, so a report that cuts two ways counts under both.
    """

    group_id: Text
    kind: GroupKind
    name: Text
    statement: Text | None
    members: list[Text]
    active: int
    total: int
    directions: DirectionCounts
    states: StateCounts
    statuses: StatusCounts = Field(description="Member requirements by coverage status.")
    latest_event_horizon: Day | None
    latest_verified: Day | None


class Picture(_ReadModel):
    """picture_<set>.json, GET /api/v1/requirement-sets/{id}/picture."""

    set_id: Text
    set_name: Text
    version: Text
    today: Day
    wbo_groups: list[GroupTile]
    impact_groups: list[GroupTile]
    requirements: list[RequirementTile]
    datecheck: DateCheckCounts


# Reports


class AssessmentLine(_ReadModel):
    """One assessment on a report list line."""

    requirement_id: Text
    code: Text | None = Field(description="The requirement's code, null when no set holds it.")
    set_id: Text | None
    direction: Direction


class ReportSummary(_ReadModel):
    """One entry of reports.json, GET /api/v1/reports: what the list and its filters need."""

    id: Text
    title: Text
    url: str
    grading: Text = Field(description="Reliability letter and credibility digit, such as B2.")
    reliability: Reliability
    credibility: Credibility
    report_type: ReportType
    state: IndicatorState
    bucket: Bucket
    directions: list[Direction] = Field(description="Distinct directions, in vocabulary order.")
    assessments: list[AssessmentLine]
    requirement_ids: list[Text]
    set_ids: list[Text]
    lane: Text
    lane_name: Text
    source_id: Text | None
    source_name: Text
    topics: list[Text] = Field(description="Topic ids.")
    hazards: list[Text] = Field(description="Hazard ids.")
    places: list[Text] = Field(description="Place ids.")
    summary: Text
    created_on: Day
    last_changed: Day = Field(description="The latest history entry's date.")
    last_verified: Day | None
    event_horizon: Day | None
    appearances: int = Field(description="Distinct runs with a sighting of the report.")
    distinct_sources: int = Field(description="Distinct watched sources that sighted it.")
    flags: list[FindingKind] = Field(description="The date check's findings on this report.")


class NamedRef(_ReadModel):
    """A catalogue entry named by id: a topic or a place."""

    id: Text
    name: Text


class HazardRef(_ReadModel):
    """A hazard and its family on the hazard families axis."""

    id: Text
    name: Text
    family: Text
    family_name: Text


class ScoresView(_ReadModel):
    """The analyst's scores for one report."""

    evidence: Level
    novelty: Level
    confidence: Level
    potential_impact: Level
    time_horizon: TimeHorizon


class AssessmentDetail(_ReadModel):
    """One assessment with its requirement named."""

    requirement_id: Text
    code: Text | None
    name: Text | None
    set_id: Text | None
    direction: Direction


class HistoryLine(_ReadModel):
    """One append-only history entry."""

    on: Day
    kind: HistoryKind
    change: Text


class SightingLine(_ReadModel):
    """One sighting linked to a report: which run, which source, which page."""

    sighting_id: Text
    run_id: Text
    run_started_at: Instant
    candidate_id: Text
    url: str | None
    source_id: Text | None
    source_name: Text | None
    discipline: Discipline | None
    query_id: Text | None


class FindingLine(_ReadModel):
    """One date check finding on a report."""

    kind: FindingKind
    severity: Severity
    detail: Text


class ReportDetail(_ReadModel):
    """reports/<id>.json, GET /api/v1/reports/{id}: everything about one report."""

    id: Text
    title: Text
    url: str
    canonical_url: str
    grading: Text
    reliability: Reliability
    reliability_label: Text
    credibility: Credibility
    credibility_label: Text
    report_type: ReportType
    state: IndicatorState
    bucket: Bucket
    lane: Text
    lane_name: Text
    lens: Lens
    source_id: Text | None
    source_name: Text
    actor_id: Text | None
    actor_name: Text | None
    directions: list[Direction]
    assessments: list[AssessmentDetail]
    requirement_ids: list[Text]
    set_ids: list[Text]
    topics: list[NamedRef]
    hazards: list[HazardRef]
    places: list[NamedRef]
    scores: ScoresView
    summary: Text
    notes: Text
    owner: Text | None
    created_on: Day
    created_run_id: Text | None
    last_changed: Day
    last_verified: Day | None
    event_horizon: Day | None
    independent_confirmation: bool
    appearances: int
    distinct_sources: int
    history: list[HistoryLine]
    sightings: list[SightingLine]
    findings: list[FindingLine]
    cited_in: list[Text] = Field(description="Ids of the products that cite this report.")


# Sources


class SourceSummary(_ReadModel):
    """One entry of sources.json, GET /api/v1/sources: the watchlist entry and its yield."""

    id: Text
    name: Text
    domain: str
    feed_url: str | None
    discipline: Discipline
    lane: Text
    lane_name: Text
    lens: Lens
    actor: Text
    actor_name: Text
    reliability: Reliability
    reliability_label: Text
    trusted: bool
    site_pass: bool
    status: SourceStatus
    added_on: Day
    notes: Text | None
    raw_hits: int = Field(description="Stored sightings: hits that passed the gates.")
    unique_candidates: int
    promoted: int
    promotion_rate: Rate | None = Field(description="Promoted over unique candidates.")
    last_run_with_hits: Text | None
    last_productive_run: Text | None
    reading: YieldReading


class FunnelPoint(_ReadModel):
    """One run's funnel on the trend."""

    run_id: Text
    started_at: Instant
    funnel: FunnelCounts
    requests_made: int
    request_budget: int
    budget_exhausted: bool


class ReadingCounts(_ReadModel):
    """Sources counted by yield reading."""

    earning_its_place: int
    high_volume_no_promotions: int
    low_volume: int
    silent: int


class SourcesHealth(_ReadModel):
    """sources_health.json, GET /api/v1/sources/health: the funnel trend and silent sources."""

    window: int = Field(description="How many of the most recent runs the trend shows at most.")
    runs_total: int
    trend: list[FunnelPoint] = Field(description="Oldest first.")
    sources: int
    active_sources: int
    readings: ReadingCounts
    silent_sources: list[Text] = Field(description="Active sources with no hit in any run.")


# Scan runs


class DispositionCounts(_ReadModel):
    """A run's candidates counted by their final disposition."""

    promoted: int
    rejected: int
    duplicate: int
    deferred: int
    reinforcement: int


class DispositionView(_ReadModel):
    """What the analyst did with one run's candidates."""

    counts: DispositionCounts
    new: int
    disposed: int
    undisposed: int = Field(description="New candidates nobody has judged yet.")
    promotion_rate: Rate | None = Field(description="Promoted over new candidates.")


class RunSummary(_ReadModel):
    """One entry of runs.json, GET /api/v1/scan-runs. Runs are listed oldest first."""

    run_id: Text
    started_at: Instant
    finished_at: Instant | None
    status: RunStatus
    instrument_version: Text
    disciplines: list[Discipline]
    funnel: FunnelCounts
    requests_made: int
    request_budget: int
    budget_exhausted: bool
    candidates: int
    promoted: int
    undisposed: int
    submissions: list[Text] = Field(description="Ids of the submissions that judged this run.")


class SourceCount(_ReadModel):
    """One source's share of a run: its sightings and the candidates it found first."""

    source_id: Text | None = Field(description="Null for the open web.")
    source_name: Text | None
    sightings: int
    candidates: int


class DisciplineCount(_ReadModel):
    """One discipline's share of a run."""

    discipline: Discipline
    candidates: int
    sightings: int


class RunDetail(_ReadModel):
    """runs/<id>.json, GET /api/v1/scan-runs/{id}: one run in full."""

    run_id: Text
    started_at: Instant
    finished_at: Instant | None
    status: RunStatus
    instrument_version: Text
    instrument_hash: str
    disciplines: list[Discipline]
    funnel: FunnelCounts
    requests_made: int
    request_budget: int
    budget_exhausted: bool
    candidates: int
    promoted: int
    undisposed: int
    submissions: list[Text]
    reinforcements_recorded: int = Field(description="Reinforcements spotted at collection.")
    notes: list[Text] = Field(description="What the run says about itself, such as the budget.")
    warnings: list[Text] = Field(description="The collectors' warnings, from the candidates file.")
    per_source: list[SourceCount]
    per_discipline: list[DisciplineCount]
    dispositions: DispositionView
    credibility: list[CredibilityBar] = Field(description="The reports this run created.")
    promoted_report_ids: list[Text]


# Coverage


class CoverageColumn(_ReadModel):
    """One column of a coverage matrix."""

    id: Text
    name: Text


class CoverageCellView(_ReadModel):
    """One cell: a count and what it means."""

    column_id: Text
    count: int
    status: CoverageStatus


class CoverageRowView(_ReadModel):
    """One row with its total and the row's status.

    On the lane matrix a row is a requirement and its status comes from its
    scanability and total, so a blind spot is never shown as quiet. On a
    taxonomy matrix a row is a node and ``expected`` counts the requirements
    expecting it.
    """

    row_id: Text
    label: Text
    code: Text | None
    cells: list[CoverageCellView]
    total: int
    status: CoverageStatus
    expected: int | None


class CoverageMatrixView(_ReadModel):
    """A coverage matrix: columns, rows and the report ids it counted."""

    columns: list[CoverageColumn]
    rows: list[CoverageRowView]
    report_ids: list[Text]


class CoverageAxisView(_ReadModel):
    """One taxonomy axis by count."""

    axis_id: Text
    axis_name: Text
    matrix: CoverageMatrixView


class LegendEntry(_ReadModel):
    """One coverage status in the legend."""

    status: CoverageStatus
    label: Text
    meaning: Text


class Coverage(_ReadModel):
    """coverage_<set>.json, GET /api/v1/coverage/{set}: both matrices and the legend."""

    set_id: Text
    set_name: Text
    legend: list[LegendEntry]
    lanes: CoverageMatrixView = Field(description="Requirements down, lanes across.")
    taxonomy: list[CoverageAxisView] = Field(description="Taxonomy nodes down, one per axis.")
    credibility: list[CredibilityBar] = Field(
        description="Active reports assessed against the set, by credibility digit."
    )


# The date check


class DateCheckLine(_ReadModel):
    """One finding in the verification queue."""

    report_id: Text
    title: Text
    state: IndicatorState
    detail: Text
    severity: Severity


class DateCheckGroup(_ReadModel):
    """Every finding of one kind."""

    kind: FindingKind
    severity: Severity
    label: Text
    meaning: Text
    count: int
    findings: list[DateCheckLine]


class DateCheck(_ReadModel):
    """datecheck.json, GET /api/v1/datecheck: findings grouped by kind, every kind listed."""

    today: Day
    reports_checked: int = Field(description="Reports still in the picture: active or matured.")
    total: int
    reports_flagged: int
    groups: list[DateCheckGroup]


# Products


class ProductSummary(_ReadModel):
    """One entry of products.json, GET /api/v1/products."""

    id: Text
    level: ProductLevel
    requirement_set_id: Text
    period: PeriodModel
    generated_on: Day
    title: Text
    report_count: int
    section_headings: list[Text]
    markdown_file: str


class ProductDetail(_ReadModel):
    """products/<id>.json, GET /api/v1/products/{id}: one product's sections and Markdown."""

    id: Text
    level: ProductLevel
    requirement_set_id: Text
    period: PeriodModel
    generated_on: Day
    title: Text
    lead: list[Text]
    sections: list[SectionModel]
    report_ids: list[Text]
    method_note: Text
    markdown_file: str
    markdown_path: str = Field(description="Where the Markdown lives, relative to the data dir.")
    body: Text = Field(description="The product as Markdown.")


READ_MODELS: dict[str, type[BaseModel]] = {
    "snapshot-coverage": Coverage,
    "snapshot-datecheck": DateCheck,
    "snapshot-enums": Enums,
    "snapshot-meta": Meta,
    "snapshot-picture": Picture,
    "snapshot-product": ProductDetail,
    "snapshot-product-summary": ProductSummary,
    "snapshot-report": ReportDetail,
    "snapshot-report-summary": ReportSummary,
    "snapshot-requirement-set": RequirementSetDetail,
    "snapshot-requirement-set-summary": RequirementSetSummary,
    "snapshot-run": RunDetail,
    "snapshot-run-summary": RunSummary,
    "snapshot-source-summary": SourceSummary,
    "snapshot-sources-health": SourcesHealth,
}
"""Every read model at the root of a snapshot file or a list item, by schema name."""
