"""The ``Database`` wrapper: pragmas, the CleanText guard and transactions."""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from gwylio.infrastructure.sqlite.db import Database
from gwylio.infrastructure.sqlite.migrate import migrate
from gwylio.shared.values import CleanText, KebabId

pytestmark = pytest.mark.integration

EM_DASH = chr(0x2014)
EN_DASH = chr(0x2013)


def scratch() -> Database:
    db = Database.memory()
    db.execute("CREATE TABLE note (id INTEGER PRIMARY KEY, body TEXT NOT NULL)")
    return db


def test_foreign_keys_are_enforced(db: Database) -> None:
    assert db.scalar("PRAGMA foreign_keys") == 1
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        db.execute(
            "INSERT INTO sighting (id, run_id, candidate_id, source_id, query_id, discipline) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("s-1", "20261006T0215Z-3f9a", "c-missing", None, "q1", "osint_web"),
        )
    assert db.scalar("SELECT COUNT(*) FROM sighting") == 0


def test_check_constraints_lock_enum_columns(db: Database) -> None:
    db.execute(
        "INSERT INTO lane (id, position, name, lens, description) VALUES (?, ?, ?, ?, ?)",
        ("senedd", 0, "Senedd", "government", "The Welsh Parliament."),
    )
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        db.execute(
            "INSERT INTO lane (id, position, name, lens, description) VALUES (?, ?, ?, ?, ?)",
            ("press", 1, "Press", "media", "Not a lens."),
        )


def test_a_file_database_uses_the_delete_journal_and_leaves_no_sidecar(tmp_path: Path) -> None:
    path = tmp_path / "gwylio.sqlite"
    with Database.open(path) as db:
        assert db.scalar("PRAGMA journal_mode") == "delete"
        migrate(db)
        with db.transaction():
            db.execute(
                "INSERT INTO topic (id, position, name) VALUES (?, ?, ?)", ("peat", 0, "Peat")
            )
    assert [p.name for p in tmp_path.iterdir()] == ["gwylio.sqlite"]


@pytest.mark.parametrize("dash", [EM_DASH, EN_DASH])
def test_a_dash_in_any_parameter_raises_before_anything_is_written(dash: str) -> None:
    db = scratch()
    with pytest.raises(ValueError, match="DASH"), db.transaction():
        db.execute("INSERT INTO note (body) VALUES (?)", ("a clean first row",))
        db.execute("INSERT INTO note (body) VALUES (?)", (f"2024 {dash} 25",))
    assert not db.in_transaction
    assert db.scalar("SELECT COUNT(*) FROM note") == 0


def test_the_guard_covers_named_parameters_and_every_row_of_executemany() -> None:
    db = scratch()
    with pytest.raises(ValueError, match="EM DASH"):
        db.execute("INSERT INTO note (body) VALUES (:body)", {"body": f"x {EM_DASH} y"})
    with pytest.raises(ValueError, match="EM DASH"):
        db.executemany("INSERT INTO note (body) VALUES (?)", [("fine",), (f"not {EM_DASH} fine",)])
    assert db.scalar("SELECT COUNT(*) FROM note") == 0


def test_text_subclasses_are_stored_as_plain_text() -> None:
    db = scratch()
    db.execute("INSERT INTO note (body) VALUES (?)", (KebabId("si4"),))
    db.execute("INSERT INTO note (body) VALUES (?)", (CleanText("clean"),))
    assert [row["body"] for row in db.fetch_all("SELECT body FROM note ORDER BY id")] == [
        "si4",
        "clean",
    ]


def test_values_without_a_declared_storage_are_refused() -> None:
    db = scratch()
    with pytest.raises(TypeError, match="unsupported database parameter of type date"):
        db.execute("INSERT INTO note (body) VALUES (?)", (date(2026, 10, 6),))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="sequence or a mapping"):
        db.execute("INSERT INTO note (body) VALUES (?)", "abc")


def test_reads_are_not_guarded() -> None:
    db = scratch()
    assert db.fetch_all("SELECT ? AS echoed", (f"a {EM_DASH} b",))[0]["echoed"] == (
        f"a {EM_DASH} b"
    )


def test_an_inner_transaction_is_a_savepoint() -> None:
    db = scratch()
    with db.transaction():
        db.execute("INSERT INTO note (body) VALUES (?)", ("outer",))
        with pytest.raises(RuntimeError), db.transaction():
            db.execute("INSERT INTO note (body) VALUES (?)", ("inner",))
            raise RuntimeError("undo the inner block only")
        assert db.in_transaction
    assert [row["body"] for row in db.fetch_all("SELECT body FROM note")] == ["outer"]


def test_a_foreign_key_that_fails_at_commit_rolls_back(db: Database) -> None:
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"), db.transaction():
        db.defer_foreign_keys()
        db.execute(
            "INSERT INTO actor (id, position, name, kind, lane) VALUES (?, ?, ?, ?, ?)",
            ("nobody", 0, "Nobody", "other", "no-such-lane"),
        )
    assert not db.in_transaction
    assert db.scalar("SELECT COUNT(*) FROM actor") == 0


def test_foreign_keys_can_only_be_deferred_inside_a_transaction(db: Database) -> None:
    with pytest.raises(RuntimeError, match="inside a transaction"):
        db.defer_foreign_keys()


def test_a_script_cannot_run_inside_a_transaction() -> None:
    db = scratch()
    with db.transaction(), pytest.raises(RuntimeError, match="inside an open transaction"):
        db.executescript("SELECT 1;")
