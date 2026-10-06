"""Publish the snapshot: every read model as a JSON file the static site reads.

``gwylio publish`` builds every read model from the database
(``ReadModels``) and writes one file per document into both
``frontend/static/data/`` (what the site is built from) and
``data/snapshots/`` (the copy kept beside the facts). The read API serves the
same documents at ``/api/v1/...``: ``snapshot_entries`` pairs each file with
its route, and both sides serialise through ``to_jsonable``, so a file and its
response are the same JSON (the contract test checks every pair).

Serialisation is deterministic: sorted keys, two-space indent, UTF-8
characters, one trailing newline, and ``generated_at`` from the injected
clock, so two publishes with the same clock are byte-identical. Every file's
text passes through ``CleanText`` before it is written: no en or em dash can
be published. Before writing, a publish removes the JSON files in each target
directory that the new snapshot no longer holds (only ``*.json`` files, and
only inside the target directories), so the site never serves a stale report.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, TypeAlias

from pydantic import BaseModel

from gwylio.infrastructure.config.loaders import LoadedConfig, load_config
from gwylio.infrastructure.config.settings import Settings
from gwylio.infrastructure.readmodels import ReadModels
from gwylio.infrastructure.sqlite.db import Database
from gwylio.infrastructure.sqlite.migrate import applied_versions, available_migrations
from gwylio.shared.clock import Clock, SystemClock
from gwylio.shared.values import CleanText

__all__ = [
    "API_PREFIX",
    "Document",
    "PublishError",
    "PublishResult",
    "SnapshotEntry",
    "database_ready",
    "dumps_snapshot",
    "publish",
    "route_for",
    "snapshot_entries",
    "snapshot_files",
    "to_jsonable",
    "write_snapshot",
]

API_PREFIX: Final[str] = "/api/v1"
"""Where the read API serves the snapshot's documents."""

Document: TypeAlias = BaseModel | Sequence[BaseModel]
"""One snapshot document: a read model, or a list of them."""


class PublishError(Exception):
    """The snapshot could not be built; nothing was written."""


@dataclass(frozen=True, slots=True)
class SnapshotEntry:
    """One snapshot file, the API route serving the same document, and the document."""

    path: str
    route: str
    document: Document

    @property
    def api_path(self) -> str:
        """The route with the API prefix, such as ``/api/v1/meta``."""
        return f"{API_PREFIX}{self.route}"


@dataclass(frozen=True, slots=True)
class PublishResult:
    """What a publish wrote: the file paths (relative) and the directories."""

    files: tuple[str, ...]
    directories: tuple[Path, ...]
    removed: int


def to_jsonable(document: Document) -> Any:
    """The document as plain JSON values: the one serialisation the API and snapshot share."""
    if isinstance(document, BaseModel):
        return document.model_dump(mode="json")
    return [item.model_dump(mode="json") for item in document]


def dumps_snapshot(document: Document) -> CleanText:
    """A snapshot file's text: sorted keys, two-space indent, UTF-8, trailing newline."""
    text = json.dumps(to_jsonable(document), indent=2, sort_keys=True, ensure_ascii=False)
    return CleanText(text + "\n")


def snapshot_entries(models: ReadModels) -> list[SnapshotEntry]:
    """Every document the snapshot holds, by file path, each with its API route."""
    entries = [
        SnapshotEntry("meta.json", "/meta", models.meta()),
        SnapshotEntry("enums.json", "/meta/enums", models.enums()),
        SnapshotEntry("requirement_sets.json", "/requirement-sets", models.requirement_sets()),
        SnapshotEntry("reports.json", "/reports", models.reports()),
        SnapshotEntry("sources.json", "/sources", models.sources()),
        SnapshotEntry("sources_health.json", "/sources/health", models.sources_health()),
        SnapshotEntry("runs.json", "/scan-runs", models.runs()),
        SnapshotEntry("datecheck.json", "/datecheck", models.datecheck()),
        SnapshotEntry("products.json", "/products", models.products()),
    ]
    for set_id in models.requirement_set_ids():
        entries.extend(
            [
                SnapshotEntry(
                    f"requirement_set_{set_id}.json",
                    f"/requirement-sets/{set_id}",
                    models.requirement_set(set_id),
                ),
                SnapshotEntry(
                    f"picture_{set_id}.json",
                    f"/requirement-sets/{set_id}/picture",
                    models.picture(set_id),
                ),
                SnapshotEntry(
                    f"coverage_{set_id}.json", f"/coverage/{set_id}", models.coverage(set_id)
                ),
            ]
        )
    entries.extend(
        SnapshotEntry(
            f"reports/{report_id}.json", f"/reports/{report_id}", models.report(report_id)
        )
        for report_id in models.report_ids()
    )
    entries.extend(
        SnapshotEntry(f"runs/{run_id}.json", f"/scan-runs/{run_id}", models.run(run_id))
        for run_id in models.run_ids()
    )
    entries.extend(
        SnapshotEntry(
            f"products/{product_id}.json", f"/products/{product_id}", models.product(product_id)
        )
        for product_id in models.product_ids()
    )
    return sorted(entries, key=lambda entry: entry.path)


