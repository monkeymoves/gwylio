"""Shared pytest fixtures for the whole backend suite."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from gwylio.shared.clock import FixedClock
from tests.support import PROJECT_ROOT

FIXED_INSTANT = datetime(2026, 7, 23, 9, 30, tzinfo=UTC)


@pytest.fixture
def fixed_clock() -> FixedClock:
    """A clock pinned to 23 July 2026, 09:30 UTC."""
    return FixedClock(FIXED_INSTANT)


@pytest.fixture
def project_copy(tmp_path: Path) -> Path:
    """A throwaway project root holding a copy of the shipped config/ directory.

    Tests mutate files under it freely. ``backend/pyproject.toml`` is a marker
    so ``find_project_root`` recognises the directory.
    """
    shutil.copytree(PROJECT_ROOT / "config", tmp_path / "config")
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    return tmp_path
