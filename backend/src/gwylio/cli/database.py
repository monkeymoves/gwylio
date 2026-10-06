"""``gwylio migrate``, ``gwylio export`` and ``gwylio rebuild``: the database as a projection."""

from __future__ import annotations

import typer

from gwylio.infrastructure.config.settings import Settings
from gwylio.infrastructure.sqlite.db import Database
from gwylio.infrastructure.sqlite.export import (
    write_products_export,
    write_register_export,
    write_runs_export,
)
from gwylio.infrastructure.sqlite.migrate import applied_versions, available_migrations, migrate
from gwylio.infrastructure.sqlite.rebuild import RebuildError, rebuild

__all__ = ["run_export", "run_migrate", "run_rebuild"]


def run_migrate(settings: Settings) -> int:
    """Create or upgrade the database at ``settings.db_path``; return the exit code."""
    with Database.open(settings.db_path) as db:
        applied = migrate(db)
        total = len(applied_versions(db))
    for migration in applied:
        typer.echo(f"applied {migration.path.name}")
    if applied:
        typer.echo(f"migrated {settings.db_path}: {total} migration{'s' if total != 1 else ''}")
    else:
        typer.echo(
            f"{settings.db_path} is up to date: {total} migration{'s' if total != 1 else ''}"
        )
    return 0


def run_export(settings: Settings) -> int:
    """Write ``runs.json``, ``register.json`` and ``products.json`` under the exports directory."""
    if not settings.db_path.is_file():
        typer.echo(
            f"export: no database at {settings.db_path}; run `gwylio rebuild` or `gwylio migrate`",
            err=True,
        )
        return 1
    with Database.open(settings.db_path) as db:
        pending = len(available_migrations()) - len(applied_versions(db))
        if pending:
            typer.echo(
                f"export: the database needs {pending} more migration"
                f"{'s' if pending != 1 else ''}; run `gwylio migrate`",
                err=True,
            )
            return 1
        paths = (
            write_runs_export(db, settings.runs_export_path),
            write_register_export(db, settings.register_export_path),
            write_products_export(db, settings.products_export_path),
        )
    for path in paths:
        typer.echo(f"wrote  {path}")
    return 0


def run_rebuild(settings: Settings) -> int:
    """Rebuild the database from configuration and the data files; return the exit code."""
    try:
        summary = rebuild(settings.data_dir, settings.config_dir, settings.db_path)
    except RebuildError as error:
        typer.echo(f"rebuild: {error}", err=True)
        typer.echo(f"rebuild: nothing replaced; {settings.db_path} is as it was", err=True)
        return 1
    typer.echo(f"rebuilt {settings.db_path} from {settings.config_dir} and {settings.data_dir}")
    for line in summary.table():
        typer.echo(line)
    return 0
