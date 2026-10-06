"""The shipped config/ loads into SQLite through the real loaders, with the WP1 counts."""

from __future__ import annotations

import pytest

from gwylio.infrastructure.config.loaders import LoadedConfig
from gwylio.infrastructure.sqlite.db import Database
from gwylio.infrastructure.sqlite.repositories import (
    SqliteReferenceRepository,
    SqliteRequirementSetRepository,
    SqliteSourceRepository,
)
from gwylio.reference.model import SONARR_AXIS

pytestmark = pytest.mark.integration


def count(db: Database, sql: str, *params: str) -> int:
    return int(db.scalar(sql, params) or 0)


def test_headline_counts_match_the_shipped_config_test(configured: Database) -> None:
    nrw = ("nrw-corporate-plan",)
    assert count(configured, "SELECT COUNT(*) FROM requirement WHERE set_id = ?", *nrw) == 12
    groups = "SELECT COUNT(*) FROM requirement_group WHERE set_id = ? AND kind = ?"
    assert count(configured, groups, *nrw, "impact") == 6
    assert count(configured, groups, *nrw, "wbo") == 3
    nodes = "SELECT COUNT(*) FROM taxonomy_node WHERE axis_id = ?"
    assert count(configured, nodes, SONARR_AXIS) == 11
    assert count(configured, "SELECT COUNT(*) FROM lane") == 10
    assert count(configured, "SELECT COUNT(*) FROM source") == 43
    assert count(configured, "SELECT COUNT(*) FROM source WHERE status = 'parked'") == 2


def test_every_catalogue_reads_back_equal(
    configured: Database, shipped_config: LoadedConfig
) -> None:
    catalogue = shipped_config.catalogue
    assert SqliteReferenceRepository(configured).load() == catalogue
    assert SqliteRequirementSetRepository(configured).all() == shipped_config.requirement_sets
    assert SqliteSourceRepository(configured).all() == shipped_config.sources
    for table, expected in (
        ("topic", len(catalogue.topics)),
        ("hazard", len(catalogue.hazards)),
        ("place", len(catalogue.places)),
        ("actor", len(catalogue.actors)),
        ("taxonomy_node", len(catalogue.taxonomy.node_ids())),
    ):
        assert count(configured, f"SELECT COUNT(*) FROM {table}") == expected


def test_the_blind_spot_scanabilities_are_stored_as_transcribed(configured: Database) -> None:
    rows = configured.fetch_all(
        "SELECT id, scanability FROM requirement WHERE set_id = 'nrw-corporate-plan' "
        "AND scanability IN ('low', 'none') ORDER BY position"
    )
    assert [(row["id"], row["scanability"]) for row in rows] == [
        ("si9", "low"),
        ("si11", "low"),
        ("si12", "none"),
    ]
