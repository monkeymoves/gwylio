"""Products: what the register is turned into for its readers.

Pure, frozen domain objects. A ``Product`` is one rendered document: its
level (strategic, operational, tactical), the requirement set and period it
covers, a title and lead paragraphs, its sections, the reports it cites and
its method note. ``to_markdown`` renders it deterministically: ``#`` for the
title, ``##`` and ``###`` for sections, pipe tables, ``-`` bullets. Every
piece of text is ``CleanText``, so a product can never carry an en or em dash.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Final

from gwylio.shared.errors import DomainError
from gwylio.shared.values import CleanText, IsoDate, KebabId

__all__ = [
    "TACTICAL_MESSAGE",
    "Level",
    "NotImplementedInV1",
    "Period",
    "Product",
    "ProductLevel",
    "Section",
    "Table",
    "product_id",
    "product_stem",
    "to_markdown",
]

TACTICAL_MESSAGE: Final[str] = "tactical alerts are a designed seam, not built in v1"
"""What asking for a tactical product says, word for word."""

_MONTH_RE: Final[re.Pattern[str]] = re.compile(r"([0-9]{4})-([0-9]{2})")
_YEAR_RE: Final[re.Pattern[str]] = re.compile(r"[0-9]{4}")


class NotImplementedInV1(DomainError):  # noqa: N818, the name the brief and the domain use
    """A product level designed as a seam and not built in version 1."""


class ProductLevel(StrEnum):
    """The level a product serves: the annual picture, the monthly summary, or an alert."""

    STRATEGIC = "strategic"
    OPERATIONAL = "operational"
    TACTICAL = "tactical"


Level = ProductLevel
"""The product level, as the Dissemination context names it. The class is
``ProductLevel`` so its generated schema never collides with the score
``Level`` (low, medium, high) in ``gwylio.shared.vocabulary``."""


@dataclass(frozen=True, slots=True)
class Period:
    """The dates a product covers, inclusive, and its label, such as ``2026-10`` or ``2026``."""

    start: IsoDate
    end: IsoDate
    label: str

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError(f"period {self.label} ends before it starts")
        KebabId(self.label)

    @classmethod
    def month(cls, year: int, month: int) -> Period:
        """One calendar month, labelled ``YYYY-MM``."""
        if not 1 <= month <= 12:
            raise ValueError(f"no month {month}")
        last = calendar.monthrange(year, month)[1]
        return cls(
            IsoDate(date(year, month, 1)),
            IsoDate(date(year, month, last)),
            f"{year:04d}-{month:02d}",
        )

    @classmethod
    def year(cls, year: int) -> Period:
        """One calendar year, labelled ``YYYY``."""
        return cls(IsoDate(date(year, 1, 1)), IsoDate(date(year, 12, 31)), f"{year:04d}")

    @classmethod
    def for_level(cls, level: Level, text: str | None, today: date) -> Period:
        """The period a product of ``level`` covers.

        Operational products cover one month (``YYYY-MM``) and strategic ones
        one year (``YYYY``); with no ``text`` the period holding ``today``.
        Raises ``ValueError`` for text of the wrong shape for the level.
        """
        if level is Level.STRATEGIC:
            if text is None:
                return cls.year(today.year)
            if not _YEAR_RE.fullmatch(text):
                raise ValueError(f"a strategic period is a year, YYYY, not {text!r}")
            return cls.year(int(text))
        if text is None:
            return cls.month(today.year, today.month)
        match = _MONTH_RE.fullmatch(text)
        if match is None:
            raise ValueError(f"an operational period is a month, YYYY-MM, not {text!r}")
        return cls.month(int(match.group(1)), int(match.group(2)))

    @property
    def is_month(self) -> bool:
        """True when the label names a month."""
        return _MONTH_RE.fullmatch(self.label) is not None

    def contains(self, day: IsoDate) -> bool:
        """True when ``day`` falls inside the period, ends included."""
        return self.start <= day <= self.end


@dataclass(frozen=True, slots=True)
class Table:
    """A table: header cells and rows of cells, every row as wide as the header."""

    headers: tuple[CleanText, ...]
    rows: tuple[tuple[CleanText, ...], ...]

    def __post_init__(self) -> None:
        if not self.headers:
            raise ValueError("a table needs at least one column")
        for r, row in enumerate(self.rows):
            if len(row) != len(self.headers):
                raise ValueError(
                    f"table row {r} has {len(row)} cells but the header has {len(self.headers)}"
                )


@dataclass(frozen=True, slots=True)
class Section:
    """One section of a product: a heading, then paragraphs, tables and bullets, in that order.

    ``depth`` is 2 for a top-level section and 3 for a subsection.
    """

    heading: CleanText
    body: tuple[CleanText, ...] = ()
    bullets: tuple[CleanText, ...] = ()
    tables: tuple[Table, ...] = ()
    depth: int = 2

    def __post_init__(self) -> None:
        if not self.heading.strip():
            raise ValueError("a section needs a heading")
        if self.depth not in (2, 3):
            raise ValueError(f"section depth must be 2 or 3, got {self.depth}")


@dataclass(frozen=True, slots=True)
class Product:
    """One rendered product: what a reader receives, and what it was built from."""

    id: KebabId
    level: Level
    requirement_set_id: KebabId
    period: Period
    generated_on: IsoDate
    title: CleanText
    lead: tuple[CleanText, ...]
    sections: tuple[Section, ...]
    report_ids: tuple[KebabId, ...]
    method_note: CleanText

    def __post_init__(self) -> None:
        if len(set(self.report_ids)) != len(self.report_ids):
            raise ValueError(f"product {self.id} cites a report twice")
        if list(self.report_ids) != sorted(self.report_ids):
            raise ValueError(f"product {self.id} must list its report ids in order")


def product_id(level: Level, period: Period, set_id: str, default_set: bool) -> KebabId:
    """``<level>-<period label>``, plus ``-<set id>`` for any set but the default one."""
    base = f"{level.value}-{period.label}"
    return KebabId(base if default_set else f"{base}-{set_id}")


def product_stem(level: Level, period: Period, set_id: str, default_set: bool) -> str:
    """The file name without extension: ``<level>_<period label>``, plus ``_<set id>`` likewise."""
    base = f"{level.value}_{period.label}"
    return base if default_set else f"{base}_{set_id}"


def _cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "\\|")


def _table(table: Table) -> list[str]:
    lines = [
        "| " + " | ".join(_cell(h) for h in table.headers) + " |",
        "|" + "|".join("---" for _ in table.headers) + "|",
    ]
    lines.extend("| " + " | ".join(_cell(c) for c in row) + " |" for row in table.rows)
    return lines


def to_markdown(product: Product) -> CleanText:
    """The product as Markdown: deterministic, blank-line separated, one trailing newline."""
    blocks: list[str] = [f"# {product.title}", *product.lead]
    for section in product.sections:
        blocks.append(f"{'#' * section.depth} {section.heading}")
        blocks.extend(section.body)
        blocks.extend("\n".join(_table(table)) for table in section.tables)
        if section.bullets:
            blocks.append("\n".join(f"- {' '.join(bullet.split())}" for bullet in section.bullets))
    return CleanText("\n\n".join(block.strip() for block in blocks if block.strip()) + "\n")
