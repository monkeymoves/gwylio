"""The strategic assessment: the annual picture for one requirement set.

``render_strategic`` assembles the product from the views and the copy; no
prose is generated. The sections:

- Purpose: standing paragraphs from the copy.
- Standing picture: per requirement, the active reports by direction and by
  state, the grading spread, the coverage status, the scanability note
  verbatim, and the three active reports with the highest potential impact
  (threats first among equals). Matured reports are named as settled context
  and not counted as active.
- Questions: per well-being objective, one question per active report that
  threatens a member requirement or cuts both ways, phrased from the copy's
  template. Questions about the world, never recommendations.
- Coverage audit: the requirement by lane matrix and the taxonomy counts, as
  Markdown tables.
- Method note: as the INTSUM's, for the year.
"""

from __future__ import annotations

from collections import Counter

from gwylio.dissemination.copy import Copy, fill
from gwylio.dissemination.inputs import (
    LaneMatrixView,
    NodeCountsView,
    ProductInputs,
    ReportView,
    RequirementView,
)
from gwylio.dissemination.model import Level, Period, Product, Section, Table, product_id
from gwylio.dissemination.render_common import (
    DIRECTION_ORDER,
    codes,
    count_list,
    direction_label,
    directions_text,
    method_section,
    period_name,
    relevant,
    report_rank,
    scanability_label,
    state_label,
    status_label,
)
from gwylio.shared.coverage import CoverageStatus, coverage_status
from gwylio.shared.values import CleanText, IsoDate, KebabId
from gwylio.shared.vocabulary import Direction, IndicatorState
from gwylio.shared.vocabulary import Level as ScoreLevel

__all__ = ["TOP_REPORTS", "render_strategic"]

TOP_REPORTS = 3
"""How many of the highest potential impact reports each requirement names."""

_QUESTION_DIRECTIONS = frozenset({Direction.THREATENS, Direction.NEUTRAL})
_TRAILING = ".?!:;, "


def _impact(copy: Copy, level: ScoreLevel) -> str:
    s = copy.strategic
    return {ScoreLevel.HIGH: s.impact_high, ScoreLevel.MEDIUM: s.impact_medium}.get(
        level, s.impact_low
    )


def _requirement(
    copy: Copy, inputs: ProductInputs, requirement: RequirementView
) -> tuple[Section, list[str]]:
    s = copy.strategic
    rs = inputs.requirement_set
    ids = [requirement.id]
    assessed = [r for r in inputs.reports if relevant(r, ids)]
    active = [r for r in assessed if r.state.active]
    matured = [r for r in assessed if r.state is IndicatorState.MATURED]
    count = inputs.active_count(requirement.id)
    status = coverage_status(requirement.scanability, count)
    directions = Counter(a.direction for r in active for a in relevant(r, ids))
    states = Counter(r.state for r in active)
    gradings = Counter(r.grading for r in active)
    body = [
        fill(s.status_line, status=status_label(copy, status), active=count),
        fill(
            s.directions_line,
            directions=count_list(
                copy, ((direction_label(copy, d), directions[d]) for d in DIRECTION_ORDER)
            ),
        ),
        fill(
            s.states_line,
            states=count_list(
                copy,
                ((state_label(copy, st), states[st]) for st in IndicatorState if st.active),
            ),
        ),
        fill(s.grading_line, gradings=count_list(copy, sorted(gradings.items()))),
    ]
    if matured:
        body.append(fill(s.matured_line, count=len(matured)))
    body.append(
        fill(
            s.scanability_line,
            scanability=scanability_label(copy, requirement.scanability),
            note=requirement.scanability_note,
        )
    )
    if status is CoverageStatus.BLIND_SPOT:
        body.append(CleanText(copy.common.blind_spot_rule))
    top = sorted(active, key=lambda r: report_rank_by_impact(r, ids))[:TOP_REPORTS]
    if top:
        body.append(CleanText(s.top_intro))
    bullets = tuple(
        fill(
            s.top_line,
            grading=r.grading,
            title=r.title,
            directions=directions_text(copy, rs, r, ids),
            state=state_label(copy, r.state),
            impact=_impact(copy, r.potential_impact),
            report_id=r.id,
        )
        for r in top
    )
    heading = fill(s.requirement_heading, code=requirement.code, name=requirement.name)
    section = Section(heading, body=tuple(body), bullets=bullets, depth=3)
    return section, [r.id for r in active]


def report_rank_by_impact(report: ReportView, ids: list[str]) -> tuple[int, int, str]:
    """Sort key for the top reports: potential impact first, then threats first, then id."""
    worst, impact, report_id = report_rank(report, ids)
    return (impact, worst, report_id)


