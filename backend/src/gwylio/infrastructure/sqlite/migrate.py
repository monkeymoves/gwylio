"""Numbered SQL migrations: ``migrations/NNNN_name.sql``, applied in order, once each.

``migrate(db)`` applies every migration whose number is not yet in
``schema_migrations``, each in its own transaction together with the row that
records it, so a failing migration leaves the database as it was. Running it
again does nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from gwylio.infrastructure.sqlite.db import Database

__all__ = ["MIGRATIONS_DIR", "Migration", "applied_versions", "available_migrations", "migrate"]

MIGRATIONS_DIR: Final[Path] = Path(__file__).resolve().parent / "migrations"
_NAME_RE: Final[re.Pattern[str]] = re.compile(r"([0-9]{4})_([a-z0-9_]+)\.sql")
_BOOTSTRAP: Final[str] = (
    "CREATE TABLE IF NOT EXISTS schema_migrations ("
    "version INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, applied_at TEXT NOT NULL)"
)


@dataclass(frozen=True, slots=True)
class Migration:
    """One numbered migration file."""

    version: int
    name: str
    path: Path

    @property
    def sql(self) -> str:
        """The migration's statements."""
        return self.path.read_text(encoding="utf-8")


def available_migrations(directory: Path = MIGRATIONS_DIR) -> tuple[Migration, ...]:
    """Every migration file in ``directory``, in version order; refuses gaps and stray files."""
    found: list[Migration] = []
    for path in sorted(directory.glob("*.sql")):
        match = _NAME_RE.fullmatch(path.name)
        if match is None:
            raise ValueError(f"migration file {path.name} is not named NNNN_name.sql")
        found.append(Migration(int(match.group(1)), match.group(2), path))
    for expected, migration in enumerate(found, start=1):
        if migration.version != expected:
            raise ValueError(
                f"migration {migration.path.name} should be number {expected:04d}; "
                "migrations are numbered from 0001 without gaps"
            )
    return tuple(found)


def applied_versions(db: Database) -> tuple[int, ...]:
    """The migration numbers already applied, in order."""
    db.execute(_BOOTSTRAP)
    rows = db.fetch_all("SELECT version FROM schema_migrations ORDER BY version")
    return tuple(int(row[0]) for row in rows)


def migrate(
    db: Database, *, directory: Path = MIGRATIONS_DIR, now: datetime | None = None
) -> tuple[Migration, ...]:
    """Apply every pending migration in order; return the ones applied (none when up to date)."""
    if db.in_transaction:
        raise RuntimeError("migrate runs its own transactions; call it outside one")
    done = set(applied_versions(db))
    applied: list[Migration] = []
    for migration in available_migrations(directory):
        if migration.version in done:
            continue
        stamp = (now or datetime.now(UTC)).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        script = (
            "BEGIN;\n"
            f"{migration.sql}\n;\n"
            "INSERT INTO schema_migrations (version, name, applied_at) "
            f"VALUES ({migration.version}, '{migration.name}', '{stamp}');\n"
            "COMMIT;\n"
        )
        try:
            db.executescript(script)
        except Exception:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
        applied.append(migration)
    return tuple(applied)
