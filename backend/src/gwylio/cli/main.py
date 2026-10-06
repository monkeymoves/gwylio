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
from gwylio.cli.collect import run_collect, run_probe
from gwylio.cli.schema import run_schema
from gwylio.collection.model import Discipline
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


@app.command("collect")
def collect_command(
    root: RootOption = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Use fake collectors and in-memory storage; keep nothing."),
    ] = False,
    out: Annotated[
        Path | None,
        typer.Option(
            "--out",
            help="Write the candidates file here (default: standard output).",
            dir_okay=False,
        ),
    ] = None,
    discipline: Annotated[
        list[Discipline] | None,
        typer.Option(
            "--discipline",
            help="Run only this discipline; repeat for more. Default: web, site and feed, "
            "plus academic when GWYLIO_ACADEMIC=1.",
        ),
    ] = None,
) -> None:
    """Run the instrument once and write a candidates file, printing the funnel."""
    raise typer.Exit(
        code=run_collect(_root(root), dry_run=dry_run, out=out, disciplines=discipline or ())
    )


@app.command("probe")
def probe_command(
    text: Annotated[str, typer.Argument(help="The query text to try.")],
    discipline: Annotated[
        Discipline, typer.Option("--discipline", help="The discipline to probe with.")
    ] = Discipline.OSINT_WEB,
    source: Annotated[
        list[str] | None,
        typer.Option("--source", help="A source id for an osint_site probe; repeat for more."),
    ] = None,
    root: RootOption = None,
) -> None:
    """Try one query text and print its hits, storing nothing."""
    raise typer.Exit(code=run_probe(_root(root), text, discipline, source or ()))


if __name__ == "__main__":  # pragma: no cover
    app()
