"""``Settings``: one place for the root, the data and config directories and the database."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from gwylio.infrastructure.config.settings import (
    ACADEMIC_ENV_VAR,
    CONFIG_DIR_ENV_VAR,
    CONTACT_EMAIL_ENV_VAR,
    DATA_DIR_ENV_VAR,
    DB_PATH_ENV_VAR,
    DEFAULT_CONTACT_EMAIL,
    SEARCH_KEYS_FILE,
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
    assert settings.register_export_path == PROJECT_ROOT / "data" / "exports" / "register.json"
    assert settings.submissions_dir == PROJECT_ROOT / "data" / "submissions"
    assert settings.sweeps_dir == PROJECT_ROOT / "data" / "sweeps"
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


def test_the_brave_key_comes_from_the_environment_then_the_keys_file(tmp_path: Path) -> None:
    assert Settings.load(tmp_path, environ={}).brave_api_key is None
    (tmp_path / SEARCH_KEYS_FILE).write_text(
        "# keys\nOTHER=1\nBRAVE_API_KEY = from-file\n", encoding="utf-8"
    )
    from_file = Settings.load(tmp_path, environ={})
    assert from_file.brave_api_key is not None
    assert from_file.brave_api_key.get_secret_value() == "from-file"
    plain = Settings.load(tmp_path, environ={"BRAVE_API_KEY": "plain"})
    assert plain.brave_api_key is not None
    assert plain.brave_api_key.get_secret_value() == "plain"
    ours = Settings.load(
        tmp_path, environ={"BRAVE_API_KEY": "plain", "GWYLIO_BRAVE_API_KEY": "ours"}
    )
    assert ours.brave_api_key is not None
    assert ours.brave_api_key.get_secret_value() == "ours"
    assert "ours" not in repr(ours)


def test_a_blank_key_and_an_unreadable_keys_file_mean_no_key(tmp_path: Path) -> None:
    (tmp_path / SEARCH_KEYS_FILE).mkdir()
    assert Settings.load(tmp_path, environ={"BRAVE_API_KEY": "  "}).brave_api_key is None


def test_the_academic_flag_and_the_contact_address(tmp_path: Path) -> None:
    default = Settings.load(tmp_path, environ={})
    assert default.academic_enabled is False
    assert default.contact_email == DEFAULT_CONTACT_EMAIL == "gwylio@example.invalid"
    assert default.with_academic().academic_enabled is True
    chosen = Settings.load(
        tmp_path,
        environ={ACADEMIC_ENV_VAR: "1", CONTACT_EMAIL_ENV_VAR: "luke@example.org"},
    )
    assert chosen.academic_enabled is True
    assert chosen.contact_email == "luke@example.org"
    assert Settings.load(tmp_path, environ={ACADEMIC_ENV_VAR: "yes"}).academic_enabled is False
    with pytest.raises(ValidationError, match="contact email"):
        Settings.load(tmp_path, environ={CONTACT_EMAIL_ENV_VAR: "not an address"})
