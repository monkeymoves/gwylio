"""Fixtures for the read API and snapshot tests: the seed, rebuilt in memory from its files.

The seed under ``backend/tests/fixtures/seed`` is replayed through ``rebuild``
into an in-memory database once per session, so no test depends on a
committed database file. The app and the publisher share that database, the
shipped configuration and one pinned clock, as the contract requires.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Final

import pytest
from fastapi.testclient import TestClient

from gwylio.api.app import create_app
from gwylio.infrastructure.config.loaders import LoadedConfig
from gwylio.infrastructure.config.settings import DATA_DIR_ENV_VAR, Settings
from gwylio.infrastructure.readmodels import ReadModels
from gwylio.infrastructure.sqlite.db import Database
from gwylio.infrastructure.sqlite.rebuild import rebuild_into
from gwylio.shared.clock import FixedClock
from tests.support import PROJECT_ROOT

SEED: Final = PROJECT_ROOT / "backend" / "tests" / "fixtures" / "seed"
CLOCK: Final = FixedClock(datetime(2026, 10, 6, 9, 0, tzinfo=UTC))
SET_ID: Final = "nrw-corporate-plan"


@pytest.fixture(scope="session")
def seed_settings() -> Settings:
    """Settings whose data directory is the seed (its database file is never opened)."""
    return Settings.load(PROJECT_ROOT, {DATA_DIR_ENV_VAR: str(SEED)})


@pytest.fixture(scope="session")
def seed_db() -> Iterator[Database]:
    """The seed replayed into memory; any thread may read it (the test client uses another)."""
    db = Database.memory(check_same_thread=False)
    rebuild_into(db, SEED, PROJECT_ROOT / "config")
    yield db
    db.close()


@pytest.fixture(scope="session")
def models(seed_db: Database, shipped_config: LoadedConfig, seed_settings: Settings) -> ReadModels:
    """The read models over the seed with the pinned clock."""
    return ReadModels(seed_db, shipped_config, clock=CLOCK, data_dir=seed_settings.data_dir)


@pytest.fixture(scope="session")
def client(seed_db: Database, seed_settings: Settings) -> Iterator[TestClient]:
    """The read API over the seed with the pinned clock."""
    with TestClient(create_app(seed_settings, clock=CLOCK, database=seed_db)) as test_client:
        yield test_client
