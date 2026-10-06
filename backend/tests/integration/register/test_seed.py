"""The committed seed under backend/tests/fixtures/seed is what ``make seed`` builds."""

from __future__ import annotations

from pathlib import Path

import pytest

from gwylio.infrastructure.sqlite.db import Database
from gwylio.infrastructure.sqlite.rebuild import rebuild_into
from gwylio.infrastructure.sqlite.repositories import SqliteReportRepository
from tests.integration.register.conftest import Cli
from tests.integration.register.test_sweep_and_rebuild import seeded
from tests.support import PROJECT_ROOT

pytestmark = pytest.mark.integration

SEED = PROJECT_ROOT / "backend" / "tests" / "fixtures" / "seed"
FACTS = ("candidates", "instruments", "submissions", "exports")


def files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for folder in FACTS
        for path in sorted((root / folder).glob("*.json"))
    }


def test_the_committed_seed_is_reproduced_byte_for_byte(cli: Cli, data: Path) -> None:
    seeded(cli)
    committed = files(SEED)
    assert len(committed) == 7, "run make seed to rebuild backend/tests/fixtures/seed"
    assert files(data) == committed


def test_the_seed_rebuilds_into_memory_from_its_files() -> None:
    db = Database.memory()
    summary = rebuild_into(db, SEED, PROJECT_ROOT / "config")
    assert (summary.candidates_files, summary.submission_files) == (2, 2)
    reports = SqliteReportRepository(db).list()
    assert len(reports) == 10
    assert summary.counts["disposition"] == 18
