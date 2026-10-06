"""Entry point for the ``gwylio`` command line tool.

Each verb's logic lives in its own module (``check.py``, ``schema.py``,
``collect.py``, ``database.py``, ``register.py``, ``evaluate.py``,
``product.py``, ``publish.py``, ``serve.py``); this module only declares the Typer commands
and registers them. Every command takes its paths from one ``Settings``
object, built by ``_settings`` from ``--root`` and the ``GWYLIO_`` environment.
"""

from __future__ import annotations

from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from typer.main import get_command

from gwylio.cli.check import run_check
from gwylio.cli.collect import run_collect, run_probe
from gwylio.cli.database import run_export, run_migrate, run_rebuild
from gwylio.cli.evaluate import run_audit, run_yield
from gwylio.cli.product import run_product
from gwylio.cli.publish import run_publish
from gwylio.cli.register import run_datecheck, run_import_legacy, run_ingest, run_sweep
from gwylio.cli.schema import run_schema
from gwylio.cli.serve import DEFAULT_HOST, DEFAULT_PORT, run_serve
from gwylio.collection.model import Discipline
from gwylio.dissemination.model import Level
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
            help="For a stored run (real or --fake): use this data directory (database and "
            "candidates file) instead of the settings data directory.",
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
    at: Annotated[
        datetime | None,
        typer.Option(
            "--at",
            formats=["%Y-%m-%dT%H:%M:%S%z"],
            help="With --fake or --dry-run: pin the run's clock to this instant (such as "
            "2026-09-01T09:00:00+0000) and its run id suffix to 0000, for reproducible fixtures.",
        ),
    ] = None,
    hits: Annotated[
        Path | None,
        typer.Option(
            "--hits",
            help="With --fake or --dry-run: the scripted hits file to replay (default: "
            "backend/tests/fixtures/fake_hits.json).",
            dir_okay=False,
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
            at=at,
            hits=hits,
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
        typer.Option(
            "--source",
            help="A source id: needed for osint_site, optional for osint_feed (default: every "
            "active feed); repeat for more.",
        ),
    ] = None,
    fake: Annotated[
        bool,
        typer.Option("--fake", help="Use the fake collector and its scripted hits; no network."),
    ] = False,
    root: RootOption = None,
) -> None:
    """Try one query text and print its hits, storing nothing."""
    raise typer.Exit(code=run_probe(_settings(root), text, discipline, source or (), fake=fake))


@app.command("migrate")
def migrate_command(root: RootOption = None) -> None:
    """Create or upgrade the SQLite database at the settings database path."""
    raise typer.Exit(code=run_migrate(_settings(root)))


@app.command("export")
def export_command(root: RootOption = None) -> None:
    """Write the deterministic exports: runs.json, register.json and products.json."""
    raise typer.Exit(code=run_export(_settings(root)))


@app.command("rebuild")
def rebuild_command(root: RootOption = None) -> None:
    """Rebuild the database from config/ and the files under data/, printing row counts."""
    raise typer.Exit(code=run_rebuild(_settings(root)))


@app.command("ingest")
def ingest_command(
    file: Annotated[
        Path,
        typer.Argument(
            help="The submission file. One outside data/submissions/ is copied in on success.",
            dir_okay=False,
        ),
    ],
    allow_deferred: Annotated[
        bool,
        typer.Option(
            "--allow-deferred",
            help="Accept a run submission that leaves candidates without a disposition.",
        ),
    ] = False,
    root: RootOption = None,
) -> None:
    """Validate a submission and apply it to the register, all or nothing."""
    raise typer.Exit(code=run_ingest(_settings(root), file, allow_deferred=allow_deferred))


@app.command("sweep")
def sweep_command(
    today: Annotated[
        str | None,
        typer.Option("--today", help="The date to sweep on, YYYY-MM-DD (default: today, UTC)."),
    ] = None,
    root: RootOption = None,
) -> None:
    """Fade active reports quiet in the two most recent complete runs; print faded ids."""
    raise typer.Exit(code=run_sweep(_settings(root), today=today))


