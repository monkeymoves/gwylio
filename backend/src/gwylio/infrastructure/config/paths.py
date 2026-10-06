"""Where the configuration files live, relative to the project root."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

__all__ = [
    "ACTORS_FILE",
    "CANDIDATES_DIR",
    "CONFIG_DIR",
    "DATECHECK_FILE",
    "FAKE_HITS_FILE",
    "GATING_FILE",
    "HAZARDS_FILE",
    "INSTRUMENT_FILE",
    "LANES_FILE",
    "PLACES_FILE",
    "REQUIREMENT_SETS_DIR",
    "ROOT_ENV_VAR",
    "SOURCES_FILE",
    "TAXONOMY_FILE",
    "TOPICS_FILE",
    "find_project_root",
]

CONFIG_DIR: Final[str] = "config"
TAXONOMY_FILE: Final[str] = "config/taxonomy.json"
LANES_FILE: Final[str] = "config/lanes.json"
TOPICS_FILE: Final[str] = "config/reference/topics.json"
HAZARDS_FILE: Final[str] = "config/reference/hazards.json"
PLACES_FILE: Final[str] = "config/reference/places.json"
ACTORS_FILE: Final[str] = "config/reference/actors.json"
REQUIREMENT_SETS_DIR: Final[str] = "config/requirement_sets"
SOURCES_FILE: Final[str] = "config/sources.json"
INSTRUMENT_FILE: Final[str] = "config/instrument.json"
GATING_FILE: Final[str] = "config/gating.json"
DATECHECK_FILE: Final[str] = "config/datecheck.json"
CANDIDATES_DIR: Final[str] = "data/candidates"
"""Where real scan runs write ``<run_id>.json``: append-only, committed facts."""
FAKE_HITS_FILE: Final[str] = "backend/tests/fixtures/fake_hits.json"
"""The scripted hits ``gwylio collect --dry-run`` and ``gwylio probe`` feed to fake collectors."""
ROOT_ENV_VAR: Final[str] = "GWYLIO_ROOT"
"""Environment variable that names the project root explicitly."""


def _is_root(path: Path) -> bool:
    return (path / CONFIG_DIR).is_dir() and (path / "backend" / "pyproject.toml").is_file()


def find_project_root(start: Path | None = None) -> Path:
    """The Gwylio project root: the directory holding ``config/`` and ``backend/``.

    Uses ``$GWYLIO_ROOT`` when set; otherwise walks up from ``start`` (the
    current directory by default), then falls back to the checkout this
    package was installed from. Raises ``FileNotFoundError`` when none fits.
    """
    explicit = os.environ.get(ROOT_ENV_VAR)
    if explicit:
        path = Path(explicit).resolve()
        if not _is_root(path):
            raise FileNotFoundError(f"${ROOT_ENV_VAR}={explicit} is not a Gwylio project root")
        return path
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if _is_root(candidate):
            return candidate
    installed = Path(__file__).resolve().parents[5]
    if _is_root(installed):
        return installed
    raise FileNotFoundError(
        f"no Gwylio project root (a directory with config/ and backend/) above {here}"
    )
