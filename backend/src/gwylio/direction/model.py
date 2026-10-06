"""Requirement sets: the Priority Intelligence Requirements the system scans against.

Pure, frozen domain objects with no input or output. A ``RequirementSet``
holds requirements and the groups (impacts, well-being objectives) that
organise them. ``validate`` checks the set against a taxonomy, which this
context sees only through the small ``NodeIndex`` protocol so that it never
imports the Reference context.
"""

from __future__ import annotations

import re
from collections.abc import Set
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final, Protocol

from gwylio.shared.coverage import Scanability
from gwylio.shared.errors import DomainError, DuplicateId, UnknownReference
from gwylio.shared.values import CleanText, KebabId

__all__ = [
    "REQUIREMENT_CODE_PATTERN",
    "SHORT_NAME_MAX_WORDS",
    "GroupKind",
    "NodeIndex",
    "Requirement",
    "RequirementGroup",
    "RequirementSet",
    "Scanability",
]

REQUIREMENT_CODE_PATTERN: Final[str] = r"^[A-Z][A-Z0-9]{0,15}$"
"""A requirement code such as ``SI1``: an upper-case letter then letters or digits."""
SHORT_NAME_MAX_WORDS: Final[int] = 6
"""The most words a requirement's short name may have."""

_CODE_RE: Final[re.Pattern[str]] = re.compile(REQUIREMENT_CODE_PATTERN)
_SCOPE: Final[str] = "requirement_set"


class GroupKind(StrEnum):
    """What a requirement group stands for."""

    IMPACT = "impact"
    WBO = "wbo"


class NodeIndex(Protocol):
    """What a requirement set needs to know about a taxonomy: which node ids exist."""

    def node_ids(self) -> Set[str]:
        """Every node identifier in the taxonomy."""
        ...


@dataclass(frozen=True, slots=True)
class Requirement:
    """One Priority Intelligence Requirement (PIR), such as one NRW strategic indicator."""

    code: str
    id: KebabId
    name: CleanText
    short: CleanText
    scanability: Scanability
    scanability_note: CleanText
    keywords: tuple[CleanText, ...] = ()
    expected_coverage: tuple[KebabId, ...] = ()
    metric_sources: tuple[CleanText, ...] = ()
    development: bool = False

    def __post_init__(self) -> None:
        if not _CODE_RE.fullmatch(self.code):
            raise ValueError(
                f"requirement code '{self.code}' must be an upper-case letter followed by up "
                "to fifteen upper-case letters or digits, such as 'SI1'"
            )
        words = len(self.short.split())
        if words == 0:
            raise ValueError(f"requirement {self.code} needs a short name")
        if words > SHORT_NAME_MAX_WORDS:
            raise ValueError(
                f"requirement {self.code} short name has {words} words, "
                f"the most is {SHORT_NAME_MAX_WORDS}: '{self.short}'"
            )


@dataclass(frozen=True, slots=True)
class RequirementGroup:
    """A named set of requirements: an impact statement or a well-being objective."""

    id: KebabId
    kind: GroupKind
    name: CleanText
    members: tuple[KebabId, ...]
    statement: CleanText | None = None
    note: CleanText | None = None
    related_groups: tuple[KebabId, ...] = ()


