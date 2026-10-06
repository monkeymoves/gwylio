# WP3 brief: SQLite persistence, export, rebuild

You are building work package 3 of the project described in `docs/PLAN.md`
(read it fully first). Then read `CLAUDE.md`, the briefs WP0 to WP2 under
`docs/briefs/`, and the code they produced under `backend/src/gwylio/`,
especially the repository ports in `collection/ports.py`, the domain models in
`reference/`, `direction/` and `collection/`, the in-memory repositories under
`infrastructure/memory/`, and the config loaders under
`infrastructure/config/`. Follow their conventions exactly. Project root is
`gwylio/`. Do not touch anything outside it. Do not run git.

## Principle (ADR 0002)

Files are the facts. `config/` plus `data/candidates/*.json` (and, from WP5,
`data/submissions/*.json`) are the record. SQLite under `data/gwylio.sqlite`
is a projection that `gwylio rebuild` reconstructs from those files. Nothing
may exist in the database that cannot be rebuilt.

## Deliverables

`backend/src/gwylio/infrastructure/sqlite/`

- `db.py`: `Database` wrapper over the standard library `sqlite3`. Opens with
  `PRAGMA foreign_keys = ON`, `journal_mode = DELETE` (no sidecar files in the
  data directory), `isolation_level = None` with explicit `transaction()`
  context manager. Every write goes through `execute(sql, params)` which
  inspects `params`: any `str` that is not already a `CleanText` instance is
  passed through `CleanText(...)` so a dash anywhere raises before the write.
  Row factory returns `sqlite3.Row`. In-memory databases supported for tests
  (`Database.memory()`).
- `migrations/0001_init.sql` creating every table the plan lists for the
  contexts built so far (requirement_set, requirement, requirement_group,
  requirement_group_member, requirement_expected_coverage, taxonomy_axis,
  taxonomy_node, topic, hazard, place, actor, lane, source, instrument_version,
  instrument_query, scan_run, candidate, sighting) plus `schema_migrations`.
  Foreign keys everywhere a reference exists; `candidate(run_id,
  canonical_url)` unique; `sighting` references candidate and run; enum
  columns are TEXT with a CHECK constraint listing the allowed values (the
  domain validates too; the CHECK is a second lock). Store dates as ISO text
  and timestamps as ISO UTC text.
- `migrate.py`: `migrate(db)` applies numbered `.sql` files not yet in
  `schema_migrations`, in order, each in a transaction. Idempotent.
- `repositories.py`: SQLite implementations of every port that WP1 and WP2
  defined (reference catalogue, requirement sets, sources, instrument,
  scan runs, candidates and sightings, the seen index). Load the whole
  aggregate on read; write the whole aggregate on save (delete and reinsert
  children inside one transaction). Keep SQL in this module only.
- `export.py`: `export_runs(db) -> dict` and a writer producing
  `data/exports/runs.json`: every scan run with funnel, requests, status and
  per-discipline counts, sorted by run id, keys sorted, two-space indent,
  trailing newline. Deterministic: two exports of the same database are
  byte-identical.
- `rebuild.py`: `rebuild(data_dir, config_dir, db_path)`: deletes the
  database file if present, migrates, loads every config file through the WP1
  and WP2 loaders into the reference, direction, source and instrument tables,
  then replays every `data/candidates/*.json` in run id order into scan_run,
  candidate and sighting (the candidates file carries everything needed;
  if it does not, extend the candidates file model in `processing/
  candidates_file.py` and regenerate the schema). Returns a summary of counts.

`backend/src/gwylio/infrastructure/config/settings.py`

- `Settings` (Pydantic): `data_dir` (default `data` relative to the project
  root), `config_dir` (default `config`), `db_path` (default
  `<data_dir>/gwylio.sqlite`), loaded from environment variables prefixed
  `GWYLIO_` with sensible defaults. Every CLI command takes the settings from
  one place.

CLI

- `gwylio migrate`: create or upgrade the database at `db_path`.
- `gwylio collect --fake [--out-dir DIR]`: fake collectors from the WP2 fixture
  with REAL persistence: SQLite repositories plus a candidates file written to
  `<data_dir>/candidates/<run_id>.json`. `--dry-run` keeps the WP2 behaviour
  (in-memory, nothing persisted). Plain `collect` still exits 2 pointing at WP4.
- `gwylio export`: writes `data/exports/runs.json`.
- `gwylio rebuild`: as above, prints the summary table.
- Wire `make seed` to: migrate, then `collect --fake` into a temporary data
  dir under `backend/tests/fixtures/seed/` only if you judge it useful for
  later packages; otherwise leave `seed` as a stub and say so.

## Tests (`backend/tests/integration/sqlite/`)

- Migration applies on an empty database and is idempotent on a second call.
- Foreign keys are enforced (inserting a sighting for a missing candidate
  raises `sqlite3.IntegrityError`).
- The CleanText guard: a parameter containing `chr(0x2014)` raises before any
  row is written, and the transaction leaves no partial state.
- Round trip for each repository: save an aggregate built in Python, load it,
  assert equality with the original (domain objects are frozen dataclasses, so
  `==` works).
- Seen index: canonical URLs from an earlier run are reported, those from the
  current run are not.
- Export determinism: export twice, byte-identical; export after one more run
  differs only by the new run.
- Rebuild equivalence: run `collect --fake` into data dir A with database A;
  `rebuild` into database B from the same files; dump the scan_run,
  candidate and sighting tables from both (ordered) and assert equality.
- The shipped `config/` loads into SQLite through the real loaders and the
  counts match the WP1 shipped-config test.

## Style rules

No em or en dashes anywhere (the db guard will remind you). British English.
Domain packages must not import `infrastructure`; the import-rule test will
fail if they do.

## Definition of done

1. `make ci` exits 0 from `gwylio/`.
2. From a clean data directory: `gwylio migrate`, `gwylio collect --fake`,
   `gwylio export`, `gwylio rebuild` all exit 0 and the rebuilt database
   matches, as the equivalence test proves.
3. Report back: commands run with status lines, test counts before and after,
   deviations and why, and notes for WP4 (how a real collector plugs into
   `collect`, what the candidates file now carries).
