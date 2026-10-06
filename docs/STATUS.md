# Gwylio status

Date: 6 October 2026. Written at the close of work package 10 (WP10), against
`docs/PLAN.md`. Gwylio (Welsh: to watch, to keep watch) is a Welsh
environmental open-source intelligence (OSINT) system. This page says what is
built, what is partly built and what is deferred, and it does not round up.

Key: **built** means done and tested; **partial** says what is missing;
**deferred** says where the seam is.

## Summary

The whole cycle is built and proven on recorded data: collect, judge (by
file), ingest, sweep, product, export, publish, rebuild. It has not yet run
against the live internet. There are no live scan runs in the register. The
build container's egress proxy blocked the feed hosts, so the collectors are
proven on recorded fixtures and cassettes, not on the real services. The
register holds the 35 reports imported from the previous tool.

Final counts:

| Suite | Count |
|---|---|
| Backend (pytest) | 927 passed, 1 live test deselected |
| Front end (Vitest) | 196 passed |
| End to end (Playwright) | 24 on the committed snapshot, 26 on the seed copy |

## Known limits

1. **No live run yet.** `data/candidates/` does not exist. The dry run
   (`backend/tests/e2e/test_cycle.py`, part of `make ci`) uses cassettes and
   never the network. The plan's first live RSS (Really Simple Syndication)
   run was not possible.
2. **Brave key absent.** Without a Brave Search key only the osint_feed
   discipline runs. Only two of the 43 watched sources (the Climate Change
   Committee and Audit Wales) carry a feed address, so a key-less scan is
   thin. Web and site search have run only on cassettes.
3. **Firebase deploy not done.** `firebase.json`, `make deploy` and
   `docs/DEPLOY.md` are written and tested as files. The owner must log in and
   choose a project. No `.firebaserc` is committed.
4. **Access control is proposed only.** ADR 0005 is "proposed". The site is
   public by URL once deployed. A client-side login over static files would
   not be access control.
5. **The tactical level is a seam.** `gwylio product --level tactical` exits 4.
6. **GEOINT (geospatial intelligence) and sensor disciplines are reserved
   values only.** There are no collectors for them.
7. **The project is a directory, not yet a repository.** It lives under
   `gwylio/` inside the NRW-Scan-Tool repository, on branch
   `ccr-816c602f-p92i3h`. When the owner has created the empty `gwylio`
   repository on GitHub, split it out with `git subtree split --prefix=gwylio`
   and push the result. The continuous integration (CI) workflow in
   `gwylio/.github/` only takes effect after that split.
8. **Imported grades are defaults.** The 35 imported reports carry
   conservative grades (government B, others C, campaign groups D) and say so
   in their history. They await analyst review. All 35 will show as stale on
   the first date check, which is the honest state of the seed (ADR 0003).
9. **Continuous integration has not run on GitHub.** The workflow has not
   been pushed anywhere it can run. `make ci` and `make e2e` are the evidence.

## Plan items

### Decisions and foundations

| Plan item | Status | Notes |
|---|---|---|
| Python 3.11 backend, uv, ruff, mypy strict, pytest | built | `make check` and `make test` pass. No syntax newer than 3.11. |
| hypothesis, respx and syrupy in the test suite | built | Property tests for value objects, cassettes for HTTP, snapshots for the API contract. |
| Typer CLI, Pydantic v2 contracts, plain `sqlite3` with numbered migrations | built | Three migrations; no object-relational mapper. |
| SvelteKit, Svelte 5, Vitest, Playwright, Node 22, pnpm | built | Static adapter, every page prerendered. |
| Makefile (no `just`) | built | Plan targets plus `build`, `serve`, `frontend-dev`, `deploy`, `seed-screenshots`. |
| Repo and package name `gwylio` | partial | Package named; the GitHub repository is not created (limit 7). |
| Private repository `monkeymoves/gwylio`, cloned to `/home/user/gwylio` | deferred | The owner creates it, then splits with `git subtree split`. |
| Files are the facts, database is a projection (ADR 0002) | built | Rebuild reproduces every export byte for byte; proven by the dry run. |
| Seed from the 35 legacy signals through a legacy submission (ADR 0003) | built | `data/submissions/legacy__2026-07-25.json`; 33 emerging, 2 matured. |
| ADR template, ADR 0001 and 0002 | built | Also 0003 to 0005. |
| CI workflow (backend, frontend, end to end; no search network) | partial | Written at `.github/workflows/ci.yml`; never run (limit 9). |
| Hosting on Firebase, static site, API a development tool (ADR 0001) | partial | Configured and documented; not deployed (limit 3). |
| Cloud Run as a designed seam | deferred | Documented in ADR 0001 and `docs/ARCHITECTURE.md`; not built. |

