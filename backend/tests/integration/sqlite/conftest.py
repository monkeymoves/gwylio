"""Fixtures for the SQLite tests: a migrated in-memory database, with and without config."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from gwylio.infrastructure.config.loaders import LoadedConfig
from gwylio.infrastructure.sqlite.db import Database
from gwylio.infrastructure.sqlite.migrate import migrate
from gwylio.infrastructure.sqlite.repositories import save_config


@pytest.fixture
def db() -> Iterator[Database]:
    """A migrated, empty in-memory database."""
    database = Database.memory()
    migrate(database)
    yield database
    database.close()


@pytest.fixture
def configured(db: Database, shipped_config: LoadedConfig) -> Database:
    """The migrated database holding the shipped configuration (no instrument, no runs)."""
    save_config(db, shipped_config)
    return db
