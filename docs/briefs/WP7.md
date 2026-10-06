# WP7 brief: read API, snapshot publish, seed database

You are building work package 7 of the project described in `docs/PLAN.md`
(read it fully first). Then read `CLAUDE.md`, the briefs WP0 to WP6 under
`docs/briefs/`, ADR 0001, and the code under `backend/src/gwylio/`,
especially `evaluation/`, `dissemination/`, the SQLite repositories and
exports, `infrastructure/config/settings.py`, `infrastructure/codegen/` and
the CLI. Follow their conventions exactly. Project root is `gwylio/`. Do not
touch anything outside it. Do not run git.

## Principle (ADR 0001)

Production is a static SvelteKit site on Firebase Hosting reading JSON
snapshots. FastAPI is a local dev and analyst tool. The snapshot files and the
API responses are the SAME Pydantic read models serialised the same way; a
contract test proves it.

## Read models (`backend/src/gwylio/api/schemas.py`, Pydantic v2)

Every model has an identifier title and is registered with `gwylio schema` so
TypeScript types generate into `frontend/src/lib/data/types.generated.ts`
(the front end builds on these in WP8). Dates as ISO strings. Enums as their
string values.

- `Meta`: generated_at, instrument_version, latest_run_id, counts (reports by
  state, runs, sources, submissions), rubric_version, app version.
- `RequirementSetSummary` and `RequirementSetDetail` (requirements with
  scanability and groups).
- `Picture`: for a requirement set: per group of kind wbo and impact and per
  requirement: active report counts by direction, by state, coverage status,
  latest event horizon, latest verification; plus the date check counts.
- `ReportSummary` (id, title, grading string, reliability, credibility,
  report_type, state, bucket, directions summary, requirement ids, lane,
  source name, created_on, last_verified, event_horizon, appearances,
  distinct_sources) and `ReportDetail` (everything, with assessments, tags
  resolved to names, scores, history, sightings with run id and source name).
- `SourceSummary` (watchlist fields plus yield fields) and `SourcesHealth`
  (funnel trend over the last N runs, silent sources).
- `RunSummary` and `RunDetail` (funnel, requests, budget, disciplines, per
  source counts, disposition summary, credibility distribution).
- `Coverage` (both matrices with row statuses and the legend).
- `DateCheck` (findings grouped by kind).
- `ProductSummary` and `ProductDetail` (sections, markdown path, body).
- `Enums`: every closed enum with labels, for the UI legend.

## API (`backend/src/gwylio/api/app.py`, routes under `/api/v1`, GET only)

`meta`, `meta/enums`, `requirement-sets`, `requirement-sets/{id}`,
`requirement-sets/{id}/picture`, `reports` (query filters: set, requirement,
direction, state, bucket, lane, hazard, place, topic, since, q over title and
summary), `reports/{id}`, `sources`, `sources/health`, `sources/{id}/yield`,
`scan-runs`, `scan-runs/{id}`, `coverage/{set}`, `datecheck`, `products`,
`products/{id}`. 404 with a JSON body for unknown ids. CORS allowing the Vite
dev origin. One dependency providing the Database per request from Settings.
Serve the OpenAPI document; `gwylio schema` also writes
`docs/schema/openapi.json` (drift-tested).

## Publish (`backend/src/gwylio/infrastructure/snapshot.py`)

- `publish(settings, out_dirs)`: builds every read model from the database and
  writes `meta.json`, `enums.json`, `requirement_sets.json` (list of
  summaries), `requirement_set_<id>.json`, `picture_<set>.json`,
  `reports.json` (list of summaries), `reports/<id>.json` (details),
  `sources.json`, `sources_health.json`, `runs.json`, `runs/<id>.json`,
  `coverage_<set>.json`, `datecheck.json`, `products.json`,
  `products/<id>.json` into BOTH `frontend/static/data/` and
  `data/snapshots/`. Deterministic serialisation (sorted keys, two-space
  indent, trailing newline); `generated_at` comes from the injected clock so
  tests can assert byte equality. Remove stale files in the target
  directories before writing (only inside those two directories).
- Contract test: for every endpoint, `TestClient` response JSON equals the
  corresponding snapshot file JSON on the seed database.

## CLI

- `gwylio serve [--port 8000]`: uvicorn on the FastAPI app.
- `gwylio publish`: as above; prints the file count and the two directories.
- `make dev`: runs `gwylio serve` and `pnpm -C frontend dev` together (use a
  simple shell `&` with `wait`, or two Make targets documented in CLAUDE.md).
- `make publish`: `gwylio publish`.

## Seed database (`make seed`, extend WP5's)

Ensure the seed under `backend/tests/fixtures/seed/` covers: at least two
complete runs, at least eight reports across several requirements including
one `none` scanability requirement with none (so `blind_spot` appears), one
report with three distinct sources (reinforced), one matured, one faded, a
report with a passed event horizon, and one product of each built level.
Tests load the seed into an in-memory database through `rebuild` so they
never depend on a committed binary.

## Snapshot for the real data

After tests are green, in the real `data/` directory: `gwylio rebuild`
(which replays the legacy submission and the live feed run if present),
`gwylio product --level operational`, `gwylio product --level strategic`,
then `gwylio publish`. Leave the published files under `frontend/static/data/`
and `data/snapshots/` in place for the orchestrator to commit. Report the
counts.

## Tests

- Syrupy snapshot tests for every endpoint on the seed database (commit the
  `__snapshots__`).
- Filter tests on `reports` (each filter alone, two combined, `q`).
- 404s.
- Publish determinism (two publishes with the same clock are byte-identical)
  and the exporter-equals-API contract test.
- OpenAPI drift test.
- A test that `frontend/static/data/` contains no file the API does not also
  serve (the snapshot is a mirror, not a superset).

## Style rules

No em or en dashes anywhere. British English. `api` and `infrastructure`
may import contexts; contexts never import them.

## Definition of done

1. `make ci` exits 0 from `gwylio/`.
2. `gwylio serve` starts and `curl localhost:8000/api/v1/meta` returns JSON
   (then stop it).
3. `gwylio publish` on the real data directory exits 0 and
   `frontend/static/data/meta.json` exists with 35 or more reports counted.
4. Report back: commands with status lines, test counts before and after,
   deviations and why, and notes for WP8 (the exact snapshot file names and
   the TypeScript type names the front end should import).
