"""Reference catalogues: taxonomy, topics, hazards, places, actors and lanes.

Pure, frozen domain objects with no input or output. Construction checks the
rules that concern one object alone (a centroid in range, a canonical domain);
``ReferenceCatalogue.validate`` checks the rules that span catalogues (a
hazard's family exists, a place's parent exists, an actor's lane exists).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final, Protocol, TypeVar

from gwylio.shared.errors import DomainError, DuplicateId, UnknownReference
from gwylio.shared.values import CanonicalUrl, CleanText, KebabId

__all__ = [
    "HAZARD_FAMILIES_AXIS",
    "SONARR_AXIS",
    "Actor",
    "ActorKind",
    "Hazard",
    "Lane",
    "Lens",
    "NodeKind",
    "Place",
    "PlaceKind",
    "ReferenceCatalogue",
    "Taxonomy",
    "TaxonomyAxis",
    "TaxonomyNode",
    "Topic",
]

SONARR_AXIS: Final[KebabId] = KebabId("sonarr-ecosystems")
"""The axis of SoNaRR's eight broad ecosystems and three cross-cutting resources."""
HAZARD_FAMILIES_AXIS: Final[KebabId] = KebabId("hazard-families")
"""The axis whose nodes are the families every hazard belongs to."""


class NodeKind(StrEnum):
    """What a taxonomy node stands for."""

    ECOSYSTEM = "ecosystem"
    RESOURCE = "resource"
    HAZARD_FAMILY = "hazard_family"


class Lens(StrEnum):
    """The three viewpoints the commission asked for; every lane sits under one."""

    GOVERNMENT = "government"
    PARTNERSHIP_SOCIETY = "partnership_society"
    INTERNATIONAL = "international"


class PlaceKind(StrEnum):
    """The kind of a named place."""

    NATION = "nation"
    REGION = "region"
    AREA = "area"
    RIVER_BASIN = "river_basin"
    SETTLEMENT = "settlement"
    SITE = "site"


class ActorKind(StrEnum):
    """The kind of an organisation."""

    GOVERNMENT = "government"
    LEGISLATURE = "legislature"
    REGULATOR = "regulator"
    PUBLIC_BODY = "public_body"
    RESEARCH = "research"
    NGO = "ngo"
    BUSINESS = "business"
    UNION = "union"
    MEDIA = "media"
    INTERNATIONAL = "international"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class TaxonomyNode:
    """One value on a taxonomy axis."""

    id: KebabId
    name: CleanText
    kind: NodeKind
    note: CleanText | None = None


@dataclass(frozen=True, slots=True)
class TaxonomyAxis:
    """One dimension of the taxonomy."""

    id: KebabId
    name: CleanText
    nodes: tuple[TaxonomyNode, ...]

    def node_ids(self) -> frozenset[KebabId]:
        """Every node identifier on this axis."""
        return frozenset(node.id for node in self.nodes)


@dataclass(frozen=True, slots=True)
class Taxonomy:
    """The classification axes. Node identifiers are unique across all axes."""

    axes: tuple[TaxonomyAxis, ...]

    def axis(self, axis_id: str) -> TaxonomyAxis:
        """The axis with this identifier, or ``UnknownReference``."""
        for axis in self.axes:
            if axis.id == axis_id:
                return axis
        raise UnknownReference(f"unknown taxonomy axis '{axis_id}'", scope="taxonomy")

    def node_ids(self) -> frozenset[KebabId]:
        """Every node identifier on every axis."""
        return frozenset(node.id for axis in self.axes for node in axis.nodes)

    def require_node(self, node_id: str, axis_id: str | None = None) -> TaxonomyNode:
        """The node with this identifier, optionally only on one axis, or ``UnknownReference``."""
        axes = self.axes if axis_id is None else (self.axis(axis_id),)
        for axis in axes:
            for node in axis.nodes:
                if node.id == node_id:
                    return node
        where = "the taxonomy" if axis_id is None else f"axis '{axis_id}'"
        raise UnknownReference(f"unknown taxonomy node '{node_id}' on {where}", scope="taxonomy")

    def find_problems(self) -> tuple[DomainError, ...]:
        """Duplicate axis identifiers and node identifiers repeated anywhere in the taxonomy."""
        problems: list[DomainError] = []
        seen_axes: set[str] = set()
        seen_nodes: set[str] = set()
        for a, axis in enumerate(self.axes):
            if axis.id in seen_axes:
                problems.append(
                    DuplicateId(
                        f"axis id '{axis.id}' is used twice",
                        scope="taxonomy",
                        location=f"axes[{a}].id",
                    )
                )
            seen_axes.add(axis.id)
            for n, node in enumerate(axis.nodes):
                if node.id in seen_nodes:
                    problems.append(
                        DuplicateId(
                            f"node id '{node.id}' is used twice in the taxonomy",
                            scope="taxonomy",
                            location=f"axes[{a}].nodes[{n}].id",
                        )
                    )
                seen_nodes.add(node.id)
        return tuple(problems)


