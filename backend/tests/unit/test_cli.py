"""Tests for the Typer command line application."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gwylio.cli.main import app, cli_verbs, package_version
from gwylio.infrastructure.codegen.generate import GLOSSARY_PATH, TYPESCRIPT_PATH
from gwylio.infrastructure.config.paths import ROOT_ENV_VAR, find_project_root
from tests.support import PROJECT_ROOT

runner = CliRunner()


def test_version_prints_the_package_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == package_version()
    assert package_version() == "0.1.0"


def test_help_lists_every_verb() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for verb in (
        "version",
        "check",
        "schema",
        "collect",
        "probe",
        "migrate",
        "export",
        "rebuild",
        "ingest",
        "sweep",
        "datecheck",
        "import-legacy",
        "audit",
        "yield",
        "product",
    ):
        assert verb in result.stdout


def test_cli_verbs_are_sorted_with_help() -> None:
    verbs = cli_verbs()
    assert [name for name, _ in verbs] == [
        "audit",
        "check",
        "collect",
        "datecheck",
        "export",
        "import-legacy",
        "ingest",
        "migrate",
        "probe",
        "product",
        "rebuild",
        "schema",
        "sweep",
        "version",
        "yield",
    ]
    assert all(help_text for _, help_text in verbs)


def test_check_passes_on_the_shipped_config() -> None:
    result = runner.invoke(app, ["check", "--root", str(PROJECT_ROOT)])
    assert result.exit_code == 0, result.output
    lines = result.stdout.splitlines()
    assert lines[0] == (
        "ok     config/taxonomy.json: 2 axes, 22 nodes (sonarr-ecosystems 11, hazard-families 11)"
    )
    assert "ok     config/lanes.json: 10 lanes" in lines
    assert (
        "ok     config/requirement_sets/nrw-corporate-plan.json: 12 requirements, "
        "9 groups (6 impact, 3 wbo)"
    ) in lines
    assert "ok     config/sources.json: 43 sources (41 active, 2 parked)" in lines
    assert "ok     config/gating.json: 4 own domains, 25 relevance tokens" in lines
    assert (
        "ok     config/datecheck.json: 10 future-framed phrases, verification stale after 45 days"
        in lines
    )
    assert lines[-1] == "check passed: 12 configuration files valid"


@pytest.mark.integration
def test_check_fails_with_file_and_path_on_a_dash(project_copy: Path) -> None:
    path = project_copy / "config/reference/topics.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["topics"][0]["note"] = "Nature " + chr(0x2013) + " and ecosystems"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    result = runner.invoke(app, ["check", "--root", str(project_copy)])
    assert result.exit_code == 1
    assert "error  config/reference/topics.json: topics[0].note: Value error" in result.stderr
    assert "U+2013 EN DASH" in result.stderr
    assert "note   reference cross-checks skipped" in result.stderr
    assert result.stderr.strip().endswith("check failed: 1 problem")


@pytest.mark.integration
def test_check_finds_the_root_from_the_environment(
    project_copy: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ROOT_ENV_VAR, str(project_copy))
    result = runner.invoke(app, ["check"])
    assert result.exit_code == 0, result.output


def test_bad_root_environment_variable_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ROOT_ENV_VAR, str(tmp_path))
    result = runner.invoke(app, ["check"])
    assert result.exit_code == 2
    assert "not a Gwylio project root" in result.stderr


def test_find_project_root_walks_up(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ROOT_ENV_VAR, raising=False)
    assert find_project_root(PROJECT_ROOT / "backend" / "src") == PROJECT_ROOT


def test_schema_check_passes_on_the_committed_files() -> None:
    result = runner.invoke(app, ["schema", "--check", "--root", str(PROJECT_ROOT)])
    assert result.exit_code == 0, result.output
    assert "up to date" in result.stdout


@pytest.mark.integration
def test_schema_writes_then_reports_nothing_changed(project_copy: Path) -> None:
    first = runner.invoke(app, ["schema", "--root", str(project_copy)])
    assert first.exit_code == 0, first.output
    assert f"wrote  {GLOSSARY_PATH}" in first.stdout
    assert (project_copy / TYPESCRIPT_PATH).is_file()
    for relative in (GLOSSARY_PATH, TYPESCRIPT_PATH):
        assert (project_copy / relative).read_bytes() == (PROJECT_ROOT / relative).read_bytes()
    again = runner.invoke(app, ["schema", "--root", str(project_copy)])
    assert again.stdout.strip().endswith("0 changed")


@pytest.mark.integration
def test_schema_check_reports_drift_and_removes_stale_files(project_copy: Path) -> None:
    shutil.copytree(PROJECT_ROOT / "docs" / "schema", project_copy / "docs" / "schema")
    (project_copy / "docs/schema/old.schema.json").write_text("{}\n", encoding="utf-8")
    drift = runner.invoke(app, ["schema", "--check", "--root", str(project_copy)])
    assert drift.exit_code == 1
    assert "extra  docs/schema/old.schema.json" in drift.stdout
    assert f"stale  {GLOSSARY_PATH}" in drift.stdout
    fixed = runner.invoke(app, ["schema", "--root", str(project_copy)])
    assert "removed docs/schema/old.schema.json" in fixed.stdout
    assert runner.invoke(app, ["schema", "--check", "--root", str(project_copy)]).exit_code == 0


@pytest.mark.integration
def test_schema_refuses_to_generate_from_invalid_config(project_copy: Path) -> None:
    (project_copy / "config/lanes.json").write_text("[]", encoding="utf-8")
    result = runner.invoke(app, ["schema", "--root", str(project_copy)])
    assert result.exit_code == 1
    assert "configuration is invalid" in result.stderr
