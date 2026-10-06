"""Requirement sets: lookups, construction rules and every validate() path."""

from __future__ import annotations

from dataclasses import replace

import pytest

from gwylio.direction.model import GroupKind, RequirementSet, Scanability
from gwylio.shared.errors import DuplicateId, UnknownReference
from gwylio.shared.values import CleanText, KebabId
from tests.support import group, requirement, small_taxonomy


def make_set(
    requirements: tuple[object, ...] | None = None, groups: tuple[object, ...] | None = None
) -> RequirementSet:
    reqs = (
        requirements
        if requirements is not None
        else (
            requirement("SI1", coverage=("marine", "soils")),
            requirement("SI2", scanability=Scanability.LOW),
        )
    )
    grps = (
        groups
        if groups is not None
        else (
            group("i1", ("si1", "si2")),
            group("nature", ("si1",), GroupKind.WBO, related=("i1",)),
        )
    )
    return RequirementSet(
        id=KebabId("test-set"),
        name=CleanText("Test set"),
        version=CleanText("1"),
        source_doc=CleanText("A document"),
        requirements=reqs,  # type: ignore[arg-type]
        groups=grps,  # type: ignore[arg-type]
    )


def test_a_consistent_set_validates() -> None:
    s = make_set()
    s.validate(small_taxonomy())
    assert s.find_problems(small_taxonomy()) == ()


def test_lookups() -> None:
    s = make_set()
    assert s.requirement("si2").scanability is Scanability.LOW
    assert s.requirement_by_code("SI1").id == "si1"
    assert s.requirement_ids() == {"si1", "si2"}
    assert [g.id for g in s.groups_of_kind(GroupKind.IMPACT)] == ["i1"]
    assert [g.id for g in s.groups_of_kind(GroupKind.WBO)] == ["nature"]
    assert [g.id for g in s.groups_of("si1")] == ["i1", "nature"]
    with pytest.raises(UnknownReference):
        s.requirement("si9")
    with pytest.raises(UnknownReference):
        s.requirement_by_code("SI9")


def test_unknown_coverage_node_is_refused() -> None:
    s = make_set(requirements=(requirement("SI1", coverage=("marine", "tundra")),), groups=())
    with pytest.raises(UnknownReference, match="unknown taxonomy node 'tundra'") as caught:
        s.validate(small_taxonomy())
    assert caught.value.location == "requirements[0].expected_coverage[1]"


def test_unknown_group_member_is_refused() -> None:
    s = make_set(groups=(group("i1", ("si1", "si7")),))
    with pytest.raises(UnknownReference, match="unknown requirement 'si7'") as caught:
        s.validate(small_taxonomy())
    assert caught.value.location == "groups[0].members[1]"


def test_unknown_related_group_is_refused() -> None:
    s = make_set(groups=(group("nature", ("si1",), GroupKind.WBO, related=("i9",)),))
    with pytest.raises(UnknownReference, match="unknown related group 'i9'"):
        s.validate(small_taxonomy())


def test_a_group_cannot_relate_to_itself() -> None:
    s = make_set(groups=(group("i1", ("si1",), related=("i1",)),))
    with pytest.raises(UnknownReference):
        s.validate(small_taxonomy())


def test_duplicate_code_is_refused() -> None:
    first = requirement("SI1")
    second = requirement("SI1")
    s = make_set(requirements=(first, second), groups=())
    with pytest.raises(DuplicateId, match="code 'SI1'") as caught:
        s.validate(small_taxonomy())
    assert caught.value.location == "requirements[1].code"


def test_duplicate_id_with_different_code_is_refused() -> None:
    first = requirement("SI1")
    clash = replace(requirement("SI2"), id=first.id)
    s = make_set(requirements=(first, clash), groups=())
    with pytest.raises(DuplicateId, match="id 'si1'") as caught:
        s.validate(small_taxonomy())
    assert caught.value.location == "requirements[1].id"


def test_duplicate_group_id_is_refused() -> None:
    s = make_set(groups=(group("i1", ("si1",)), group("i1", ("si2",))))
    with pytest.raises(DuplicateId, match="group id 'i1'"):
        s.validate(small_taxonomy())


def test_group_id_cannot_reuse_a_requirement_id() -> None:
    s = make_set(groups=(group("si1", ("si1",)),))
    with pytest.raises(DuplicateId):
        s.validate(small_taxonomy())


def test_group_listing_a_member_twice_is_refused() -> None:
    s = make_set(groups=(group("i1", ("si1", "si1")),))
    with pytest.raises(DuplicateId, match="twice") as caught:
        s.validate(small_taxonomy())
    assert caught.value.location == "groups[0].members[1]"


@pytest.mark.parametrize("code", ["si1", "1SI", "S I1", "", "SI1234567890123456"])
def test_requirement_code_must_be_upper_case_alphanumeric(code: str) -> None:
    with pytest.raises(ValueError, match="requirement code"):
        replace(requirement("SI1"), code=code)


def test_short_name_has_at_most_six_words() -> None:
    assert requirement("SI1", short="one two three four five six").short
    with pytest.raises(ValueError, match="7 words"):
        requirement("SI1", short="one two three four five six seven")
    with pytest.raises(ValueError, match="needs a short name"):
        requirement("SI1", short="   ")


def test_scanability_values_have_meanings() -> None:
    assert [s.value for s in Scanability] == ["high", "medium", "low", "none"]
    assert all(s.meaning.endswith(".") for s in Scanability)
