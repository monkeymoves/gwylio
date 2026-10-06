"""The operational intelligence summary (INTSUM): what moved in the register in one month.

``render_intsum`` assembles the product from the views and the copy; no prose
is generated, every sentence is a copy template filled with numbers and
titles. The sections:

- Summary: new reports (created in the period), lifecycle state changes
  (history entries), reports faded and reports verified, and the directions
  of the assessments on every report that moved; one sentence each, then the
  numbers in a table.
- What moved: per well-being objective, every report created or changed in
  the period (any history entry inside it), each on one line with its
  grading, title, directions and state. Threats and two-way signals come
  first within each list. Reports outside every objective get a list of
  their own.
- Quiet and blind spots: the requirements nothing moved on, each labelled by
  ``coverage_status`` for no movement, with the standing sentence that a
  blind spot is not quiet.
- Verification due: the date check's findings, by kind.
- Method note: the period's runs, dispositions, promotions and their
  non-government share, the credibility spread, the instrument version and
  the known blind spots.
"""

from __future__ import annotations

from collections import Counter

from gwylio.dissemination.copy import Copy, FindingCopy, fill
from gwylio.dissemination.inputs import (
    FINDING_KINDS,
    HISTORY_FADED,
    HISTORY_STATE_CHANGES,
    HISTORY_VERIFIED,
    ProductInputs,
    ReportView,
)
from gwylio.dissemination.model import Level, Period, Product, Section, Table, product_id
from gwylio.dissemination.render_common import (
    DIRECTION_ORDER,
    codes,
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
from gwylio.shared.coverage import coverage_status
from gwylio.shared.values import CleanText, IsoDate, KebabId
from gwylio.shared.vocabulary import Direction

__all__ = ["render_intsum"]


def _moved(report: ReportView, period: Period) -> bool:
    return period.contains(report.created_on) or any(period.contains(h.on) for h in report.history)


def _report_line(
    copy: Copy, inputs: ProductInputs, report: ReportView, ids: list[str]
) -> CleanText:
    return fill(
        copy.intsum.report_line,
        grading=report.grading,
        title=report.title,
        directions=directions_text(copy, inputs.requirement_set, report, ids),
        state=state_label(copy, report.state),
        report_id=report.id,
    )


def _summary(copy: Copy, inputs: ProductInputs, period: Period, moved: list[ReportView]) -> Section:
    c = copy.intsum
    set_ids = [r.id for r in inputs.requirement_set.requirements]
    reports = inputs.reports
    new = sum(1 for r in reports if period.contains(r.created_on))
    entries = [(r.id, h.kind) for r in reports for h in r.history if period.contains(h.on)]
    changes = sum(1 for _, kind in entries if kind in HISTORY_STATE_CHANGES)
    faded = len({rid for rid, kind in entries if kind == HISTORY_FADED})
    verified = len({rid for rid, kind in entries if kind == HISTORY_VERIFIED})
    directions = Counter(a.direction for r in moved for a in relevant(r, set_ids))
    body = (
        fill(c.summary_new, count=new),
        fill(c.summary_state_changes, count=changes),
        fill(c.summary_faded, count=faded),
        fill(c.summary_verified, count=verified),
        fill(
            c.summary_directions,
            threatens=directions[Direction.THREATENS],
            neutral=directions[Direction.NEUTRAL],
            informs_baseline=directions[Direction.INFORMS_BASELINE],
            supports=directions[Direction.SUPPORTS],
        ),
    )
    rows = [
        (c.measure_new, new),
        (c.measure_state_changes, changes),
        (c.measure_faded, faded),
        (c.measure_verified, verified),
        *(
            (fill(c.measure_direction, direction=direction_label(copy, d)), directions[d])
            for d in DIRECTION_ORDER
        ),
    ]
    table = Table(
        headers=(CleanText(copy.common.header_measure), CleanText(copy.common.header_count)),
        rows=tuple((CleanText(label), CleanText(str(count))) for label, count in rows),
    )
    return Section(CleanText(c.summary_heading), body=body, tables=(table,))


def _what_moved(copy: Copy, inputs: ProductInputs, moved: list[ReportView]) -> list[Section]:
    c = copy.intsum
    rs = inputs.requirement_set
    sections = [Section(CleanText(c.moved_heading), body=(CleanText(c.moved_intro),))]
    in_groups: set[str] = set()
    for group in rs.wbo_groups():
        members = list(group.members)
        in_groups |= set(members)
        listed = sorted(
            (r for r in moved if relevant(r, members)), key=lambda r: report_rank(r, members)
        )
        heading = fill(c.group_heading, name=group.name, codes=codes(copy, rs, members))
        sections.append(
            Section(
                heading,
                body=() if listed else (CleanText(c.group_empty),),
                bullets=tuple(_report_line(copy, inputs, r, members) for r in listed),
                depth=3,
            )
        )
    outside_ids = [r.id for r in rs.requirements if r.id not in in_groups]
    outside = sorted(
        (r for r in moved if relevant(r, outside_ids) and not relevant(r, sorted(in_groups))),
        key=lambda r: report_rank(r, outside_ids),
    )
    if outside:
        sections.append(
            Section(
                CleanText(c.outside_heading),
                bullets=tuple(_report_line(copy, inputs, r, outside_ids) for r in outside),
                depth=3,
            )
        )
    return sections


def _quiet(copy: Copy, inputs: ProductInputs, moved: list[ReportView]) -> Section:
    c = copy.intsum
    touched = {a.requirement_id for r in moved for a in r.assessments}
    lines = tuple(
        fill(
            c.quiet_line,
            code=r.code,
            short=r.short,
            status=status_label(copy, coverage_status(r.scanability, 0)),
            active=inputs.active_count(r.id),
            scanability=scanability_label(copy, r.scanability),
        )
        for r in inputs.requirement_set.requirements
        if r.id not in touched
    )
    body = (
        CleanText(copy.common.blind_spot_rule),
        CleanText(c.quiet_intro if lines else c.quiet_none),
    )
    return Section(CleanText(c.quiet_heading), body=body, bullets=lines)


def _verification(copy: Copy, inputs: ProductInputs, today: IsoDate) -> list[Section]:
    c = copy.intsum
    findings = inputs.findings
    titles = {r.id: r.title for r in inputs.reports}
    if not findings:
        return [Section(CleanText(c.verification_heading), body=(CleanText(c.verification_none),))]
    intro = fill(
        c.verification_intro,
        count=len(findings),
        reports=len({f.report_id for f in findings}),
        today=today,
    )
    sections = [Section(CleanText(c.verification_heading), body=(intro,))]
    for kind in FINDING_KINDS:
        group = [f for f in findings if f.kind == kind]
        if not group:
            continue
        words: FindingCopy = getattr(c, kind)
        sections.append(
            Section(
                CleanText(words.heading),
                body=(CleanText(words.meaning),),
                bullets=tuple(
                    fill(
                        c.finding_line,
                        title=titles.get(f.report_id, f.report_id),
                        report_id=f.report_id,
                        detail=f.detail,
                    )
                    for f in group
                ),
                depth=3,
            )
        )
    return sections


def render_intsum(
    inputs: ProductInputs, period: Period, generated_on: IsoDate, copy: Copy
) -> Product:
    """The INTSUM for ``period``, as of ``generated_on``, from the views and the copy."""
    rs = inputs.requirement_set
    moved = [r for r in inputs.reports if _moved(r, period)]
    method, note = method_section(copy, inputs)
    sections = (
        _summary(copy, inputs, period, moved),
        *_what_moved(copy, inputs, moved),
        _quiet(copy, inputs, moved),
        *_verification(copy, inputs, generated_on),
        method,
    )
    cited = {r.id for r in moved} | {f.report_id for f in inputs.findings}
    return Product(
        id=product_id(Level.OPERATIONAL, period, rs.id, inputs.default_set),
        level=Level.OPERATIONAL,
        requirement_set_id=KebabId(rs.id),
        period=period,
        generated_on=generated_on,
        title=fill(copy.intsum.title, period=period_name(copy, period), set_name=rs.name),
        lead=(
            fill(copy.common.set_line, name=rs.name, version=rs.version),
            fill(
                copy.common.period_line,
                start=period.start,
                end=period.end,
                generated_on=generated_on,
            ),
            CleanText(copy.intsum.purpose),
        ),
        sections=sections,
        report_ids=tuple(KebabId(i) for i in sorted(cited)),
        method_note=note,
    )
