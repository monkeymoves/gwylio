"""Run the sweep and keep its fact: ``data/sweeps/<on>__<n>.json``.

The fade rule depends on which runs and sightings existed when it ran, so a
rebuild cannot re-run it; it applies the fades the sweep recorded instead.
``sweep`` plans the fades, applies them and writes the sweep file inside one
database transaction (the file before the commit, as collect and ingest do).
A sweep that fades nothing writes no file.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from gwylio.infrastructure.sqlite.db import Database
from gwylio.infrastructure.sqlite.repositories import (
    SqliteReportRepository,
    SqliteSightingLookup,
    SqliteSubmissionRepository,
)
from gwylio.intelligence.service import FadeDecision, Sweep
from gwylio.processing.ingest import (
    SWEEP_FORMAT,
    FadeEntry,
    SweepFile,
    dumps_sweep,
    loads_sweep,
    next_sweep_stem,
)
from gwylio.shared.values import CleanText, IsoDate, KebabId

__all__ = ["SweepFileError", "SweepOutcome", "apply_sweep_file", "read_sweep_files", "sweep"]


class SweepFileError(ValueError):
    """A sweep file could not be read or applied."""


@dataclass(frozen=True, slots=True)
class SweepOutcome:
    """What one sweep faded, and the file that records it (none when nothing faded)."""

    faded: tuple[FadeDecision, ...]
    path: Path | None


def sweep(db: Database, sweeps_dir: Path, today: IsoDate) -> SweepOutcome:
    """Apply the fade rule on ``today`` and record the fades in a new sweep file."""
    with db.transaction():
        service = Sweep(reports=SqliteReportRepository(db), sightings=SqliteSightingLookup(db))
        decisions = service.plan()
        if not decisions:
            return SweepOutcome((), None)
        service.apply(decisions, today)
        existing = [p.stem for p in sweeps_dir.glob("*.json")] if sweeps_dir.is_dir() else []
        stem = next_sweep_stem(str(today), existing)
        document = SweepFile(
            format=SWEEP_FORMAT,
            on=str(today),
            after_submissions=len(SqliteSubmissionRepository(db).all()),
            faded=[FadeEntry(report_id=d.report_id, change=d.change) for d in decisions],
        )
        path = sweeps_dir / f"{stem}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dumps_sweep(document), encoding="utf-8")
    return SweepOutcome(decisions, path)


def read_sweep_files(sweeps_dir: Path) -> list[tuple[Path, SweepFile]]:
    """Every sweep file under ``sweeps_dir``, by file name."""
    if not sweeps_dir.is_dir():
        return []
    found: list[tuple[Path, SweepFile]] = []
    for path in sorted(sweeps_dir.glob("*.json")):
        try:
            found.append((path, loads_sweep(path.read_text(encoding="utf-8"))))
        except (OSError, UnicodeDecodeError, ValidationError) as error:
            raise SweepFileError(f"{path}: not a valid sweep file: {error}") from error
    return found


def apply_sweep_file(db: Database, document: SweepFile) -> None:
    """Apply the fades a sweep file recorded, on the day it ran."""
    service = Sweep(reports=SqliteReportRepository(db), sightings=SqliteSightingLookup(db))
    decisions = [FadeDecision(KebabId(f.report_id), CleanText(f.change)) for f in document.faded]
    service.apply(decisions, IsoDate(document.on))
