"""``gwylio product``: render a product, record it, and write its files.

``--level operational`` renders the monthly intelligence summary (INTSUM),
``--level strategic`` the annual strategic assessment; ``--level tactical``
exits 4, because tactical alerts are a designed seam, not built in v1. The
period defaults to the month (or year) holding ``--today``. The product is
stored in the ``product`` table and written to
``data/products/<level>_<period>.md`` (what a reader opens) and ``.json``
(what a rebuild replays), and ``data/exports/products.json`` is refreshed.
"""

from __future__ import annotations

import typer

from gwylio.cli.common import database, load, today
from gwylio.dissemination.model import Level, NotImplementedInV1, Period
from gwylio.dissemination.render_tactical import render_tactical
from gwylio.infrastructure.adapters import render_product
from gwylio.infrastructure.config.settings import Settings
from gwylio.infrastructure.handoff.product_file import write_product
from gwylio.infrastructure.sqlite.export import write_products_export

__all__ = ["TACTICAL_EXIT", "run_product"]

TACTICAL_EXIT = 4
"""The exit code for a product level that is not built in version 1."""


def run_product(
    settings: Settings,
    level: Level,
    *,
    period: str | None = None,
    set_id: str | None = None,
    on: str | None = None,
) -> int:
    """Render and record one product; print where it was written; return the exit code."""
    day = today(on)
    if day is None:
        return 2
    try:
        chosen_period = Period.for_level(level, period, day.value)
    except ValueError as error:
        typer.echo(f"product: {error}", err=True)
        return 2
    config = load(settings.config_root, "product")
    if config is None:
        return 1
    chosen = set_id or str(config.requirement_sets[0].id)
    if chosen not in {str(rs.id) for rs in config.requirement_sets}:
        known = ", ".join(str(rs.id) for rs in config.requirement_sets)
        typer.echo(f"product: no requirement set '{chosen}'; configured: {known}", err=True)
        return 2
    if level is Level.TACTICAL:
        try:
            render_tactical()
        except NotImplementedInV1 as error:
            typer.echo(error.message, err=True)
            return TACTICAL_EXIT
    with database(settings, config, "product") as db:
        if db is None:
            return 1
        product, stem = render_product(db, config, level, chosen_period, day.value, chosen)
        written = write_product(db, settings.products_dir, product, stem)
        export = write_products_export(db, settings.products_export_path)
    typer.echo(written.markdown)
    typer.echo(
        f"product: {product.id}, {len(product.sections)} sections citing "
        f"{len(product.report_ids)} report{'s' if len(product.report_ids) != 1 else ''}"
    )
    typer.echo(f"wrote  {written.record}")
    typer.echo(f"wrote  {export}")
    return 0
