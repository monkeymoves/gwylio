"""Pydantic models describing every configuration file under ``config/``.

These models are the file contract: they parse JSON, refuse unknown keys,
and turn every prose field into ``CleanText`` (so an en or em dash anywhere
fails with a path). They carry no cross-references; the loaders build domain
objects from them and the domain ``validate`` methods check the references.
``gwylio schema`` generates JSON Schema and TypeScript from ``SCHEMA_MODELS``.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Final

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from gwylio.direction.model import REQUIREMENT_CODE_PATTERN, GroupKind, Scanability
from gwylio.direction.scanability import CoverageStatus
from gwylio.reference.model import ActorKind, Lens, NodeKind, PlaceKind
from gwylio.shared.values import KEBAB_MAX_LENGTH, KEBAB_PATTERN, CleanText, KebabId

__all__ = [
    "SCHEMA_ENUMS",
    "SCHEMA_MODELS",
    "ActorConfig",
    "ActorsFile",
    "HazardConfig",
    "HazardsFile",
    "LaneConfig",
    "LanesFile",
    "PlaceConfig",
    "PlacesFile",
    "Prose",
    "RequirementConfig",
    "RequirementGroupConfig",
    "RequirementSetFile",
    "TaxonomyAxisConfig",
    "TaxonomyFile",
    "TaxonomyNodeConfig",
    "TopicConfig",
    "TopicsFile",
]

Prose = Annotated[str, AfterValidator(CleanText)]
"""Human-readable text. Validated into ``CleanText``: no en or em dash."""

Id = Annotated[
    str,
    Field(pattern=KEBAB_PATTERN, max_length=KEBAB_MAX_LENGTH),
    AfterValidator(KebabId),
]
"""A lowercase kebab-case identifier."""

Host = Annotated[
    str,
    Field(pattern=r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$"),
]
"""A bare lower-case host name such as ``gov.wales``."""


class _ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# Taxonomy


class TaxonomyNodeConfig(_ConfigModel):
    """One value on a taxonomy axis."""

    id: Id = Field(description="Unique across the whole taxonomy.")
    name: Prose
    kind: NodeKind
    note: Prose | None = None


class TaxonomyAxisConfig(_ConfigModel):
    """One dimension of the taxonomy."""

    id: Id
    name: Prose
    nodes: list[TaxonomyNodeConfig] = Field(min_length=1)


class TaxonomyFile(_ConfigModel):
    """config/taxonomy.json: the classification axes."""

    notes: Prose | None = None
    axes: list[TaxonomyAxisConfig] = Field(min_length=1)


# Lanes


class LaneConfig(_ConfigModel):
    """Where we look: a grouping of sources under one lens."""

    id: Id
    name: Prose
    lens: Lens
    description: Prose = Field(description="One sentence on what the lane watches.")


class LanesFile(_ConfigModel):
    """config/lanes.json: the collection lanes."""

    notes: Prose | None = None
    lanes: list[LaneConfig] = Field(min_length=1)


# Reference catalogues


class TopicConfig(_ConfigModel):
    """A subject area used to hint what a query or report is about."""

    id: Id
    name: Prose
    note: Prose | None = None


class TopicsFile(_ConfigModel):
    """config/reference/topics.json: the topic catalogue."""

    notes: Prose | None = None
    topics: list[TopicConfig] = Field(min_length=1)


class HazardConfig(_ConfigModel):
    """A named threat to the Welsh environment."""

    id: Id
    name: Prose
    family: Id = Field(description="A node id on the hazard-families taxonomy axis.")
    note: Prose | None = None


class HazardsFile(_ConfigModel):
    """config/reference/hazards.json: the hazard catalogue."""

    notes: Prose | None = None
    hazards: list[HazardConfig] = Field(min_length=1)


class PlaceConfig(_ConfigModel):
    """A named location."""

    id: Id
    name: Prose
    welsh_name: Prose | None = Field(default=None, description="The Welsh name, where different.")
    kind: PlaceKind
    parent: Id | None = Field(default=None, description="The id of the containing place.")
    centroid: tuple[float, float] | None = Field(
        default=None, description="Latitude and longitude in decimal degrees (WGS 84)."
    )


class PlacesFile(_ConfigModel):
    """config/reference/places.json: the place catalogue."""

    notes: Prose | None = None
    places: list[PlaceConfig] = Field(min_length=1)


class ActorConfig(_ConfigModel):
    """An organisation that publishes or is reported on."""

    id: Id
    name: Prose
    kind: ActorKind
    lane: Id = Field(description="The lane where this actor is usually found.")
    domain: Host | None = Field(default=None, description="Bare host, such as gov.wales.")


class ActorsFile(_ConfigModel):
    """config/reference/actors.json: the actor catalogue."""

    notes: Prose | None = None
    actors: list[ActorConfig] = Field(min_length=1)


# Requirement sets


class RequirementConfig(_ConfigModel):
    """One Priority Intelligence Requirement (PIR)."""

    code: str = Field(pattern=REQUIREMENT_CODE_PATTERN, description="Display code, e.g. SI1.")
    id: Id
    name: Prose
    short: Prose = Field(description="At most six words, for tiles and tables.")
    scanability: Scanability
    scanability_note: Prose
    keywords: list[Prose] = Field(default_factory=list)
    expected_coverage: list[Id] = Field(
        default_factory=list, description="Taxonomy node ids this requirement should touch."
    )
    metric_sources: list[Prose] = Field(default_factory=list)
    development: bool = Field(
        default=False, description="True while the indicator is still being developed."
    )


class RequirementGroupConfig(_ConfigModel):
    """An impact statement or a well-being objective grouping requirements."""

    id: Id
    kind: GroupKind
    name: Prose
    statement: Prose | None = None
    members: list[Id] = Field(min_length=1, description="Requirement ids in this group.")
    related_groups: list[Id] = Field(
        default_factory=list, description="Ids of other groups in the set this one maps to."
    )
    note: Prose | None = None


class RequirementSetFile(_ConfigModel):
    """config/requirement_sets/<id>.json: one requirement set."""

    notes: Prose | None = None
    id: Id = Field(description="Must equal the file name without .json.")
    name: Prose
    version: Prose
    source_doc: Prose
    requirements: list[RequirementConfig] = Field(min_length=1)
    groups: list[RequirementGroupConfig] = Field(default_factory=list)


SCHEMA_MODELS: Final[dict[str, type[BaseModel]]] = {
    "actors": ActorsFile,
    "hazards": HazardsFile,
    "lanes": LanesFile,
    "places": PlacesFile,
    "requirement-set": RequirementSetFile,
    "taxonomy": TaxonomyFile,
    "topics": TopicsFile,
}
"""Every file contract, by schema name: ``docs/schema/<name>.schema.json``."""

SCHEMA_ENUMS: Final[tuple[type[Enum], ...]] = (CoverageStatus,)
"""Enums the front end needs that no configuration file mentions."""