@dataclass(frozen=True, slots=True)
class Lane:
    """Where we look: a grouping of sources under one lens."""

    id: KebabId
    name: CleanText
    lens: Lens
    description: CleanText


@dataclass(frozen=True, slots=True)
class Topic:
    """A subject area used to hint what a query or report is about."""

    id: KebabId
    name: CleanText
    note: CleanText | None = None


@dataclass(frozen=True, slots=True)
class Hazard:
    """A named threat to the Welsh environment, in one hazard family."""

    id: KebabId
    name: CleanText
    family: KebabId
    note: CleanText | None = None


@dataclass(frozen=True, slots=True)
class Place:
    """A named location with an optional parent and an optional centroid.

    The centroid is ``(latitude, longitude)`` in decimal degrees (WGS 84, the
    World Geodetic System 1984). Geometry arrives with a geospatial discipline.
    """

    id: KebabId
    name: CleanText
    kind: PlaceKind
    parent: KebabId | None = None
    centroid: tuple[float, float] | None = None
    welsh_name: CleanText | None = None

    def __post_init__(self) -> None:
        if self.parent == self.id:
            raise ValueError(f"place '{self.id}' cannot be its own parent")
        if self.centroid is not None:
            latitude, longitude = self.centroid
            if not -90.0 <= latitude <= 90.0:
                raise ValueError(f"latitude {latitude} is outside 90 south to 90 north")
            if not -180.0 <= longitude <= 180.0:
                raise ValueError(f"longitude {longitude} is outside 180 west to 180 east")


@dataclass(frozen=True, slots=True)
class Actor:
    """An organisation that publishes or is reported on."""

    id: KebabId
    name: CleanText
    kind: ActorKind
    lane: KebabId
    domain: str | None = None

    def __post_init__(self) -> None:
        if self.domain is not None:
            canonical = CanonicalUrl(self.domain)
            if canonical.value != self.domain or canonical.host != self.domain:
                raise ValueError(
                    f"domain '{self.domain}' must be a bare lower-case host such as "
                    "'gov.wales', with no scheme, 'www.', port, path or query"
                )


class _HasId(Protocol):
    @property
    def id(self) -> KebabId: ...


_T = TypeVar("_T", bound=_HasId)


def _index(items: Iterable[_T]) -> dict[str, _T]:
    index: dict[str, _T] = {}
    for item in items:
        index.setdefault(item.id, item)
    return index


def _duplicates(scope: str, items: tuple[_HasId, ...]) -> list[DomainError]:
    seen: set[str] = set()
    problems: list[DomainError] = []
    for i, item in enumerate(items):
        if item.id in seen:
            problems.append(
                DuplicateId(
                    f"id '{item.id}' is used twice", scope=scope, location=f"{scope}[{i}].id"
                )
            )
        seen.add(item.id)
    return problems


def _require(index: Mapping[str, _T], item_id: str, what: str) -> _T:
    try:
        return index[item_id]
    except KeyError:
        raise UnknownReference(f"unknown {what} '{item_id}'", scope=f"{what}s") from None


