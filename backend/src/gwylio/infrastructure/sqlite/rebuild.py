"""Rebuild the database from the files: configuration plus everything under ``data/``.

The files are the facts and the database is their projection (ADR 0002), so
``rebuild`` must reproduce what the commands wrote. It migrates a fresh
database, loads ``config/`` through the real loaders into the reference,
direction and source tables, stores every archived instrument version
(``data/instruments/*.json``) and the current one, then replays every
candidates file (``data/candidates/*.json``) in the order the runs started,
through the same repositories a scan writes with. Then it replays the
register: every submission (``data/submissions/*.json``) in ``received_on``
then file name order through the same ingest as ``gwylio ingest`` (with
``allow_deferred``, so a historic file always replays), and every sweep file
(``data/sweeps/*.json``) at the point it ran. Last come the products
(``data/products/*.json``): each was rendered from the register as it stood
on its day, so the recorded product is stored rather than rendered again.
Everything after the migration
happens in one transaction, with foreign keys checked at the commit: a run
can record a reinforcement of a report that a later-replayed submission
creates.

``rebuild`` builds into a scratch file beside the database and moves it into
place only when it succeeds, so a failed rebuild leaves the old database as it was.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from gwylio.infrastructure.config import paths
from gwylio.infrastructure.config.loaders import ConfigInvalidError, load_config
from gwylio.infrastructure.config.settings import (
    CANDIDATES_SUBDIR,
    INSTRUMENTS_SUBDIR,
    PRODUCTS_SUBDIR,
    SUBMISSIONS_SUBDIR,
    SWEEPS_SUBDIR,
)
from gwylio.infrastructure.handoff.candidates_file import (
    CandidatesFileError,
    read_candidates_file,
    result_from_document,
)
from gwylio.infrastructure.handoff.instrument_file import (
    InstrumentFileError,
    read_instrument_archives,
)
from gwylio.infrastructure.handoff.product_file import (
    ProductFileError,
    apply_product_file,
    read_product_files,
)
from gwylio.infrastructure.handoff.submission_file import ingest_submission
from gwylio.infrastructure.handoff.sweep_file import (
    SweepFileError,
    apply_sweep_file,
    read_sweep_files,
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
from gwylio.processing.ingest import SweepFile, replay_order
from gwylio.processing.submission import Submission, parse_submission
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
    submission_files: int = 0
    sweep_files: int = 0
    product_files: int = 0

    def table(self) -> list[str]:
        """The summary as aligned text lines: files read, then rows per table."""
        width = max([len(name) for name in self.counts] + [len("table")])

        def files(count: int, word: str) -> str:
            return f"{count} {word}" + ("" if count == 1 else "s")

        return [
            f"replayed {files(self.candidates_files, 'candidates file')}, "
            f"{files(self.submission_files, 'submission')}, {files(self.sweep_files, 'sweep')}, "
            f"{files(self.product_files, 'product')} "
            f"and {files(self.instrument_files, 'archived instrument')}",
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


def _read_submissions(submissions_dir: Path) -> dict[str, tuple[Path, Submission]]:
    found: dict[str, tuple[Path, Submission]] = {}
    if submissions_dir.is_dir():
        for path in sorted(submissions_dir.glob("*.json")):
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as error:
                raise RebuildError(f"{path}: cannot read: {error}") from error
            submission, problems = parse_submission(text)
            if submission is None:
                details = "; ".join(str(problem) for problem in problems)
                raise RebuildError(f"{path}: not a valid submission: {details}")
            found[path.stem] = (path, submission)
    return found


def _read_sweeps(sweeps_dir: Path) -> dict[str, tuple[Path, SweepFile]]:
    try:
        return {path.stem: (path, document) for path, document in read_sweep_files(sweeps_dir)}
    except SweepFileError as error:
        raise RebuildError(str(error)) from error


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
    submissions = _read_submissions(data_dir / SUBMISSIONS_SUBDIR)
    sweeps = _read_sweeps(data_dir / SWEEPS_SUBDIR)
    try:
        products = read_product_files(data_dir / PRODUCTS_SUBDIR)
    except ProductFileError as error:
        raise RebuildError(str(error)) from error
    try:
        steps = replay_order(
            [(s.received_on, stem) for stem, (_, s) in submissions.items()],
            [(d.after_submissions, stem) for stem, (_, d) in sweeps.items()],
        )
    except ValueError as error:
        raise RebuildError(str(error)) from error
    migrate(db)
    instruments = SqliteInstrumentRepository(db)
    runs = SqliteScanRunRepository(db)
    candidates = SqliteCandidateRepository(db)
    try:
        with db.transaction():
            db.defer_foreign_keys()
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
            for kind, stem in steps:
                if kind == "sweep":
                    apply_sweep_file(db, sweeps[stem][1])
                    continue
                path, submission = submissions[stem]
                outcome = ingest_submission(db, config, submission, stem, allow_deferred=True)
                if not outcome.ok:
                    raise RebuildError(
                        f"{path}: the submission no longer ingests:\n  "
                        + "\n  ".join(outcome.problems)
                    )
            for path, product in products:
                try:
                    apply_product_file(db, product)
                except ProductFileError as error:
                    raise RebuildError(f"{path}: {error}") from error
    except (DomainError, ValueError) as error:
        raise RebuildError(f"rebuild failed: {error}") from error
    except sqlite3.IntegrityError as error:
        raise RebuildError(f"rebuild failed: the files do not agree: {error}") from error
    return RebuildSummary(
        len(documents),
        len(archived),
        table_counts(db),
        len(submissions),
        len(sweeps),
        len(products),
    )


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
