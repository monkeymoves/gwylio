"""``gwylio publish``: write the snapshot the static site reads.

Builds every read model from the database and writes them as JSON into
``frontend/static/data/`` and ``data/snapshots/`` (or the ``--out``
directories), removing JSON files the new snapshot no longer holds. Prints
the file count and the directories. ``--at`` pins the clock, so a publish is
reproducible byte for byte.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

import typer

from gwylio.cli.common import load
from gwylio.infrastructure.config.settings import Settings
from gwylio.infrastructure.snapshot import PublishError, publish
from gwylio.shared.clock import Clock, FixedClock, SystemClock

__all__ = ["run_publish"]


def run_publish(settings: Settings, *, out: Sequence[Path] = (), at: datetime | None = None) -> int:
    """Publish the snapshot; return the exit code."""
    if at is not None and (at.tzinfo is None or at.utcoffset() is None):
        typer.echo("publish: --at needs a time zone, such as 2026-10-06T09:00:00+0000", err=True)
        return 2
    config = load(settings.config_root, "publish")
    if config is None:
        return 1
    clock: Clock = SystemClock() if at is None else FixedClock(at)
    try:
        result = publish(settings, [path.resolve() for path in out], clock=clock, config=config)
    except PublishError as error:
        typer.echo(f"publish: {error}", err=True)
        return 1
    count = len(result.files)
    typer.echo(
        f"publish: {count} file{'s' if count != 1 else ''} into "
        f"{len(result.directories)} director{'ies' if len(result.directories) != 1 else 'y'}"
    )
    for directory in result.directories:
        typer.echo(f"wrote  {directory}")
    if result.removed:
        typer.echo(f"removed {result.removed} stale file{'s' if result.removed != 1 else ''}")
    return 0
