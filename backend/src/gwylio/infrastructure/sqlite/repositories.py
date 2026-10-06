"""SQLite repositories for the Reference, Direction and Collection contexts.

Every SQL statement the application runs against its tables lives in this
module. Each repository loads a whole aggregate on read and writes a whole
aggregate on save, deleting and reinserting its children inside one
transaction. They keep the behaviour of the in-memory repositories in
``gwylio.infrastructure.memory`` (the same refusals, raised as the same domain
errors), with three differences that come from the database:

- a candidate needs its run, its source and its lane stored first, and a
  sighting its source (foreign keys);
- a candidate is reinforced at most once (the candidates file says the same);
- a run's candidates, sightings and reinforcements come back in the
  candidates file's normalised order (canonical URL; sighting id; report id
  then candidate id) rather than insertion order, so a database rebuilt from
  the files reads exactly like the one the scan wrote.

``save_config`` writes the whole configuration (catalogues, requirement sets,
sources) in one transaction. Rows that facts point at (a source a candidate
names, a lane) may vanish for a moment while their table is rewritten, so
foreign keys are checked at commit: removing a source from ``config/`` that a
stored run names fails there, which is why sources are retired, never deleted.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Final, TypeVar

from gwylio.collection.model import (
    Candidate,
    Funnel,
    Query,
    QueryInstrument,
    Reinforcement,
    RunId,
    RunImmutable,
    RunStatus,
    ScanRun,
    Sighting,
    Source,
    SourceStatus,
)
from gwylio.direction.model import (
    GroupKind,
    Requirement,
    RequirementGroup,
    RequirementSet,
    Scanability,
)
from gwylio.infrastructure.config.loaders import LoadedConfig
from gwylio.infrastructure.sqlite.db import Database, Value
from gwylio.reference.model import (
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
    TaxonomyNode,
    Topic,
)
from gwylio.shared.errors import DomainError, DuplicateId, UnknownReference
from gwylio.shared.values import CanonicalUrl, CleanText, IsoDate, KebabId
from gwylio.shared.vocabulary import Discipline, MatchedBy, Reliability

__all__ = [
    "TIMESTAMP_FORMAT",
    "SqliteCandidateRepository",
    "SqliteInstrumentRepository",
    "SqliteReferenceRepository",
    "SqliteRequirementSetRepository",
    "SqliteScanRunRepository",
    "SqliteSourceRepository",
    "dump_table",
    "format_timestamp",
    "parse_timestamp",
    "save_config",
    "table_counts",
]

TIMESTAMP_FORMAT: Final[str] = "%Y-%m-%dT%H:%M:%S.%fZ"
"""How timestamps are stored: ISO 8601 in UTC with microseconds, so text order is time order."""

_T = TypeVar("_T")


# Conversions between domain values and column values.


def format_timestamp(moment: datetime) -> str:
    """An aware datetime as stored text, in UTC."""
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("only timezone-aware datetimes are stored")
    return moment.astimezone(UTC).strftime(TIMESTAMP_FORMAT)


def parse_timestamp(text: str) -> datetime:
    """Stored timestamp text as an aware UTC datetime."""
    return datetime.strptime(text, TIMESTAMP_FORMAT).replace(tzinfo=UTC)


def _json(values: Iterable[str]) -> str:
    return json.dumps([str(value) for value in values], ensure_ascii=False, separators=(",", ":"))


def _strings(text: str) -> list[str]:
    values = json.loads(text)
    if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
        raise ValueError(f"expected a JSON array of strings, got {text!r}")
    return values


def _clean_tuple(text: str) -> tuple[CleanText, ...]:
    return tuple(CleanText(value) for value in _strings(text))


def _kebab_tuple(text: str) -> tuple[KebabId, ...]:
    return tuple(KebabId(value) for value in _strings(text))


def _opt_clean(value: object) -> CleanText | None:
    return None if value is None else CleanText(str(value))


def _opt_kebab(value: object) -> KebabId | None:
    return None if value is None else KebabId(str(value))


def _opt_str(value: object) -> str | None:
    return None if value is None else str(value)


def _integrity(error: sqlite3.IntegrityError, messages: Mapping[str, DomainError]) -> DomainError:
    """The domain error for a constraint failure, chosen by the constraint SQLite names."""
    text = str(error)
    for fragment, domain_error in messages.items():
        if fragment in text:
            return domain_error
    return DomainError(f"the database refused the write: {text}")


def _group_rows(rows: Iterable[sqlite3.Row], key: str) -> dict[str, list[sqlite3.Row]]:
    grouped: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        grouped.setdefault(str(row[key]), []).append(row)
    return grouped


# Reference.


class SqliteReferenceRepository:
    """The reference catalogue: taxonomy, lanes, topics, hazards, places and actors."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def save(self, catalogue: ReferenceCatalogue) -> None:
        """Replace the whole stored catalogue with ``catalogue``."""
        db = self._db
        with db.transaction():
            db.defer_foreign_keys()
            for table in ("actor", "place", "hazard", "topic", "lane", "taxonomy_node"):
                db.execute(f"DELETE FROM {table}")
            db.execute("DELETE FROM taxonomy_axis")
            for a, axis in enumerate(catalogue.taxonomy.axes):
                db.execute(
                    "INSERT INTO taxonomy_axis (id, position, name) VALUES (?, ?, ?)",
                    (axis.id, a, axis.name),
                )
                db.executemany(
                    "INSERT INTO taxonomy_node (id, axis_id, position, name, kind, note) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    [
                        (node.id, axis.id, n, node.name, node.kind.value, node.note)
                        for n, node in enumerate(axis.nodes)
                    ],
                )
            db.executemany(
                "INSERT INTO lane (id, position, name, lens, description) VALUES (?, ?, ?, ?, ?)",
                [
                    (lane.id, i, lane.name, lane.lens.value, lane.description)
                    for i, lane in enumerate(catalogue.lanes)
                ],
            )
            db.executemany(
                "INSERT INTO topic (id, position, name, note) VALUES (?, ?, ?, ?)",
                [(t.id, i, t.name, t.note) for i, t in enumerate(catalogue.topics)],
            )
            db.executemany(
                "INSERT INTO hazard (id, position, name, family, note) VALUES (?, ?, ?, ?, ?)",
                [(h.id, i, h.name, h.family, h.note) for i, h in enumerate(catalogue.hazards)],
            )
            db.executemany(
                "INSERT INTO place (id, position, name, welsh_name, kind, parent, latitude, "
                "longitude) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        p.id,
                        i,
                        p.name,
                        p.welsh_name,
                        p.kind.value,
                        p.parent,
                        None if p.centroid is None else p.centroid[0],
                        None if p.centroid is None else p.centroid[1],
                    )
                    for i, p in enumerate(catalogue.places)
                ],
            )
            db.executemany(
                "INSERT INTO actor (id, position, name, kind, lane, domain) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (actor.id, i, actor.name, actor.kind.value, actor.lane, actor.domain)
                    for i, actor in enumerate(catalogue.actors)
                ],
            )

    def load(self) -> ReferenceCatalogue | None:
        """The stored catalogue, or ``None`` when none has been saved."""
        db = self._db
        axis_rows = db.fetch_all("SELECT id, name FROM taxonomy_axis ORDER BY position")
        if not axis_rows:
            return None
        nodes = _group_rows(
            db.fetch_all(
                "SELECT axis_id, id, name, kind, note FROM taxonomy_node ORDER BY axis_id, position"
            ),
            "axis_id",
        )
        taxonomy = Taxonomy(
            tuple(
                TaxonomyAxis(
                    KebabId(row["id"]),
                    CleanText(row["name"]),
                    tuple(
                        TaxonomyNode(
                            KebabId(n["id"]),
                            CleanText(n["name"]),
                            NodeKind(n["kind"]),
                            _opt_clean(n["note"]),
                        )
                        for n in nodes.get(str(row["id"]), [])
                    ),
                )
                for row in axis_rows
            )
        )
        lanes = tuple(
            Lane(
                KebabId(r["id"]), CleanText(r["name"]), Lens(r["lens"]), CleanText(r["description"])
            )
            for r in db.fetch_all("SELECT * FROM lane ORDER BY position")
        )
        topics = tuple(
            Topic(KebabId(r["id"]), CleanText(r["name"]), _opt_clean(r["note"]))
            for r in db.fetch_all("SELECT * FROM topic ORDER BY position")
        )
        hazards = tuple(
            Hazard(
                KebabId(r["id"]), CleanText(r["name"]), KebabId(r["family"]), _opt_clean(r["note"])
            )
            for r in db.fetch_all("SELECT * FROM hazard ORDER BY position")
        )
        places = tuple(
            Place(
                id=KebabId(r["id"]),
                name=CleanText(r["name"]),
                kind=PlaceKind(r["kind"]),
                parent=_opt_kebab(r["parent"]),
                centroid=None
                if r["latitude"] is None
                else (float(r["latitude"]), float(r["longitude"])),
                welsh_name=_opt_clean(r["welsh_name"]),
            )
            for r in db.fetch_all("SELECT * FROM place ORDER BY position")
        )
        actors = tuple(
            Actor(
                KebabId(r["id"]),
                CleanText(r["name"]),
                ActorKind(r["kind"]),
                KebabId(r["lane"]),
                _opt_str(r["domain"]),
            )
            for r in db.fetch_all("SELECT * FROM actor ORDER BY position")
        )
        return ReferenceCatalogue(taxonomy, topics, hazards, places, actors, lanes)


