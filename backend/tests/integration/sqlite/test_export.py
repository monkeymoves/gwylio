"""``runs.json``: deterministic, and a new run changes only its own entry."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from gwylio.infrastructure.config.loaders import LoadedConfig
from gwylio.infrastructure.sqlite.db import Database
from gwylio.infrastructure.sqlite.export import dumps_export, export_runs, write_runs_export
from gwylio.shared.clock import FixedClock
from gwylio.shared.vocabulary import Discipline
from tests.support import ALL, sqlite_scan

pytestmark = pytest.mark.integration

LATER = FixedClock(datetime(2026, 11, 3, 2, 15, 7, tzinfo=UTC))


def test_an_empty_database_exports_no_runs(db: Database) -> None:
    assert dumps_export(export_runs(db)) == '{\n  "format": "gwylio.runs/1",\n  "runs": []\n}\n'


def test_two_exports_of_the_same_database_are_byte_identical(
    configured: Database, shipped_config: LoadedConfig, tmp_path: Path
) -> None:
    sqlite_scan(configured, shipped_config, ALL)
    first = write_runs_export(configured, tmp_path / "a" / "runs.json")
    second = write_runs_export(configured, tmp_path / "b" / "runs.json")
    assert first.read_bytes() == second.read_bytes()
    text = first.read_text(encoding="utf-8")
    assert text.endswith("}\n")
    assert text == json.dumps(json.loads(text), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def test_an_export_carries_funnel_requests_status_and_disciplines(
    configured: Database, shipped_config: LoadedConfig
) -> None:
    result = sqlite_scan(configured, shipped_config, ALL)
    [run] = export_runs(configured)["runs"]
    assert run["run_id"] == result.run.id
    assert run["status"] == "complete"
    assert run["started_at"] == "2026-10-06T02:15:42.000000Z"
    assert run["requests_made"] == 150
    assert run["request_budget"] == 150
    assert run["budget_exhausted"] is True
    assert len(run["notes"]) == 1
    assert run["funnel"] == {
        "raw": result.run.funnel.raw,
        "dropped_own": result.run.funnel.dropped_own,
        "dropped_negative": result.run.funnel.dropped_negative,
        "dropped_unrelated": result.run.funnel.dropped_unrelated,
        "passed": result.run.funnel.passed,
        "unique": result.run.funnel.unique,
        "seen_before": result.run.funnel.seen_before,
        "new": result.run.funnel.new,
        "reinforcements": result.run.funnel.reinforcements,
    }
    assert run["disciplines"] == [d.value for d in result.run.disciplines]
    per = run["per_discipline"]
    assert set(per) == {d.value for d in result.run.disciplines}
    assert sum(p["candidates"] for p in per.values()) == result.run.funnel.unique
    assert sum(p["sightings"] for p in per.values()) == result.run.funnel.passed
    feeds = [c for c in result.candidates if c.discipline is Discipline.OSINT_FEED]
    assert per["osint_feed"]["candidates"] == len(feeds)


def test_an_export_after_one_more_run_differs_only_by_that_run(
    configured: Database, shipped_config: LoadedConfig
) -> None:
    sqlite_scan(configured, shipped_config, suffix="aaaa")
    before = export_runs(configured)
    later = sqlite_scan(configured, shipped_config, clock=LATER, suffix="bbbb")
    after = export_runs(configured)
    assert dumps_export(before) != dumps_export(after)
    kept = [run for run in after["runs"] if run["run_id"] != later.run.id]
    assert dumps_export({**after, "runs": kept}) == dumps_export(before)
    [new] = [run for run in after["runs"] if run["run_id"] == later.run.id]
    assert new["funnel"]["seen_before"] == new["funnel"]["unique"]
    assert [run["run_id"] for run in after["runs"]] == sorted(
        run["run_id"] for run in after["runs"]
    )
