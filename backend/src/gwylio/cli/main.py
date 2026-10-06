"""Entry point for the ``gwylio`` command line tool.

Each verb's logic lives in its own module (``check.py``, ``schema.py``,
``collect.py``, ``database.py``); this module only declares the Typer commands
and registers them. Every command takes its paths from one ``Settings``
object, built by ``_settings`` from ``--root`` and the ``GWYLIO_`` environment.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from typer.main import get_command

from gwylio.cli.check import run_check
from gwylio.cli.collect import run_collect, run_probe
from gwylio.cli.database import run_export, run_migrate, run_rebuild
from gwylio.cli.schema import run_schema
from gwylio.collection.model import Discipline
from gwylio.infrastructure.config.settings import Settings

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


def _settings(root: Path | None) -> Settings:
    """The settings every command uses: ``--root`` (or the found root) plus the environment."""
    try:
        return Settings.load(root)
    except FileNotFoundError as error:
        typer.echo(f"error  {error}", err=True)
        raise typer.Exit(code=2) from error
    except ValidationError as error:
        for detail in error.errors(include_url=False):
            typer.echo(f"error  settings: {detail['msg']}", err=True)
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
    raise typer.Exit(code=run_check(_settings(root).config_root))


@app.command("schema")
def schema_command(
    root: RootOption = None,
    check: Annotated[
        bool, typer.Option("--check", help="Report out-of-date generated files; write nothing.")
    ] = False,
) -> None:
    """Generate JSON Schema, TypeScript types, the glossary and the skill reference."""
    raise typer.Exit(code=run_schema(_settings(root).root, cli_verbs(), check_only=check))


@app.command("collect")
def collect_command(
    root: RootOption = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Use fake collectors and in-memory storage; keep nothing."),
    ] = False,
    fake: Annotated[
        bool,
        typer.Option(
            "--fake",
            help="Use fake collectors with real storage: SQLite plus the candidates file.",
        ),
    ] = False,
    out: Annotated[
        Path | None,
        typer.Option(
            "--out",
            help="With --dry-run: write the candidates file here (default: standard output).",
            dir_okay=False,
        ),
    ] = None,
    out_dir: Annotated[
        Path | None,
        typer.Option(
            "--out-dir",
            help="With --fake: use this data directory (database and candidates file) instead "
            "of the settings data directory.",
            file_okay=False,
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
        code=run_collect(
            _settings(root),
            dry_run=dry_run,
            fake=fake,
            out=out,
            out_dir=out_dir,
            disciplines=discipline or (),
        )
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
    raise typer.Exit(code=run_probe(_settings(root), text, discipline, source or ()))


@app.command("migrate")
def migrate_command(root: RootOption = None) -> None:
    """Create or upgrade the SQLite database at the settings database path."""
    raise typer.Exit(code=run_migrate(_settings(root)))


@app.command("export")
def export_command(root: RootOption = None) -> None:
    """Write the deterministic runs export, data/exports/runs.json, from the database."""
    raise typer.Exit(code=run_export(_settings(root)))


@app.command("rebuild")
def rebuild_command(root: RootOption = None) -> None:
    """Rebuild the database from config/ and the files under data/, printing row counts."""
    raise typer.Exit(code=run_rebuild(_settings(root)))


if __name__ == "__main__":  # pragma: no cover
    app()
