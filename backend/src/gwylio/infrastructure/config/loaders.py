"""Load the configuration files into validated domain objects.

Each file is parsed through its Pydantic model in ``schemas.py``, turned into
domain objects, and then checked across files by the domain ``find_problems``
methods. Problems carry the file and the path inside it, so ``gwylio check``
can print every one of them; ``load_config`` raises ``ConfigInvalidError`` with all
of them at once rather than stopping at the first.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from gwylio.collection.gates import GatingRules, relevance_tokens
from gwylio.collection.model import Query, QueryInstrument, Source, find_source_problems
from gwylio.direction.model import (
    GroupKind,
    Requirement,
    RequirementGroup,
    RequirementSet,
)
from gwylio.infrastructure.config import paths
from gwylio.infrastructure.config.schemas import (
    ActorConfig,
    ActorsFile,
    GatingFile,
    HazardConfig,
    HazardsFile,
    InstrumentFile,
    LaneConfig,
    LanesFile,
    PlaceConfig,
    PlacesFile,
    QueryConfig,
    RequirementConfig,
    RequirementGroupConfig,
    RequirementSetFile,
    SourceConfig,
    SourcesFile,
    TaxonomyAxisConfig,
    TaxonomyFile,
    TaxonomyNodeConfig,
    TopicConfig,
    TopicsFile,
)
from gwylio.reference.model import (
    Actor,
    Hazard,
    Lane,
    Place,
    ReferenceCatalogue,
    Taxonomy,
    TaxonomyAxis,
    TaxonomyNode,
    Topic,
)
from gwylio.shared.errors import DomainError
from gwylio.shared.values import CleanText, IsoDate, KebabId
from gwylio.shared.vocabulary import Discipline

__all__ = [
    "CheckReport",
    "ConfigInvalidError",
    "ConfigProblem",
    "FileSummary",
    "LoadedConfig",
    "check_config",
    "load_config",
]

_M = TypeVar("_M", bound=BaseModel)
_C = TypeVar("_C")
_D = TypeVar("_D")


@dataclass(frozen=True, slots=True)
class ConfigProblem:
    """One problem in one configuration file, located by a path inside it."""

    file: str
    location: str
    message: str

    def __str__(self) -> str:
        where = f"{self.file}: {self.location}" if self.location else self.file
        return f"{where}: {self.message}"


class ConfigInvalidError(Exception):
    """The configuration has one or more problems."""

    def __init__(self, problems: Sequence[ConfigProblem]) -> None:
        self.problems = tuple(problems)
        super().__init__("\n".join(str(problem) for problem in self.problems))


@dataclass(frozen=True, slots=True)
class FileSummary:
    """What one configuration file holds, in one line."""

    file: str
    summary: str


@dataclass(frozen=True, slots=True)
class LoadedConfig:
    """The validated configuration: catalogues, requirement sets, sources, instrument, gates."""

    catalogue: ReferenceCatalogue
    requirement_sets: tuple[RequirementSet, ...]
    sources: tuple[Source, ...]
    instrument: QueryInstrument
    gating: GatingRules

    def requirement_set(self, set_id: str) -> RequirementSet:
        """The requirement set with this identifier, or ``KeyError``."""
        for requirement_set in self.requirement_sets:
            if requirement_set.id == set_id:
                return requirement_set
        raise KeyError(set_id)


@dataclass(frozen=True, slots=True)
class CheckReport:
    """The outcome of checking every configuration file."""

    summaries: tuple[FileSummary, ...]
    problems: tuple[ConfigProblem, ...]
    config: LoadedConfig | None
    notes: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        """True when there are no problems."""
        return not self.problems


def _opt(text: str | None) -> CleanText | None:
    return None if text is None else CleanText(text)


def _location(loc: Sequence[int | str]) -> str:
    out = ""
    for part in loc:
        out += f"[{part}]" if isinstance(part, int) else (f".{part}" if out else str(part))
    return out


class _Collector:
    """Accumulates problems while files are parsed and built."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.problems: list[ConfigProblem] = []
        self.notes: list[str] = []

    def add(self, file: str, location: str, message: str) -> None:
        self.problems.append(ConfigProblem(file, location, message))

    def parse(self, file: str, model: type[_M]) -> _M | None:
        path = self.root / file
        try:
            raw: Any = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            self.add(file, "", "file not found")
            return None
        except json.JSONDecodeError as error:
            self.add(
                file, f"line {error.lineno} column {error.colno}", f"invalid JSON: {error.msg}"
            )
            return None
        except UnicodeDecodeError as error:
            self.add(file, "", f"not UTF-8 text: {error.reason}")
            return None
        try:
            return model.model_validate(raw)
        except ValidationError as error:
            for detail in error.errors(include_url=False):
                self.add(file, _location(detail["loc"]), detail["msg"])
            return None

    def build(
        self,
        file: str,
        key: str,
        configs: Sequence[_C],
        factory: Callable[[_C], _D],
    ) -> tuple[_D, ...]:
        """Build one domain object per config entry, recording a problem for each refusal."""
        built: list[_D] = []
        for index, config in enumerate(configs):
            try:
                built.append(factory(config))
            except (ValueError, TypeError, DomainError) as error:
                self.add(file, f"{key}[{index}]", str(error))
        return tuple(built)

    def add_domain(self, file: str, problem: DomainError) -> None:
        self.add(file, problem.location, problem.message)


