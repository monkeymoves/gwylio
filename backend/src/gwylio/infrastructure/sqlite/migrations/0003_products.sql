-- Migration 0003: the products the register feeds (Dissemination).
--
-- Same conventions as 0001. data/products/<stem>.json is the fact behind
-- every row here (ADR 0002): a product is rendered once, from the register
-- as it stood that day, so a rebuild replays the recorded product rather
-- than rendering it again. Rendering the same level, set and period again
-- replaces the row.
--
-- requirement_set_id has no foreign key: a product is history, and outlives
-- a requirement set removed from config/. The report links carry no ON
-- DELETE CASCADE, because saving a report deletes and rewrites its row.

CREATE TABLE product (
    id                 TEXT PRIMARY KEY,
    level              TEXT NOT NULL CHECK (level IN ('strategic', 'operational', 'tactical')),
    requirement_set_id TEXT NOT NULL,
    period_label       TEXT NOT NULL,
    period_start       TEXT NOT NULL
        CHECK (period_start GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    period_end         TEXT NOT NULL
        CHECK (period_end GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    generated_on       TEXT NOT NULL
        CHECK (generated_on GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    title              TEXT NOT NULL,
    lead               TEXT NOT NULL CHECK (json_valid(lead) AND json_type(lead) = 'array'),
    -- The sections as the product file spells them: headings, paragraphs, tables, bullets.
    sections           TEXT NOT NULL CHECK (json_valid(sections) AND json_type(sections) = 'array'),
    method_note        TEXT NOT NULL,
    markdown_file      TEXT NOT NULL UNIQUE,
    CHECK (period_end >= period_start),
    UNIQUE (level, requirement_set_id, period_label)
);

CREATE TABLE product_report (
    product_id TEXT NOT NULL REFERENCES product (id) ON DELETE CASCADE,
    position   INTEGER NOT NULL,
    report_id  TEXT NOT NULL REFERENCES report (id),
    PRIMARY KEY (product_id, position),
    UNIQUE (product_id, report_id)
);

CREATE INDEX product_report_report ON product_report (report_id);