# Direction.


class SqliteRequirementSetRepository:
    """Requirement sets with their requirements, groups, members and expected coverage."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def save(self, requirement_set: RequirementSet) -> None:
        """Store ``requirement_set``, replacing a stored set with the same id."""
        db = self._db
        with db.transaction():
            db.defer_foreign_keys()
            position = db.scalar(
                "SELECT position FROM requirement_set WHERE id = ?", (requirement_set.id,)
            )
            if position is None:
                position = db.scalar("SELECT COALESCE(MAX(position) + 1, 0) FROM requirement_set")
            self._delete(requirement_set.id)
            self._insert(requirement_set, int(position or 0))

    def replace_all(self, requirement_sets: Sequence[RequirementSet]) -> None:
        """Replace every stored set with ``requirement_sets``, in this order."""
        db = self._db
        with db.transaction():
            db.defer_foreign_keys()
            for row in db.fetch_all("SELECT id FROM requirement_set"):
                self._delete(str(row["id"]))
            for position, requirement_set in enumerate(requirement_sets):
                self._insert(requirement_set, position)

    def _delete(self, set_id: str) -> None:
        for table in (
            "requirement_group_related",
            "requirement_group_member",
            "requirement_group",
            "requirement_expected_coverage",
            "requirement",
        ):
            self._db.execute(f"DELETE FROM {table} WHERE set_id = ?", (set_id,))
        self._db.execute("DELETE FROM requirement_set WHERE id = ?", (set_id,))

    def _insert(self, rs: RequirementSet, position: int) -> None:
        db = self._db
        db.execute(
            "INSERT INTO requirement_set (id, position, name, version, source_doc) "
            "VALUES (?, ?, ?, ?, ?)",
            (rs.id, position, rs.name, rs.version, rs.source_doc),
        )
        db.executemany(
            "INSERT INTO requirement (set_id, id, position, code, name, short, scanability, "
            "scanability_note, keywords, metric_sources, development) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    rs.id,
                    r.id,
                    i,
                    r.code,
                    r.name,
                    r.short,
                    r.scanability.value,
                    r.scanability_note,
                    _json(r.keywords),
                    _json(r.metric_sources),
                    r.development,
                )
                for i, r in enumerate(rs.requirements)
            ],
        )
        db.executemany(
            "INSERT INTO requirement_expected_coverage (set_id, requirement_id, position, node_id) "
            "VALUES (?, ?, ?, ?)",
            [
                (rs.id, r.id, c, node)
                for r in rs.requirements
                for c, node in enumerate(r.expected_coverage)
            ],
        )
        db.executemany(
            "INSERT INTO requirement_group (set_id, id, position, kind, name, statement, note) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (rs.id, g.id, i, g.kind.value, g.name, g.statement, g.note)
                for i, g in enumerate(rs.groups)
            ],
        )
        db.executemany(
            "INSERT INTO requirement_group_member (set_id, group_id, position, requirement_id) "
            "VALUES (?, ?, ?, ?)",
            [(rs.id, g.id, m, member) for g in rs.groups for m, member in enumerate(g.members)],
        )
        db.executemany(
            "INSERT INTO requirement_group_related (set_id, group_id, position, related_group_id) "
            "VALUES (?, ?, ?, ?)",
            [
                (rs.id, g.id, n, related)
                for g in rs.groups
                for n, related in enumerate(g.related_groups)
            ],
        )

    def get(self, set_id: str) -> RequirementSet | None:
        """The stored set with this id, or ``None``."""
        row = self._db.fetch_one("SELECT * FROM requirement_set WHERE id = ?", (set_id,))
        return None if row is None else self._load(row)

    def all(self) -> tuple[RequirementSet, ...]:
        """Every stored set, in stored order."""
        rows = self._db.fetch_all("SELECT * FROM requirement_set ORDER BY position")
        return tuple(self._load(row) for row in rows)

    def _load(self, row: sqlite3.Row) -> RequirementSet:
        db = self._db
        set_id = str(row["id"])
        coverage = _group_rows(
            db.fetch_all(
                "SELECT requirement_id, node_id FROM requirement_expected_coverage "
                "WHERE set_id = ? ORDER BY requirement_id, position",
                (set_id,),
            ),
            "requirement_id",
        )
        requirements = tuple(
            Requirement(
                code=str(r["code"]),
                id=KebabId(r["id"]),
                name=CleanText(r["name"]),
                short=CleanText(r["short"]),
                scanability=Scanability(r["scanability"]),
                scanability_note=CleanText(r["scanability_note"]),
                keywords=_clean_tuple(r["keywords"]),
                expected_coverage=tuple(
                    KebabId(c["node_id"]) for c in coverage.get(str(r["id"]), [])
                ),
                metric_sources=_clean_tuple(r["metric_sources"]),
                development=bool(r["development"]),
            )
            for r in db.fetch_all(
                "SELECT * FROM requirement WHERE set_id = ? ORDER BY position", (set_id,)
            )
        )
        members = _group_rows(
            db.fetch_all(
                "SELECT group_id, requirement_id FROM requirement_group_member "
                "WHERE set_id = ? ORDER BY group_id, position",
                (set_id,),
            ),
            "group_id",
        )
        related = _group_rows(
            db.fetch_all(
                "SELECT group_id, related_group_id FROM requirement_group_related "
                "WHERE set_id = ? ORDER BY group_id, position",
                (set_id,),
            ),
            "group_id",
        )
        groups = tuple(
            RequirementGroup(
                id=KebabId(g["id"]),
                kind=GroupKind(g["kind"]),
                name=CleanText(g["name"]),
                members=tuple(KebabId(m["requirement_id"]) for m in members.get(str(g["id"]), [])),
                statement=_opt_clean(g["statement"]),
                note=_opt_clean(g["note"]),
                related_groups=tuple(
                    KebabId(r["related_group_id"]) for r in related.get(str(g["id"]), [])
                ),
            )
            for g in db.fetch_all(
                "SELECT * FROM requirement_group WHERE set_id = ? ORDER BY position", (set_id,)
            )
        )
        return RequirementSet(
            id=KebabId(set_id),
            name=CleanText(row["name"]),
            version=CleanText(row["version"]),
            source_doc=CleanText(row["source_doc"]),
            requirements=requirements,
            groups=groups,
        )


# Collection: sources and instruments.


def _source_row(source: Source, position: int) -> tuple[Value, ...]:
    return (
        source.id,
        position,
        source.name,
        source.domain,
        source.feed_url,
        source.discipline.value,
        source.lane,
        source.actor,
        source.reliability.value,
        source.trusted,
        source.site_pass,
        source.status.value,
        str(source.added_on),
        source.notes,
    )


_SOURCE_INSERT: Final[str] = (
    "INSERT INTO source (id, position, name, domain, feed_url, discipline, lane, actor, "
    "reliability, trusted, site_pass, status, added_on, notes) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)


def _source(row: sqlite3.Row) -> Source:
    return Source(
        id=KebabId(row["id"]),
        name=CleanText(row["name"]),
        domain=str(row["domain"]),
        feed_url=_opt_str(row["feed_url"]),
        discipline=Discipline(row["discipline"]),
        lane=KebabId(row["lane"]),
        actor=KebabId(row["actor"]),
        reliability=Reliability(row["reliability"]),
        trusted=bool(row["trusted"]),
        site_pass=bool(row["site_pass"]),
        status=SourceStatus(row["status"]),
        added_on=IsoDate(str(row["added_on"])),
        notes=_opt_clean(row["notes"]),
    )


class SqliteSourceRepository:
    """The watchlist, in configuration order."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def add(self, source: Source) -> None:
        """Store a new source; refuse an id that is already stored."""
        db = self._db
        with db.transaction():
            if db.scalar("SELECT 1 FROM source WHERE id = ?", (source.id,)) is not None:
                raise DuplicateId(f"source '{source.id}' is already stored", scope="sources")
            position = db.scalar("SELECT COALESCE(MAX(position) + 1, 0) FROM source")
            try:
                db.execute(_SOURCE_INSERT, _source_row(source, int(position or 0)))
            except sqlite3.IntegrityError as error:
                raise _integrity(
                    error,
                    {
                        "source.domain": DuplicateId(
                            f"domain '{source.domain}' is already watched", scope="sources"
                        ),
                        "FOREIGN KEY": UnknownReference(
                            f"source '{source.id}' names a lane or actor that is not stored",
                            scope="sources",
                        ),
                    },
                ) from error

    def replace_all(self, sources: Sequence[Source]) -> None:
        """Replace the whole watchlist with ``sources``, in this order."""
        db = self._db
        with db.transaction():
            db.defer_foreign_keys()
            db.execute("DELETE FROM source")
            db.executemany(_SOURCE_INSERT, [_source_row(s, i) for i, s in enumerate(sources)])

    def get(self, source_id: str) -> Source | None:
        """The source with this id, or ``None``."""
        row = self._db.fetch_one("SELECT * FROM source WHERE id = ?", (source_id,))
        return None if row is None else _source(row)

    def all(self) -> tuple[Source, ...]:
        """Every stored source, in order."""
        return tuple(
            _source(r) for r in self._db.fetch_all("SELECT * FROM source ORDER BY position")
        )


