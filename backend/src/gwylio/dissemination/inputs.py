"""What the renderers read: plain, frozen views of the register and the evaluation.

The Dissemination context imports only ``gwylio.shared`` and itself, so the
infrastructure layer builds these views from the repositories, the
configuration and the Evaluation context's outputs, and hands them in. The
renderers compute nothing a view already carries: the coverage matrices and
the method note's numbers arrive counted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from gwylio.shared.coverage import CoverageStatus, Scanability
from gwylio.shared.values import IsoDate
from gwylio.shared.vocabulary import (
    Credibility,
    Direction,
    DispositionOutcome,
    IndicatorState,
)
from gwylio.shared.vocabulary import Level as ScoreLevel

__all__ = [
    "FINDING_KINDS",
    "HISTORY_FADED",
    "HISTORY_STATE_CHANGES",
    "HISTORY_VERIFIED",
    "AssessmentView",
    "FindingView",
    "GroupView",
    "HistoryView",
    "LaneMatrixView",
    "LaneRowView",
    "MethodFacts",
    "NodeCountsView",
    "NodeRowView",
    "ProductInputs",
    "ReportView",
    "RequirementSetView",
    "RequirementView",
    "RunView",
]

HISTORY_STATE_CHANGES: Final[frozenset[str]] = frozenset({"state_changed", "revived"})
"""History kinds that record a lifecycle state change other than a fade."""
HISTORY_FADED: Final[str] = "faded"
"""The history kind the sweep records when it fades a report."""
HISTORY_VERIFIED: Final[str] = "verified"
"""The history kind a verification records."""
FINDING_KINDS: Final[tuple[str, ...]] = (
    "passed_horizon",
    "future_language",
    "stale_verification",
    "never_verified",
)
"""The date check's finding kinds, in the order products list them."""


@dataclass(frozen=True, slots=True)
class RequirementView:
    """One requirement, with its scanability and the note that explains it."""

    id: str
    code: str
    name: str
    short: str
    scanability: Scanability
    scanability_note: str


@dataclass(frozen=True, slots=True)
class GroupView:
    """One requirement group; ``kind`` is ``wbo`` or ``impact``."""

    id: str
    kind: str
    name: str
    members: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RequirementSetView:
    """The requirement set a product covers."""

    id: str
    name: str
    version: str
    requirements: tuple[RequirementView, ...]
    groups: tuple[GroupView, ...]

    def requirement(self, requirement_id: str) -> RequirementView:
        """The requirement with this id, or ``KeyError``."""
        for requirement in self.requirements:
            if requirement.id == requirement_id:
                return requirement
        raise KeyError(requirement_id)

    def wbo_groups(self) -> tuple[GroupView, ...]:
        """The well-being objective groups, in set order."""
        return tuple(group for group in self.groups if group.kind == "wbo")


@dataclass(frozen=True, slots=True)
class AssessmentView:
    """One assessment of a report against a requirement."""

    requirement_id: str
    direction: Direction


@dataclass(frozen=True, slots=True)
class HistoryView:
    """One dated history entry; ``kind`` is the history kind's value, such as ``verified``."""

    on: IsoDate
    kind: str


@dataclass(frozen=True, slots=True)
class ReportView:
    """One report as a product cites it."""

    id: str
    title: str
    grading: str
    credibility: Credibility
    state: IndicatorState
    lens: str
    assessments: tuple[AssessmentView, ...]
    potential_impact: ScoreLevel
    created_on: IsoDate
    history: tuple[HistoryView, ...]


@dataclass(frozen=True, slots=True)
class FindingView:
    """One date check finding; ``kind`` is the finding kind's value."""

    report_id: str
    kind: str
    detail: str


@dataclass(frozen=True, slots=True)
class RunView:
    """One scan run and what was done with its candidates."""

    run_id: str
    started_on: IsoDate
    instrument_version: str
    raw: int
    unique: int
    new: int
    reinforcements: int
    requests_made: int
    budget_exhausted: bool


@dataclass(frozen=True, slots=True)
class MethodFacts:
    """The method note's numbers for one period, counted by the Evaluation context.

    ``promotions`` counts the reports created in the period and
    ``non_government`` those of them outside government lanes;
    ``credibility`` holds the period's reports per digit, 1 to 6;
    ``dispositions`` counts the final dispositions of the period's runs'
    candidates; ``undisposed`` the new candidates nobody has judged;
    ``instrument_versions`` the versions the period's runs used;
    ``blind_spots`` the labels of the requirements that read blind spot.
    """

    runs: tuple[RunView, ...]
    dispositions: tuple[tuple[DispositionOutcome, int], ...]
    undisposed: int
    promotions: int
    non_government: int
    credibility: tuple[tuple[Credibility, int], ...]
    instrument_versions: tuple[str, ...]
    current_instrument_version: str
    blind_spots: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LaneRowView:
    """One requirement row of the requirement by lane matrix."""

    label: str
    counts: tuple[int, ...]
    total: int
    status: CoverageStatus


@dataclass(frozen=True, slots=True)
class LaneMatrixView:
    """Requirements down, lanes across.

    ``columns`` are the lane names in order; each row's ``counts`` has one more
    entry than ``columns``: the last counts the unattributed reports.
    """

    columns: tuple[str, ...]
    rows: tuple[LaneRowView, ...]

    def __post_init__(self) -> None:
        for row in self.rows:
            if len(row.counts) != len(self.columns) + 1:
                raise ValueError(f"row {row.label} needs one count per lane plus unattributed")


@dataclass(frozen=True, slots=True)
class NodeRowView:
    """One taxonomy node: requirements expecting it, active reports touching it, status."""

    label: str
    expected: int
    count: int
    status: CoverageStatus


@dataclass(frozen=True, slots=True)
class NodeCountsView:
    """One taxonomy axis counted node by node."""

    axis_name: str
    rows: tuple[NodeRowView, ...]


@dataclass(frozen=True, slots=True)
class ProductInputs:
    """Everything a renderer reads for one requirement set and one period.

    ``reports`` holds every report assessed against a requirement of the set,
    in any state; ``active_counts`` the active reports per requirement id
    (what the coverage status counts); ``default_set`` whether the set is the
    first configured one (its products carry no set suffix).
    """

    requirement_set: RequirementSetView
    reports: tuple[ReportView, ...]
    findings: tuple[FindingView, ...]
    method: MethodFacts
    lane_matrix: LaneMatrixView
    node_counts: tuple[NodeCountsView, ...]
    active_counts: tuple[tuple[str, int], ...]
    default_set: bool = True

    def active_count(self, requirement_id: str) -> int:
        """Active reports assessed against one requirement."""
        return dict(self.active_counts).get(requirement_id, 0)