_ID: Final[str] = r"([a-zA-Z0-9-]+)"
_ROUTES: Final[tuple[tuple[re.Pattern[str], str], ...]] = tuple(
    (re.compile(pattern), route)
    for pattern, route in (
        (r"meta\.json", "/meta"),
        (r"enums\.json", "/meta/enums"),
        (r"requirement_sets\.json", "/requirement-sets"),
        (rf"requirement_set_{_ID}\.json", "/requirement-sets/{0}"),
        (rf"picture_{_ID}\.json", "/requirement-sets/{0}/picture"),
        (rf"coverage_{_ID}\.json", "/coverage/{0}"),
        (r"reports\.json", "/reports"),
        (rf"reports/{_ID}\.json", "/reports/{0}"),
        (r"sources\.json", "/sources"),
        (r"sources_health\.json", "/sources/health"),
        (r"runs\.json", "/scan-runs"),
        (rf"runs/{_ID}\.json", "/scan-runs/{0}"),
        (r"datecheck\.json", "/datecheck"),
        (r"products\.json", "/products"),
        (rf"products/{_ID}\.json", "/products/{0}"),
    )
)


def route_for(path: str) -> str | None:
    """The API route serving the snapshot file at ``path``, or ``None`` when no route does."""
    for pattern, route in _ROUTES:
        match = pattern.fullmatch(path)
        if match is not None:
            return route.format(*match.groups())
    return None


def snapshot_files(models: ReadModels) -> dict[str, str]:
    """Every snapshot file's text, keyed by its path relative to the snapshot directory."""
    return {entry.path: dumps_snapshot(entry.document) for entry in snapshot_entries(models)}


def _remove_stale(out_dir: Path, keep: Mapping[str, str]) -> int:
    removed = 0
    for path in sorted(out_dir.rglob("*.json")):
        if path.is_file() and path.relative_to(out_dir).as_posix() not in keep:
            path.unlink()
            removed += 1
    for folder in sorted((p for p in out_dir.rglob("*") if p.is_dir()), reverse=True):
        if not any(folder.iterdir()):
            folder.rmdir()
    return removed


def write_snapshot(files: Mapping[str, str], out_dir: Path) -> int:
    """Write every file under ``out_dir`` after removing stale JSON; return the count removed."""
    out_dir.mkdir(parents=True, exist_ok=True)
    removed = _remove_stale(out_dir, files)
    for relative, text in files.items():
        path = out_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        data = text.encode("utf-8")
        if not path.is_file() or path.read_bytes() != data:
            path.write_bytes(data)
    return removed


def database_ready(db: Database) -> bool:
    """True when every migration has been applied to ``db``."""
    return len(applied_versions(db)) >= len(available_migrations())


def publish(
    settings: Settings,
    out_dirs: Sequence[Path] | None = None,
    *,
    clock: Clock | None = None,
    database: Database | None = None,
    config: LoadedConfig | None = None,
) -> PublishResult:
    """Build every read model and write the snapshot into each of ``out_dirs``.

    ``out_dirs`` defaults to ``frontend/static/data/`` and ``data/snapshots/``.
    ``database`` defaults to the settings database, which must exist and be
    migrated; raises ``PublishError`` otherwise, having written nothing.
    """
    targets = tuple(out_dirs) if out_dirs else (settings.site_data_dir, settings.snapshots_dir)
    loaded = config if config is not None else load_config(settings.config_root)
    if database is None and not settings.db_path.is_file():
        raise PublishError(f"no database at {settings.db_path}; run `gwylio rebuild`")
    db = database if database is not None else Database.open(settings.db_path)
    try:
        if not database_ready(db):
            raise PublishError(f"the database at {settings.db_path} needs `gwylio migrate`")
        models = ReadModels(db, loaded, clock=clock or SystemClock(), data_dir=settings.data_dir)
        files = snapshot_files(models)
    finally:
        if database is None:
            db.close()
    removed = sum(write_snapshot(files, target) for target in targets)
    return PublishResult(tuple(files), targets, removed)
