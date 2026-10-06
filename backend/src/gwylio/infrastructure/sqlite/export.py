"""Deterministic exports of the database: ``runs.json``, ``register.json`` and ``products.json``.

Exports are derived: written after a scan or an ingest so the state of the
projection is readable in a diff, and never read back as input. Two exports
of the same database are byte-identical: runs and reports sorted by id, keys
sorted, two-space indent, UTF-8 characters and a trailing newline, and no
export time in the file.

``register.json`` holds every intelligence report with its history, its
sighting ids and the two counts derived from those sightings: ``appearances``
(distinct runs) and ``distinct_sources`` (distinct source ids).

``products.json`` holds every rendered product as its product file records
it (``gwylio.product/1``), by id.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Final

from gwylio.dissemination.product_file import product_document
from gwylio.infrastructure.sqlite.db import Database
from gwylio.infrastructure.sqlite.repositories import (
    SqliteCandidateRepository,
    SqliteProductRepository,
    SqliteReportRepository,
    SqliteScanRunRepository,
    SqliteSightingLookup,
    format_timestamp,
)
from gwylio.intelligence.model import IntelligenceReport
from gwylio.intelligence.service import derived_counts

__all__ = [
    "PRODUCTS_EXPORT_FORMAT",
    "REGISTER_EXPORT_FORMAT",
    "RUNS_EXPORT_FORMAT",
    "dumps_export",
    "export_products",
    "export_register",
    "export_runs",
    "report_document",
    "write_products_export",
    "write_register_export",
    "write_runs_export",
]

RUNS_EXPORT_FORMAT: Final[str] = "gwylio.runs/1"
"""The format identifier ``runs.json`` carries."""
REGISTER_EXPORT_FORMAT: Final[str] = "gwylio.register/1"
"""The format identifier ``register.json`` carries."""
PRODUCTS_EXPORT_FORMAT: Final[str] = "gwylio.products/1"
"""The format identifier ``products.json`` carries."""


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


def report_document(
    report: IntelligenceReport, appearances: int, distinct_sources: int
) -> dict[str, Any]:
    """One report as plain JSON values, with its derived counts."""
    return {
        "id": str(report.id),
        "title": str(report.title),
        "url": report.url,
        "canonical_url": report.canonical_url.value,
        "source_id": report.source_id,
        "source_name": str(report.source_name),
        "actor_id": report.actor_id,
        "lane": str(report.lane),
        "report_type": report.report_type.value,
        "grading": str(report.grading),
        "reliability": report.grading.reliability.value,
        "credibility": int(report.grading.credibility),
        "assessments": [
            {"requirement_id": str(a.requirement_id), "direction": a.direction.value}
            for a in report.assessments
        ],
        "topics": [str(t) for t in report.topics],
        "hazards": [str(h) for h in report.hazards],
        "places": [str(p) for p in report.places],
        "scores": {
            "evidence": report.scores.evidence.value,
            "novelty": report.scores.novelty.value,
            "confidence": report.scores.confidence.value,
            "potential_impact": report.scores.potential_impact.value,
            "time_horizon": report.scores.time_horizon.value,
        },
        "state": report.state.value,
        "bucket": report.bucket.value,
        "event_horizon": None if report.event_horizon is None else str(report.event_horizon),
        "last_verified": None if report.last_verified is None else str(report.last_verified),
        "summary": str(report.summary),
        "notes": str(report.notes),
        "owner": None if report.owner is None else str(report.owner),
        "created_on": str(report.created_on),
        "created_run_id": report.created_run_id,
        "independent_confirmation": report.independent_confirmation,
        "history": [
            {"on": str(h.on), "kind": h.kind.value, "change": str(h.change)} for h in report.history
        ],
        "sighting_ids": [str(s) for s in report.sighting_ids],
        "appearances": appearances,
        "distinct_sources": distinct_sources,
    }


def export_register(db: Database) -> dict[str, Any]:
    """Every intelligence report, by id, with history, sightings and derived counts."""
    lookup = SqliteSightingLookup(db)
    reports = []
    for report in SqliteReportRepository(db).list():
        appearances, sources = derived_counts(lookup.sightings(report.sighting_ids))
        reports.append(report_document(report, appearances, sources))
    return {"format": REGISTER_EXPORT_FORMAT, "reports": reports}


def write_register_export(db: Database, path: Path) -> Path:
    """Write ``register.json`` to ``path``, replacing any earlier export."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps_export(export_register(db)), encoding="utf-8")
    return path


def export_products(db: Database) -> dict[str, Any]:
    """Every stored product, by id, as its product file records it."""
    products = [
        product_document(stored.product, stored.markdown_file).model_dump(mode="json")
        for stored in SqliteProductRepository(db).all()
    ]
    return {"format": PRODUCTS_EXPORT_FORMAT, "products": products}


def write_products_export(db: Database, path: Path) -> Path:
    """Write ``products.json`` to ``path``, replacing any earlier export."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps_export(export_products(db)), encoding="utf-8")
    return path
