"""Helpers shared by test modules: project paths and small domain builders."""

from __future__ import annotations

from pathlib import Path
from typing import Final

from gwylio.direction.model import GroupKind, Requirement, RequirementGroup, Scanability
from gwylio.reference.model import (
    HAZARD_FAMILIES_AXIS,
    SONARR_AXIS,
    NodeKind,
    Taxonomy,
    TaxonomyAxis,
    TaxonomyNode,
)
from gwylio.shared.values import CleanText, KebabId

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
"""The gwylio/ directory: the repository root holding config/ and backend/."""


def node(node_id: str, kind: NodeKind = NodeKind.ECOSYSTEM) -> TaxonomyNode:
    return TaxonomyNode(KebabId(node_id), CleanText(node_id.replace("-", " ").title()), kind)


def small_taxonomy() -> Taxonomy:
    """Two axes: three SoNaRR nodes and two hazard families."""
    return Taxonomy(
        (
            TaxonomyAxis(
                SONARR_AXIS,
                CleanText("SoNaRR"),
                (node("marine"), node("freshwaters"), node("soils", NodeKind.RESOURCE)),
            ),
            TaxonomyAxis(
                HAZARD_FAMILIES_AXIS,
                CleanText("Hazard families"),
                (
                    node("wildfire", NodeKind.HAZARD_FAMILY),
                    node("plant-tree-disease", NodeKind.HAZARD_FAMILY),
                ),
            ),
        )
    )


def requirement(
    code: str,
    *,
    scanability: Scanability = Scanability.HIGH,
    coverage: tuple[str, ...] = (),
    short: str = "A short name",
) -> Requirement:
    return Requirement(
        code=code,
        id=KebabId(code.lower()),
        name=CleanText(f"Requirement {code}"),
        short=CleanText(short),
        scanability=scanability,
        scanability_note=CleanText("A note."),
        expected_coverage=tuple(KebabId(c) for c in coverage),
    )


def group(
    group_id: str,
    members: tuple[str, ...],
    kind: GroupKind = GroupKind.IMPACT,
    related: tuple[str, ...] = (),
) -> RequirementGroup:
    return RequirementGroup(
        id=KebabId(group_id),
        kind=kind,
        name=CleanText(group_id.upper()),
        members=tuple(KebabId(m) for m in members),
        related_groups=tuple(KebabId(r) for r in related),
    )
