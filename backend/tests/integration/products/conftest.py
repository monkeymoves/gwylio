"""Fixtures for the product and evaluation tests: scratch data directories driven by the CLI."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from gwylio.cli.main import app
from gwylio.infrastructure.config.settings import (
    ACADEMIC_ENV_VAR,
    DATA_DIR_ENV_VAR,
    DB_PATH_ENV_VAR,
)
from tests.support import PROJECT_ROOT

SEED = PROJECT_ROOT / "backend" / "tests" / "fixtures" / "seed"
LEGACY = Path("/home/user/NRW-Scan-Tool/data/signals.json")
TODAY = "2026-10-06"

Cli = Callable[..., Result]


@pytest.fixture
def data(tmp_path: Path) -> Path:
    return tmp_path / "data"


@pytest.fixture
def cli(data: Path) -> Cli:
    """Run a gwylio verb against the scratch data directory."""
    runner = CliRunner()

    def invoke(*args: str) -> Result:
        environment = {DATA_DIR_ENV_VAR: str(data), DB_PATH_ENV_VAR: "", ACADEMIC_ENV_VAR: ""}
        return runner.invoke(app, [*args, "--root", str(PROJECT_ROOT)], env=environment)

    return invoke


@pytest.fixture
def seeded(cli: Cli, data: Path) -> Cli:
    """The data directory holding the committed seed's facts, rebuilt into a database."""
    for folder in ("candidates", "instruments", "submissions"):
        shutil.copytree(SEED / folder, data / folder)
    result = cli("rebuild")
    assert result.exit_code == 0, result.output
    return cli


@pytest.fixture
def legacy(cli: Cli) -> Cli:
    """The data directory after importing the old register, or a skip when it is absent."""
    if not LEGACY.is_file():
        pytest.skip(f"the old register is not at {LEGACY}")
    result = cli("import-legacy", str(LEGACY))
    assert result.exit_code == 0, result.output
    return cli
