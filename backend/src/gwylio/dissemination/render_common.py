"""Pieces both renderers share: labels, ordering, report lines and the method note.

Every word comes from the ``Copy``. Ordering puts threats first, then two-way
(neutral) signals, then baseline evidence, then support: the optimism guard
made structural, so a reader meets the bad news before the good.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Final

from gwylio.dissemination.copy import Copy, fill
from gwylio.dissemination.inputs import (
    AssessmentView,
    ProductInputs,
    ReportView,
    RequirementSetView,
)
from gwylio.dissemination.model import Period, Section, Table
from gwylio.shared.coverage import CoverageStatus, Scanability
from gwylio.shared.values import CleanText
from gwylio.shared.vocabulary import Direction, DispositionOutcome, IndicatorState
from gwylio.shared.vocabulary import Level as ScoreLevel

__all__ = [
    "DIRECTION_ORDER",
    "codes",
    "count_list",
    "direction_label",
    "directions_text",
    "method_section",
    "period_name",
    "relevant",
    "report_rank",
    "scanability_label",
    "state_label",
    "status_label",
]

DIRECTION_ORDER: Final[tuple[Direction, ...]] = (
    Direction.THREATENS,
    Direction.NEUTRAL,
    Direction.INFORMS_BASELINE,
    Direction.SUPPORTS,
)
"""The order directions are listed in: threats and two-way signals first."""

_IMPACT_ORDER: Final[dict[ScoreLevel, int]] = {
    ScoreLevel.HIGH: 0,
    ScoreLevel.MEDIUM: 1,
    ScoreLevel.LOW: 2,
}


def direction_label(copy: Copy, direction: Direction) -> str:
    """How a direction reads."""
    labels = copy.common.directions
    return {
        Direction.THREATENS: labels.threatens,
        Direction.NEUTRAL: labels.neutral,
        Direction.INFORMS_BASELINE: labels.informs_baseline,
        Direction.SUPPORTS: labels.supports,
    }[direction]


def state_label(copy: Copy, state: IndicatorState) -> str:
    """How an indicator state reads."""
    return str(getattr(copy.common.states, state.value))


def status_label(copy: Copy, status: CoverageStatus) -> str:
    """How a coverage status reads."""
    return str(getattr(copy.common.statuses, status.value))


def scanability_label(copy: Copy, scanability: Scanability) -> str:
    """How a scanability value reads."""
    return str(getattr(copy.common.scanability, scanability.value))


def period_name(copy: Copy, period: Period) -> str:
    """``October 2026`` for a month period, the label itself for a year."""
    if period.is_month:
        month = period.start.value.month
        return f"{copy.common.months[month - 1]} {period.start.value.year}"
    return period.label


def count_list(copy: Copy, pairs: Iterable[tuple[str, int]], *, skip_zero: bool = True) -> str:
    """``supports 3, threatens 1``: label and count pairs as a running list, or ``none``."""
    items = [
        fill(copy.common.count_pair, label=label, count=count)
        for label, count in pairs
        if count or not skip_zero
    ]
    return copy.common.list_separator.join(items) if items else copy.common.none


def _rank(direction: Direction) -> int:
    return DIRECTION_ORDER.index(direction)


def relevant(report: ReportView, requirement_ids: Iterable[str]) -> tuple[AssessmentView, ...]:
    """The report's assessments on these requirements, threats first."""
    wanted = set(requirement_ids)
    return tuple(
        sorted(
            (a for a in report.assessments if a.requirement_id in wanted),
            key=lambda a: (_rank(a.direction), a.requirement_id),
        )
    )


def report_rank(report: ReportView, requirement_ids: Iterable[str]) -> tuple[int, int, str]:
    """Sort key: the most worrying direction on these requirements, then impact, then id."""
    found = relevant(report, requirement_ids)
    worst = min((_rank(a.direction) for a in found), default=len(DIRECTION_ORDER))
    return (worst, _IMPACT_ORDER[report.potential_impact], report.id)


