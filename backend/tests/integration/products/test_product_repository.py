"""The product table: a product is stored whole, replaced in its slot, and cites stored reports."""

from __future__ import annotations

from dataclasses import replace

import pytest

from gwylio.dissemination.model import Period
from gwylio.dissemination.render_intsum import render_intsum
from gwylio.infrastructure.config.loaders import LoadedConfig
from gwylio.infrastructure.sqlite.db import Database
from gwylio.infrastructure.sqlite.export import export_products
from gwylio.infrastructure.sqlite.rebuild import rebuild_into
from gwylio.infrastructure.sqlite.repositories import SqliteProductRepository
from gwylio.shared.errors import UnknownReference
from gwylio.shared.values import IsoDate, KebabId
from tests.integration.products.conftest import SEED
from tests.support import PROJECT_ROOT
from tests.unit.dissemination.builders import inputs, shipped_copy

pytestmark = pytest.mark.integration


@pytest.fixture
def db() -> Database:
    database = Database.memory()
    rebuild_into(database, SEED, PROJECT_ROOT / "config")
    return database


def product_for(report_ids: tuple[str, ...], day: str = "2026-10-06"):  # type: ignore[no-untyped-def]
    product = render_intsum(
        inputs(reports=()), Period.month(2026, 10), IsoDate(day), shipped_copy()
    )
    return replace(product, report_ids=tuple(KebabId(r) for r in report_ids))


def test_a_product_round_trips_and_is_replaced_in_its_slot(
    db: Database, shipped_config: LoadedConfig
) -> None:
    repo = SqliteProductRepository(db)
    first = product_for(("south-west-wales-drought-2026",))
    repo.save(first, "operational_2026-10.md")
    stored = repo.get("operational-2026-10")
    assert stored is not None and stored.product == first
    second = product_for(
        ("south-west-wales-drought-2026", "storm-claudia-monmouthshire-flooding"), day="2026-10-20"
    )
    repo.save(second, "operational_2026-10.md")
    stored_ids = [p.product.id for p in repo.all()]
    assert stored_ids == ["operational-2026-10", "strategic-2026"], "the seed's two products"
    [only] = [p for p in repo.all() if p.product.id == "operational-2026-10"]
    assert only.product == second
    exported = {p["id"]: p for p in export_products(db)["products"]}
    assert exported["operational-2026-10"]["generated_on"] == "2026-10-20"


def test_a_product_citing_an_unknown_report_is_refused(db: Database) -> None:
    before = SqliteProductRepository(db).all()
    with pytest.raises(UnknownReference, match="cites a report that is not stored"):
        SqliteProductRepository(db).save(product_for(("no-such-report",)), "x.md")
    assert SqliteProductRepository(db).all() == before
