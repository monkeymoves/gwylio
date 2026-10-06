"""``gwylio collect`` and ``gwylio probe``: run the instrument, or try one query.

Real collectors arrive in work package 4 (WP4). Until then ``collect`` runs
only on the fake collectors fed from the scripted hits in
``backend/tests/fixtures/fake_hits.json``, in one of two ways:

- ``--dry-run``: in-memory repositories; the candidates file goes to ``--out``
  or standard output and nothing is kept.
- ``--fake``: real persistence. The run, its candidates, sightings and
  reinforcements are stored in SQLite in one transaction, and before that
  transaction commits the instrument is archived under
  ``<data_dir>/instruments/`` and the candidates file written to
  ``<data_dir>/candidates/<run_id>.json``, so the files (the facts) never lag
  the database (their projection). The runs export is refreshed afterwards.

``probe`` uses the same fake collectors and writes nothing.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import typer

from gwylio.collection.model import Discipline, Funnel, ScanRun, Source
from gwylio.collection.service import PROBE_QUERY_ID, Probe, RunResult, RunScan, ScanAborted
from gwylio.infrastructure.collectors.fake import FakeCollector, load_fake_hits
from gwylio.infrastructure.config.loaders import LoadedConfig, check_config
from gwylio.infrastructure.config.settings import Settings
from gwylio.infrastructure.handoff.candidates_file import (
    CandidatesFileError,
    candidates_document,
    write_candidates_file,
)
from gwylio.infrastructure.handoff.instrument_file import InstrumentFileError, archive_instrument
from gwylio.infrastructure.ids import RandomIdGenerator
from gwylio.infrastructure.memory import (
    MemoryCandidateRepository,
    MemoryInstrumentRepository,
    MemoryScanRunRepository,
    NullKnownReports,
)
from gwylio.infrastructure.sqlite.db import Database
from gwylio.infrastructure.sqlite.export import write_runs_export
from gwylio.infrastructure.sqlite.migrate import migrate
from gwylio.infrastructure.sqlite.repositories import (
    SqliteCandidateRepository,
    SqliteInstrumentRepository,
    SqliteScanRunRepository,
    save_config,
)
from gwylio.processing.candidates_file import dumps_candidates
from gwylio.shared.clock import SystemClock
from gwylio.shared.errors import DomainError

__all__ = ["ACADEMIC_ENV_VAR", "default_disciplines", "funnel_table", "run_collect", "run_probe"]

ACADEMIC_ENV_VAR = "GWYLIO_ACADEMIC"
"""Set to 1 to include osint_academic in a scan's default disciplines."""
NOT_YET = (
    "collect: real collectors arrive in WP4; until then use `gwylio collect --fake` "
    "(fake collectors, stored) or `gwylio collect --dry-run` (fake collectors, nothing kept)"
)


def default_disciplines() -> tuple[Discipline, ...]:
    """Web, site and feed; academic too when ``GWYLIO_ACADEMIC=1``."""
    chosen = [Discipline.OSINT_WEB, Discipline.OSINT_SITE, Discipline.OSINT_FEED]
    if os.environ.get(ACADEMIC_ENV_VAR) == "1":
        chosen.append(Discipline.OSINT_ACADEMIC)
    return tuple(d for d in Discipline if d in chosen)


def funnel_table(run: ScanRun) -> str:
    """The run's funnel as a small text table, with the request budget underneath."""
    funnel: Funnel = run.funnel
    rows = [
        ("raw hits", funnel.raw),
        ("dropped: own domain", funnel.dropped_own),
        ("dropped: negative term", funnel.dropped_negative),
        ("dropped: unrelated", funnel.dropped_unrelated),
        ("passed the gates", funnel.passed),
        ("unique candidates", funnel.unique),
        ("  new", funnel.new),
        ("  seen before", funnel.seen_before),
        ("  reinforcements", funnel.reinforcements),
    ]
    width = max(len(label) for label, _ in rows)
    lines = [
        f"Funnel for run {run.id} (instrument {run.instrument_version})",
        f"  {'stage'.ljust(width)}  {'count':>6}",
        *(f"  {label.ljust(width)}  {count:>6}" for label, count in rows),
        f"requests made: {run.requests_made} of {run.request_budget}; budget "
        + ("exhausted" if run.budget_exhausted else "not exhausted"),
        *(f"note: {note}" for note in run.notes),
    ]
    return "\n".join(lines)


def _load(root: Path) -> LoadedConfig | None:
    report = check_config(root)
    if report.config is None:
        for problem in report.problems:
            typer.echo(f"error  {problem}", err=True)
        typer.echo("configuration is invalid, run `gwylio check`", err=True)
    return report.config


def _fake_collectors(
    hits_file: Path, disciplines: Sequence[Discipline]
) -> dict[Discipline, FakeCollector]:
    hits = load_fake_hits(hits_file)
    return {discipline: FakeCollector(discipline, hits) for discipline in disciplines}


def _flag_problem(
    *, dry_run: bool, fake: bool, out: Path | None, out_dir: Path | None
) -> str | None:
    if dry_run and fake:
        return "collect: choose --dry-run (nothing kept) or --fake (stored), not both"
    if out is not None and not dry_run:
        return "collect: --out goes with --dry-run; a stored run writes under the data directory"
    if out_dir is not None and not fake:
        return "collect: --out-dir goes with --fake"
    if not dry_run and not fake:
        return NOT_YET
    return None


