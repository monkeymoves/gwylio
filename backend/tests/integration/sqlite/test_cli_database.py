"""``gwylio migrate``, ``collect --fake``, ``export`` and ``rebuild`` through the Typer app."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gwylio.cli.main import app
from gwylio.infrastructure.config.settings import (
    CONFIG_DIR_ENV_VAR,
    DATA_DIR_ENV_VAR,
    DB_PATH_ENV_VAR,
)
from gwylio.infrastructure.handoff.candidates_file import read_candidates_file
from gwylio.infrastructure.handoff.instrument_file import read_instrument_file
from gwylio.infrastructure.sqlite.db import Database
from gwylio.infrastructure.sqlite.repositories import SqliteScanRunRepository
from tests.support import PROJECT_ROOT

pytestmark = pytest.mark.integration

runner = CliRunner()
ROOT = ["--root", str(PROJECT_ROOT)]


@pytest.fixture
def env(tmp_path: Path) -> dict[str, str]:
    """Point every command at a scratch data directory, never the real one."""
    return {DATA_DIR_ENV_VAR: str(tmp_path / "data")}


def test_migrate_creates_then_reports_up_to_date(tmp_path: Path, env: dict[str, str]) -> None:
    first = runner.invoke(app, ["migrate", *ROOT], env=env)
    assert first.exit_code == 0, first.output
    db_path = tmp_path / "data" / "gwylio.sqlite"
    assert first.stdout.splitlines() == [
        "applied 0001_init.sql",
        f"migrated {db_path}: 1 migration",
    ]
    again = runner.invoke(app, ["migrate", *ROOT], env=env)
    assert again.stdout.strip() == f"{db_path} is up to date: 1 migration"


def test_collect_fake_stores_the_run_and_writes_its_files(
    tmp_path: Path, env: dict[str, str]
) -> None:
    result = runner.invoke(app, ["collect", "--fake", *ROOT], env=env)
    assert result.exit_code == 0, result.output
    data = tmp_path / "data"
    [path] = list((data / "candidates").iterdir())
    document = read_candidates_file(path)
    assert document.run_status == "complete"
    assert document.funnel.unique == 17
    lines = result.stdout.splitlines()
    assert lines[:3] == [
        f"wrote  {path}",
        f"stored run {document.run_id} in {data / 'gwylio.sqlite'}",
        f"wrote  {data / 'exports' / 'runs.json'}",
    ]
    assert lines[3].startswith(f"Funnel for run {document.run_id}")
    archived = read_instrument_file(data / "instruments" / f"{document.instrument_version}.json")
    assert archived.content_hash == document.instrument_hash
    with Database.open(data / "gwylio.sqlite") as db:
        [run] = SqliteScanRunRepository(db).all()
    assert run.id == document.run_id
    export = json.loads((data / "exports" / "runs.json").read_text(encoding="utf-8"))
    assert [r["run_id"] for r in export["runs"]] == [run.id]


def test_collect_fake_honours_out_dir(tmp_path: Path, env: dict[str, str]) -> None:
    out = tmp_path / "elsewhere"
    result = runner.invoke(app, ["collect", "--fake", "--out-dir", str(out), *ROOT], env=env)
    assert result.exit_code == 0, result.output
    assert (out / "gwylio.sqlite").is_file()
    assert len(list((out / "candidates").iterdir())) == 1
    assert not (tmp_path / "data").exists()


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--fake", "--dry-run"], "not both"),
        (["--fake", "--out", "x.json"], "--out goes with --dry-run"),
        (["--dry-run", "--out-dir", "x"], "--out-dir goes with a stored run, not --dry-run"),
        (["--fake", "--discipline", "sensor"], "no collector serves sensor"),
    ],
)
def test_collect_refuses_flag_combinations(
    args: list[str], message: str, env: dict[str, str], tmp_path: Path
) -> None:
    result = runner.invoke(app, ["collect", *args, *ROOT], env=env)
    assert result.exit_code == 2
    assert message in result.stderr
    assert not (tmp_path / "data").exists()


def test_collect_fake_refuses_when_a_stored_source_leaves_config(
    project_copy: Path, tmp_path: Path, env: dict[str, str]
) -> None:
    shutil.copytree(PROJECT_ROOT / "backend" / "tests", project_copy / "backend" / "tests")
    root = ["--root", str(project_copy)]
    assert runner.invoke(app, ["collect", "--fake", *root], env=env).exit_code == 0
    path = project_copy / "config" / "sources.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["sources"] = [s for s in data["sources"] if s["id"] != "bto"]
    instrument = json.loads((project_copy / "config" / "instrument.json").read_text("utf-8"))
    assert all("bto" not in q.get("site_source_ids", []) for q in instrument["queries"])
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    result = runner.invoke(app, ["collect", "--fake", *root], env=env)
    assert result.exit_code == 1, result.output
    assert "retire sources rather than removing them" in result.stderr
    assert len(list((tmp_path / "data" / "candidates").iterdir())) == 1


def test_export_needs_a_database_then_writes_runs_json(tmp_path: Path, env: dict[str, str]) -> None:
    missing = runner.invoke(app, ["export", *ROOT], env=env)
    assert missing.exit_code == 1
    assert "no database at" in missing.stderr
    assert runner.invoke(app, ["collect", "--fake", *ROOT], env=env).exit_code == 0
    export = tmp_path / "data" / "exports" / "runs.json"
    before = export.read_bytes()
    export.unlink()
    result = runner.invoke(app, ["export", *ROOT], env=env)
    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == f"wrote  {export}"
    assert export.read_bytes() == before


def test_export_refuses_an_unmigrated_database(tmp_path: Path, env: dict[str, str]) -> None:
    Database.open(tmp_path / "data" / "gwylio.sqlite").close()
    result = runner.invoke(app, ["export", *ROOT], env=env)
    assert result.exit_code == 1
    assert "needs 1 more migration" in result.stderr


def test_rebuild_prints_the_summary_and_reports_failure(
    tmp_path: Path, env: dict[str, str]
) -> None:
    assert runner.invoke(app, ["collect", "--fake", *ROOT], env=env).exit_code == 0
    result = runner.invoke(app, ["rebuild", *ROOT], env=env)
    assert result.exit_code == 0, result.output
    lines = result.stdout.splitlines()
    assert lines[1] == "replayed 1 candidates file and 1 archived instrument"
    assert "  scan_run                            1" in lines
    assert "  candidate                          17" in lines
    (tmp_path / "data" / "candidates" / "20261006T0000Z-0000.json").write_text("{", "utf-8")
    failed = runner.invoke(app, ["rebuild", *ROOT], env=env)
    assert failed.exit_code == 1
    assert "not a valid candidates file" in failed.stderr
    assert "nothing replaced" in failed.stderr


def test_a_config_directory_with_another_name_exits_2(env: dict[str, str]) -> None:
    result = runner.invoke(app, ["rebuild", *ROOT], env=env | {CONFIG_DIR_ENV_VAR: "settings"})
    assert result.exit_code == 2
    assert "must be named 'config'" in result.stderr


def test_db_path_can_point_outside_the_data_directory(tmp_path: Path, env: dict[str, str]) -> None:
    db_path = tmp_path / "other" / "g.sqlite"
    result = runner.invoke(app, ["migrate", *ROOT], env=env | {DB_PATH_ENV_VAR: str(db_path)})
    assert result.exit_code == 0, result.output
    assert db_path.is_file()
