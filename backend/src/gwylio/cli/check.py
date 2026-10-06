"""``gwylio check``: load and validate every configuration file."""

from __future__ import annotations

from pathlib import Path

import typer

from gwylio.infrastructure.config.loaders import check_config

__all__ = ["run_check"]


def run_check(root: Path) -> int:
    """Print one line per configuration file, then every problem; return the exit code."""
    report = check_config(root)
    for summary in report.summaries:
        typer.echo(f"ok     {summary.file}: {summary.summary}")
    for problem in report.problems:
        typer.echo(f"error  {problem}", err=True)
    for note in report.notes:
        typer.echo(f"note   {note}", err=True)
    if report.ok:
        typer.echo(f"check passed: {len(report.summaries)} configuration files valid")
        return 0
    count = len(report.problems)
    typer.echo(f"check failed: {count} problem{'s' if count != 1 else ''}", err=True)
    return 1
