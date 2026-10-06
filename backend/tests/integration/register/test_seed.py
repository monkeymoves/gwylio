"""The committed seed under backend/tests/fixtures/seed is what ``make seed`` builds."""

from __future__ import annotations

from pathlib import Path

import pytest

from gwylio.infrastructure.sqlite.db import Database
from gwylio.infrastructure.sqlite.rebuild import rebuild_into
from gwylio.infrastructure.sqlite.repositories import (
    SqliteProductRepository,
    SqliteReportRepository,
)
from gwylio.shared.vocabulary import IndicatorState
from tests.integration.register.conftest import SEED_SUBMISSIONS, Cli
from tests.integration.register.test_sweep_and_rebuild import seeded
from tests.support import PROJECT_ROOT

pytestmark = pytest.mark.integration

SEED = PROJECT_ROOT / "backend" / "tests" / "fixtures" / "seed"
SEED_HITS = PROJECT_ROOT / "backend" / "tests" / "fixtures" / "seed_hits.json"
THIRD = "20261003T0900Z-0000"
FACTS = ("candidates", "instruments", "submissions", "sweeps", "products", "exports")


def full_seed(cli: Cli) -> None:
    """Every step ``make seed`` runs after the first two runs and submissions."""
    seeded(cli)
    for args in (
        ("collect", "--fake", "--hits", str(SEED_HITS), "--at", "2026-10-03T09:00:00+0000"),
        ("ingest", str(SEED_SUBMISSIONS / f"{THIRD}__1.json")),
        ("collect", "--fake", "--hits", str(SEED_HITS), "--at", "2026-10-04T09:00:00+0000"),
        ("sweep", "--today", "2026-10-05"),
        ("product", "--level", "operational", "--period", "2026-10", "--today", "2026-10-06"),
        ("product", "--level", "strategic", "--period", "2026", "--today", "2026-10-06"),
    ):
        result = cli(*args)
        assert result.exit_code == 0, result.output


def files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for folder in FACTS
        for path in sorted((root / folder).glob("*.json"))
    }


def test_the_committed_seed_is_reproduced_byte_for_byte(cli: Cli, data: Path) -> None:
    full_seed(cli)
    committed = files(SEED)
    assert len(committed) == 14, "run make seed to rebuild backend/tests/fixtures/seed"
    assert files(data) == committed
    for markdown in ("operational_2026-10.md", "strategic_2026.md"):
        assert (data / "products" / markdown).read_bytes() == (
            SEED / "products" / markdown
        ).read_bytes()


def test_the_seed_rebuilds_into_memory_from_its_files() -> None:
    db = Database.memory()
    summary = rebuild_into(db, SEED, PROJECT_ROOT / "config")
    assert (summary.candidates_files, summary.submission_files) == (4, 3)
    assert (summary.sweep_files, summary.product_files) == (1, 2)
    reports = SqliteReportRepository(db).list()
    assert len(reports) == 10
    assert summary.counts["disposition"] == 21
    assert len(SqliteProductRepository(db).all()) == 2


def test_the_seed_holds_every_case_the_read_models_must_show() -> None:
    db = Database.memory()
    rebuild_into(db, SEED, PROJECT_ROOT / "config")
    states = {str(r.id): r.state for r in SqliteReportRepository(db).list()}
    assert states["ccc-progress-report-2026"] is IndicatorState.MATURED
    assert states["storm-claudia-monmouthshire-flooding"] is IndicatorState.FADED
    assert states["sustainable-farming-scheme-concerns"] is IndicatorState.PARKED
    assert states["phosphate-welsh-rivers-2026"] is IndicatorState.REINFORCED
    assert states["south-west-wales-drought-2026"] is IndicatorState.REINFORCED
    assert all(
        a.requirement_id != "si12"
        for report in SqliteReportRepository(db).list()
        for a in report.assessments
    ), "SI12 (no scanability) stays without reports, so it reads as a blind spot"
