"""The coverage audit, down both axes: requirements by lane, and taxonomy nodes by count.

Pure functions over plain inputs. The infrastructure layer resolves what the
register stores (a report's assessments name only requirement ids; a hazard
names only its family) and hands the facts in as the small records below, so
this context never imports Direction, Intelligence or Reference.

Only active reports count (emerging, tracking, reinforced). The status of a
requirement row comes from ``coverage_status(scanability, total)``, so a
blind spot is labelled from the requirement's scanability and never from the
count alone. A cell's status is ``covered`` at three or more, ``thin`` at one
or two, and ``quiet`` at zero, unless its row is a blind spot, when an empty
cell is a blind spot too.

A taxonomy node no requirement expects and no report touches is a blind spot
of the framework: the requirement set does not foreground it, so silence there
says nothing.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from gwylio.shared.coverage import (
    COVERED_MIN_REPORTS,
    CoverageStatus,
    Scanability,
    coverage_status,
)
from gwylio.shared.vocabulary import Credibility, IndicatorState

__all__ = [
    "GOVERNMENT_LENS",
    "UNATTRIBUTED",
    "AxisFacts",
    "CoverageCell",
    "CoverageMatrix",
    "CoverageRow",
    "CredibilityCount",
    "NodeFacts",
    "ReportFacts",
    "RequirementFacts",
    "RequirementSetFacts",
    "cell_status",
    "credibility_distribution",
    "lane_of",
    "lens_counts",
    "non_government_share",
    "requirement_by_lane",
    "taxonomy_by_count",
]

UNATTRIBUTED: Final[str] = "unattributed"
"""The column for a report whose lane cannot be resolved from its source, actor or itself."""
GOVERNMENT_LENS: Final[str] = "government"
"""The lens whose share the mainstream bias guard asks about."""


@dataclass(frozen=True, slots=True)
class RequirementFacts:
    """One requirement, as the audit needs it."""

    id: str
    code: str
    short: str
    scanability: Scanability
    expected_coverage: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RequirementSetFacts:
    """A requirement set: its id and requirements, in order."""

    id: str
    requirements: tuple[RequirementFacts, ...]

    def requirement_ids(self) -> frozenset[str]:
        """Every requirement id in the set."""
        return frozenset(r.id for r in self.requirements)


@dataclass(frozen=True, slots=True)
class NodeFacts:
    """One taxonomy node."""

    id: str
    name: str


@dataclass(frozen=True, slots=True)
class AxisFacts:
    """One taxonomy axis and its nodes, in order."""

    id: str
    name: str
    nodes: tuple[NodeFacts, ...]


@dataclass(frozen=True, slots=True)
class ReportFacts:
    """One intelligence report, as the audit needs it.

    ``lane`` is the report's own lane (the source's lane when watched, else the
    analyst's); ``lens`` is that lane's lens. ``hazard_families`` are the
    taxonomy nodes of the report's hazards.
    """

    id: str
    state: IndicatorState
    requirement_ids: tuple[str, ...]
    source_id: str | None
    actor_id: str | None
    lane: str | None
    lens: str
    credibility: Credibility
    created_run_id: str | None
    created_on: str
    hazard_families: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CoverageCell:
    """One cell of a coverage matrix: a count and what it means."""

    row_id: str
    column_id: str
    count: int
    status: CoverageStatus


@dataclass(frozen=True, slots=True)
class CoverageRow:
    """One row of a coverage matrix with its total and the row's status.

    ``expected`` is set on taxonomy rows only: how many requirements expect
    the node.
    """

    row_id: str
    label: str
    cells: tuple[CoverageCell, ...]
    total: int
    status: CoverageStatus
    expected: int | None = None


@dataclass(frozen=True, slots=True)
class CoverageMatrix:
    """A coverage matrix: rows, the column ids in order, and the report ids it counted."""

    columns: tuple[str, ...]
    rows: tuple[CoverageRow, ...]
    report_ids: tuple[str, ...]

    def row(self, row_id: str) -> CoverageRow:
        """The row with this id, or ``KeyError``."""
        for row in self.rows:
            if row.row_id == row_id:
                return row
        raise KeyError(row_id)

    def cell(self, row_id: str, column_id: str) -> CoverageCell:
        """The cell at this row and column, or ``KeyError``."""
        for cell in self.row(row_id).cells:
            if cell.column_id == column_id:
                return cell
        raise KeyError(column_id)

    def column_total(self, column_id: str) -> int:
        """The sum of one column."""
        return sum(self.cell(row.row_id, column_id).count for row in self.rows)


@dataclass(frozen=True, slots=True)
class CredibilityCount:
    """How many reports carry one credibility digit."""

    credibility: Credibility
    count: int


def cell_status(count: int, row_status: CoverageStatus) -> CoverageStatus:
    """A cell's status: covered, thin or quiet by count; empty in a blind-spot row, blind spot."""
    if count >= COVERED_MIN_REPORTS:
        return CoverageStatus.COVERED
    if count > 0:
        return CoverageStatus.THIN
    if row_status is CoverageStatus.BLIND_SPOT:
        return CoverageStatus.BLIND_SPOT
    return CoverageStatus.QUIET


