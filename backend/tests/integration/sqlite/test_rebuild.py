"""Rebuild equivalence: the database rebuilt from the files equals the one the scans wrote."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gwylio.cli.collect import ACADEMIC_ENV_VAR
from gwylio.cli.main import app
from gwylio.collection.model import ScanRun
from gwylio.collection.service import RunResult
from gwylio.infrastructure.config.loaders import LoadedConfig
from gwylio.infrastructure.config.settings import DATA_DIR_ENV_VAR, DB_PATH_ENV_VAR
from gwylio.infrastructure.handoff.candidates_file import (
    candidates_document,
    read_candidates_file,
    result_from_document,
    write_candidates_file,
)
from gwylio.infrastructure.handoff.instrument_file import archive_instrument
from gwylio.infrastructure.memory import StaticKnownReports
from gwylio.infrastructure.sqlite.db import Database
from gwylio.infrastructure.sqlite.migrate import migrate
from gwylio.infrastructure.sqlite.rebuild import RebuildError, rebuild, rebuild_into
from gwylio.infrastructure.sqlite.repositories import (
    SqliteCandidateRepository,
    SqliteInstrumentRepository,
    SqliteScanRunRepository,
    dump_table,
    save_config,
)
from gwylio.processing.candidates_file import dumps_candidates
from gwylio.shared.clock import FixedClock
from gwylio.shared.values import CleanText, RunId
from tests.support import ALL, PROJECT_ROOT, sqlite_scan

pytestmark = pytest.mark.integration

runner = CliRunner()
CONFIG_DIR = PROJECT_ROOT / "config"
DROUGHT = "nation.cymru/news/drought-declared-across-south-west-wales"


def assert_equivalent(a: Database, b: Database) -> None:
    """Every table holds the same rows; migrations match apart from when they ran."""
    assert a.table_names() == b.table_names()
    for table in a.table_names():
        if table == "schema_migrations":
            query = "SELECT version, name FROM schema_migrations ORDER BY version"
            assert [tuple(r) for r in a.fetch_all(query)] == [tuple(r) for r in b.fetch_all(query)]
        else:
            assert dump_table(a, table) == dump_table(b, table), f"table {table} differs"


def persist(db: Database, data_dir: Path, result: RunResult, config: LoadedConfig) -> Path:
    """Write the files a stored scan leaves behind: the archived instrument and the run."""
    archive_instrument(config.instrument, data_dir / "instruments")
    return write_candidates_file(result, data_dir / "candidates" / f"{result.run.id}.json")


def stored_result(db: Database, run_id: str, warnings: tuple[CleanText, ...]) -> RunResult:
    run = SqliteScanRunRepository(db).get(run_id)
    assert run is not None
    candidates = SqliteCandidateRepository(db)
    return RunResult(
        run,
        candidates.candidates_for_run(run_id),
        candidates.sightings_for_run(run_id),
        candidates.reinforcements_for_run(run_id),
        warnings,
    )


def test_collect_fake_then_rebuild_gives_an_equivalent_database(tmp_path: Path) -> None:
    data = tmp_path / "data"
    root = ["--root", str(PROJECT_ROOT)]
    env = {DATA_DIR_ENV_VAR: str(data)}
    for extra in ({}, {}, {ACADEMIC_ENV_VAR: "1"}):
        collected = runner.invoke(app, ["collect", "--fake", *root], env=env | extra)
        assert collected.exit_code == 0, collected.output
    rebuilt_path = tmp_path / "b" / "gwylio.sqlite"
    rebuilt = runner.invoke(app, ["rebuild", *root], env=env | {DB_PATH_ENV_VAR: str(rebuilt_path)})
    assert rebuilt.exit_code == 0, rebuilt.output
    assert "replayed 3 candidates files and 1 archived instrument" in rebuilt.stdout
    documents = [read_candidates_file(p) for p in sorted((data / "candidates").iterdir())]
    with Database.open(data / "gwylio.sqlite") as a, Database.open(rebuilt_path) as b:
        for table, rows in (
            ("scan_run", 3),
            ("candidate", sum(len(d.candidates) for d in documents)),
            ("sighting", sum(len(d.sightings) for d in documents)),
        ):
            assert len(dump_table(a, table)) == rows > 0, table
        assert_equivalent(a, b)
        runs = SqliteScanRunRepository(a).all()
        assert [run.funnel.seen_before for run in runs][:2] == [0, 17]
        assert runs[2].budget_exhausted
    assert sorted(p.name for p in (data / "candidates").iterdir()) == sorted(
        f"{run.id}.json" for run in runs
    )


def test_a_rebuild_replays_reinforcements_and_an_aborted_run(
    configured: Database, shipped_config: LoadedConfig, tmp_path: Path
) -> None:
    data = tmp_path / "data"
    aborted_run = ScanRun.start(
        RunId("20261005T2300Z-dead"),
        datetime(2026, 10, 5, 23, 0, tzinfo=UTC),
        shipped_config.instrument,
        ALL,
    ).add_hits(4, 2)
    aborted_run = aborted_run.abort(
        datetime(2026, 10, 5, 23, 1, tzinfo=UTC), CleanText("aborted: ConnectionError: down")
    )
    with configured.transaction():
        SqliteInstrumentRepository(configured).add(shipped_config.instrument)
        SqliteScanRunRepository(configured).add(aborted_run)
    persist(configured, data, RunResult(aborted_run, (), (), ()), shipped_config)
    known = StaticKnownReports(by_url={DROUGHT: "drought-2026"})
    result = sqlite_scan(configured, shipped_config, ALL, known=known)
    persist(configured, data, result, shipped_config)
    assert result.reinforcements

    fresh = Database.memory()
    summary = rebuild_into(fresh, data, CONFIG_DIR)
    assert summary.candidates_files == 2
    assert summary.instrument_files == 1
    assert summary.counts["reinforcement"] == 1
    assert_equivalent(configured, fresh)
    assert SqliteScanRunRepository(fresh).get(aborted_run.id) == aborted_run


def test_write_read_rebuild_round_trips_the_run_and_the_file_text(
    configured: Database, shipped_config: LoadedConfig, tmp_path: Path
) -> None:
    known = StaticKnownReports(by_url={DROUGHT: "drought-2026"})
    result = sqlite_scan(configured, shipped_config, ALL, known=known)
    path = persist(configured, tmp_path, result, shipped_config)
    text = path.read_text(encoding="utf-8")
    document = read_candidates_file(path)
    from_file = result_from_document(document)
    assert from_file == stored_result(configured, result.run.id, result.warnings)

    fresh = Database.memory()
    rebuild_into(fresh, tmp_path, CONFIG_DIR)
    from_rebuild = stored_result(fresh, result.run.id, from_file.warnings)
    assert from_rebuild == from_file
    assert dumps_candidates(candidates_document(from_rebuild)) == text


def test_runs_in_the_same_minute_replay_in_the_order_they_started(
    configured: Database, shipped_config: LoadedConfig, tmp_path: Path
) -> None:
    first = sqlite_scan(
        configured,
        shipped_config,
        clock=FixedClock(datetime(2026, 10, 6, 2, 15, 1, tzinfo=UTC)),
        suffix="ffff",
    )
    second = sqlite_scan(
        configured,
        shipped_config,
        clock=FixedClock(datetime(2026, 10, 6, 2, 15, 59, tzinfo=UTC)),
        suffix="0000",
    )
    assert second.run.id < first.run.id
    assert {c.first_seen_run_id for c in second.candidates} == {first.run.id}
    persist(configured, tmp_path, first, shipped_config)
    persist(configured, tmp_path, second, shipped_config)
    fresh = Database.memory()
    rebuild_into(fresh, tmp_path, CONFIG_DIR)
    assert_equivalent(configured, fresh)


def test_a_failed_rebuild_leaves_the_old_database_alone(
    shipped_config: LoadedConfig, tmp_path: Path
) -> None:
    db_path = tmp_path / "data" / "gwylio.sqlite"
    with Database.open(db_path) as old:
        migrate(old)
        save_config(old, shipped_config)
    before = db_path.read_bytes()
    broken = tmp_path / "data" / "candidates" / "20261006T0215Z-3f9a.json"
    broken.parent.mkdir(parents=True)
    broken.write_text("{}", encoding="utf-8")
    with pytest.raises(RebuildError, match="not a valid candidates file"):
        rebuild(tmp_path / "data", CONFIG_DIR, db_path)
    assert db_path.read_bytes() == before
    assert sorted(p.name for p in db_path.parent.iterdir()) == ["candidates", "gwylio.sqlite"]


def test_a_rebuild_needs_the_instrument_a_run_used(
    configured: Database, shipped_config: LoadedConfig, tmp_path: Path
) -> None:
    result = sqlite_scan(configured, shipped_config)
    path = write_candidates_file(result, tmp_path / "candidates" / f"{result.run.id}.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["instrument_version"] = "2026.9.0"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(RebuildError, match="neither archived under instruments/"):
        rebuild_into(Database.memory(), tmp_path, CONFIG_DIR)


def test_a_file_must_be_named_for_its_run(
    configured: Database, shipped_config: LoadedConfig, tmp_path: Path
) -> None:
    result = sqlite_scan(configured, shipped_config)
    write_candidates_file(result, tmp_path / "candidates" / "20261006T0215Z-0000.json")
    with pytest.raises(RebuildError, match="holds run 20261006T0215Z-3f9a"):
        rebuild_into(Database.memory(), tmp_path, CONFIG_DIR)


def test_the_configuration_directory_must_be_called_config(tmp_path: Path) -> None:
    with pytest.raises(RebuildError, match="must be named 'config'"):
        rebuild_into(Database.memory(), tmp_path, tmp_path / "settings")
    with pytest.raises(RebuildError, match="no configuration directory"):
        rebuild_into(Database.memory(), tmp_path, tmp_path / "config")


def test_an_empty_data_directory_rebuilds_the_configuration_only(
    shipped_config: LoadedConfig, tmp_path: Path
) -> None:
    db_path = tmp_path / "gwylio.sqlite"
    summary = rebuild(tmp_path / "data", CONFIG_DIR, db_path)
    assert summary.candidates_files == 0
    assert summary.counts["scan_run"] == 0
    assert summary.counts["source"] == len(shipped_config.sources)
    assert summary.counts["instrument_version"] == 1
    assert summary.table()[0] == "replayed 0 candidates files and 0 archived instruments"
    assert [p.name for p in tmp_path.iterdir()] == ["gwylio.sqlite"]
    with Database.open(db_path) as db:
        stored = SqliteInstrumentRepository(db).get(shipped_config.instrument.version)
        assert stored == shipped_config.instrument
        assert SqliteScanRunRepository(db).all() == ()
