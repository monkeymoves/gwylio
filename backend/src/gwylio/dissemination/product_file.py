"""The product file contract: ``data/products/<stem>.json`` (``gwylio.product/1``).

A product is rendered once, on the day it is asked for, from the register as
it stood then; a rebuild cannot render it again and get the same words. So
``gwylio product`` writes two files: the Markdown a reader opens
(``<stem>.md``) and this record of the product's structure (``<stem>.json``),
which a rebuild replays into the ``product`` table and the snapshot reads.
Rendering the same level, set and period again replaces both files: a
product is a publication, and git keeps the earlier version.

This module holds the Pydantic model and the pure conversions; reading and
writing files is infrastructure's job.
"""

from __future__ import annotations

import json
from typing import Annotated, Final, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from gwylio.dissemination.model import Level, Period, Product, Section, Table
from gwylio.shared.values import KEBAB_MAX_LENGTH, KEBAB_PATTERN, CleanText, IsoDate, KebabId

__all__ = [
    "PRODUCT_FORMAT",
    "PeriodModel",
    "ProductFile",
    "SectionModel",
    "TableModel",
    "dumps_product",
    "loads_product",
    "product_document",
    "product_from_document",
]

PRODUCT_FORMAT: Final = "gwylio.product/1"
"""The format identifier every product file carries."""

Text = Annotated[str, AfterValidator(CleanText)]
Id = Annotated[str, Field(pattern=KEBAB_PATTERN, max_length=KEBAB_MAX_LENGTH)]


def _date(value: str) -> str:
    IsoDate(value)
    return value


DateText = Annotated[
    str,
    Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$", description="A date, YYYY-MM-DD."),
    AfterValidator(_date),
]


class _FileModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PeriodModel(_FileModel):
    """The dates a product covers, inclusive, and its label."""

    start: DateText
    end: DateText
    label: Id = Field(description="YYYY-MM for a month, YYYY for a year.")


class TableModel(_FileModel):
    """A table: header cells, then rows of cells as wide as the header."""

    headers: list[Text] = Field(min_length=1)
    rows: list[list[Text]]


class SectionModel(_FileModel):
    """One section: heading, paragraphs, tables and bullets, rendered in that order."""

    heading: Text
    depth: int = Field(ge=2, le=3, description="2 for a section, 3 for a subsection.")
    body: list[Text]
    tables: list[TableModel]
    bullets: list[Text]


class ProductFile(_FileModel):
    """data/products/<stem>.json: one rendered product's structure."""

    format: Literal["gwylio.product/1"] = Field(description="Always gwylio.product/1.")
    id: Id
    level: Level
    requirement_set_id: Id
    period: PeriodModel
    generated_on: DateText
    title: Text
    lead: list[Text]
    sections: list[SectionModel] = Field(min_length=1)
    report_ids: list[Id]
    method_note: Text
    markdown_file: str = Field(
        pattern=r"^[a-z0-9_-]+\.md$", description="The Markdown file beside this one."
    )


def product_document(product: Product, markdown_file: str) -> ProductFile:
    """The product as its file contract."""
    return ProductFile(
        format=PRODUCT_FORMAT,
        id=str(product.id),
        level=product.level,
        requirement_set_id=str(product.requirement_set_id),
        period=PeriodModel(
            start=str(product.period.start),
            end=str(product.period.end),
            label=product.period.label,
        ),
        generated_on=str(product.generated_on),
        title=str(product.title),
        lead=[str(p) for p in product.lead],
        sections=[
            SectionModel(
                heading=str(s.heading),
                depth=s.depth,
                body=[str(p) for p in s.body],
                tables=[
                    TableModel(
                        headers=[str(h) for h in t.headers],
                        rows=[[str(c) for c in row] for row in t.rows],
                    )
                    for t in s.tables
                ],
                bullets=[str(b) for b in s.bullets],
            )
            for s in product.sections
        ],
        report_ids=[str(r) for r in product.report_ids],
        method_note=str(product.method_note),
        markdown_file=markdown_file,
    )


def product_from_document(document: ProductFile) -> Product:
    """The product a file records; raises ``ValueError`` when it breaks a product rule."""
    return Product(
        id=KebabId(document.id),
        level=document.level,
        requirement_set_id=KebabId(document.requirement_set_id),
        period=Period(
            IsoDate(document.period.start), IsoDate(document.period.end), document.period.label
        ),
        generated_on=IsoDate(document.generated_on),
        title=CleanText(document.title),
        lead=tuple(CleanText(p) for p in document.lead),
        sections=tuple(
            Section(
                heading=CleanText(s.heading),
                body=tuple(CleanText(p) for p in s.body),
                bullets=tuple(CleanText(b) for b in s.bullets),
                tables=tuple(
                    Table(
                        headers=tuple(CleanText(h) for h in t.headers),
                        rows=tuple(tuple(CleanText(c) for c in row) for row in t.rows),
                    )
                    for t in s.tables
                ),
                depth=s.depth,
            )
            for s in document.sections
        ),
        report_ids=tuple(KebabId(r) for r in document.report_ids),
        method_note=CleanText(document.method_note),
    )


def dumps_product(document: ProductFile) -> str:
    """The product file's text: sorted keys, two-space indent, UTF-8, trailing newline."""
    data = document.model_dump(mode="json")
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def loads_product(text: str) -> ProductFile:
    """Parse a product file's text; raises ``pydantic.ValidationError``."""
    return ProductFile.model_validate_json(text)
