"""``Database``: a thin wrapper over the standard library ``sqlite3``.

- Foreign keys are on and the journal is in ``DELETE`` mode, so no sidecar
  files are left in the data directory between commands.
- The connection runs in autocommit mode (``isolation_level=None``);
  ``transaction()`` opens an explicit transaction, or a savepoint when one is
  already open, so a repository's own transaction nests inside a caller's.
- Every write goes through ``execute`` or ``executemany``, which pass every
  ``str`` parameter through ``CleanText``: an en or em dash anywhere raises
  ``ValueError`` before anything is written. Only ``None``, ``bool``, ``int``,
  ``float``, ``str`` and ``bytes`` parameters are accepted, so no implicit
  adapter (dates, datetimes) ever decides how a value is stored.
- Rows come back as ``sqlite3.Row``.
"""

from __future__ import annotations

import itertools
import sqlite3
from collections.abc import Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import TypeAlias

from gwylio.shared.values import CleanText

__all__ = ["Database", "Params", "Value"]

Value: TypeAlias = bool | int | float | str | bytes | None
"""A value SQLite stores as it is."""
Params: TypeAlias = Sequence[Value] | Mapping[str, Value]
"""Positional or named statement parameters."""

_savepoints = itertools.count(1)


def _clean(value: Value) -> Value:
    if value is None or isinstance(value, bool | int | float | bytes):
        return value
    if isinstance(value, str):
        # CleanText refuses an en or em dash; str() hands sqlite3 an exact str.
        return str(value if isinstance(value, CleanText) else CleanText(value))
    raise TypeError(
        f"unsupported database parameter of type {type(value).__name__}; "
        "convert it to text or a number first"
    )


def _guard(params: Params) -> Params:
    if isinstance(params, Mapping):
        return {key: _clean(value) for key, value in params.items()}
    if isinstance(params, str | bytes):
        raise TypeError("parameters must be a sequence or a mapping, not a single value")
    return tuple(_clean(value) for value in params)


class Database:
    """One SQLite connection with the project's pragmas, guard and transactions."""

    def __init__(self, connection: sqlite3.Connection, path: Path | None = None) -> None:
        connection.isolation_level = None
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = DELETE")
        if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise RuntimeError("this SQLite build cannot enforce foreign keys")
        self._connection = connection
        self.path = path

    @classmethod
    def open(cls, path: Path, *, check_same_thread: bool = True) -> Database:
        """Open (creating if needed) the database file at ``path``.

        ``check_same_thread=False`` lets another thread use the connection, as
        the read API does: it opens the database in one worker thread and may
        read it in another, one request at a time.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(
            path, isolation_level=None, check_same_thread=check_same_thread
        )
        return cls(connection, path)

    @classmethod
    def memory(cls, *, check_same_thread: bool = True) -> Database:
        """A private in-memory database, for tests (any thread may use it when unchecked)."""
        connection = sqlite3.connect(
            ":memory:", isolation_level=None, check_same_thread=check_same_thread
        )
        return cls(connection)

    def close(self) -> None:
        """Close the connection; an open transaction is rolled back."""
        self._connection.close()

    def __enter__(self) -> Database:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @property
    def in_transaction(self) -> bool:
        """True while a transaction is open."""
        return self._connection.in_transaction

    # Writes: every parameter passes the CleanText guard first.

    def execute(self, sql: str, params: Params = ()) -> sqlite3.Cursor:
        """Run one statement with guarded parameters."""
        return self._connection.execute(sql, _guard(params))

    def executemany(self, sql: str, rows: Iterable[Params]) -> sqlite3.Cursor:
        """Run one statement once per parameter row; every row is guarded before any runs."""
        guarded = [_guard(row) for row in rows]
        return self._connection.executemany(sql, guarded)

    def executescript(self, script: str) -> None:
        """Run a script of statements with no parameters, such as a migration.

        The script text itself passes the dash rule. ``sqlite3`` commits any
        open transaction before a script, so a script may not run inside one.
        """
        if self.in_transaction:
            raise RuntimeError("a script cannot run inside an open transaction")
        self._connection.executescript(str(CleanText(script)))

    # Reads.

    def fetch_all(self, sql: str, params: Params = ()) -> list[sqlite3.Row]:
        """Every row a query returns."""
        return list(self._connection.execute(sql, params))

    def fetch_one(self, sql: str, params: Params = ()) -> sqlite3.Row | None:
        """The first row a query returns, or ``None``."""
        row: sqlite3.Row | None = self._connection.execute(sql, params).fetchone()
        return row

    def scalar(self, sql: str, params: Params = ()) -> Value:
        """The first column of the first row, or ``None`` when there is no row."""
        row = self.fetch_one(sql, params)
        if row is None:
            return None
        value: Value = row[0]
        return value

    # Transactions.

    @contextmanager
    def transaction(self) -> Iterator[Database]:
        """Commit on success and roll back on any exception.

        Inside an open transaction this opens a savepoint instead, so a failure
        undoes only the inner block and the outer transaction decides the rest.
        """
        if self.in_transaction:
            name = f"gwylio_{next(_savepoints)}"
            self._connection.execute(f"SAVEPOINT {name}")
            try:
                yield self
            except BaseException:
                self._connection.execute(f"ROLLBACK TO SAVEPOINT {name}")
                self._connection.execute(f"RELEASE SAVEPOINT {name}")
                raise
            self._connection.execute(f"RELEASE SAVEPOINT {name}")
            return
        self._connection.execute("BEGIN")
        try:
            yield self
        except BaseException:
            if self.in_transaction:
                self._connection.execute("ROLLBACK")
            raise
        try:
            self._connection.execute("COMMIT")
        except sqlite3.Error:
            # A deferred foreign key fails at commit and leaves the transaction open.
            if self.in_transaction:
                self._connection.execute("ROLLBACK")
            raise

    def defer_foreign_keys(self) -> None:
        """Check foreign keys at commit rather than per statement, until this transaction ends.

        Used when a whole aggregate is deleted and written again: rows that
        other tables point at disappear for a moment and come back before commit.
        """
        if not self.in_transaction:
            raise RuntimeError("foreign keys can only be deferred inside a transaction")
        self._connection.execute("PRAGMA defer_foreign_keys = ON")

    def table_names(self) -> tuple[str, ...]:
        """Every table in the database, sorted by name."""
        rows = self.fetch_all(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        )
        return tuple(str(row[0]) for row in rows)
