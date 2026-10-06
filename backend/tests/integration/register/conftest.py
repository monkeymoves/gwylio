"""Fixtures for the register tests: a scratch data directory driven through the CLI."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner, Result

from gwylio.cli.main import app
from gwylio.infrastructure.config.settings import (
    ACADEMIC_ENV_VAR,
    DATA_DIR_ENV_VAR,
    DB_PATH_ENV_VAR,
)
from tests.support import PROJECT_ROOT

SEED_SUBMISSIONS = PROJECT_ROOT / "backend" / "tests" / "fixtures" / "seed_submissions"
FIRST = "20260901T0900Z-0000"
SECOND = "20261001T0900Z-0000"

Cli = Callable[..., Result]


@pytest.fixture
def data(tmp_path: Path) -> Path:
    return tmp_path / "data"


@pytest.fixture
def cli(data: Path) -> Cli:
    """Run a gwylio verb against the scratch data directory; extra env as keyword arguments."""
    runner = CliRunner()

    def invoke(*args: str, **env: str) -> Result:
        environment = {DATA_DIR_ENV_VAR: str(data), DB_PATH_ENV_VAR: "", ACADEMIC_ENV_VAR: ""}
        environment.update(env)
        return runner.invoke(app, [*args, "--root", str(PROJECT_ROOT)], env=environment)

    return invoke


@pytest.fixture
def first_run(cli: Cli) -> Cli:
    """The data directory after the seed's first pinned fake run."""
    result = cli("collect", "--fake", "--at", "2026-09-01T09:00:00+0000")
    assert result.exit_code == 0, result.output
    return cli


def seed_document(name: str = f"{FIRST}__1.json") -> dict[str, Any]:
    document: dict[str, Any] = json.loads((SEED_SUBMISSIONS / name).read_text(encoding="utf-8"))
    return document


def write(path: Path, document: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def register(data: Path) -> dict[str, dict[str, Any]]:
    export = json.loads((data / "exports" / "register.json").read_text(encoding="utf-8"))
    return {report["id"]: report for report in export["reports"]}


def copy_seed(target: Path) -> None:
    shutil.copytree(SEED_SUBMISSIONS, target)
