"""Numbered migrations: applied once, in order, each all or nothing."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

import pytest

from gwylio.collection.model import RunStatus, SourceStatus
from gwylio.direction.model import GroupKind, Scanability
from gwylio.infrastructure.sqlite.db import Database
from gwylio.infrastructure.sqlite.migrate import (
    MIGRATIONS_DIR,
    applied_versions,
    available_migrations,
    migrate,
)
from gwylio.reference.model import ActorKind, Lens, NodeKind, PlaceKind
from gwylio.shared.vocabulary import Discipline, MatchedBy, Reliability

pytestmark = pytest.mark.integration

TABLES = {
    "schema_migrations",
    "taxonomy_axis",
    "taxonomy_node",
    "lane",
    "topic",
    "hazard",
    "place",
    "actor",
    "requirement_set",
    "requirement",
    "requirement_expected_coverage",
    "requirement_group",
    "requirement_group_member",
    "requirement_group_related",
    "source",
    "instrument_version",
    "instrument_query",
    "scan_run",
    "scan_run_discipline",
    "candidate",
    "sighting",
    "reinforcement",
    "submission",
    "report",
    "report_assessment",
    "report_tag",
    "report_history",
    "report_sighting",
    "disposition",
    "product",
    "product_report",
}


def test_migration_applies_on_an_empty_database_and_creates_every_table() -> None:
    db = Database.memory()
    applied = migrate(db, now=datetime(2026, 10, 6, 9, 0, tzinfo=UTC))
    assert [m.path.name for m in applied] == [
        "0001_init.sql",
        "0002_intelligence.sql",
        "0003_products.sql",
    ]
    assert set(db.table_names()) == TABLES
    rows = db.fetch_all("SELECT version, name, applied_at FROM schema_migrations ORDER BY version")
    assert [tuple(row) for row in rows] == [
        (1, "init", "2026-10-06T09:00:00.000000Z"),
        (2, "intelligence", "2026-10-06T09:00:00.000000Z"),
        (3, "products", "2026-10-06T09:00:00.000000Z"),
    ]


def test_migrate_is_idempotent() -> None:
    db = Database.memory()
    assert len(migrate(db)) == 3
    assert migrate(db) == ()
    assert applied_versions(db) == (1, 2, 3)


def test_migrate_upgrades_a_file_database_in_place(tmp_path: Path) -> None:
    path = tmp_path / "data" / "gwylio.sqlite"
    with Database.open(path) as db:
        migrate(db)
    with Database.open(path) as db:
        assert migrate(db) == ()
        assert set(db.table_names()) == TABLES
    assert sorted(p.name for p in path.parent.iterdir()) == ["gwylio.sqlite"]


def test_migrate_refuses_to_run_inside_a_transaction() -> None:
    db = Database.memory()
    with db.transaction(), pytest.raises(RuntimeError, match="outside one"):
        migrate(db)


def test_a_failing_migration_leaves_nothing_behind(tmp_path: Path) -> None:
    (tmp_path / "0001_good.sql").write_text("CREATE TABLE a (x INTEGER);\n", encoding="utf-8")
    (tmp_path / "0002_bad.sql").write_text(
        "CREATE TABLE b (x INTEGER);\nINSERT INTO nowhere VALUES (1);\n", encoding="utf-8"
    )
    db = Database.memory()
    with pytest.raises(Exception, match="no such table: nowhere"):
        migrate(db, directory=tmp_path)
    assert not db.in_transaction
    assert applied_versions(db) == (1,)
    assert "a" in db.table_names()
    assert "b" not in db.table_names()


@pytest.mark.parametrize(
    ("names", "message"),
    [
        (["0001_a.sql", "0003_c.sql"], "should be number 0002"),
        (["0001_a.sql", "2_b.sql"], "is not named NNNN_name.sql"),
    ],
)
def test_migration_files_are_numbered_without_gaps(
    tmp_path: Path, names: list[str], message: str
) -> None:
    for name in names:
        (tmp_path / name).write_text("SELECT 1;\n", encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        available_migrations(tmp_path)


ENUM_COLUMNS: list[tuple[type[StrEnum], str]] = [
    (NodeKind, "kind"),
    (Lens, "lens"),
    (PlaceKind, "kind"),
    (ActorKind, "kind"),
    (Scanability, "scanability"),
    (GroupKind, "kind"),
    (Discipline, "discipline"),
    (Reliability, "reliability"),
    (SourceStatus, "status"),
    (RunStatus, "status"),
    (MatchedBy, "matched_by"),
]


@pytest.mark.parametrize(("enum", "column"), ENUM_COLUMNS, ids=lambda v: getattr(v, "__name__", v))
def test_every_enum_check_lists_the_domain_values_in_order(
    enum: type[StrEnum], column: str
) -> None:
    sql = (MIGRATIONS_DIR / "0001_init.sql").read_text(encoding="utf-8")
    values = ", ".join(f"'{member.value}'" for member in enum)
    assert f"CHECK ({column} IN ({values}))" in sql


def test_no_enum_check_lists_values_the_domain_does_not_have() -> None:
    sql = (MIGRATIONS_DIR / "0001_init.sql").read_text(encoding="utf-8")
    known = {", ".join(f"'{member.value}'" for member in enum) for enum, _ in ENUM_COLUMNS}
    for found in re.findall(r"CHECK \(\w+ IN \(('[^)]*)\)\)", sql):
        assert found in known
