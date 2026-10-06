"""The product file contract round-trips a product exactly."""

from __future__ import annotations

from gwylio.dissemination.model import Period, to_markdown
from gwylio.dissemination.product_file import (
    dumps_product,
    loads_product,
    product_document,
    product_from_document,
)
from gwylio.dissemination.render_strategic import render_strategic
from gwylio.shared.values import IsoDate
from tests.unit.dissemination.builders import inputs, shipped_copy


def test_a_product_round_trips_through_its_file() -> None:
    product = render_strategic(inputs(), Period.year(2026), IsoDate("2026-10-06"), shipped_copy())
    document = product_document(product, "strategic_2026.md")
    text = dumps_product(document)
    assert text.endswith("}\n")
    again = product_from_document(loads_product(text))
    assert again == product
    assert to_markdown(again) == to_markdown(product)