def _node(config: TaxonomyNodeConfig) -> TaxonomyNode:
    return TaxonomyNode(KebabId(config.id), CleanText(config.name), config.kind, _opt(config.note))


def _axis(config: TaxonomyAxisConfig) -> TaxonomyAxis:
    nodes = tuple(_node(node) for node in config.nodes)
    return TaxonomyAxis(KebabId(config.id), CleanText(config.name), nodes)


def _lane(config: LaneConfig) -> Lane:
    return Lane(
        KebabId(config.id), CleanText(config.name), config.lens, CleanText(config.description)
    )


def _topic(config: TopicConfig) -> Topic:
    return Topic(KebabId(config.id), CleanText(config.name), _opt(config.note))


def _hazard(config: HazardConfig) -> Hazard:
    return Hazard(
        KebabId(config.id), CleanText(config.name), KebabId(config.family), _opt(config.note)
    )


def _place(config: PlaceConfig) -> Place:
    return Place(
        id=KebabId(config.id),
        name=CleanText(config.name),
        kind=config.kind,
        parent=None if config.parent is None else KebabId(config.parent),
        centroid=config.centroid,
        welsh_name=_opt(config.welsh_name),
    )


def _actor(config: ActorConfig) -> Actor:
    return Actor(
        KebabId(config.id), CleanText(config.name), config.kind, KebabId(config.lane), config.domain
    )


def _requirement(config: RequirementConfig) -> Requirement:
    return Requirement(
        code=config.code,
        id=KebabId(config.id),
        name=CleanText(config.name),
        short=CleanText(config.short),
        scanability=config.scanability,
        scanability_note=CleanText(config.scanability_note),
        keywords=tuple(CleanText(keyword) for keyword in config.keywords),
        expected_coverage=tuple(KebabId(node) for node in config.expected_coverage),
        metric_sources=tuple(CleanText(source) for source in config.metric_sources),
        development=config.development,
    )


def _group(config: RequirementGroupConfig) -> RequirementGroup:
    return RequirementGroup(
        id=KebabId(config.id),
        kind=config.kind,
        name=CleanText(config.name),
        members=tuple(KebabId(member) for member in config.members),
        statement=_opt(config.statement),
        note=_opt(config.note),
        related_groups=tuple(KebabId(group) for group in config.related_groups),
    )


def _source(config: SourceConfig) -> Source:
    return Source(
        id=KebabId(config.id),
        name=CleanText(config.name),
        domain=config.domain,
        feed_url=config.feed_url,
        discipline=config.discipline,
        lane=KebabId(config.lane),
        actor=KebabId(config.actor),
        reliability=config.reliability,
        trusted=config.trusted,
        site_pass=config.site_pass,
        status=config.status,
        added_on=IsoDate(config.added_on),
        notes=_opt(config.notes),
    )