@dataclass(frozen=True, slots=True)
class RequirementSet:
    """A list of requirements and the groups that organise them."""

    id: KebabId
    name: CleanText
    version: CleanText
    source_doc: CleanText
    requirements: tuple[Requirement, ...]
    groups: tuple[RequirementGroup, ...] = ()
    _by_id: dict[str, Requirement] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        index: dict[str, Requirement] = {}
        for requirement in self.requirements:
            index.setdefault(requirement.id, requirement)
        object.__setattr__(self, "_by_id", index)

    def requirement(self, requirement_id: str) -> Requirement:
        """The requirement with this identifier, or ``UnknownReference``."""
        try:
            return self._by_id[requirement_id]
        except KeyError:
            raise UnknownReference(
                f"requirement set '{self.id}' has no requirement '{requirement_id}'",
                scope=_SCOPE,
            ) from None

    def requirement_by_code(self, code: str) -> Requirement:
        """The requirement with this code, such as ``SI4``, or ``UnknownReference``."""
        for requirement in self.requirements:
            if requirement.code == code:
                return requirement
        raise UnknownReference(
            f"requirement set '{self.id}' has no requirement coded '{code}'", scope=_SCOPE
        )

    def requirement_ids(self) -> frozenset[str]:
        """Every requirement identifier in the set."""
        return frozenset(self._by_id)

    def groups_of_kind(self, kind: GroupKind) -> tuple[RequirementGroup, ...]:
        """The groups of one kind, in the order the set lists them."""
        return tuple(group for group in self.groups if group.kind is kind)

    def groups_of(self, requirement_id: str) -> tuple[RequirementGroup, ...]:
        """The groups that list this requirement as a member."""
        return tuple(group for group in self.groups if requirement_id in group.members)

    def find_problems(self, taxonomy: NodeIndex) -> tuple[DomainError, ...]:
        """Every broken rule in the set, in a stable order."""
        problems: list[DomainError] = []
        problems.extend(self._duplicate_problems())
        nodes = taxonomy.node_ids()
        for r, requirement in enumerate(self.requirements):
            for c, node_id in enumerate(requirement.expected_coverage):
                if node_id not in nodes:
                    problems.append(
                        UnknownReference(
                            f"requirement {requirement.code} expects coverage of unknown "
                            f"taxonomy node '{node_id}'",
                            scope=_SCOPE,
                            location=f"requirements[{r}].expected_coverage[{c}]",
                        )
                    )
        group_ids = {group.id for group in self.groups}
        for g, group in enumerate(self.groups):
            for m, member in enumerate(group.members):
                if member not in self._by_id:
                    problems.append(
                        UnknownReference(
                            f"group '{group.id}' names unknown requirement '{member}'",
                            scope=_SCOPE,
                            location=f"groups[{g}].members[{m}]",
                        )
                    )
            for n, related in enumerate(group.related_groups):
                if related not in group_ids or related == group.id:
                    problems.append(
                        UnknownReference(
                            f"group '{group.id}' names unknown related group '{related}'",
                            scope=_SCOPE,
                            location=f"groups[{g}].related_groups[{n}]",
                        )
                    )
        return tuple(problems)

    def validate(self, taxonomy: NodeIndex) -> None:
        """Raise the first broken rule (``UnknownReference`` or ``DuplicateId``), if any."""
        problems = self.find_problems(taxonomy)
        if problems:
            raise problems[0]

    def _duplicate_problems(self) -> list[DomainError]:
        problems: list[DomainError] = []
        codes: set[str] = set()
        ids: set[str] = set()
        for r, requirement in enumerate(self.requirements):
            if requirement.code in codes:
                problems.append(
                    DuplicateId(
                        f"requirement code '{requirement.code}' is used twice",
                        scope=_SCOPE,
                        location=f"requirements[{r}].code",
                    )
                )
            if requirement.id in ids:
                problems.append(
                    DuplicateId(
                        f"requirement id '{requirement.id}' is used twice",
                        scope=_SCOPE,
                        location=f"requirements[{r}].id",
                    )
                )
            codes.add(requirement.code)
            ids.add(requirement.id)
        group_ids: set[str] = set()
        for g, group in enumerate(self.groups):
            if group.id in group_ids or group.id in ids:
                problems.append(
                    DuplicateId(
                        f"group id '{group.id}' is already used by another group or requirement",
                        scope=_SCOPE,
                        location=f"groups[{g}].id",
                    )
                )
            group_ids.add(group.id)
            members: set[str] = set()
            for m, member in enumerate(group.members):
                if member in members:
                    problems.append(
                        DuplicateId(
                            f"group '{group.id}' lists requirement '{member}' twice",
                            scope=_SCOPE,
                            location=f"groups[{g}].members[{m}]",
                        )
                    )
                members.add(member)
        return problems
