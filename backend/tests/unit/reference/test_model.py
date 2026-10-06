"""Reference catalogue: lookups, construction rules and every validate() path."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from gwylio.reference.model import (
    HAZARD_FAMILIES_AXIS,
    SONARR_AXIS,
    Actor,
    ActorKind,
    Hazard,
    Lane,
    Lens,
    NodeKind,
    Place,
    PlaceKind,
    ReferenceCatalogue,
    Taxonomy,
    TaxonomyAxis,
    Topic,
)
from gwylio.shared.errors import DomainError, DuplicateId, UnknownReference
from gwylio.shared.values import CleanText, KebabId
from tests.support import node, small_taxonomy


def lane(lane_id: str = "senedd", lens: Lens = Lens.GOVERNMENT) -> Lane:
    return Lane(KebabId(lane_id), CleanText(lane_id.title()), lens, CleanText("Watches."))


def place(place_id: str, parent: str | None = None, kind: PlaceKind = PlaceKind.REGION) -> Place:
    return Place(
        KebabId(place_id),
        CleanText(place_id.title()),
        kind,
        None if parent is None else KebabId(parent),
    )


def actor(actor_id: str = "senedd", lane_id: str = "senedd", domain: str | None = None) -> Actor:
    return Actor(
        KebabId(actor_id),
        CleanText(actor_id.title()),
        ActorKind.LEGISLATURE,
        KebabId(lane_id),
        domain,
    )


def hazard(hazard_id: str = "upland-wildfire", family: str = "wildfire") -> Hazard:
    return Hazard(KebabId(hazard_id), CleanText(hazard_id.title()), KebabId(family))


def catalogue(**overrides: object) -> ReferenceCatalogue:
    base = ReferenceCatalogue(
        taxonomy=small_taxonomy(),
        topics=(Topic(KebabId("peatland"), CleanText("Peatland")),),
        hazards=(hazard(),),
        places=(place("wales", kind=PlaceKind.NATION), place("north-wales", "wales")),
        actors=(actor(domain="senedd.wales"),),
        lanes=(lane(),),
    )
    return replace(base, **overrides)  # type: ignore[arg-type]


# Taxonomy


def test_taxonomy_lists_node_ids_across_axes() -> None:
    assert small_taxonomy().node_ids() == {
        "marine",
        "freshwaters",
        "soils",
        "wildfire",
        "plant-tree-disease",
    }


def test_require_node_finds_a_node_and_can_restrict_to_one_axis() -> None:
    taxonomy = small_taxonomy()
    assert taxonomy.require_node("soils").kind is NodeKind.RESOURCE
    assert taxonomy.require_node("wildfire", HAZARD_FAMILIES_AXIS).id == "wildfire"
    with pytest.raises(UnknownReference, match="unknown taxonomy node 'wildfire' on axis"):
        taxonomy.require_node("wildfire", SONARR_AXIS)


def test_require_node_raises_for_an_unknown_node() -> None:
    with pytest.raises(UnknownReference, match="'tundra'"):
        small_taxonomy().require_node("tundra")


def test_unknown_axis_raises() -> None:
    with pytest.raises(UnknownReference, match="unknown taxonomy axis"):
        small_taxonomy().axis("colours")


def test_taxonomy_reports_duplicate_axes_and_nodes() -> None:
    axis = TaxonomyAxis(KebabId("a"), CleanText("A"), (node("x"), node("y"), node("x")))
    problems = Taxonomy((axis, axis)).find_problems()
    locations = [p.location for p in problems]
    assert "axes[0].nodes[2].id" in locations
    assert "axes[1].id" in locations
    assert all(isinstance(p, DuplicateId) for p in problems)


def test_a_node_id_shared_between_axes_is_a_duplicate() -> None:
    first = TaxonomyAxis(KebabId("a"), CleanText("A"), (node("water"),))
    second = TaxonomyAxis(KebabId("b"), CleanText("B"), (node("water"),))
    [problem] = Taxonomy((first, second)).find_problems()
    assert problem.location == "axes[1].nodes[0].id"


# Construction rules


def test_place_cannot_be_its_own_parent() -> None:
    with pytest.raises(ValueError, match="its own parent"):
        place("wales", "wales")


@pytest.mark.parametrize("centroid", [(91.0, 0.0), (-90.5, 0.0), (52.0, 181.0), (52.0, -180.1)])
def test_place_centroid_must_be_in_range(centroid: tuple[float, float]) -> None:
    with pytest.raises(ValueError, match="outside"):
        Place(KebabId("x"), CleanText("X"), PlaceKind.SITE, centroid=centroid)


def test_place_centroid_in_range_is_kept() -> None:
    p = Place(KebabId("x"), CleanText("X"), PlaceKind.SITE, centroid=(52.4, -3.7))
    assert p.centroid == (52.4, -3.7)


@pytest.mark.parametrize(
    "domain",
    ["https://gov.wales", "www.gov.wales", "GOV.WALES", "gov.wales/path", "gov.wales:8080"],
)
def test_actor_domain_must_be_a_bare_host(domain: str) -> None:
    with pytest.raises(ValueError, match="bare lower-case host"):
        actor(domain=domain)


def test_actor_domain_may_be_absent_or_bare() -> None:
    assert actor(domain=None).domain is None
    assert actor(domain="planthealthportal.defra.gov.uk").domain == "planthealthportal.defra.gov.uk"


def test_domain_objects_are_frozen() -> None:
    with pytest.raises(FrozenInstanceError):
        lane().name = CleanText("Other")  # type: ignore[misc]


# Catalogue lookups


def test_lookups_return_the_named_item() -> None:
    c = catalogue()
    assert c.topic("peatland").name == "Peatland"
    assert c.hazard("upland-wildfire").family == "wildfire"
    assert c.place("north-wales").parent == "wales"
    assert c.actor("senedd").domain == "senedd.wales"
    assert c.lane("senedd").lens is Lens.GOVERNMENT
    assert c.children_of("wales") == (c.place("north-wales"),)
    assert c.lane_ids() == {"senedd"}
    assert c.topic_ids() == {"peatland"}
    assert c.hazard_ids() == {"upland-wildfire"}
    assert c.place_ids() == {"wales", "north-wales"}
    assert c.actor_ids() == {"senedd"}


@pytest.mark.parametrize("method", ["topic", "hazard", "place", "actor", "lane"])
def test_lookups_raise_unknown_reference(method: str) -> None:
    with pytest.raises(UnknownReference, match=f"unknown {method} 'nope'"):
        getattr(catalogue(), method)("nope")


# Catalogue validation


def test_a_consistent_catalogue_validates() -> None:
    catalogue().validate()
    assert catalogue().find_problems() == ()


def test_unknown_hazard_family_is_refused() -> None:
    c = catalogue(hazards=(hazard(), hazard("ash-dieback", family="tree-disease")))
    with pytest.raises(UnknownReference, match="unknown family 'tree-disease'") as caught:
        c.validate()
    assert caught.value.location == "hazards[1].family"
    assert caught.value.scope == "hazards"


def test_hazard_family_must_be_on_the_hazard_families_axis() -> None:
    c = catalogue(hazards=(hazard(family="marine"),))
    with pytest.raises(UnknownReference, match="unknown family 'marine'"):
        c.validate()


def test_missing_hazard_families_axis_is_refused() -> None:
    sonarr_only = Taxonomy((small_taxonomy().axis(SONARR_AXIS),))
    with pytest.raises(UnknownReference, match="no hazard-families axis"):
        catalogue(taxonomy=sonarr_only).validate()


def test_unknown_place_parent_is_refused() -> None:
    c = catalogue(places=(place("wales", kind=PlaceKind.NATION), place("dee", "cymru")))
    with pytest.raises(UnknownReference, match="unknown parent 'cymru'") as caught:
        c.validate()
    assert caught.value.location == "places[1].parent"


def test_place_parent_cycle_is_refused() -> None:
    c = catalogue(places=(place("a", "b"), place("b", "a")))
    with pytest.raises(DomainError, match="its own ancestor"):
        c.validate()


def test_unknown_actor_lane_is_refused() -> None:
    c = catalogue(actors=(actor(), actor("audit-wales", "governance")))
    with pytest.raises(UnknownReference, match="unknown lane 'governance'") as caught:
        c.validate()
    assert caught.value.location == "actors[1].lane"


@pytest.mark.parametrize(
    ("field", "items", "location"),
    [
        ("lanes", (lane(), lane()), "lanes[1].id"),
        (
            "topics",
            (
                Topic(KebabId("peatland"), CleanText("P")),
                Topic(KebabId("peatland"), CleanText("Q")),
            ),
            "topics[1].id",
        ),
        ("hazards", (hazard(), hazard()), "hazards[1].id"),
        ("places", (place("wales"), place("wales")), "places[1].id"),
        ("actors", (actor(), actor()), "actors[1].id"),
    ],
)
def test_duplicate_ids_are_refused(field: str, items: tuple[object, ...], location: str) -> None:
    with pytest.raises(DuplicateId) as caught:
        catalogue(**{field: items}).validate()
    assert caught.value.location == location


def test_find_problems_reports_every_problem_not_just_the_first() -> None:
    c = catalogue(
        hazards=(hazard(family="nope"),),
        actors=(actor(lane_id="nope"),),
        places=(place("x", "nope"),),
    )
    assert [p.scope for p in c.find_problems()] == ["hazards", "places", "actors"]