def _query(config: QueryConfig) -> Query:
    return Query(
        id=KebabId(config.id),
        discipline=config.discipline,
        lane=KebabId(config.lane),
        text=CleanText(config.text),
        requirement_hints=tuple(KebabId(hint) for hint in config.requirement_hints),
        topic_hints=tuple(KebabId(hint) for hint in config.topic_hints),
        negative_terms=tuple(CleanText(term) for term in config.negative_terms),
        site_source_ids=tuple(KebabId(source) for source in config.site_source_ids),
    )


def _plural(count: int, word: str, plural: str | None = None) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {plural or word + 's'}"


_SCOPE_FILES = {
    "taxonomy": paths.TAXONOMY_FILE,
    "lanes": paths.LANES_FILE,
    "topics": paths.TOPICS_FILE,
    "hazards": paths.HAZARDS_FILE,
    "places": paths.PLACES_FILE,
    "actors": paths.ACTORS_FILE,
    "sources": paths.SOURCES_FILE,
    "instrument": paths.INSTRUMENT_FILE,
    "gating": paths.GATING_FILE,
}


def _load_taxonomy(collector: _Collector, summaries: list[FileSummary]) -> Taxonomy | None:
    before = len(collector.problems)
    parsed = collector.parse(paths.TAXONOMY_FILE, TaxonomyFile)
    if parsed is None:
        return None
    axes = collector.build(paths.TAXONOMY_FILE, "axes", parsed.axes, _axis)
    per_axis = ", ".join(f"{axis.id} {len(axis.nodes)}" for axis in axes)
    nodes = sum(len(axis.nodes) for axis in axes)
    summaries.append(
        FileSummary(
            paths.TAXONOMY_FILE,
            f"{_plural(len(axes), 'axis', 'axes')}, {_plural(nodes, 'node')} ({per_axis})",
        )
    )
    taxonomy = Taxonomy(axes)
    for problem in taxonomy.find_problems():
        collector.add_domain(paths.TAXONOMY_FILE, problem)
    return None if len(collector.problems) > before else taxonomy


def _load_catalogue(
    collector: _Collector, summaries: list[FileSummary], taxonomy: Taxonomy | None
) -> ReferenceCatalogue | None:
    before = len(collector.problems)

    def one(file: str, model: type[_M], key: str, factory: Callable[[Any], _D]) -> tuple[_D, ...]:
        parsed = collector.parse(file, model)
        if parsed is None:
            return ()
        items = collector.build(file, key, getattr(parsed, key), factory)
        summaries.append(FileSummary(file, _plural(len(items), key.rstrip("s"))))
        return items

    lanes = one(paths.LANES_FILE, LanesFile, "lanes", _lane)
    topics = one(paths.TOPICS_FILE, TopicsFile, "topics", _topic)
    hazards = one(paths.HAZARDS_FILE, HazardsFile, "hazards", _hazard)
    places = one(paths.PLACES_FILE, PlacesFile, "places", _place)
    actors = one(paths.ACTORS_FILE, ActorsFile, "actors", _actor)

    if taxonomy is None or len(collector.problems) > before:
        collector.notes.append("reference cross-checks skipped until the problems above are fixed")
        return None
    catalogue = ReferenceCatalogue(taxonomy, topics, hazards, places, actors, lanes)
    for problem in catalogue.find_problems():
        if problem.scope != "taxonomy" or problem.location == "axes":
            # Taxonomy-internal problems were reported when the taxonomy loaded.
            collector.add_domain(_SCOPE_FILES.get(problem.scope, paths.CONFIG_DIR), problem)
    return None if len(collector.problems) > before else catalogue