def lane_of(
    report: ReportFacts, sources: Mapping[str, str], actors: Mapping[str, str] | None = None
) -> str:
    """The lane a report counts under: its source's, else its actor's, else its own, else none."""
    if report.source_id is not None and report.source_id in sources:
        return sources[report.source_id]
    if actors is not None and report.actor_id is not None and report.actor_id in actors:
        return actors[report.actor_id]
    return report.lane or UNATTRIBUTED


def _active(reports: Iterable[ReportFacts]) -> list[ReportFacts]:
    return [report for report in reports if report.state.active]


def requirement_by_lane(
    requirement_set: RequirementSetFacts,
    reports: Iterable[ReportFacts],
    sources: Mapping[str, str],
    *,
    lanes: Sequence[str],
    actors: Mapping[str, str] | None = None,
) -> CoverageMatrix:
    """Requirements down, lanes across: active reports assessed on each requirement, per lane.

    ``sources`` and ``actors`` map ids to lane ids. A report counts once per
    requirement it is assessed on, in the lane ``lane_of`` gives it. Columns
    are ``lanes`` in the order given, then ``unattributed``.
    """
    columns = (*lanes, UNATTRIBUTED)
    counts: Counter[tuple[str, str]] = Counter()
    totals: Counter[str] = Counter()
    counted: set[str] = set()
    wanted = requirement_set.requirement_ids()
    for report in _active(reports):
        lane = lane_of(report, sources, actors)
        column = lane if lane in columns else UNATTRIBUTED
        for requirement_id in set(report.requirement_ids) & wanted:
            counts[(requirement_id, column)] += 1
            totals[requirement_id] += 1
            counted.add(report.id)
    rows: list[CoverageRow] = []
    for requirement in requirement_set.requirements:
        total = totals[requirement.id]
        status = coverage_status(requirement.scanability, total)
        cells = tuple(
            CoverageCell(
                requirement.id,
                column,
                counts[(requirement.id, column)],
                cell_status(counts[(requirement.id, column)], status),
            )
            for column in columns
        )
        rows.append(
            CoverageRow(
                requirement.id, f"{requirement.code} {requirement.short}", cells, total, status
            )
        )
    return CoverageMatrix(columns, tuple(rows), tuple(sorted(counted)))


def taxonomy_by_count(
    taxonomy_axis: AxisFacts,
    requirement_set: RequirementSetFacts,
    reports: Iterable[ReportFacts],
) -> CoverageMatrix:
    """Taxonomy nodes down: active reports touching each node, and requirements expecting it.

    A report touches a node when one of its assessed requirements (in this
    set) expects the node, or when it carries a hazard whose family is the
    node. The single column is ``reports``. A node with no expecting
    requirement and no report is a blind spot; otherwise the status follows
    the count (quiet at zero).
    """
    by_id = {r.id: r for r in requirement_set.requirements}
    expected: Counter[str] = Counter(
        node_id for r in requirement_set.requirements for node_id in set(r.expected_coverage)
    )
    touched: dict[str, set[str]] = {}
    for report in _active(reports):
        nodes = {
            node_id
            for requirement_id in report.requirement_ids
            if requirement_id in by_id
            for node_id in by_id[requirement_id].expected_coverage
        }
        nodes |= set(report.hazard_families)
        for node_id in nodes:
            touched.setdefault(node_id, set()).add(report.id)
    rows: list[CoverageRow] = []
    counted: set[str] = set()
    for node in taxonomy_axis.nodes:
        ids = touched.get(node.id, set())
        counted |= ids
        count = len(ids)
        status = (
            CoverageStatus.BLIND_SPOT
            if expected[node.id] == 0 and count == 0
            else cell_status(count, CoverageStatus.QUIET)
        )
        cell = CoverageCell(node.id, "reports", count, status)
        rows.append(CoverageRow(node.id, node.name, (cell,), count, status, expected[node.id]))
    return CoverageMatrix(("reports",), tuple(rows), tuple(sorted(counted)))


def credibility_distribution(
    reports: Iterable[ReportFacts], run_id: str | None = None
) -> tuple[CredibilityCount, ...]:
    """Counts per credibility digit, 1 to 6, zeros included: the grade inflation check.

    With ``run_id``, only the reports that run created (its promotions);
    without, every report given.
    """
    tally = Counter(
        report.credibility
        for report in reports
        if run_id is None or report.created_run_id == run_id
    )
    return tuple(CredibilityCount(digit, tally[digit]) for digit in Credibility)


def lens_counts(reports: Iterable[ReportFacts]) -> dict[str, int]:
    """How many of the reports sit under each lens, by lens name."""
    return dict(sorted(Counter(report.lens for report in reports).items()))


def non_government_share(reports: Sequence[ReportFacts]) -> tuple[int, int]:
    """``(non-government, total)``: the mainstream bias guard's numbers for these reports."""
    others = sum(1 for report in reports if report.lens != GOVERNMENT_LENS)
    return others, len(reports)