### Domain, contracts and invariants

| Plan item | Status | Notes |
|---|---|---|
| Contexts: Direction, Collection, Processing, Intelligence, Dissemination, Evaluation, Reference | built | See `docs/ARCHITECTURE.md`. |
| Dependency rule enforced by a test | built | `test_import_rules.py`. |
| `CleanText` dash rule; `CanonicalUrl` rules | built | Persistence and the snapshot exporter accept only `CleanText`. |
| Whole-repo dash test | built | `test_no_dashes.py` scans every text file, these documents included. |
| Requirement set, taxonomy, sources, instrument and copy config | built | Validated by `gwylio check`; JSON Schema generated to `docs/schema/`. |
| Taxonomy axis one: SoNaRR ecosystems and resources; axis two: hazard families | built | The State of Natural Resources Report (SoNaRR) axis and hazards are in `config/taxonomy.json`. |
| Full NRW corporate plan set (12 strategic indicators, six impacts, well-being objectives) | built | One requirement set; others load from the same folder. |
| Scanability and blind spot versus quiet | built | Rule in `gwylio.shared.coverage`; shown as a chip and in the audit. |
| SQLite tables for reference, collection, intelligence and products | built | Migrations 0001 to 0003. |
| Candidates file `gwylio.candidates/1` | built | Carries more than the plan listed (see deviations). |
| Submission file `gwylio.submission/1` and its ingest rules | built | Every candidate needs one disposition; any error writes nothing. |
| Reliability from the source, lifecycle from sightings, analyst may set only matured or parked | built | Tested. |
| Lifecycle transition table, tested exhaustively | built | Including revival of a faded report to tracking. |
| `faded` only through `sweep`, after two quiet complete runs | built | Runs that collected nothing do not count. |
| Appearances and distinct sources derived from sightings | built | Never stored by hand. |
| Run immutable once complete; request budget stops collection and says so | built | Tested. |
| Date check (passed horizons, future language, stale or missing verification) | built | `gwylio datecheck`, always exit 0. |
| Report type, credibility anchors and bias guards in the rubric | built | `docs/RUBRIC.md`, version 2026.10. |

### Collection

| Plan item | Status | Notes |
|---|---|---|
| HTTP client: retries, backoff with jitter, one request per second | built | Cassette tests include 429 then 200. |
| Brave web and site collectors | partial | Built and tested on cassettes; never run with a real key. |
| Feed collector (RSS 2.0 and Atom, malformed feed gives zero hits and a warning) | partial | Built and tested on fixtures; never run against the real feeds. |
| OpenAlex and Crossref behind `GWYLIO_ACADEMIC=1` | partial | Built on fixtures; never run live. |
| Sources transcribed from the old watchlist with reliability letters | built | 43 sources; 41 active. |
| One live RSS-only run committed as the first candidates file | deferred | Blocked by the egress proxy; the first live `gwylio collect` does this. |
| Discipline `geoint` and `sensor` | deferred | Reserved values; seam is the `Collector` port. |

### Intelligence, evaluation and dissemination

| Plan item | Status | Notes |
|---|---|---|
| `ingest`, `sweep`, `import-legacy`, canonical-URL matching | built | Reinforcements count only when a submission confirms them. |
| Funnel trends, yield per source, coverage audit, credibility spread | built | `gwylio audit`, `gwylio yield`. |
| Operational intelligence summary (INTSUM) and strategic renderers from `copy.json` | built | One of each is already recorded under `data/products/`, rendered from the imported register. |
| Method note reconciled to the run | built | Part of every product. |
| Tactical alert product | deferred | `render_tactical.py` raises; the command exits 4. |

### Read API, snapshot and front end

