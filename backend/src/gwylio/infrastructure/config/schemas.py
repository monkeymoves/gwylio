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

from gwylio.collection.model import SourceStatus
from gwylio.direction.model import REQUIREMENT_CODE_PATTERN, GroupKind, Scanability
from gwylio.direction.scanability import CoverageStatus
from gwylio.intelligence.datecheck import FindingKind, Severity
from gwylio.intelligence.model import HistoryKind
from gwylio.processing.candidates_file import CandidatesFile
from gwylio.processing.ingest import SweepFile
from gwylio.processing.submission import Submission
from gwylio.reference.model import ActorKind, Lens, NodeKind, PlaceKind
from gwylio.shared.values import KEBAB_MAX_LENGTH, KEBAB_PATTERN, CleanText, IsoDate, KebabId
from gwylio.shared.vocabulary import Discipline, IndicatorState, Reliability

__all__ = [
    "SCHEMA_ENUMS",
    "SCHEMA_MODELS",
    "ActorConfig",
    "ActorsFile",
    "DatecheckFile",
    "GatingFile",
    "HazardConfig",
    "HazardsFile",
    "InstrumentFile",
    "LaneConfig",
    "LanesFile",
    "PlaceConfig",
    "PlacesFile",
    "Prose",
    "QueryConfig",
    "RequirementConfig",
    "RequirementGroupConfig",
    "RequirementSetFile",
    "SourceConfig",
    "SourcesFile",
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


def _iso_date(value: str) -> str:
    IsoDate(value)
    return value


DateText = Annotated[
    str,
    Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$", description="A date, YYYY-MM-DD."),
    AfterValidator(_iso_date),
]
"""A calendar date written ``YYYY-MM-DD``."""

INSTRUMENT_VERSION_PATTERN: Final[str] = r"^[0-9]{4}\.[0-9]{1,2}\.[0-9]+$"
"""Calendar versioning for the instrument: year, month, then a counter, such as 2026.10.0."""


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


# Collection: sources, the query instrument and the gating rules


class SourceConfig(_ConfigModel):
    """A watchlist entry: where hits come from, with a default reliability."""

    id: Id
    name: Prose
    domain: Host = Field(description="Bare host; hits are matched to sources by exact domain.")
    feed_url: str | None = Field(
        default=None, pattern=r"^https?://[^\s]+$", description="Required for osint_feed sources."
    )
    discipline: Discipline
    lane: Id
    actor: Id = Field(description="The actor that publishes on this source.")
    reliability: Reliability = Field(description="Admiralty reliability, A to F.")
    trusted: bool = Field(description="A trusted source passes the relevance gate on domain alone.")
    site_pass: bool = Field(description="Whether site queries may sweep this source's domain.")
    status: SourceStatus = SourceStatus.ACTIVE
    added_on: DateText
    notes: Prose | None = None


class SourcesFile(_ConfigModel):
    """config/sources.json: the source watchlist."""

    notes: Prose | None = None
    sources: list[SourceConfig] = Field(min_length=1)


class QueryConfig(_ConfigModel):
    """One query in the instrument."""

    id: Id
    discipline: Discipline
    lane: Id = Field(description="Where the query looks; feed queries read this lane's feeds.")
    text: Prose = Field(description="Query text; site and feed queries OR-join quoted phrases.")
    requirement_hints: list[Id] = Field(
        default_factory=list, description="Requirement ids the hits may bear on; hints, not tags."
    )
    topic_hints: list[Id] = Field(default_factory=list, description="Topic ids; hints, not tags.")
    negative_terms: list[Prose] = Field(
        default_factory=list, description="Terms that drop a hit, after the global ones."
    )
    site_source_ids: list[Id] = Field(
        default_factory=list, description="osint_site only: the sources to restrict the query to."
    )


class InstrumentFile(_ConfigModel):
    """config/instrument.json: the versioned query instrument."""

    notes: Prose | None = None
    version: str = Field(pattern=INSTRUMENT_VERSION_PATTERN, description="Such as 2026.10.0.")
    content_hash: str = Field(
        pattern=r"^sha256:[0-9a-f]{64}$",
        description="sha256 of the canonical JSON of every field except notes and this one.",
    )
    global_negative_terms: list[Prose] = Field(default_factory=list)
    max_requests_per_run: int = Field(ge=1, description="The request budget of one scan run.")
    queries: list[QueryConfig] = Field(min_length=1)


class GatingFile(_ConfigModel):
    """config/gating.json: own domains and relevance tokens for the gates."""

    notes: Prose | None = None
    own_domains: list[Host] = Field(
        min_length=1, description="The organisation's own domains: hits on them are dropped."
    )
    relevance_tokens: list[Prose] = Field(
        min_length=1, description="Lower-case words or phrases that make an untrusted hit relevant."
    )
    relevance_place_kinds: list[PlaceKind] = Field(
        default_factory=list,
        description="Places of these kinds add their English and Welsh names as tokens.",
    )


class DatecheckFile(_ConfigModel):
    """config/datecheck.json: the rules gwylio datecheck applies."""

    notes: Prose | None = None
    future_phrases: list[Prose] = Field(
        min_length=1,
        description="Future-framed phrases that rot once their date passes, matched as words.",
    )
    stale_after_days: int = Field(
        default=45, ge=1, description="A verification older than this many days is stale."
    )


SCHEMA_MODELS: Final[dict[str, type[BaseModel]]] = {
    "actors": ActorsFile,
    "candidates": CandidatesFile,
    "datecheck": DatecheckFile,
    "gating": GatingFile,
    "hazards": HazardsFile,
    "instrument": InstrumentFile,
    "lanes": LanesFile,
    "places": PlacesFile,
    "requirement-set": RequirementSetFile,
    "sources": SourcesFile,
    "submission": Submission,
    "sweep": SweepFile,
    "taxonomy": TaxonomyFile,
    "topics": TopicsFile,
}
"""Every file contract, by schema name: ``docs/schema/<name>.schema.json``.

All are configuration files except ``candidates``, ``submission`` and
``sweep``, the handoff and fact file contracts from the Processing context,
registered here so their schemas and TypeScript types are generated with the
rest."""

SCHEMA_ENUMS: Final[tuple[type[Enum], ...]] = (
    CoverageStatus,
    FindingKind,
    HistoryKind,
    IndicatorState,
    Severity,
)
"""Enums the front end needs that no file contract mentions."""