class SqliteInstrumentRepository:
    """Every instrument version a run has used. A version, once stored, never changes."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def add(self, instrument: QueryInstrument) -> None:
        """Store a new version; a stored version with the same hash is a no-op, another refused."""
        db = self._db
        with db.transaction():
            stored = db.scalar(
                "SELECT content_hash FROM instrument_version WHERE version = ?",
                (instrument.version,),
            )
            if stored is not None:
                if stored == instrument.content_hash:
                    return
                raise DomainError(
                    f"instrument version {instrument.version} is already stored with a "
                    "different hash",
                    scope="instrument",
                )
            db.execute(
                "INSERT INTO instrument_version (version, content_hash, max_requests_per_run, "
                "global_negative_terms) VALUES (?, ?, ?, ?)",
                (
                    instrument.version,
                    instrument.content_hash,
                    instrument.max_requests_per_run,
                    _json(instrument.global_negative_terms),
                ),
            )
            db.executemany(
                "INSERT INTO instrument_query (version, position, id, discipline, lane, text, "
                "requirement_hints, topic_hints, negative_terms, site_source_ids) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        instrument.version,
                        i,
                        q.id,
                        q.discipline.value,
                        q.lane,
                        q.text,
                        _json(q.requirement_hints),
                        _json(q.topic_hints),
                        _json(q.negative_terms),
                        _json(q.site_source_ids),
                    )
                    for i, q in enumerate(instrument.queries)
                ],
            )

    def get(self, version: str) -> QueryInstrument | None:
        """The instrument with this version, or ``None``."""
        db = self._db
        row = db.fetch_one("SELECT * FROM instrument_version WHERE version = ?", (version,))
        if row is None:
            return None
        queries = tuple(
            Query(
                id=KebabId(q["id"]),
                discipline=Discipline(q["discipline"]),
                lane=KebabId(q["lane"]),
                text=CleanText(q["text"]),
                requirement_hints=_kebab_tuple(q["requirement_hints"]),
                topic_hints=_kebab_tuple(q["topic_hints"]),
                negative_terms=_clean_tuple(q["negative_terms"]),
                site_source_ids=_kebab_tuple(q["site_source_ids"]),
            )
            for q in db.fetch_all(
                "SELECT * FROM instrument_query WHERE version = ? ORDER BY position", (version,)
            )
        )
        return QueryInstrument(
            version=CleanText(row["version"]),
            content_hash=str(row["content_hash"]),
            global_negative_terms=_clean_tuple(row["global_negative_terms"]),
            max_requests_per_run=int(row["max_requests_per_run"]),
            queries=queries,
        )

    def versions(self) -> tuple[str, ...]:
        """Every stored version, sorted."""
        rows = self._db.fetch_all("SELECT version FROM instrument_version ORDER BY version")
        return tuple(str(row[0]) for row in rows)


# Collection: scan runs.

_FUNNEL_FIELDS: Final[tuple[str, ...]] = (
    "raw",
    "dropped_own",
    "dropped_negative",
    "dropped_unrelated",
    "passed",
    "unique",
    "seen_before",
    "new",
    "reinforcements",
)


class SqliteScanRunRepository:
    """Every finished scan run, oldest first."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def add(self, run: ScanRun) -> None:
        """Store a finished run; refuse a running run and a run id already stored."""
        if not run.finished or run.finished_at is None:
            raise DomainError(f"run {run.id} is still running; store it when it finishes")
        db = self._db
        with db.transaction():
            if db.scalar("SELECT 1 FROM scan_run WHERE id = ?", (run.id,)) is not None:
                raise RunImmutable(f"run {run.id} is already stored and cannot change")
            columns = ", ".join(f"funnel_{name}" for name in _FUNNEL_FIELDS)
            marks = ", ".join("?" for _ in _FUNNEL_FIELDS)
            try:
                db.execute(
                    "INSERT INTO scan_run (id, started_at, finished_at, status, "
                    "instrument_version, instrument_hash, request_budget, requests_made, "
                    f"budget_exhausted, notes, {columns}) "
                    f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, {marks})",
                    (
                        run.id,
                        format_timestamp(run.started_at),
                        format_timestamp(run.finished_at),
                        run.status.value,
                        run.instrument_version,
                        run.instrument_hash,
                        run.request_budget,
                        run.requests_made,
                        run.budget_exhausted,
                        _json(run.notes),
                        *(getattr(run.funnel, name) for name in _FUNNEL_FIELDS),
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise _integrity(
                    error,
                    {
                        "FOREIGN KEY": UnknownReference(
                            f"run {run.id} used instrument {run.instrument_version} "
                            f"({run.instrument_hash}), which is not stored",
                            scope="scan_run",
                        )
                    },
                ) from error
            db.executemany(
                "INSERT INTO scan_run_discipline (run_id, position, discipline) VALUES (?, ?, ?)",
                [(run.id, i, d.value) for i, d in enumerate(run.disciplines)],
            )

    def get(self, run_id: str) -> ScanRun | None:
        """The run with this id, or ``None``."""
        row = self._db.fetch_one("SELECT * FROM scan_run WHERE id = ?", (run_id,))
        return None if row is None else self._load(row)

    def all(self) -> tuple[ScanRun, ...]:
        """Every stored run, oldest first (by start time, then id)."""
        rows = self._db.fetch_all("SELECT * FROM scan_run ORDER BY started_at, id")
        return tuple(self._load(row) for row in rows)

    def _load(self, row: sqlite3.Row) -> ScanRun:
        disciplines = tuple(
            Discipline(r["discipline"])
            for r in self._db.fetch_all(
                "SELECT discipline FROM scan_run_discipline WHERE run_id = ? ORDER BY position",
                (row["id"],),
            )
        )
        return ScanRun(
            id=RunId(row["id"]),
            started_at=parse_timestamp(row["started_at"]),
            instrument_version=CleanText(row["instrument_version"]),
            instrument_hash=str(row["instrument_hash"]),
            disciplines=disciplines,
            request_budget=int(row["request_budget"]),
            status=RunStatus(row["status"]),
            finished_at=parse_timestamp(row["finished_at"]),
            funnel=Funnel(**{name: int(row[f"funnel_{name}"]) for name in _FUNNEL_FIELDS}),
            requests_made=int(row["requests_made"]),
            budget_exhausted=bool(row["budget_exhausted"]),
            notes=_clean_tuple(row["notes"]),
        )


# Collection: candidates, sightings and reinforcements.


def _candidate(row: sqlite3.Row) -> Candidate:
    return Candidate(
        id=KebabId(row["id"]),
        run_id=RunId(row["run_id"]),
        canonical_url=CanonicalUrl(row["canonical_url"]),
        url=str(row["url"]),
        title=CleanText(row["title"]),
        snippet=CleanText(row["snippet"]),
        published_on=None if row["published_on"] is None else IsoDate(str(row["published_on"])),
        first_seen_run_id=RunId(row["first_seen_run_id"]),
        trusted=bool(row["trusted"]),
        source_id=_opt_kebab(row["source_id"]),
        lane=KebabId(row["lane"]),
        discipline=Discipline(row["discipline"]),
        query_id=KebabId(row["query_id"]),
        requirement_hints=_kebab_tuple(row["requirement_hints"]),
        topic_hints=_kebab_tuple(row["topic_hints"]),
    )


def _sighting(row: sqlite3.Row) -> Sighting:
    return Sighting(
        id=KebabId(row["id"]),
        run_id=RunId(row["run_id"]),
        candidate_id=KebabId(row["candidate_id"]),
        source_id=_opt_kebab(row["source_id"]),
        query_id=KebabId(row["query_id"]),
        discipline=Discipline(row["discipline"]),
    )


class SqliteCandidateRepository:
    """Candidates, their sightings and the reinforcements found at collection."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def _each(self, items: Sequence[_T], insert: Callable[[_T], None]) -> None:
        with self._db.transaction():
            for item in items:
                insert(item)

    def add_candidates(self, candidates: Sequence[Candidate]) -> None:
        """Store candidates; refuse a repeated id or a canonical URL repeated within a run."""
        self._each(candidates, self._add_candidate)

    def _add_candidate(self, c: Candidate) -> None:
        try:
            self._db.execute(
                "INSERT INTO candidate (id, run_id, canonical_url, url, title, snippet, "
                "published_on, first_seen_run_id, trusted, source_id, lane, discipline, "
                "query_id, requirement_hints, topic_hints) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    c.id,
                    c.run_id,
                    c.canonical_url.value,
                    c.url,
                    c.title,
                    c.snippet,
                    None if c.published_on is None else str(c.published_on),
                    c.first_seen_run_id,
                    c.trusted,
                    c.source_id,
                    c.lane,
                    c.discipline.value,
                    c.query_id,
                    _json(c.requirement_hints),
                    _json(c.topic_hints),
                ),
            )
        except sqlite3.IntegrityError as error:
            raise _integrity(
                error,
                {
                    "candidate.run_id, candidate.canonical_url": DuplicateId(
                        f"run {c.run_id} already has a candidate for {c.canonical_url.value}"
                    ),
                    "candidate.id": DuplicateId(f"candidate '{c.id}' is already stored"),
                    "FOREIGN KEY": UnknownReference(
                        f"candidate '{c.id}' names a run ({c.run_id} or {c.first_seen_run_id}), "
                        f"source ({c.source_id}) or lane ({c.lane}) that is not stored"
                    ),
                },
            ) from error

    def add_sightings(self, sightings: Sequence[Sighting]) -> None:
        """Store sightings; refuse a repeated id or a sighting of an unknown candidate."""
        self._each(sightings, self._add_sighting)

    def _add_sighting(self, s: Sighting) -> None:
        db = self._db
        if db.scalar("SELECT 1 FROM candidate WHERE id = ?", (s.candidate_id,)) is None:
            raise UnknownReference(f"sighting of unknown candidate '{s.candidate_id}'")
        try:
            db.execute(
                "INSERT INTO sighting (id, run_id, candidate_id, source_id, query_id, discipline) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (s.id, s.run_id, s.candidate_id, s.source_id, s.query_id, s.discipline.value),
            )
        except sqlite3.IntegrityError as error:
            raise _integrity(
                error,
                {
                    "sighting.id": DuplicateId(f"sighting '{s.id}' is already stored"),
                    "FOREIGN KEY": UnknownReference(
                        f"sighting '{s.id}' names a run ({s.run_id}) other than its candidate's, "
                        f"or a source ({s.source_id}) that is not stored"
                    ),
                },
            ) from error

    def add_reinforcements(self, reinforcements: Sequence[Reinforcement]) -> None:
        """Store reinforcements; refuse one for an unknown candidate."""
        self._each(reinforcements, self._add_reinforcement)

    def _add_reinforcement(self, r: Reinforcement) -> None:
        db = self._db
        if db.scalar("SELECT 1 FROM candidate WHERE id = ?", (r.candidate_id,)) is None:
            raise UnknownReference(f"reinforcement of unknown candidate '{r.candidate_id}'")
        try:
            db.execute(
                "INSERT INTO reinforcement (candidate_id, report_id, matched_by) VALUES (?, ?, ?)",
                (r.candidate_id, r.report_id, r.matched_by.value),
            )
        except sqlite3.IntegrityError as error:
            raise _integrity(
                error,
                {
                    "reinforcement.candidate_id": DuplicateId(
                        f"candidate '{r.candidate_id}' is already reinforced"
                    )
                },
            ) from error

    def candidates_for_run(self, run_id: str) -> tuple[Candidate, ...]:
        """The run's candidates, by canonical URL (the candidates file's order)."""
        rows = self._db.fetch_all(
            "SELECT * FROM candidate WHERE run_id = ? ORDER BY canonical_url", (run_id,)
        )
        return tuple(_candidate(row) for row in rows)

    def sightings_for_run(self, run_id: str) -> tuple[Sighting, ...]:
        """The run's sightings, by sighting id (the order the scan numbered them)."""
        rows = self._db.fetch_all("SELECT * FROM sighting WHERE run_id = ? ORDER BY id", (run_id,))
        return tuple(_sighting(row) for row in rows)

    def reinforcements_for_run(self, run_id: str) -> tuple[Reinforcement, ...]:
        """The run's reinforcements, by report id then candidate id."""
        rows = self._db.fetch_all(
            "SELECT r.candidate_id, r.report_id, r.matched_by FROM reinforcement AS r "
            "JOIN candidate AS c ON c.id = r.candidate_id WHERE c.run_id = ? "
            "ORDER BY r.report_id, r.candidate_id",
            (run_id,),
        )
        return tuple(
            Reinforcement(
                KebabId(row["candidate_id"]),
                KebabId(row["report_id"]),
                MatchedBy(row["matched_by"]),
            )
            for row in rows
        )

    def canonical_urls_before(self, run_id: str) -> Mapping[str, RunId]:
        """Every canonical URL another run recorded, with the earliest run that first saw it."""
        rows = self._db.fetch_all(
            "SELECT canonical_url, MIN(first_seen_run_id) AS first_seen FROM candidate "
            "WHERE run_id != ? GROUP BY canonical_url ORDER BY canonical_url",
            (run_id,),
        )
        return {str(row["canonical_url"]): RunId(row["first_seen"]) for row in rows}