| Plan item | Status | Notes |
|---|---|---|
| FastAPI read routes under `/api/v1` with report filters | built | Plus `requirement-sets/{id}` and `sources/health`. |
| Seed fixture database, syrupy contract snapshots, OpenAPI export | built | `docs/schema/openapi.json`. |
| `publish` snapshot; exporter equals API contract test | built | Every published file has an API route. |
| TypeScript types generated from the Pydantic models | built | `gwylio schema`; drift test. |
| `/` redirects to the picture page | built | A client-side redirect, since static hosting has no server. |
| `/picture/[setId]` with tiles, lifecycle mix, status chip and date-check banner | built | Screenshots under `docs/evidence/WP8/`. |
| `/reports` with URL-synced filters and `/reports/[id]` | built | Grading badge, assessments, sightings, history. |
| `/sources`, `/scans`, `/scans/[id]` | built | Funnel diagram and trend, disposition breakdown, credibility spread. |
| `/coverage/[setId]` with two heatmaps | built | Requirement by lane; taxonomy node by count. |
| `/verify`, `/intsum`, `/about` | built | Evidence under `docs/evidence/WP9/`. A `/products/[file]` route was added to serve product Markdown. |
| Phone width: 16px gutters, no horizontal scroll | built | Playwright runs at desktop and phone widths; see the wide-table fix in the deviations. |
| Playwright screenshots committed | built | `docs/evidence/WP0`, `WP8`, `WP9` and `seed`. |

### Skill, hosting, documentation and dry run

| Plan item | Status | Notes |
|---|---|---|
| `skill/SKILL.md` for the whole cycle, with a test that every CLI verb it names exists | built | `test_skill.py` also checks every verb is named. |
| `firebase.json` with clean URLs and cache headers; deploy notes | built | `docs/DEPLOY.md`; pinned by `test_hosting.py`. |
| `make deploy` | built | Fails with a clear line if `firebase` is missing; never run against a project. |
| README, GUIDE, ARCHITECTURE, CLAUDE.md | built | Plus DEPLOY and this page. |
| Scripted dry run (collect on cassettes, ingest, sweep, product, export, publish, rebuild) | built | Inside `make ci`; never touches the network. |
| Final whole-repo review against the plan | built | This page. |
| Access control for the hosted site | partial | ADR 0005 written, status proposed; nothing built (limit 4). |

## Deviations from the plan

1. **Ids are kebab-case.** Requirement ids are `si1` to `si12` and lane and
   node ids use hyphens. Enum values such as `river_basin` keep underscores.
2. **Validation collects every problem.** The plan said any error writes
   nothing. That still holds, and the error list is now complete, one
   `error <location>: <message>` line each, so a submission is fixed in one pass.
3. **The candidates file and the instrument archive carry more than the plan
   listed.** Candidates files record each candidate's status, every sighting
   and an aborted run's reason. `data/instruments/<version>.json` archives
   each instrument version a run used, because `config/instrument.json` holds
   only the current one.
4. **Sweeps and products are recorded fact files** (ADR 0004). The plan
   implied the fade rule and the products could be re-derived on rebuild. They
   cannot, because both depend on the day and on later ingests. So
   `data/sweeps/` and `data/products/*.json` are replayed, never re-run.
5. **Reliability and the coverage rule moved into the shared kernel**, so that
   Evaluation and Dissemination apply the same rule without importing each
   other or Direction. Direction re-exports the coverage rule.
6. **Processing cannot import Collection**, so the file handoff code lives in
   `infrastructure/handoff` rather than in `processing/`.
7. **Product renderer modules hold no prose.** Every heading and standing
   sentence is in `config/copy.json`, and a test refuses literal sentences in
   the renderers. This is stricter than the plan, which only said products
   render from copy.
8. **The snapshot holds more files than the plan listed**: enums, source
   health, a document per report and per product, and a requirement set
   detail file.
9. **The ProductView wide-table fix.** A product table with many columns (the
   method note's runs table has nine) overflowed at phone width. The product
   view now sets a wide table smaller and scrolls it inside its own frame, so
   the page itself does not scroll sideways.
10. **`migrate` and `version` commands were added** to the plan's CLI verbs.

## What the owner should do next

1. Create the empty `gwylio` repository on GitHub and split this directory
   into it (limit 7).
2. Add a Brave Search key and run the first live scan with the skill
   (`skill/SKILL.md`); commit what it produces.
3. Run `firebase login` and `firebase use --add`, then `make deploy`
   (`docs/DEPLOY.md`).
4. Decide ADR 0005 before publishing anything that is not already public.
5. Review the grades of the 35 imported reports.
