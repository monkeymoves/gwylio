"""``gwylio schema``: regenerate JSON Schema, TypeScript types, the glossary and the reference."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import typer

from gwylio.infrastructure.codegen.generate import render_generated, stale_files, write_generated
from gwylio.infrastructure.codegen.markdown import CliVerb
from gwylio.infrastructure.config.loaders import check_config

__all__ = ["run_schema"]


def run_schema(root: Path, verbs: Sequence[CliVerb], *, check_only: bool = False) -> int:
    """Write every generated file under ``root``; with ``check_only``, only report drift."""
    report = check_config(root)
    if report.config is None:
        for problem in report.problems:
            typer.echo(f"error  {problem}", err=True)
        typer.echo("schema: configuration is invalid, run `gwylio check`", err=True)
        return 1
    files = render_generated(report.config, verbs)
    results = write_generated(root, files, dry_run=check_only)
    stale = stale_files(root, files)
    for result in results:
        if result.changed:
            typer.echo(f"{'stale ' if check_only else 'wrote '} {result.path}")
    for path in stale:
        if check_only:
            typer.echo(f"extra  {path}")
        else:
            (root / path).unlink()
            typer.echo(f"removed {path}")
    changed = sum(result.changed for result in results) + len(stale)
    if check_only:
        if changed:
            typer.echo(
                f"schema: {changed} generated files out of date, run `make schema`", err=True
            )
            return 1
        typer.echo(f"schema: {len(results)} generated files up to date")
        return 0
    typer.echo(f"schema: {len(results)} generated files, {changed} changed")
    return 0