@dataclass(frozen=True, slots=True)
class ReferenceCatalogue:
    """The validated bundle of reference catalogues every other context points at."""

    taxonomy: Taxonomy
    topics: tuple[Topic, ...]
    hazards: tuple[Hazard, ...]
    places: tuple[Place, ...]
    actors: tuple[Actor, ...]
    lanes: tuple[Lane, ...]
    _topics: dict[str, Topic] = field(init=False, repr=False, compare=False)
    _hazards: dict[str, Hazard] = field(init=False, repr=False, compare=False)
    _places: dict[str, Place] = field(init=False, repr=False, compare=False)
    _actors: dict[str, Actor] = field(init=False, repr=False, compare=False)
    _lanes: dict[str, Lane] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_topics", _index(self.topics))
        object.__setattr__(self, "_hazards", _index(self.hazards))
        object.__setattr__(self, "_places", _index(self.places))
        object.__setattr__(self, "_actors", _index(self.actors))
        object.__setattr__(self, "_lanes", _index(self.lanes))

    def topic(self, topic_id: str) -> Topic:
        """The topic with this identifier, or ``UnknownReference``."""
        return _require(self._topics, topic_id, "topic")

    def hazard(self, hazard_id: str) -> Hazard:
        """The hazard with this identifier, or ``UnknownReference``."""
        return _require(self._hazards, hazard_id, "hazard")

    def place(self, place_id: str) -> Place:
        """The place with this identifier, or ``UnknownReference``."""
        return _require(self._places, place_id, "place")

    def actor(self, actor_id: str) -> Actor:
        """The actor with this identifier, or ``UnknownReference``."""
        return _require(self._actors, actor_id, "actor")

    def lane(self, lane_id: str) -> Lane:
        """The lane with this identifier, or ``UnknownReference``."""
        return _require(self._lanes, lane_id, "lane")

    def topic_ids(self) -> frozenset[str]:
        """Every topic identifier."""
        return frozenset(self._topics)

    def hazard_ids(self) -> frozenset[str]:
        """Every hazard identifier."""
        return frozenset(self._hazards)

    def place_ids(self) -> frozenset[str]:
        """Every place identifier."""
        return frozenset(self._places)

    def actor_ids(self) -> frozenset[str]:
        """Every actor identifier."""
        return frozenset(self._actors)

    def lane_ids(self) -> frozenset[str]:
        """Every lane identifier."""
        return frozenset(self._lanes)

    def children_of(self, place_id: str) -> tuple[Place, ...]:
        """The places whose parent is ``place_id``, in catalogue order."""
        return tuple(place for place in self.places if place.parent == place_id)

    def find_problems(self) -> tuple[DomainError, ...]:
        """Every broken rule across the catalogues, in a stable order."""
        problems: list[DomainError] = list(self.taxonomy.find_problems())
        catalogues: tuple[tuple[str, tuple[_HasId, ...]], ...] = (
            ("lanes", self.lanes),
            ("topics", self.topics),
            ("hazards", self.hazards),
            ("places", self.places),
            ("actors", self.actors),
        )
        for scope, items in catalogues:
            problems.extend(_duplicates(scope, items))
        problems.extend(self._hazard_problems())
        problems.extend(self._place_problems())
        problems.extend(self._actor_problems())
        return tuple(problems)

    def validate(self) -> None:
        """Raise the first broken rule (``UnknownReference`` or ``DuplicateId``), if any."""
        problems = self.find_problems()
        if problems:
            raise problems[0]

    def _hazard_problems(self) -> list[DomainError]:
        try:
            families = self.taxonomy.axis(HAZARD_FAMILIES_AXIS).node_ids()
        except UnknownReference:
            return [
                UnknownReference(
                    f"the taxonomy has no {HAZARD_FAMILIES_AXIS!s} axis for hazards to point at",
                    scope="taxonomy",
                    location="axes",
                )
            ]
        return [
            UnknownReference(
                f"hazard '{hazard.id}' names unknown family '{hazard.family}'; "
                f"families are the nodes of the {HAZARD_FAMILIES_AXIS!s} axis",
                scope="hazards",
                location=f"hazards[{h}].family",
            )
            for h, hazard in enumerate(self.hazards)
            if hazard.family not in families
        ]

    def _place_problems(self) -> list[DomainError]:
        problems: list[DomainError] = []
        for p, place in enumerate(self.places):
            if place.parent is not None and place.parent not in self._places:
                problems.append(
                    UnknownReference(
                        f"place '{place.id}' names unknown parent '{place.parent}'",
                        scope="places",
                        location=f"places[{p}].parent",
                    )
                )
        for p, place in enumerate(self.places):
            seen = {place.id}
            parent = place.parent
            while parent is not None and parent in self._places:
                if parent in seen:
                    problems.append(
                        DomainError(
                            f"place '{place.id}' is its own ancestor through '{parent}'",
                            scope="places",
                            location=f"places[{p}].parent",
                        )
                    )
                    break
                seen.add(parent)
                parent = self._places[parent].parent
        return problems

    def _actor_problems(self) -> list[DomainError]:
        return [
            UnknownReference(
                f"actor '{actor.id}' names unknown lane '{actor.lane}'",
                scope="actors",
                location=f"actors[{a}].lane",
            )
            for a, actor in enumerate(self.actors)
            if actor.lane not in self._lanes
        ]
