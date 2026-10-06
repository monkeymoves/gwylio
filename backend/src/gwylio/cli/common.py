"""Helpers the register, evaluation and product verbs share.

``load`` validates the configuration and prints every problem; ``database``
opens the migrated database holding the current configuration; ``today``
reads a ``--today`` option. Each prints its own error and returns ``None``
rather than raising, so a verb can choose its exit code.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import typer

from gwylio.infrastructure.config.loaders import LoadedConfig, check_config
from gwylio.infrastructure.config.settings import Settings
from gwylio.infrastructure.sqlite.db import Database
from gwylio.infrastructure.sqlite.migrate import migrate
from gwylio.infrastructure.sqlite.repositories import SqliteInstrumentRepository, save_config
from gwylio.shared.clock import SystemClock
from gwylio.shared.errors import DomainError
from gwylio.shared.values import IsoDate

__all__ = ["database", "load", "today"]


def load(root: Path, verb: str) -> LoadedConfig | None:
    """The validated configuration under ``root``, or ``None`` after printing every problem."""
    report = check_config(root)
    if report.config is None:
        for problem in report.problems:
            typer.echo(f"error  {problem}", err=True)
        typer.echo(f"{verb}: configuration is invalid, run `gwylio check`", err=True)
    return report.config


@contextmanager
def database(settings: Settings, config: LoadedConfig, verb: str) -> Iterator[Database | None]:
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


def today(value: str | None) -> IsoDate | None:
    """``value`` as a date (default: today, UTC), or ``None`` after printing why it is not one."""
    if value is None:
        return IsoDate(SystemClock().today())
    try:
        return IsoDate(value)
    except ValueError:
        typer.echo(f"not a YYYY-MM-DD date: {value!r}", err=True)
        return None
