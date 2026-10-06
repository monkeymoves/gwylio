"""``Settings``: one place for the root, the data and config directories and the database."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from gwylio.infrastructure.config.settings import (
    CONFIG_DIR_ENV_VAR,
    DATA_DIR_ENV_VAR,
    DB_PATH_ENV_VAR,
    Settings,
)
from tests.support import PROJECT_ROOT


def test_defaults_sit_under_the_project_root() -> None:
    settings = Settings.load(PROJECT_ROOT, environ={})
    assert settings.root == PROJECT_ROOT
    assert settings.data_dir == PROJECT_ROOT / "data"
    assert settings.config_dir == PROJECT_ROOT / "config"
    assert settings.config_root == PROJECT_ROOT
    assert settings.db_path == PROJECT_ROOT / "data" / "gwylio.sqlite"
    assert settings.candidates_dir == PROJECT_ROOT / "data" / "candidates"
    assert settings.instruments_dir == PROJECT_ROOT / "data" / "instruments"
    assert settings.runs_export_path == PROJECT_ROOT / "data" / "exports" / "runs.json"
    assert settings.fake_hits_path == PROJECT_ROOT / "backend/tests/fixtures/fake_hits.json"


def test_environment_variables_override_relative_to_the_root(tmp_path: Path) -> None:
    settings = Settings.load(
        tmp_path,
        environ={DATA_DIR_ENV_VAR: "scratch/data", CONFIG_DIR_ENV_VAR: str(tmp_path / "x/config")},
    )
    assert settings.data_dir == tmp_path / "scratch" / "data"
    assert settings.db_path == tmp_path / "scratch" / "data" / "gwylio.sqlite"
    assert settings.config_root == tmp_path / "x"
    explicit = Settings.load(tmp_path, environ={DB_PATH_ENV_VAR: "elsewhere.sqlite"})
    assert explicit.db_path == tmp_path / "elsewhere.sqlite"
    assert explicit.data_dir == tmp_path / "data"
    blank = Settings.load(tmp_path, environ={DATA_DIR_ENV_VAR: "  "})
    assert blank.data_dir == tmp_path / "data"


def test_another_data_directory_takes_the_database_with_it(tmp_path: Path) -> None:
    moved = Settings.load(PROJECT_ROOT, environ={}).with_data_dir(tmp_path / "run")
    assert moved.data_dir == tmp_path / "run"
    assert moved.db_path == tmp_path / "run" / "gwylio.sqlite"
    assert moved.root == PROJECT_ROOT


def test_the_configuration_directory_must_be_called_config(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="must be named 'config'"):
        Settings.load(tmp_path, environ={CONFIG_DIR_ENV_VAR: "settings"})


def test_the_root_is_found_when_not_given(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GWYLIO_ROOT", str(PROJECT_ROOT))
    assert Settings.load(environ={}).root == PROJECT_ROOT