def _questions(copy: Copy, inputs: ProductInputs) -> list[Section]:
    s = copy.strategic
    rs = inputs.requirement_set
    sections = [Section(CleanText(s.questions_heading), body=(CleanText(s.questions_intro),))]
    for group in rs.wbo_groups():
        members = list(group.members)
        asking = sorted(
            (
                r
                for r in inputs.reports
                if r.state.active
                and any(a.direction in _QUESTION_DIRECTIONS for a in relevant(r, members))
            ),
            key=lambda r: report_rank(r, members),
        )
        questions = tuple(
            fill(
                s.question,
                title=r.title.rstrip(_TRAILING),
                codes=codes(
                    copy,
                    rs,
                    [
                        a.requirement_id
                        for a in relevant(r, members)
                        if a.direction in _QUESTION_DIRECTIONS
                    ],
                ),
                report_id=r.id,
            )
            for r in asking
        )
        sections.append(
            Section(
                fill(s.group_heading, name=group.name, codes=codes(copy, rs, members)),
                body=() if questions else (CleanText(s.questions_none),),
                bullets=questions,
                depth=3,
            )
        )
    return sections


def _lane_table(copy: Copy, matrix: LaneMatrixView) -> Table:
    show_unattributed = any(row.counts[-1] for row in matrix.rows)
    width = len(matrix.columns) + (1 if show_unattributed else 0)
    columns = (*matrix.columns, copy.common.unattributed)[:width]
    c = copy.common
    return Table(
        headers=tuple(
            CleanText(h) for h in (c.header_requirement, *columns, c.header_total, c.header_status)
        ),
        rows=tuple(
            (
                CleanText(row.label),
                *(CleanText(str(n)) for n in row.counts[:width]),
                CleanText(str(row.total)),
                CleanText(status_label(copy, row.status)),
            )
            for row in matrix.rows
        ),
    )


def _node_table(copy: Copy, view: NodeCountsView) -> Table:
    c = copy.common
    return Table(
        headers=tuple(
            CleanText(h)
            for h in (c.header_node, c.header_expected, c.header_reports, c.header_status)
        ),
        rows=tuple(
            (
                CleanText(row.label),
                CleanText(str(row.expected)),
                CleanText(str(row.count)),
                CleanText(status_label(copy, row.status)),
            )
            for row in view.rows
        ),
    )


def _coverage(copy: Copy, inputs: ProductInputs) -> list[Section]:
    s = copy.strategic
    sections = [
        Section(CleanText(s.coverage_heading), body=(CleanText(s.coverage_intro),)),
        Section(
            CleanText(s.lane_matrix_heading),
            body=(CleanText(s.lane_matrix_note),),
            tables=(_lane_table(copy, inputs.lane_matrix),),
            depth=3,
        ),
    ]
    sections.extend(
        Section(
            fill(s.taxonomy_heading, axis=view.axis_name),
            body=(CleanText(s.taxonomy_note),),
            tables=(_node_table(copy, view),),
            depth=3,
        )
        for view in inputs.node_counts
    )
    return sections


def render_strategic(
    inputs: ProductInputs, period: Period, generated_on: IsoDate, copy: Copy
) -> Product:
    """The strategic assessment for ``period``, as of ``generated_on``, from the views and copy."""
    s = copy.strategic
    rs = inputs.requirement_set
    picture = [Section(CleanText(s.picture_heading), body=(CleanText(s.picture_intro),))]
    cited: set[str] = set()
    for requirement in rs.requirements:
        section, ids = _requirement(copy, inputs, requirement)
        picture.append(section)
        cited |= set(ids)
    method, note = method_section(copy, inputs)
    sections = (
        Section(CleanText(s.purpose_heading), body=tuple(CleanText(p) for p in s.purpose)),
        *picture,
        *_questions(copy, inputs),
        *_coverage(copy, inputs),
        method,
    )
    return Product(
        id=product_id(Level.STRATEGIC, period, rs.id, inputs.default_set),
        level=Level.STRATEGIC,
        requirement_set_id=KebabId(rs.id),
        period=period,
        generated_on=generated_on,
        title=fill(s.title, period=period_name(copy, period), set_name=rs.name),
        lead=(
            fill(copy.common.set_line, name=rs.name, version=rs.version),
            fill(
                copy.common.period_line,
                start=period.start,
                end=period.end,
                generated_on=generated_on,
            ),
        ),
        sections=sections,
        report_ids=tuple(KebabId(i) for i in sorted(cited)),
        method_note=note,
    )
