"""Where Gwylio keeps its files: one ``Settings`` object every command reads.

Settings come from environment variables prefixed ``GWYLIO_``, with defaults
relative to the project root:

- ``GWYLIO_ROOT``: the project root (otherwise found from the current directory).
- ``GWYLIO_DATA_DIR``: the data directory, default ``data``.
- ``GWYLIO_CONFIG_DIR``: the configuration directory, default ``config``. The
  loaders read ``<parent>/config/...``, so the directory must be named ``config``.
- ``GWYLIO_DB_PATH``: the SQLite database, default ``<data_dir>/gwylio.sqlite``.

Relative paths are taken from the project root. Nothing here reads a file.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, model_validator

from gwylio.infrastructure.config import paths
from gwylio.infrastructure.config.paths import find_project_root

__all__ = [
    "CANDIDATES_SUBDIR",
    "CONFIG_DIR_ENV_VAR",
    "DATA_DIR_ENV_VAR",
    "DB_FILE",
    "DB_PATH_ENV_VAR",
    "EXPORTS_SUBDIR",
    "INSTRUMENTS_SUBDIR",
    "RUNS_EXPORT_FILE",
    "Settings",
]

DATA_DIR_ENV_VAR: Final[str] = "GWYLIO_DATA_DIR"
CONFIG_DIR_ENV_VAR: Final[str] = "GWYLIO_CONFIG_DIR"
DB_PATH_ENV_VAR: Final[str] = "GWYLIO_DB_PATH"

DEFAULT_DATA_DIR: Final[str] = "data"
DB_FILE: Final[str] = "gwylio.sqlite"
CANDIDATES_SUBDIR: Final[str] = "candidates"
"""Under the data directory: ``<run_id>.json`` per scan run, append-only facts."""
INSTRUMENTS_SUBDIR: Final[str] = "instruments"
"""Under the data directory: ``<version>.json``, every instrument version a run used."""
EXPORTS_SUBDIR: Final[str] = "exports"
"""Under the data directory: derived, deterministic exports such as ``runs.json``."""
RUNS_EXPORT_FILE: Final[str] = "runs.json"


def _resolve(value: str | None, root: Path, default: Path) -> Path:
    if value is None or not value.strip():
        return default
    path = Path(value).expanduser()
    return (path if path.is_absolute() else root / path).resolve()


class Settings(BaseModel):
    """The project root and the directories and database every command uses."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    root: Path
    data_dir: Path
    config_dir: Path
    db_path: Path

    @model_validator(mode="after")
    def _config_dir_named_config(self) -> Settings:
        if self.config_dir.name != paths.CONFIG_DIR:
            raise ValueError(
                f"the configuration directory must be named '{paths.CONFIG_DIR}', "
                f"got {self.config_dir}"
            )
        return self

    @classmethod
    def load(cls, root: Path | None = None, environ: Mapping[str, str] | None = None) -> Settings:
        """Settings from ``environ`` (default: the process environment) under ``root``.

        ``root`` defaults to ``find_project_root()``, which honours ``GWYLIO_ROOT``.
        """
        env = os.environ if environ is None else environ
        base = (root if root is not None else find_project_root()).resolve()
        data_dir = _resolve(env.get(DATA_DIR_ENV_VAR), base, base / DEFAULT_DATA_DIR)
        config_dir = _resolve(env.get(CONFIG_DIR_ENV_VAR), base, base / paths.CONFIG_DIR)
        db_path = _resolve(env.get(DB_PATH_ENV_VAR), base, data_dir / DB_FILE)
        return cls(root=base, data_dir=data_dir, config_dir=config_dir, db_path=db_path)

    def with_data_dir(self, data_dir: Path) -> Settings:
        """These settings with another data directory and the database inside it."""
        moved = data_dir.resolve()
        return self.model_copy(update={"data_dir": moved, "db_path": moved / DB_FILE})

    @property
    def config_root(self) -> Path:
        """The directory holding ``config/``: what the configuration loaders read from."""
        return self.config_dir.parent

    @property
    def candidates_dir(self) -> Path:
        """``<data_dir>/candidates``."""
        return self.data_dir / CANDIDATES_SUBDIR

    @property
    def instruments_dir(self) -> Path:
        """``<data_dir>/instruments``."""
        return self.data_dir / INSTRUMENTS_SUBDIR

    @property
    def exports_dir(self) -> Path:
        """``<data_dir>/exports``."""
        return self.data_dir / EXPORTS_SUBDIR

    @property
    def runs_export_path(self) -> Path:
        """``<data_dir>/exports/runs.json``."""
        return self.exports_dir / RUNS_EXPORT_FILE

    @property
    def fake_hits_path(self) -> Path:
        """The scripted hits the fake collectors replay."""
        return self.root / paths.FAKE_HITS_FILE