def run_collect(
    settings: Settings,
    *,
    dry_run: bool,
    out: Path | None,
    disciplines: Sequence[Discipline],
    fake: bool = False,
    out_dir: Path | None = None,
) -> int:
    """Run a scan; return the exit code."""
    problem = _flag_problem(dry_run=dry_run, fake=fake, out=out, out_dir=out_dir)
    if problem is not None:
        typer.echo(problem, err=True)
        return 2
    chosen = tuple(disciplines) or default_disciplines()
    reserved = [d.value for d in chosen if d.reserved]
    if reserved:
        typer.echo(f"collect: no collector serves {', '.join(reserved)} in version 1", err=True)
        return 2
    config = _load(settings.config_root)
    if config is None:
        return 1
    if fake:
        target = settings if out_dir is None else settings.with_data_dir(out_dir)
        return _collect_stored(target, config, chosen)
    scan = RunScan(
        collectors=_fake_collectors(settings.fake_hits_path, chosen),
        instruments=MemoryInstrumentRepository(),
        runs=MemoryScanRunRepository(),
        candidates=MemoryCandidateRepository(),
        known=NullKnownReports(),
        rules=config.gating,
        clock=SystemClock(),
        ids=RandomIdGenerator(),
    )
    result = scan.execute(config.instrument, config.sources, chosen)
    table = funnel_table(result.run)
    if out is None:
        typer.echo(dumps_candidates(candidates_document(result)), nl=False)
        typer.echo(table, err=True)
    else:
        write_candidates_file(result, out, overwrite=True)
        typer.echo(f"wrote  {out}")
        typer.echo(table)
    for warning in result.warnings:
        typer.echo(f"warn   {warning}", err=True)
    return 0


def _collect_stored(
    settings: Settings, config: LoadedConfig, disciplines: Sequence[Discipline]
) -> int:
    """Run the fake collectors with SQLite persistence and the candidates file."""
    aborted: ScanAborted | None = None
    with Database.open(settings.db_path) as db:
        migrate(db)
        try:
            save_config(db, config)
        except sqlite3.IntegrityError as error:
            typer.echo(
                f"collect: config/ no longer matches the stored runs ({error}): a source or "
                "lane that a stored run names has gone; retire sources rather than removing "
                "them, or run `gwylio rebuild`",
                err=True,
            )
            return 1
        scan = RunScan(
            collectors=_fake_collectors(settings.fake_hits_path, disciplines),
            instruments=SqliteInstrumentRepository(db),
            runs=SqliteScanRunRepository(db),
            candidates=SqliteCandidateRepository(db),
            known=NullKnownReports(),
            rules=config.gating,
            clock=SystemClock(),
            ids=RandomIdGenerator(),
        )
        try:
            # One transaction for the run and everything it found; the files are
            # written inside it, so a fact on disk never lags the database.
            with db.transaction():
                try:
                    result = scan.execute(config.instrument, config.sources, disciplines)
                except ScanAborted as error:
                    aborted = error
                    result = RunResult(error.run, (), (), ())
                archive_instrument(config.instrument, settings.instruments_dir)
                path = write_candidates_file(
                    result, settings.candidates_dir / f"{result.run.id}.json"
                )
        except (DomainError, CandidatesFileError, InstrumentFileError) as error:
            typer.echo(f"collect: nothing stored: {error}", err=True)
            return 1
        export = write_runs_export(db, settings.runs_export_path)
    typer.echo(f"wrote  {path}")
    typer.echo(f"stored run {result.run.id} in {settings.db_path}")
    typer.echo(f"wrote  {export}")
    typer.echo(funnel_table(result.run))
    for warning in result.warnings:
        typer.echo(f"warn   {warning}", err=True)
    if aborted is not None:
        typer.echo(f"collect: {aborted}", err=True)
        return 1
    return 0


def run_probe(
    settings: Settings, text: str, discipline: Discipline, source_ids: Sequence[str] = ()
) -> int:
    """Run one query text through a fake collector, print its hits and store nothing."""
    if discipline.reserved:
        typer.echo(f"probe: no collector serves {discipline.value} in version 1", err=True)
        return 2
    config = _load(settings.config_root)
    if config is None:
        return 1
    by_id: dict[str, Source] = {source.id: source for source in config.sources}
    unknown = [source_id for source_id in source_ids if source_id not in by_id]
    if unknown:
        typer.echo(f"probe: unknown source {', '.join(unknown)}", err=True)
        return 2
    sources = tuple(by_id[source_id] for source_id in source_ids)
    if discipline is Discipline.OSINT_SITE and not sources:
        typer.echo("probe: an osint_site probe needs at least one --source", err=True)
        return 2
    words = text.casefold().split()
    scripted = (
        replace(hit, query_id=PROBE_QUERY_ID)
        for hit in load_fake_hits(settings.fake_hits_path)
        if hit.discipline is discipline
        and all(word in f"{hit.title} {hit.snippet}".casefold() for word in words)
    )
    collector = FakeCollector(discipline, scripted)
    result = Probe({discipline: collector}).run(
        text, discipline, sources=sources, budget=max(1, len(sources))
    )
    count = len(result.hits)
    typer.echo(
        f"probe ({discipline.value}, fake collector): {count} hit{'' if count == 1 else 's'}, "
        "nothing stored"
    )
    for hit in result.hits:
        date = str(hit.published_on) if hit.published_on else "undated"
        typer.echo(f"  {date}  {hit.title}")
        typer.echo(f"              {hit.url}")
    for warning in result.warnings:
        typer.echo(f"warn   {warning}", err=True)
    return 0
