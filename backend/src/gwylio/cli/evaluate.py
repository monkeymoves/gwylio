"""``gwylio audit`` and ``gwylio yield``: how well the collection is working.

``audit`` prints the coverage audit of one requirement set: requirements by
lane and every taxonomy axis by count, each row with its status, then the
credibility spread of the active reports. ``yield`` prints every watched
source's yield, silent sources last. Both read only; both need the database.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

import typer

from gwylio.cli.common import database, load
from gwylio.evaluation.coverage import UNATTRIBUTED, CoverageMatrix
from gwylio.evaluation.yield_ import SourceYield, YieldReading
from gwylio.infrastructure.adapters import CoverageAudit, audit, funnel_trend, source_yield
from gwylio.infrastructure.config.settings import Settings
from gwylio.shared.coverage import CoverageStatus

__all__ = ["run_audit", "run_yield"]

_READING_ORDER = tuple(YieldReading)


def _rows(
    header: Sequence[str], rows: Sequence[Sequence[str]], numeric: range | set[int]
) -> list[str]:
    """Aligned text rows: the ``numeric`` columns to the right, the rest to the left."""
    widths = [max(len(row[i]) for row in (header, *rows)) for i in range(len(header))]

    def line(cells: Sequence[str]) -> str:
        parts = [
            cell.rjust(widths[i]) if i in numeric else cell.ljust(widths[i])
            for i, cell in enumerate(cells)
        ]
        return "  " + "  ".join(parts).rstrip()

    return [line(header), *(line(row) for row in rows)]


def _status_mix(matrix: CoverageMatrix) -> str:
    counts = Counter(row.status for row in matrix.rows)
    return ", ".join(
        f"{status.value} {counts[status]}" for status in CoverageStatus if counts[status]
    )


def _print_audit(result: CoverageAudit) -> None:
    rs = result.requirement_set
    lanes = result.lanes
    typer.echo(f"coverage audit: {rs.id} ({rs.name}), active reports only")
    typer.echo("")
    typer.echo("requirements by lane")
    keys = [f"L{i}" for i in range(1, len(lanes.columns))] + ["U"]
    legend = [f"{key} {column}" for key, column in zip(keys, lanes.columns, strict=True)]
    typer.echo("  lanes: " + ", ".join(legend))
    header = ["requirement", *keys, "total", "status"]
    rows = [
        [row.label, *(str(cell.count) for cell in row.cells), str(row.total), row.status.value]
        for row in lanes.rows
    ]
    for text in _rows(header, rows, range(1, len(header) - 1)):
        typer.echo(text)
    typer.echo(f"  row statuses: {_status_mix(lanes)}")
    if lanes.column_total(UNATTRIBUTED):
        typer.echo(f"  unattributed reports: {lanes.column_total(UNATTRIBUTED)}")
    for axis, matrix in result.taxonomy:
        typer.echo("")
        typer.echo(f"taxonomy: {axis.id} ({axis.name})")
        rows = [
            [row.row_id, str(row.expected or 0), str(row.total), row.status.value]
            for row in matrix.rows
        ]
        for text in _rows(["node", "expected", "reports", "status"], rows, {1, 2}):
            typer.echo(text)
        typer.echo(f"  node statuses: {_status_mix(matrix)}")
    typer.echo("")
    typer.echo("credibility distribution (active reports assessed against the set)")
    rows = [
        [str(int(c.credibility)), c.credibility.label, str(c.count)] for c in result.credibility
    ]
    for text in _rows(["digit", "meaning", "reports"], rows, {2}):
        typer.echo(text)


def run_audit(settings: Settings, set_id: str | None = None) -> int:
    """Print the coverage audit of one requirement set; return the exit code."""
    config = load(settings.config_root, "audit")
    if config is None:
        return 1
    chosen = set_id or str(config.requirement_sets[0].id)
    if chosen not in {str(rs.id) for rs in config.requirement_sets}:
        known = ", ".join(str(rs.id) for rs in config.requirement_sets)
        typer.echo(f"audit: no requirement set '{chosen}'; configured: {known}", err=True)
        return 2
    if not settings.db_path.is_file():
        typer.echo(f"audit: no database at {settings.db_path}; run `gwylio rebuild`", err=True)
        return 1
    with database(settings, config, "audit") as db:
        if db is None:
            return 1
        result = audit(db, config, chosen)
    _print_audit(result)
    return 0


def _rate(value: float | None) -> str:
    return "" if value is None else f"{100 * value:.0f}%"


def _yield_order(item: SourceYield) -> tuple[int, int, int, int, str]:
    silent = item.reading is YieldReading.SILENT
    return (
        int(silent),
        _READING_ORDER.index(item.reading),
        -item.promoted,
        -item.unique_candidates,
        item.source_id,
    )


def run_yield(settings: Settings) -> int:
    """Print the yield of every watched source, silent sources last; return the exit code."""
    config = load(settings.config_root, "yield")
    if config is None:
        return 1
    if not settings.db_path.is_file():
        typer.echo(f"yield: no database at {settings.db_path}; run `gwylio rebuild`", err=True)
        return 1
    with database(settings, config, "yield") as db:
        if db is None:
            return 1
        yields = source_yield(db, config)
        runs = len(funnel_trend(db).runs)
    ordered = sorted(yields, key=_yield_order)
    typer.echo(f"yield of {len(ordered)} sources over {runs} run{'s' if runs != 1 else ''}")
    header = [
        "source",
        "raw hits",
        "unique",
        "promoted",
        "rate",
        "last run with hits",
        "last productive run",
        "reading",
    ]
    rows = [
        [
            item.source_id + ("" if item.active else " (not active)"),
            str(item.raw_hits),
            str(item.unique_candidates),
            str(item.promoted),
            _rate(item.promotion_rate),
            item.last_run_with_hits or "",
            item.last_productive_run or "",
            item.reading.value,
        ]
        for item in ordered
    ]
    for text in _rows(header, rows, {1, 2, 3, 4}):
        typer.echo(text)
    readings = Counter(item.reading for item in ordered)
    typer.echo(
        "readings: " + ", ".join(f"{r.value} {readings[r]}" for r in YieldReading if readings[r])
    )
    silent = [item.source_id for item in ordered if item.reading is YieldReading.SILENT]
    typer.echo(f"silent sources ({len(silent)}): {', '.join(silent) if silent else 'none'}")
    return 0