def _load_requirement_set(
    collector: _Collector,
    file: str,
    taxonomy: Taxonomy | None,
    summaries: list[FileSummary],
) -> RequirementSet | None:
    before = len(collector.problems)
    parsed = collector.parse(file, RequirementSetFile)
    if parsed is None:
        return None
    stem = Path(file).stem
    if parsed.id != stem:
        collector.add(file, "id", f"set id '{parsed.id}' must match the file name '{stem}'")
    requirements = collector.build(file, "requirements", parsed.requirements, _requirement)
    groups = collector.build(file, "groups", parsed.groups, _group)
    impacts = sum(1 for group in groups if group.kind is GroupKind.IMPACT)
    wbos = sum(1 for group in groups if group.kind is GroupKind.WBO)
    summaries.append(
        FileSummary(
            file,
            f"{_plural(len(requirements), 'requirement')}, {_plural(len(groups), 'group')} "
            f"({impacts} impact, {wbos} wbo)",
        )
    )
    if len(collector.problems) > before:
        return None
    requirement_set = RequirementSet(
        id=KebabId(parsed.id),
        name=CleanText(parsed.name),
        version=CleanText(parsed.version),
        source_doc=CleanText(parsed.source_doc),
        requirements=requirements,
        groups=groups,
    )
    if taxonomy is None:
        collector.notes.append(f"{file}: taxonomy cross-checks skipped until the taxonomy loads")
        return None
    for problem in requirement_set.find_problems(taxonomy):
        collector.add_domain(file, problem)
    return None if len(collector.problems) > before else requirement_set


def _load_sources(
    collector: _Collector, summaries: list[FileSummary], catalogue: ReferenceCatalogue | None
) -> tuple[Source, ...] | None:
    before = len(collector.problems)
    parsed = collector.parse(paths.SOURCES_FILE, SourcesFile)
    if parsed is None:
        return None
    sources = collector.build(paths.SOURCES_FILE, "sources", parsed.sources, _source)
    by_status = ", ".join(
        f"{count} {status}"
        for status, count in sorted(Counter(s.status.value for s in sources).items())
    )
    summaries.append(
        FileSummary(paths.SOURCES_FILE, f"{_plural(len(sources), 'source')} ({by_status})")
    )
    if len(collector.problems) > before:
        return None
    if catalogue is None:
        collector.notes.append(
            f"{paths.SOURCES_FILE}: cross-checks skipped until the catalogues load"
        )
        return None
    for problem in find_source_problems(
        sources, lane_ids=catalogue.lane_ids(), actor_ids=catalogue.actor_ids()
    ):
        collector.add_domain(paths.SOURCES_FILE, problem)
    return None if len(collector.problems) > before else sources


def _load_gating(
    collector: _Collector,
    summaries: list[FileSummary],
    catalogue: ReferenceCatalogue | None,
    sources: tuple[Source, ...] | None,
) -> GatingRules | None:
    before = len(collector.problems)
    parsed = collector.parse(paths.GATING_FILE, GatingFile)
    if parsed is None:
        return None
    if catalogue is None:
        collector.notes.append(
            f"{paths.GATING_FILE}: place tokens skipped until the catalogues load"
        )
        return None
    seen_tokens: set[str] = set()
    for t, token in enumerate(parsed.relevance_tokens):
        if token != " ".join(token.casefold().split()):
            collector.add(
                paths.GATING_FILE,
                f"relevance_tokens[{t}]",
                f"token '{token}' must be lower-case words separated by one space",
            )
        elif token in seen_tokens:
            collector.add(
                paths.GATING_FILE, f"relevance_tokens[{t}]", f"token '{token}' is repeated"
            )
        seen_tokens.add(token)
    if len(collector.problems) > before:
        return None
    kinds = set(parsed.relevance_place_kinds)
    names = [
        name
        for place in catalogue.places
        if place.kind in kinds
        for name in (place.name, place.welsh_name)
        if name is not None
    ]
    try:
        rules = GatingRules(
            frozenset(parsed.own_domains), relevance_tokens(parsed.relevance_tokens, names)
        )
    except ValueError as error:
        collector.add(paths.GATING_FILE, "", str(error))
        return None
    summaries.append(
        FileSummary(
            paths.GATING_FILE,
            f"{_plural(len(rules.own_domains), 'own domain')}, "
            f"{_plural(len(rules.relevance_tokens), 'relevance token')}",
        )
    )
    for s, source in enumerate(sources or ()):
        if rules.is_own_domain(source.domain):
            collector.add(
                paths.SOURCES_FILE,
                f"sources[{s}].domain",
                f"source '{source.id}' is on an own domain, so the gates would drop every hit",
            )
    return None if len(collector.problems) > before else rules


