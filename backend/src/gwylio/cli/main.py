"""Entry point for the ``gwylio`` command line tool.

Each verb's logic lives in its own module (``check.py``, ``schema.py``);
this module only declares the Typer commands and registers them.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Annotated

import typer
from typer.main import get_command

from gwylio.cli.check import run_check
from gwylio.cli.schema import run_schema
from gwylio.infrastructure.config.paths import find_project_root

app = typer.Typer(
    name="gwylio",
    help="Gwylio: a Welsh environmental open-source intelligence (OSINT) system.",
    no_args_is_help=True,
    add_completion=False,
)

RootOption = Annotated[
    Path | None,
    typer.Option(
        "--root",
        help="Project root holding config/ (default: found from the current directory).",
        file_okay=False,
        exists=True,
    ),
]


def package_version() -> str:
    """The installed version of the ``gwylio`` distribution."""
    try:
        return version("gwylio")
    except PackageNotFoundError:  # pragma: no cover, only when run from a bare checkout
        return "0.0.0+unknown"


def cli_verbs() -> tuple[tuple[str, str], ...]:
    """Every verb registered on the app with its one-line help, in name order."""
    group = get_command(app)
    commands = getattr(group, "commands", {})
    return tuple((name, commands[name].get_short_help_str(limit=120)) for name in sorted(commands))


def _root(root: Path | None) -> Path:
    try:
        return root.resolve() if root is not None else find_project_root()
    except FileNotFoundError as error:
        typer.echo(f"error  {error}", err=True)
        raise typer.Exit(code=2) from error


@app.callback()
def main() -> None:
    """Gwylio: a Welsh environmental open-source intelligence (OSINT) system."""


@app.command("version")
def version_command() -> None:
    """Print the package version."""
    typer.echo(package_version())


@app.command("check")
def check_command(root: RootOption = None) -> None:
    """Validate every configuration file and print a summary per file."""
    raise typer.Exit(code=run_check(_root(root)))


@app.command("schema")
def schema_command(
    root: RootOption = None,
    check: Annotated[
        bool, typer.Option("--check", help="Report out-of-date generated files; write nothing.")
    ] = False,
) -> None:
    """Generate JSON Schema, TypeScript types, the glossary and the skill reference."""
    raise typer.Exit(code=run_schema(_root(root), cli_verbs(), check_only=check))


if __name__ == "__main__":  # pragma: no cover
    app()
