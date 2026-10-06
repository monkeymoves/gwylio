"""``gwylio collect`` and ``gwylio probe``: run the instrument, or try one query.

Real collectors arrive in work package 4 (WP4). Until then ``collect`` runs
only with ``--dry-run``: in-memory repositories and fake collectors fed from
the scripted hits in ``backend/tests/fixtures/fake_hits.json``. ``probe``
uses the same fake collectors and writes nothing.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import typer

from gwylio.collection.model import Discipline, Funnel, ScanRun, Source
from gwylio.collection.service import PROBE_QUERY_ID, Probe, RunScan
from gwylio.infrastructure.collectors.fake import FakeCollector, load_fake_hits
from gwylio.infrastructure.config import paths
from gwylio.infrastructure.config.loaders import LoadedConfig, check_config
from gwylio.infrastructure.handoff.candidates_file import (
    candidates_document,
    write_candidates_file,
)
from gwylio.infrastructure.ids import RandomIdGenerator
from gwylio.infrastructure.memory import (
    MemoryCandidateRepository,
    MemoryInstrumentRepository,
    MemoryScanRunRepository,
    NullKnownReports,
)
from gwylio.processing.candidates_file import dumps_candidates
from gwylio.shared.clock import SystemClock

__all__ = ["ACADEMIC_ENV_VAR", "default_disciplines", "funnel_table", "run_collect", "run_probe"]

ACADEMIC_ENV_VAR = "GWYLIO_ACADEMIC"
"""Set to 1 to include osint_academic in a scan's default disciplines."""
NOT_YET = "collect: real collectors arrive in WP4; run `gwylio collect --dry-run` to use fakes"


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
    root: Path, disciplines: Sequence[Discipline]
) -> dict[Discipline, FakeCollector]:
    hits = load_fake_hits(root / paths.FAKE_HITS_FILE)
    return {discipline: FakeCollector(discipline, hits) for discipline in disciplines}


def run_collect(
    root: Path,
    *,
    dry_run: bool,
    out: Path | None,
    disciplines: Sequence[Discipline],
) -> int:
    """Run a scan; return the exit code."""
    if not dry_run:
        typer.echo(NOT_YET, err=True)
        return 2
    chosen = tuple(disciplines) or default_disciplines()
    reserved = [d.value for d in chosen if d.reserved]
    if reserved:
        typer.echo(f"collect: no collector serves {', '.join(reserved)} in version 1", err=True)
        return 2
    config = _load(root)
    if config is None:
        return 1
    scan = RunScan(
        collectors=_fake_collectors(root, chosen),
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


def run_probe(root: Path, text: str, discipline: Discipline, source_ids: Sequence[str] = ()) -> int:
    """Run one query text through a fake collector, print its hits and store nothing."""
    if discipline.reserved:
        typer.echo(f"probe: no collector serves {discipline.value} in version 1", err=True)
        return 2
    config = _load(root)
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
        for hit in load_fake_hits(root / paths.FAKE_HITS_FILE)
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