def _load_instrument(
    collector: _Collector,
    summaries: list[FileSummary],
    catalogue: ReferenceCatalogue | None,
    requirement_sets: Sequence[RequirementSet] | None,
    sources: tuple[Source, ...] | None,
) -> QueryInstrument | None:
    before = len(collector.problems)
    parsed = collector.parse(paths.INSTRUMENT_FILE, InstrumentFile)
    if parsed is None:
        return None
    queries = collector.build(paths.INSTRUMENT_FILE, "queries", parsed.queries, _query)
    if len(collector.problems) > before:
        return None
    try:
        instrument = QueryInstrument(
            version=CleanText(parsed.version),
            content_hash=parsed.content_hash,
            global_negative_terms=tuple(CleanText(t) for t in parsed.global_negative_terms),
            max_requests_per_run=parsed.max_requests_per_run,
            queries=queries,
        )
    except ValueError as error:
        collector.add(paths.INSTRUMENT_FILE, "", str(error))
        return None
    per_discipline = Counter(query.discipline for query in queries)
    mix = ", ".join(f"{per_discipline[d]} {d.value}" for d in Discipline if per_discipline[d])
    summaries.append(
        FileSummary(
            paths.INSTRUMENT_FILE,
            f"version {instrument.version}, {_plural(len(queries), 'query', 'queries')} ({mix}), "
            f"budget {instrument.max_requests_per_run} requests",
        )
    )
    if catalogue is None or sources is None or requirement_sets is None:
        collector.notes.append(
            f"{paths.INSTRUMENT_FILE}: cross-checks skipped until the catalogues, requirement "
            "sets and sources load"
        )
        return None
    requirement_ids = {r for rs in requirement_sets for r in rs.requirement_ids()}
    for problem in instrument.find_problems(
        lane_ids=catalogue.lane_ids(),
        requirement_ids=requirement_ids,
        topic_ids=catalogue.topic_ids(),
        sources={source.id: source for source in sources},
    ):
        collector.add_domain(paths.INSTRUMENT_FILE, problem)
    return None if len(collector.problems) > before else instrument


def check_config(root: Path) -> CheckReport:
    """Load and validate every configuration file under ``root``, collecting every problem."""
    collector = _Collector(root)
    summaries: list[FileSummary] = []
    taxonomy = _load_taxonomy(collector, summaries)
    catalogue = _load_catalogue(collector, summaries, taxonomy)
    sets_dir = root / paths.REQUIREMENT_SETS_DIR
    set_files = sorted(sets_dir.glob("*.json")) if sets_dir.is_dir() else []
    if not set_files:
        collector.add(paths.REQUIREMENT_SETS_DIR, "", "no requirement set files found")
    requirement_sets: list[RequirementSet] = []
    for path in set_files:
        file = path.relative_to(root).as_posix()
        loaded = _load_requirement_set(collector, file, taxonomy, summaries)
        if loaded is not None:
            requirement_sets.append(loaded)
    sources = _load_sources(collector, summaries, catalogue)
    gating = _load_gating(collector, summaries, catalogue, sources)
    all_sets = requirement_sets if len(requirement_sets) == len(set_files) else None
    instrument = _load_instrument(collector, summaries, catalogue, all_sets, sources)
    problems = tuple(collector.problems)
    config = (
        LoadedConfig(catalogue, tuple(requirement_sets), sources, instrument, gating)
        if catalogue is not None
        and sources is not None
        and instrument is not None
        and gating is not None
        and not problems
        else None
    )
    return CheckReport(tuple(summaries), problems, config, tuple(collector.notes))


def load_config(root: Path) -> LoadedConfig:
    """The validated configuration under ``root``, or ``ConfigInvalidError`` with every problem."""
    report = check_config(root)
    if report.config is None:
        raise ConfigInvalidError(report.problems)
    return report.config
