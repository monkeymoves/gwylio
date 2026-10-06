"""Deterministic exports of the database: ``data/exports/runs.json``.

Exports are derived: written after a scan so the state of the projection is
readable in a diff, and never read back as input. Two exports of the same
database are byte-identical: runs sorted by id, keys sorted, two-space indent,
UTF-8 characters and a trailing newline, and no export time in the file.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Final

from gwylio.infrastructure.sqlite.db import Database
from gwylio.infrastructure.sqlite.repositories import (
    SqliteCandidateRepository,
    SqliteScanRunRepository,
    format_timestamp,
)

__all__ = ["RUNS_EXPORT_FORMAT", "dumps_export", "export_runs", "write_runs_export"]

RUNS_EXPORT_FORMAT: Final[str] = "gwylio.runs/1"
"""The format identifier ``runs.json`` carries."""


def export_runs(db: Database) -> dict[str, Any]:
    """Every stored scan run with its funnel, requests, status and counts per discipline."""
    runs = SqliteScanRunRepository(db).all()
    candidates = SqliteCandidateRepository(db)
    exported: list[dict[str, Any]] = []
    for run in sorted(runs, key=lambda r: r.id):
        found = Counter(c.discipline for c in candidates.candidates_for_run(run.id))
        seen = Counter(s.discipline for s in candidates.sightings_for_run(run.id))
        reinforced = len(candidates.reinforcements_for_run(run.id))
        exported.append(
            {
                "run_id": str(run.id),
                "status": run.status.value,
                "started_at": format_timestamp(run.started_at),
                "finished_at": None
                if run.finished_at is None
                else format_timestamp(run.finished_at),
                "instrument_version": str(run.instrument_version),
                "instrument_hash": run.instrument_hash,
                "disciplines": [d.value for d in run.disciplines],
                "request_budget": run.request_budget,
                "requests_made": run.requests_made,
                "budget_exhausted": run.budget_exhausted,
                "notes": [str(note) for note in run.notes],
                "funnel": {
                    "raw": run.funnel.raw,
                    "dropped_own": run.funnel.dropped_own,
                    "dropped_negative": run.funnel.dropped_negative,
                    "dropped_unrelated": run.funnel.dropped_unrelated,
                    "passed": run.funnel.passed,
                    "unique": run.funnel.unique,
                    "seen_before": run.funnel.seen_before,
                    "new": run.funnel.new,
                    "reinforcements": run.funnel.reinforcements,
                },
                "reinforcements_recorded": reinforced,
                "per_discipline": {
                    d.value: {"candidates": found[d], "sightings": seen[d]} for d in run.disciplines
                },
            }
        )
    return {"format": RUNS_EXPORT_FORMAT, "runs": exported}


def dumps_export(document: dict[str, Any]) -> str:
    """The export's text: sorted keys, two-space indent, UTF-8 characters, trailing newline."""
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_runs_export(db: Database, path: Path) -> Path:
    """Write ``runs.json`` to ``path``, replacing any earlier export."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps_export(export_runs(db)), encoding="utf-8")
    return path
