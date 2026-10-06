"""Where Gwylio keeps its files: one ``Settings`` object every command reads.

Settings come from environment variables prefixed ``GWYLIO_``, with defaults
relative to the project root:

- ``GWYLIO_ROOT``: the project root (otherwise found from the current directory).
- ``GWYLIO_DATA_DIR``: the data directory, default ``data``.
- ``GWYLIO_CONFIG_DIR``: the configuration directory, default ``config``. The
  loaders read ``<parent>/config/...``, so the directory must be named ``config``.
- ``GWYLIO_DB_PATH``: the SQLite database, default ``<data_dir>/gwylio.sqlite``.
- ``GWYLIO_BRAVE_API_KEY``, then ``BRAVE_API_KEY``, then a ``BRAVE_API_KEY=``
  line in ``search_keys.txt`` at the project root (gitignored): the Brave
  Search API key. Without one the web and site collectors are absent.
- ``GWYLIO_ACADEMIC``: ``1`` switches the academic indexes on.
- ``GWYLIO_CONTACT_EMAIL``: the contact address in the User-Agent and the
  ``mailto`` the academic indexes ask for, default ``gwylio@example.invalid``.

Relative paths are taken from the project root. The only file read here is
the optional ``search_keys.txt``.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, SecretStr, model_validator

from gwylio.infrastructure.config import paths
from gwylio.infrastructure.config.paths import find_project_root

__all__ = [
    "ACADEMIC_ENV_VAR",
    "BRAVE_KEY_ENV_VARS",
    "CANDIDATES_SUBDIR",
    "CONFIG_DIR_ENV_VAR",
    "CONTACT_EMAIL_ENV_VAR",
    "DATA_DIR_ENV_VAR",
    "DB_FILE",
    "DB_PATH_ENV_VAR",
    "DEFAULT_CONTACT_EMAIL",
    "EXPORTS_SUBDIR",
    "INSTRUMENTS_SUBDIR",
    "PRODUCTS_EXPORT_FILE",
    "PRODUCTS_SUBDIR",
    "REGISTER_EXPORT_FILE",
    "RUNS_EXPORT_FILE",
    "SEARCH_KEYS_FILE",
    "SUBMISSIONS_SUBDIR",
    "SWEEPS_SUBDIR",
    "Settings",
]

DATA_DIR_ENV_VAR: Final[str] = "GWYLIO_DATA_DIR"
CONFIG_DIR_ENV_VAR: Final[str] = "GWYLIO_CONFIG_DIR"
DB_PATH_ENV_VAR: Final[str] = "GWYLIO_DB_PATH"
BRAVE_KEY_ENV_VARS: Final[tuple[str, ...]] = ("GWYLIO_BRAVE_API_KEY", "BRAVE_API_KEY")
"""Where the Brave Search API key is looked for, in order, before ``search_keys.txt``."""
ACADEMIC_ENV_VAR: Final[str] = "GWYLIO_ACADEMIC"
"""Set to 1 to switch the academic indexes on."""
CONTACT_EMAIL_ENV_VAR: Final[str] = "GWYLIO_CONTACT_EMAIL"
DEFAULT_CONTACT_EMAIL: Final[str] = "gwylio@example.invalid"
SEARCH_KEYS_FILE: Final[str] = "search_keys.txt"
"""At the project root, gitignored: ``BRAVE_API_KEY=<key>`` on a line of its own."""

DEFAULT_DATA_DIR: Final[str] = "data"
DB_FILE: Final[str] = "gwylio.sqlite"
CANDIDATES_SUBDIR: Final[str] = "candidates"
"""Under the data directory: ``<run_id>.json`` per scan run, append-only facts."""
INSTRUMENTS_SUBDIR: Final[str] = "instruments"
"""Under the data directory: ``<version>.json``, every instrument version a run used."""
EXPORTS_SUBDIR: Final[str] = "exports"
"""Under the data directory: derived, deterministic exports such as ``runs.json``."""
RUNS_EXPORT_FILE: Final[str] = "runs.json"
REGISTER_EXPORT_FILE: Final[str] = "register.json"
SUBMISSIONS_SUBDIR: Final[str] = "submissions"
"""Under the data directory: the analyst's submissions, append-only facts."""
SWEEPS_SUBDIR: Final[str] = "sweeps"
"""Under the data directory: ``<on>__<n>.json`` per sweep that faded anything."""
PRODUCTS_SUBDIR: Final[str] = "products"
"""Under the data directory: ``<level>_<period>.md`` and ``.json`` per rendered product."""
PRODUCTS_EXPORT_FILE: Final[str] = "products.json"