def directions_text(
    copy: Copy,
    requirement_set: RequirementSetView,
    report: ReportView,
    requirement_ids: Iterable[str],
) -> str:
    """``SI1 threatens, SI3 supports``: the report's assessments on these requirements."""
    order = [r.id for r in requirement_set.requirements]
    found = sorted(
        relevant(report, requirement_ids),
        key=lambda a: (_rank(a.direction), order.index(a.requirement_id)),
    )
    tags = [
        fill(
            copy.common.direction_tag,
            code=requirement_set.requirement(a.requirement_id).code,
            direction=direction_label(copy, a.direction),
        )
        for a in found
    ]
    return copy.common.list_separator.join(tags) if tags else copy.common.none


def codes(copy: Copy, requirement_set: RequirementSetView, requirement_ids: Sequence[str]) -> str:
    """The requirement codes as a running list, in set order."""
    wanted = set(requirement_ids)
    return copy.common.list_separator.join(
        r.code for r in requirement_set.requirements if r.id in wanted
    )


def _runs_table(copy: Copy, inputs: ProductInputs) -> Table:
    m = copy.method
    yes, no = copy.common.yes, copy.common.no
    return Table(
        headers=tuple(
            CleanText(h)
            for h in (
                m.header_run,
                m.header_started,
                m.header_instrument,
                m.header_raw,
                m.header_unique,
                m.header_new,
                m.header_reinforcements,
                m.header_requests,
                m.header_budget,
            )
        ),
        rows=tuple(
            tuple(
                CleanText(str(cell))
                for cell in (
                    run.run_id,
                    run.started_on,
                    run.instrument_version,
                    run.raw,
                    run.unique,
                    run.new,
                    run.reinforcements,
                    run.requests_made,
                    yes if run.budget_exhausted else no,
                )
            )
            for run in inputs.method.runs
        ),
    )


def method_section(copy: Copy, inputs: ProductInputs) -> tuple[Section, CleanText]:
    """The method note as a section, and as one text for the product record."""
    m = copy.method
    facts = inputs.method
    body: list[CleanText] = []
    tables: list[Table] = []
    if facts.runs:
        body.append(fill(m.runs, count=len(facts.runs)))
        tables.append(_runs_table(copy, inputs))
        counts = dict(facts.dispositions)
        body.append(
            fill(
                m.dispositions,
                promoted=counts.get(DispositionOutcome.PROMOTED, 0),
                rejected=counts.get(DispositionOutcome.REJECTED, 0),
                duplicate=counts.get(DispositionOutcome.DUPLICATE, 0),
                deferred=counts.get(DispositionOutcome.DEFERRED, 0),
                reinforcement=counts.get(DispositionOutcome.REINFORCEMENT, 0),
                undisposed=facts.undisposed,
            )
        )
    else:
        body.append(CleanText(m.no_runs))
    if facts.promotions:
        percent = round(100 * facts.non_government / facts.promotions)
        body.append(
            fill(
                m.promotions,
                count=facts.promotions,
                non_government=facts.non_government,
                share=fill(copy.common.share, percent=percent),
            )
        )
        body.append(fill(m.credibility, count=facts.promotions))
        tables.append(
            Table(
                headers=(
                    CleanText(copy.common.header_credibility),
                    CleanText(copy.common.header_label),
                    CleanText(m.header_reports),
                ),
                rows=tuple(
                    (
                        CleanText(str(int(digit))),
                        CleanText(copy.common.credibility.label(int(digit))),
                        CleanText(str(count)),
                    )
                    for digit, count in facts.credibility
                ),
            )
        )
    else:
        body.append(CleanText(m.no_promotions))
    if facts.instrument_versions:
        body.append(fill(m.instrument, versions=", ".join(facts.instrument_versions)))
    else:
        body.append(fill(m.instrument_current, version=facts.current_instrument_version))
    if facts.blind_spots:
        body.append(fill(m.blind_spots, codes=copy.common.list_separator.join(facts.blind_spots)))
    else:
        body.append(CleanText(m.no_blind_spots))
    body.append(CleanText(m.streetlight))
    body.append(CleanText(copy.common.undercount))
    section = Section(CleanText(m.heading), body=tuple(body), tables=tuple(tables))
    return section, CleanText("\n\n".join(body))
