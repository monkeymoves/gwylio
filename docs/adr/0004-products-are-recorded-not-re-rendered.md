# ADR 0004: Products are recorded facts, rendered from copy, never re-rendered on rebuild

- Status: accepted
- Date: 2026-10-06
- Deciders: Luke Maggs, with the work package 6 builder

## Context

Work package 6 adds the products: the monthly operational intelligence
summary (INTSUM) and the annual strategic assessment. A product is rendered
on one day from the register as it stood that day, and the brief asks for it
to be written to `data/products/` and recorded in a `product` table. ADR 0002
says the database is a projection that `gwylio rebuild` reconstructs from
files, and the read API and snapshot (work package 7) must serve the stored
products from a rebuilt database. A rebuild cannot render a product again
and get the same words: the date check, the coverage counts and the method
note all depend on the day and on everything ingested since.

The products must also carry no generated prose. Every heading and standing
sentence has to be editable without touching code, and a reviewer has to be
able to see that the renderers hold only structure.

## Decision

- `gwylio product` writes two files per product: `data/products/<stem>.md`,
  the Markdown a reader opens, and `data/products/<stem>.json`, the product's
  structure in the `gwylio.product/1` contract (`docs/schema/product.schema.json`).
  The stem is `<level>_<period label>`, with `_<set id>` appended for any
  requirement set but the first configured one.
- The JSON record is a fact. `rebuild` replays every `data/products/*.json`
  into `product` and `product_report` after the submissions and sweeps; it
  never renders a product. `data/exports/products.json` is a derived export.
- A product occupies a slot: level, requirement set and period. Rendering the
  same slot again replaces both files and the row. Products are publications,
  not append-only evidence; git keeps the earlier version.
- Every heading and standing sentence lives in `config/copy.json`, validated
  by the `Copy` model in `gwylio.dissemination.copy` (each template declares
  the blanks it may use). A test refuses any string constant of three or
  more words in the renderer modules.
- The coverage rule (`Scanability`, `CoverageStatus`, `coverage_status`)
  moved from `gwylio.direction` to `gwylio.shared.coverage`, so the
  Evaluation and Dissemination contexts apply the same rule without importing
  Direction; `gwylio.direction` re-exports it.

## Consequences

- A rebuilt database serves exactly the products that were published, and a
  diff of `data/products/` shows what a reader was told and when.
- Changing `config/copy.json` changes future products only; published ones
  keep their words until they are rendered again.
- A product cites reports by id with a foreign key; reports are never
  deleted, so a recorded product always replays.
- Revisit if products need to be regenerated in bulk after a copy change
  (a `--rerender` flag would then be an explicit, dated act).

## Alternatives considered

- Re-render products during rebuild: rejected, because the output depends on
  the day and on later ingests, so the rebuilt product would differ from the
  published one.
- Parse the Markdown back on rebuild: rejected as fragile; the JSON record is
  the structure and the Markdown is its rendering.
- Keep products only in the database: rejected by ADR 0002; anything not on
  disk is lost on rebuild.
