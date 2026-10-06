"""Write and replay products: ``data/products/<stem>.md`` and ``<stem>.json``.

``write_product`` stores a rendered product in the ``product`` table and
writes its two files inside one database transaction (the files before the
commit, as collect and ingest do), so the facts on disk never lag the
projection. The Markdown is what a reader opens; the JSON record
(``gwylio.product/1``) is what ``rebuild`` replays, because a product cannot
be rendered again later and come out the same. Rendering the same slot again
replaces both files and the row.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from gwylio.dissemination.model import Product, to_markdown
from gwylio.dissemination.product_file import (
    ProductFile,
    dumps_product,
    loads_product,
    product_document,
    product_from_document,
)
from gwylio.infrastructure.sqlite.db import Database
from gwylio.infrastructure.sqlite.repositories import SqliteProductRepository

__all__ = [
    "ProductFileError",
    "WrittenProduct",
    "apply_product_file",
    "read_product_files",
    "write_product",
]


class ProductFileError(ValueError):
    """A product file could not be read or replayed."""


@dataclass(frozen=True, slots=True)
class WrittenProduct:
    """The two files one product was written to."""

    markdown: Path
    record: Path


def write_product(db: Database, products_dir: Path, product: Product, stem: str) -> WrittenProduct:
    """Store ``product`` and write ``<stem>.md`` and ``<stem>.json`` under ``products_dir``."""
    markdown = products_dir / f"{stem}.md"
    record = products_dir / f"{stem}.json"
    with db.transaction():
        SqliteProductRepository(db).save(product, markdown.name)
        products_dir.mkdir(parents=True, exist_ok=True)
        markdown.write_text(to_markdown(product), encoding="utf-8")
        record.write_text(dumps_product(product_document(product, markdown.name)), encoding="utf-8")
    return WrittenProduct(markdown, record)


def read_product_files(products_dir: Path) -> list[tuple[Path, ProductFile]]:
    """Every product record under ``products_dir``, by file name."""
    if not products_dir.is_dir():
        return []
    found: list[tuple[Path, ProductFile]] = []
    for path in sorted(products_dir.glob("*.json")):
        try:
            document = loads_product(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValidationError) as error:
            raise ProductFileError(f"{path}: not a valid product file: {error}") from error
        if document.markdown_file != f"{path.stem}.md":
            raise ProductFileError(
                f"{path}: names {document.markdown_file}, not {path.stem}.md, as its Markdown"
            )
        found.append((path, document))
    return found


def apply_product_file(db: Database, document: ProductFile) -> None:
    """Store the product a file records."""
    try:
        product = product_from_document(document)
    except ValueError as error:
        raise ProductFileError(f"product {document.id}: {error}") from error
    SqliteProductRepository(db).save(product, document.markdown_file)