# The whole configuration, and plain dumps for tests and summaries.


def save_config(db: Database, config: LoadedConfig) -> None:
    """Write the catalogues, requirement sets and sources from ``config`` in one transaction.

    The instrument is not written here: instrument versions are history, stored
    when a run uses them (``RunScan``) or when a rebuild replays the archive.
    """
    with db.transaction():
        db.defer_foreign_keys()
        SqliteReferenceRepository(db).save(config.catalogue)
        SqliteRequirementSetRepository(db).replace_all(config.requirement_sets)
        SqliteSourceRepository(db).replace_all(config.sources)


def dump_table(db: Database, table: str) -> list[tuple[object, ...]]:
    """Every row of ``table`` as tuples ordered by every column, to compare two databases."""
    if table not in db.table_names():
        raise ValueError(f"no table named {table!r}")
    columns = [str(row[1]) for row in db.fetch_all(f"PRAGMA table_info({table})")]
    order = ", ".join(columns)
    return [tuple(row) for row in db.fetch_all(f"SELECT {order} FROM {table} ORDER BY {order}")]


def table_counts(db: Database) -> dict[str, int]:
    """How many rows each table holds, by table name."""
    return {
        table: int(db.scalar(f"SELECT COUNT(*) FROM {table}") or 0) for table in db.table_names()
    }