def _key_from_file(path: Path) -> str | None:
    """The ``BRAVE_API_KEY=`` value in a keys file, or ``None`` when absent or unreadable."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    for line in lines:
        name, sep, value = line.strip().partition("=")
        if sep and name.strip() == "BRAVE_API_KEY" and value.strip():
            return value.strip()
    return None


def _brave_key(env: Mapping[str, str], root: Path) -> SecretStr | None:
    for name in BRAVE_KEY_ENV_VARS:
        value = env.get(name, "").strip()
        if value:
            return SecretStr(value)
    from_file = _key_from_file(root / SEARCH_KEYS_FILE)
    return None if from_file is None else SecretStr(from_file)


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
    brave_api_key: SecretStr | None = None
    academic_enabled: bool = False
    contact_email: str = DEFAULT_CONTACT_EMAIL

    @model_validator(mode="after")
    def _config_dir_named_config(self) -> Settings:
        if self.config_dir.name != paths.CONFIG_DIR:
            raise ValueError(
                f"the configuration directory must be named '{paths.CONFIG_DIR}', "
                f"got {self.config_dir}"
            )
        return self

    @model_validator(mode="after")
    def _contact_is_an_address(self) -> Settings:
        email = self.contact_email
        if "@" not in email or any(char.isspace() for char in email):
            raise ValueError(f"the contact email must be an address such as a@b.org, got {email!r}")
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
        contact = env.get(CONTACT_EMAIL_ENV_VAR, "").strip() or DEFAULT_CONTACT_EMAIL
        return cls(
            root=base,
            data_dir=data_dir,
            config_dir=config_dir,
            db_path=db_path,
            brave_api_key=_brave_key(env, base),
            academic_enabled=env.get(ACADEMIC_ENV_VAR, "").strip() == "1",
            contact_email=contact,
        )

    def with_data_dir(self, data_dir: Path) -> Settings:
        """These settings with another data directory and the database inside it."""
        moved = data_dir.resolve()
        return self.model_copy(update={"data_dir": moved, "db_path": moved / DB_FILE})

    def with_academic(self) -> Settings:
        """These settings with the academic indexes switched on."""
        return self.model_copy(update={"academic_enabled": True})

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
    def register_export_path(self) -> Path:
        """``<data_dir>/exports/register.json``."""
        return self.exports_dir / REGISTER_EXPORT_FILE

    @property
    def submissions_dir(self) -> Path:
        """``<data_dir>/submissions``."""
        return self.data_dir / SUBMISSIONS_SUBDIR

    @property
    def sweeps_dir(self) -> Path:
        """``<data_dir>/sweeps``."""
        return self.data_dir / SWEEPS_SUBDIR

    @property
    def products_dir(self) -> Path:
        """``<data_dir>/products``."""
        return self.data_dir / PRODUCTS_SUBDIR

    @property
    def products_export_path(self) -> Path:
        """``<data_dir>/exports/products.json``."""
        return self.exports_dir / PRODUCTS_EXPORT_FILE

    @property
    def fake_hits_path(self) -> Path:
        """The scripted hits the fake collectors replay."""
        return self.root / paths.FAKE_HITS_FILE
