"""Rebuild the database from the files: configuration plus everything under ``data/``.

The files are the facts and the database is their projection (ADR 0002), so
``rebuild`` must reproduce what the commands wrote. It migrates a fresh
database, loads ``config/`` through the real loaders into the reference,
direction and source tables, stores every archived instrument version
(``data/instruments/*.json``) and the current one, then replays every
candidates file (``data/candidates/*.json``) in the order the runs started,
through the same repositories a scan writes with. Everything after the
migration happens in one transaction.

``rebuild`` builds into a scratch file beside the database and moves it into
place only when it succeeds, so a failed rebuild leaves the old database as it was.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from gwylio.infrastructure.config import paths
from gwylio.infrastructure.config.loaders import ConfigInvalidError, load_config
from gwylio.infrastructure.config.settings import CANDIDATES_SUBDIR, INSTRUMENTS_SUBDIR
from gwylio.infrastructure.handoff.candidates_file import (
    CandidatesFileError,
    read_candidates_file,
    result_from_document,
)
from gwylio.infrastructure.handoff.instrument_file import (
    InstrumentFileError,
    read_instrument_archives,
)
from gwylio.infrastructure.sqlite.db import Database
from gwylio.infrastructure.sqlite.migrate import migrate
from gwylio.infrastructure.sqlite.repositories import (
    SqliteCandidateRepository,
    SqliteInstrumentRepository,
    SqliteScanRunRepository,
    save_config,
    table_counts,
)
from gwylio.processing.candidates_file import CandidatesFile
from gwylio.shared.errors import DomainError

__all__ = ["RebuildError", "RebuildSummary", "rebuild", "rebuild_into"]

_SCRATCH_SUFFIX: Final[str] = ".rebuilding"


class RebuildError(Exception):
    """The files could not be replayed; nothing was replaced."""


@dataclass(frozen=True, slots=True)
class RebuildSummary:
    """What a rebuild read and what the database now holds."""

    candidates_files: int
    instrument_files: int
    counts: dict[str, int] = field(default_factory=dict)

    def table(self) -> list[str]:
        """The summary as aligned text lines: files read, then rows per table."""
        width = max([len(name) for name in self.counts] + [len("table")])
        return [
            f"replayed {self.candidates_files} candidates file"
            + ("" if self.candidates_files == 1 else "s")
            + f" and {self.instrument_files} archived instrument"
            + ("" if self.instrument_files == 1 else "s"),
            f"  {'table'.ljust(width)}  {'rows':>6}",
            *(f"  {name.ljust(width)}  {count:>6}" for name, count in self.counts.items()),
        ]


def _config_root(config_dir: Path) -> Path:
    if config_dir.name != paths.CONFIG_DIR:
        raise RebuildError(f"the configuration directory must be named 'config': {config_dir}")
    if not config_dir.is_dir():
        raise RebuildError(f"no configuration directory at {config_dir}")
    return config_dir.parent


def _read_runs(candidates_dir: Path) -> list[tuple[Path, CandidatesFile]]:
    documents: list[tuple[Path, CandidatesFile]] = []
    if candidates_dir.is_dir():
        for path in sorted(candidates_dir.glob("*.json")):
            try:
                document = read_candidates_file(path)
            except CandidatesFileError as error:
                raise RebuildError(str(error)) from error
            if path.stem != document.run_id:
                raise RebuildError(f"{path}: holds run {document.run_id}, not {path.stem}")
            documents.append((path, document))
    # Run ids sort by start minute; the start instant breaks ties within a minute.
    return sorted(documents, key=lambda item: (item[1].started_at, item[1].run_id))


def rebuild_into(db: Database, data_dir: Path, config_dir: Path) -> RebuildSummary:
    """Replay configuration and data files into ``db``, which should be empty."""
    root = _config_root(config_dir)
    try:
        config = load_config(root)
    except ConfigInvalidError as error:
        raise RebuildError(f"configuration is invalid, run `gwylio check`:\n{error}") from error
    try:
        archived = read_instrument_archives(data_dir / INSTRUMENTS_SUBDIR)
    except InstrumentFileError as error:
        raise RebuildError(str(error)) from error
    documents = _read_runs(data_dir / CANDIDATES_SUBDIR)
    migrate(db)
    instruments = SqliteInstrumentRepository(db)
    runs = SqliteScanRunRepository(db)
    candidates = SqliteCandidateRepository(db)
    try:
        with db.transaction():
            save_config(db, config)
            for instrument in (*archived, config.instrument):
                instruments.add(instrument)
            for path, document in documents:
                stored = instruments.get(document.instrument_version)
                if stored is None or stored.content_hash != document.instrument_hash:
                    raise RebuildError(
                        f"{path}: run {document.run_id} used instrument "
                        f"{document.instrument_version} ({document.instrument_hash}), which "
                        f"is neither archived under {INSTRUMENTS_SUBDIR}/ nor in "
                        f"{paths.INSTRUMENT_FILE}"
                    )
                result = result_from_document(document)
                runs.add(result.run)
                candidates.add_candidates(result.candidates)
                candidates.add_sightings(result.sightings)
                candidates.add_reinforcements(result.reinforcements)
    except (DomainError, ValueError) as error:
        raise RebuildError(f"rebuild failed: {error}") from error
    return RebuildSummary(len(documents), len(archived), table_counts(db))


def _remove(paths_to_remove: Sequence[Path]) -> None:
    for path in paths_to_remove:
        path.unlink(missing_ok=True)


def rebuild(data_dir: Path, config_dir: Path, db_path: Path) -> RebuildSummary:
    """Rebuild the database at ``db_path`` from ``config_dir`` and ``data_dir``.

    The old database, if any, is replaced only once the new one is complete.
    """
    scratch = db_path.with_name(db_path.name + _SCRATCH_SUFFIX)
    leftovers = [scratch, scratch.with_name(scratch.name + "-journal")]
    _remove(leftovers)
    db = Database.open(scratch)
    try:
        summary = rebuild_into(db, data_dir, config_dir)
    except BaseException:
        db.close()
        _remove(leftovers)
        raise
    db.close()
    os.replace(scratch, db_path)
    return summary
