"""``gwylio ingest``, ``sweep``, ``datecheck`` and ``import-legacy``: the register's verbs.

``ingest`` validates a submission and applies it all or nothing; ``sweep``
applies the fade rule; ``import-legacy`` seeds the register from the old
tool's ``signals.json`` through a legacy submission. Each refreshes
``data/exports/register.json`` and ``runs.json`` after a change. ``datecheck``
reads only and always exits 0: it informs, it does not block.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import typer

from gwylio.infrastructure.config.loaders import LoadedConfig, check_config
from gwylio.infrastructure.config.settings import Settings
from gwylio.infrastructure.handoff.legacy import LegacyImportError, import_legacy
from gwylio.infrastructure.handoff.submission_file import IngestOutcome, ingest_file
from gwylio.infrastructure.handoff.sweep_file import sweep
from gwylio.infrastructure.sqlite.db import Database
from gwylio.infrastructure.sqlite.export import write_register_export, write_runs_export
from gwylio.infrastructure.sqlite.migrate import applied_versions, available_migrations, migrate
from gwylio.infrastructure.sqlite.repositories import (
    SqliteInstrumentRepository,
    SqliteReportRepository,
    save_config,
)
from gwylio.intelligence.datecheck import FindingKind, date_check
from gwylio.shared.clock import SystemClock
from gwylio.shared.errors import DomainError
from gwylio.shared.values import IsoDate

__all__ = ["run_datecheck", "run_import_legacy", "run_ingest", "run_sweep"]


def _load(root: Path, verb: str) -> LoadedConfig | None:
    report = check_config(root)
    if report.config is None:
        for problem in report.problems:
            typer.echo(f"error  {problem}", err=True)
        typer.echo(f"{verb}: configuration is invalid, run `gwylio check`", err=True)
    return report.config


@contextmanager
def _database(settings: Settings, config: LoadedConfig, verb: str) -> Iterator[Database | None]:
    """The migrated database holding the current configuration, or ``None`` after an error.

    The current instrument is stored too (a no-op once stored), as a rebuild
    does, so a database these verbs wrote rebuilds to the same projection.
    """
    with Database.open(settings.db_path) as db:
        migrate(db)
        try:
            with db.transaction():
                save_config(db, config)
                SqliteInstrumentRepository(db).add(config.instrument)
        except (sqlite3.IntegrityError, DomainError) as error:
            typer.echo(
                f"{verb}: config/ no longer matches the stored facts ({error}); retire sources "
                "rather than removing them, or run `gwylio rebuild`",
                err=True,
            )
            yield None
            return
        yield db


def _exports(db: Database, settings: Settings) -> None:
    for path in (
        write_register_export(db, settings.register_export_path),
        write_runs_export(db, settings.runs_export_path),
    ):
        typer.echo(f"wrote  {path}")


def _print_outcome(outcome: IngestOutcome, verb: str) -> None:
    result = outcome.result
    if result is None:
        return
    typer.echo(f"{verb}: applied submission {outcome.submission_id} ({outcome.path})")
    rows = [
        *((f"disposition: {name}", count) for name, count in result.outcomes.items()),
        ("reports created", len(result.created)),
        ("reports changed", len(result.changed)),
        ("sightings linked", result.sightings_linked),
        ("state changes", len(result.state_changes)),
    ]
    width = max(len(label) for label, _ in rows)
    for label, count in rows:
        typer.echo(f"  {label.ljust(width)}  {count:>5}")
    for report_id, before, after in result.state_changes:
        typer.echo(f"  {report_id}: {before} to {after}")


def _refused(outcome: IngestOutcome, verb: str, path: Path | None, inside: bool) -> int:
    for problem in outcome.problems:
        typer.echo(f"error  {problem}", err=True)
    count = len(outcome.problems)
    typer.echo(
        f"{verb}: refused, nothing written: {count} problem{'s' if count != 1 else ''}", err=True
    )
    if path is not None and inside:
        typer.echo(
            f"{verb}: {path} was never ingested, so it is not yet a fact: fix it and ingest "
            "again, or remove it before the next rebuild",
            err=True,
        )
    return 1


def run_ingest(settings: Settings, path: Path, *, allow_deferred: bool = False) -> int:
    """Validate and apply the submission at ``path``; return the exit code."""
    if not path.is_file():
        typer.echo(f"ingest: no file at {path}", err=True)
        return 2
    config = _load(settings.config_root, "ingest")
    if config is None:
        return 1
    with _database(settings, config, "ingest") as db:
        if db is None:
            return 1
        outcome = ingest_file(
            db, config, path, settings.submissions_dir, allow_deferred=allow_deferred
        )
        if not outcome.ok:
            inside = path.resolve().parent == settings.submissions_dir.resolve()
            return _refused(outcome, "ingest", path, inside)
        _print_outcome(outcome, "ingest")
        _exports(db, settings)
    return 0


def _today(value: str | None) -> IsoDate | None:
    if value is None:
        return IsoDate(SystemClock().today())
    try:
        return IsoDate(value)
    except ValueError:
        typer.echo(f"not a YYYY-MM-DD date: {value!r}", err=True)
        return None


def run_sweep(settings: Settings, *, today: str | None = None) -> int:
    """Apply the fade rule and record what faded; return the exit code."""
    on = _today(today)
    if on is None:
        return 2
    config = _load(settings.config_root, "sweep")
    if config is None:
        return 1
    with _database(settings, config, "sweep") as db:
        if db is None:
            return 1
        outcome = sweep(db, settings.sweeps_dir, on)
        for decision in outcome.faded:
            typer.echo(f"faded  {decision.report_id}: {decision.change}")
        if outcome.path is None:
            typer.echo(f"sweep: nothing to fade on {on}")
            return 0
        count = len(outcome.faded)
        typer.echo(f"sweep: {count} report{'s' if count != 1 else ''} faded; wrote {outcome.path}")
        _exports(db, settings)
    return 0


def run_datecheck(settings: Settings, *, today: str | None = None) -> int:
    """Print the date check findings grouped by kind; always exit 0."""
    on = _today(today)
    if on is None:
        return 0
    config = _load(settings.config_root, "datecheck")
    if config is None:
        return 0
    if not settings.db_path.is_file():
        typer.echo(f"datecheck: no database at {settings.db_path}; nothing to check")
        return 0
    with Database.open(settings.db_path) as db:
        if len(applied_versions(db)) < len(available_migrations()):
            typer.echo("datecheck: the database needs `gwylio migrate`; nothing checked")
            return 0
        reports = SqliteReportRepository(db).list()
    rules = config.datecheck
    findings = date_check(
        reports, on, rules.future_phrases, stale_after_days=rules.stale_after_days
    )
    live = sum(1 for report in reports if report.state.live)
    flagged = len({finding.report_id for finding in findings})
    typer.echo(
        f"date check on {on}: {len(findings)} finding{'s' if len(findings) != 1 else ''} on "
        f"{flagged} of {live} report{'s' if live != 1 else ''} in the picture"
    )
    for kind in FindingKind:
        group = [finding for finding in findings if finding.kind is kind]
        if not group:
            continue
        typer.echo("")
        typer.echo(f"{kind.value} ({group[0].severity.value}, {len(group)}): {kind.meaning}")
        for finding in group:
            typer.echo(f"  {finding.report_id}: {finding.detail}")
    return 0


def run_import_legacy(settings: Settings, signals: Path, *, received_on: str | None = None) -> int:
    """Write the legacy submission and ingest it; return the exit code."""
    if received_on is not None:
        try:
            IsoDate(received_on)
        except ValueError:
            typer.echo(f"import-legacy: not a YYYY-MM-DD date: {received_on!r}", err=True)
            return 2
    if not signals.is_file():
        typer.echo(f"import-legacy: no file at {signals}", err=True)
        return 2
    config = _load(settings.config_root, "import-legacy")
    if config is None:
        return 1
    with _database(settings, config, "import-legacy") as db:
        if db is None:
            return 1
        try:
            outcome = import_legacy(
                db, config, signals, settings.submissions_dir, received_on=received_on
            )
        except LegacyImportError as error:
            typer.echo(f"import-legacy: {error}", err=True)
            return 1
        if not outcome.ok:
            return _refused(outcome, "import-legacy", None, inside=False)
        _print_outcome(outcome, "import-legacy")
        _exports(db, settings)
    return 0
