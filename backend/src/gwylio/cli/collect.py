"""``gwylio collect`` and ``gwylio probe``: run the instrument, or try one query.

``collect`` runs in one of three ways:

- no flag: the real collectors from ``infrastructure.collectors.registry``
  (Brave web and site search with a key, the feeds always, the academic
  indexes when switched on) with real persistence. A requested discipline
  that cannot run here is named with the reason and skipped; the run goes
  ahead on the rest (exit 0), and only when none can run does it exit 3.
- ``--fake``: the fake collectors fed from the scripted hits in
  ``backend/tests/fixtures/fake_hits.json`` (or the file ``--hits`` names),
  with the same real persistence.
- ``--dry-run``: the fake collectors with in-memory repositories; the
  candidates file goes to ``--out`` or standard output and nothing is kept.

With persistence, the scan spots reinforcements against the register (a
candidate whose canonical URL, or failing that exact title, matches a stored
intelligence report), and the run, its candidates, sightings and
reinforcements are stored in SQLite in one transaction, and before that transaction commits the
instrument is archived under ``<data_dir>/instruments/`` and the candidates
file written to ``<data_dir>/candidates/<run_id>.json``, so the files (the
facts) never lag the database (their projection). The runs export is
refreshed afterwards.

``--at`` pins the clock of a ``--fake`` or ``--dry-run`` scan to one UTC
instant and the run id suffix to ``0000``, so a fixture run (``make seed``)
has the same run id and candidate ids every time.

``probe`` runs one query text through the real collector for a discipline
(or the fake one with ``--fake``) and writes nothing.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import typer

from gwylio.collection.model import Discipline, Funnel, ScanRun, Source
from gwylio.collection.ports import Collector
from gwylio.collection.service import (
    PROBE_QUERY_ID,
    Probe,
    ProbeResult,
    RunResult,
    RunScan,
    ScanAborted,
)
from gwylio.infrastructure.collectors.fake import FakeCollector, load_fake_hits
from gwylio.infrastructure.collectors.feed import FeedCollector
from gwylio.infrastructure.collectors.registry import (
    build_collectors,
    describe_collector,
    missing_disciplines,
)
from gwylio.infrastructure.config.loaders import LoadedConfig, check_config
from gwylio.infrastructure.config.settings import ACADEMIC_ENV_VAR, Settings
from gwylio.infrastructure.handoff.candidates_file import (
    CandidatesFileError,
    candidates_document,
    write_candidates_file,
)
from gwylio.infrastructure.handoff.instrument_file import InstrumentFileError, archive_instrument
from gwylio.infrastructure.http.client import HttpClient
from gwylio.infrastructure.ids import FixedIdGenerator, RandomIdGenerator
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
    SqliteReportRepository,
    SqliteScanRunRepository,
    save_config,
)
from gwylio.intelligence.service import KnownReportsAdapter
from gwylio.processing.candidates_file import dumps_candidates
from gwylio.shared.clock import Clock, FixedClock, SystemClock
from gwylio.shared.errors import DomainError

__all__ = [
    "ACADEMIC_ENV_VAR",
    "NONE_AVAILABLE_EXIT",
    "default_disciplines",
    "funnel_table",
    "make_http_client",
    "run_collect",
    "run_probe",
]

NONE_AVAILABLE_EXIT = 3
"""The exit code when no requested discipline has a collector in this environment."""


def default_disciplines(academic_enabled: bool | None = None) -> tuple[Discipline, ...]:
    """Web, site and feed; academic too when switched on.

    ``academic_enabled`` defaults to ``GWYLIO_ACADEMIC=1`` in the environment.
    """
    if academic_enabled is None:
        academic_enabled = os.environ.get(ACADEMIC_ENV_VAR, "").strip() == "1"
    chosen = [Discipline.OSINT_WEB, Discipline.OSINT_SITE, Discipline.OSINT_FEED]
    if academic_enabled:
        chosen.append(Discipline.OSINT_ACADEMIC)
    return tuple(d for d in Discipline if d in chosen)


def make_http_client(settings: Settings) -> HttpClient:
    """The HTTP client a real scan or probe uses; tests replace it with one that never sleeps."""
    return HttpClient(contact_email=settings.contact_email)


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
    *,
    dry_run: bool,
    fake: bool,
    out: Path | None,
    out_dir: Path | None,
    at: datetime | None,
    hits: Path | None = None,
) -> str | None:
    if hits is not None and not (dry_run or fake):
        return "collect: --hits goes with --fake or --dry-run; a real scan reads the network"
    if hits is not None and not hits.is_file():
        return f"collect: no scripted hits file at {hits}"
    if at is not None and not (dry_run or fake):
        return "collect: --at goes with --fake or --dry-run; a real scan runs now"
    if at is not None and (at.tzinfo is None or at.utcoffset() is None):
        return "collect: --at needs a time zone, such as 2026-09-01T09:00:00+00:00"
    if dry_run and fake:
        return "collect: choose --dry-run (nothing kept) or --fake (stored), not both"
    if out is not None and not dry_run:
        return "collect: --out goes with --dry-run; a stored run writes under the data directory"
    if out_dir is not None and dry_run:
        return "collect: --out-dir goes with a stored run, not --dry-run"
    return None


def run_collect(
    settings: Settings,
    *,
    dry_run: bool,
    out: Path | None,
    disciplines: Sequence[Discipline],
    fake: bool = False,
    out_dir: Path | None = None,
    at: datetime | None = None,
    hits: Path | None = None,
) -> int:
    """Run a scan; return the exit code."""
    problem = _flag_problem(dry_run=dry_run, fake=fake, out=out, out_dir=out_dir, at=at, hits=hits)
    if problem is not None:
        typer.echo(problem, err=True)
        return 2
    chosen = tuple(dict.fromkeys(disciplines)) or default_disciplines(settings.academic_enabled)
    reserved = [d.value for d in chosen if d.reserved]
    if reserved:
        typer.echo(f"collect: no collector serves {', '.join(reserved)} in version 1", err=True)
        return 2
    config = _load(settings.config_root)
    if config is None:
        return 1
    target = settings if out_dir is None else settings.with_data_dir(out_dir)
    pinned = at is not None
    scripted = hits or settings.fake_hits_path
    clock: Clock = SystemClock() if at is None else FixedClock(at)
    if fake:
        return _collect_stored(
            target,
            config,
            chosen,
            _fake_collectors(scripted, chosen),
            clock=clock,
            pinned=pinned,
        )
    if not dry_run:
        return _collect_real(target, config, chosen, explicit=bool(disciplines))
    scan = RunScan(
        collectors=_fake_collectors(scripted, chosen),
        instruments=MemoryInstrumentRepository(),
        runs=MemoryScanRunRepository(),
        candidates=MemoryCandidateRepository(),
        known=NullKnownReports(),
        rules=config.gating,
        clock=clock,
        ids=FixedIdGenerator() if pinned else RandomIdGenerator(),
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


def _collect_real(
    settings: Settings,
    config: LoadedConfig,
    chosen: Sequence[Discipline],
    *,
    explicit: bool,
) -> int:
    """Run the real collectors that can run here, naming any requested one that cannot."""
    if explicit and Discipline.OSINT_ACADEMIC in chosen:
        settings = settings.with_academic()
    with make_http_client(settings) as http:
        collectors = build_collectors(settings, http)
        for line in missing_disciplines(chosen, collectors):
            typer.echo(f"skip   {line}", err=True)
        runnable = tuple(d for d in chosen if d in collectors)
        if not runnable:
            typer.echo(
                "collect: none of the requested disciplines can run here; nothing collected",
                err=True,
            )
            return NONE_AVAILABLE_EXIT
        code = _collect_stored(settings, config, runnable, collectors)
    for collector in collectors.values():
        if isinstance(collector, FeedCollector) and Discipline.OSINT_FEED in runnable:
            typer.echo(collector.summary())
    return code


def _collect_stored(
    settings: Settings,
    config: LoadedConfig,
    disciplines: Sequence[Discipline],
    collectors: Mapping[Discipline, Collector],
    *,
    clock: Clock | None = None,
    pinned: bool = False,
) -> int:
    """Run ``collectors`` with SQLite persistence and the candidates file."""
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
            collectors={d: collectors[d] for d in disciplines},
            instruments=SqliteInstrumentRepository(db),
            runs=SqliteScanRunRepository(db),
            candidates=SqliteCandidateRepository(db),
            known=KnownReportsAdapter(SqliteReportRepository(db)),
            rules=config.gating,
            clock=clock or SystemClock(),
            ids=FixedIdGenerator() if pinned else RandomIdGenerator(),
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
    settings: Settings,
    text: str,
    discipline: Discipline,
    source_ids: Sequence[str] = (),
    *,
    fake: bool = False,
) -> int:
    """Run one query text through a real (or with ``fake``, scripted) collector; store nothing."""
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
    if fake:
        return _probe_fake(settings, text, discipline, sources)
    if discipline is Discipline.OSINT_FEED and not sources:
        sources = tuple(
            source
            for source in config.sources
            if source.active and source.discipline is Discipline.OSINT_FEED and source.feed_url
        )
    if discipline is Discipline.OSINT_ACADEMIC:
        settings = settings.with_academic()
    with make_http_client(settings) as http:
        collectors = build_collectors(settings, http)
        missing = missing_disciplines((discipline,), collectors)
        if missing:
            typer.echo(f"probe: cannot run {missing[0]}", err=True)
            return NONE_AVAILABLE_EXIT
        budget = max(2 if discipline is Discipline.OSINT_ACADEMIC else 1, len(sources))
        result = Probe(collectors).run(text, discipline, sources=sources, budget=budget)
    _print_probe(result, f"{discipline.value}, {describe_collector(discipline)}")
    return 0


def _probe_fake(
    settings: Settings, text: str, discipline: Discipline, sources: Sequence[Source]
) -> int:
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
    _print_probe(result, f"{discipline.value}, fake collector")
    return 0


def _print_probe(result: ProbeResult, label: str) -> None:
    count = len(result.hits)
    requests = result.requests_used
    typer.echo(
        f"probe ({label}): {count} hit{'' if count == 1 else 's'}, "
        f"{requests} request{'' if requests == 1 else 's'}, nothing stored"
    )
    for hit in result.hits:
        date = str(hit.published_on) if hit.published_on else "undated"
        typer.echo(f"  {date}  {hit.title}")
        typer.echo(f"              {hit.url}")
    for warning in result.warnings:
        typer.echo(f"warn   {warning}", err=True)