@app.command("datecheck")
def datecheck_command(
    today: Annotated[
        str | None,
        typer.Option("--today", help="The date to check against, YYYY-MM-DD (default: today)."),
    ] = None,
    root: RootOption = None,
) -> None:
    """Print reports whose dates or wording may have rotted, grouped by kind; always exit 0."""
    raise typer.Exit(code=run_datecheck(_settings(root), today=today))


@app.command("import-legacy")
def import_legacy_command(
    signals: Annotated[
        Path,
        typer.Argument(help="The old tool's data/signals.json.", dir_okay=False),
    ],
    received_on: Annotated[
        str | None,
        typer.Option(
            "--received-on",
            help="The legacy submission's date, YYYY-MM-DD (default: the file's scan_date).",
        ),
    ] = None,
    root: RootOption = None,
) -> None:
    """Seed the register from the old signals.json through a legacy submission."""
    raise typer.Exit(code=run_import_legacy(_settings(root), signals, received_on=received_on))


@app.command("audit")
def audit_command(
    set_id: Annotated[
        str | None,
        typer.Option("--set", help="The requirement set to audit (default: the first configured)."),
    ] = None,
    root: RootOption = None,
) -> None:
    """Print the coverage audit: requirements by lane, taxonomy by count, credibility spread."""
    raise typer.Exit(code=run_audit(_settings(root), set_id))


@app.command("yield")
def yield_command(root: RootOption = None) -> None:
    """Print each watched source's yield and reading, silent sources last."""
    raise typer.Exit(code=run_yield(_settings(root)))


@app.command("product")
def product_command(
    level: Annotated[
        Level,
        typer.Option(
            "--level",
            help="operational (the monthly INTSUM), strategic (the annual picture) or tactical "
            "(a seam, exits 4).",
        ),
    ],
    period: Annotated[
        str | None,
        typer.Option(
            "--period",
            help="YYYY-MM for operational, YYYY for strategic (default: the one holding today).",
        ),
    ] = None,
    set_id: Annotated[
        str | None,
        typer.Option("--set", help="The requirement set (default: the first configured)."),
    ] = None,
    today: Annotated[
        str | None,
        typer.Option("--today", help="The render date, YYYY-MM-DD (default: today, UTC)."),
    ] = None,
    root: RootOption = None,
) -> None:
    """Render a product to data/products/ and record it; print the Markdown path."""
    raise typer.Exit(
        code=run_product(_settings(root), level, period=period, set_id=set_id, on=today)
    )


@app.command("publish")
def publish_command(
    out: Annotated[
        list[Path] | None,
        typer.Option(
            "--out",
            help="Write the snapshot here instead of frontend/static/data and data/snapshots; "
            "repeat for more.",
            file_okay=False,
        ),
    ] = None,
    at: Annotated[
        datetime | None,
        typer.Option(
            "--at",
            formats=["%Y-%m-%dT%H:%M:%S%z"],
            help="Pin the clock (generated_at and the date check's today), such as "
            "2026-10-06T09:00:00+0000, for a reproducible snapshot.",
        ),
    ] = None,
    root: RootOption = None,
) -> None:
    """Publish the JSON snapshot the static site reads; print the file count."""
    raise typer.Exit(code=run_publish(_settings(root), out=out or (), at=at))


@app.command("serve")
def serve_command(
    port: Annotated[int, typer.Option("--port", help="The port to listen on.")] = DEFAULT_PORT,
    host: Annotated[str, typer.Option("--host", help="The address to bind.")] = DEFAULT_HOST,
    root: RootOption = None,
) -> None:
    """Run the read API (a development tool) at http://HOST:PORT/api/v1."""
    raise typer.Exit(code=run_serve(_settings(root), host=host, port=port))


if __name__ == "__main__":  # pragma: no cover
    app()
