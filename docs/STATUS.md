# Gwylio status

Date: 6 October 2026. Written at the close of work package 10 (WP10), against
`docs/PLAN.md`, and updated the same evening after the first deployment and
the first live scan. Gwylio (Welsh: to watch, to keep watch) is a Welsh
environmental open-source intelligence (OSINT) system. This page says what is
built, what is partly built and what is deferred, and it does not round up.

Key: **built** means done and tested; **partial** says what is missing;
**deferred** says where the seam is.

## Summary

The whole cycle is built, proven on recorded data and now run once against
the live internet. The site is deployed to Firebase Hosting at
https://gwylio.web.app (project `gwylio`). The first live scan, run
`20261006T2155Z-6ae7` on 6 October 2026, collected 1,782 unique candidates
with the web, site and feed disciplines, and every one was read and judged
against the rubric: 60 promoted, 48 reinforcements, 116 duplicates, 1,540
rejected, none deferred. The register now holds 95 reports: the 35 imported
from the previous tool, all verified on 6 October 2026, and the 60 new ones.
The date check reports no findings. That scan exposed three test problems,
listed as limits 9 to 11.

Counts at the WP10 close, before the scan:

| Suite | Count |
|---|---|
| Backend (pytest) | 927 passed, 1 live test deselected |
| Front end (Vitest) | 196 passed |
| End to end (Playwright) | 24 on the committed snapshot, 26 on the seed copy |

Counts after the deployment and the scan, on the owner's machine:

| Suite | Count |
|---|---|
| Backend (pytest) | 919 passed, 7 skipped, 1 failed (limit 10), 1 live test deselected |
| Front end (Vitest) | 192 passed, 4 failed (limit 9) |
| End to end (Playwright) | not re-run |

## Known limits

1. **One live run only.** The fade rule needs two complete runs after a
   report is created, so nothing can fade until at least the third run.
   Lifecycle states beyond emerging and matured appear only from the second
   run on.
2. **Feeds are thin and one is broken.** Only two of the 43 watched sources
   (the Climate Change Committee and Audit Wales) carry a feed address. On 6
   October 2026 the Audit Wales feed returned malformed XML, so only the
   Climate Change Committee feed responded. Web and site search, with the
   Brave key in a gitignored `search_keys.txt`, carried the scan.
3. **Web search brings back a long evergreen tail.** Of 1,764 new candidates,
   1,540 were rejected, mostly as items from before October 2025 with no
   later movement or as guidance, landing and index pages. An instrument
   review (date-bounded queries, a narrower site list) should cut the noise;
   changing the instrument is a separate, versioned change.
4. **Access control is proposed only.** ADR 0005 is "proposed". The deployed
   site is public by URL, including every file under `/data/`. A client-side
   login over static files would not be access control.
5. **The tactical level is a seam.** `gwylio product --level tactical` exits 4.
6. **GEOINT (geospatial intelligence) and sensor disciplines are reserved
   values only.** There are no collectors for them, and osint_academic has not
   yet run live.
7. **Imported grades are still defaults.** The 35 imported reports were
   verified against their sources on 6 October 2026 and 15 were rewritten,
   but their grades (government B, others C, campaign groups D) still await
   analyst review.
8. **The first scan's judging was delegated.** Ten analyst subagents read the
   candidate pages in slices; the lead analyst merged duplicates across
   slices and lowered seven credibility grades on review. The method note in
   `data/submissions/20261006T2155Z-6ae7__1.json` records this.
9. **Four front-end tests read the live snapshot.** `tests/routes/verify.test.ts`,
   `Heatmap.test.ts` and `RequirementTile.test.ts` assume the committed
   snapshot under `frontend/static/data` has date check findings and a blind
   spot. After the scan it has neither, so they fail. They should read a
   fixed fixture, as the seed copy does.
10. **The hosting test fails on a linked clone.** `test_no_project_id_is_committed`
    checks that `.firebaserc` does not exist on disk. The deploy guide's
    `firebase use --add` writes it locally (it is uncommitted, as intended), so
    the test should check git tracking instead.
11. **Continuous integration fails on GitHub.** The workflow ran on the push of
    the WP10b commit and failed: the academic collector tests read
    `/root/.ccr/ca-bundle.crt`, a certificate path from the build container,
    and get a permission error on the GitHub runner.

## Plan items

### Decisions and foundations

| Plan item | Status | Notes |
|---|---|---|
| Python 3.11 backend, uv, ruff, mypy strict, pytest | built | `make check` and `make test` pass. No syntax newer than 3.11. |
| hypothesis, respx and syrupy in the test suite | built | Property tests for value objects, cassettes for HTTP, snapshots for the API contract. |
| Typer CLI, Pydantic v2 contracts, plain `sqlite3` with numbered migrations | built | Three migrations; no object-relational mapper. |
| SvelteKit, Svelte 5, Vitest, Playwright, Node 22, pnpm | built | Static adapter, every page prerendered. |
| Makefile (no `just`) | built | Plan targets plus `build`, `serve`, `frontend-dev`, `deploy`, `seed-screenshots`. |
| Repo and package name `gwylio` | built | Package named; the repository is `monkeymoves/gwylio` on GitHub. |
| Private repository `monkeymoves/gwylio` | built | Created and cloned by the owner; the clone is the working copy. |
| Files are the facts, database is a projection (ADR 0002) | built | Rebuild reproduces every export byte for byte; proven by the dry run. |
| Seed from the 35 legacy signals through a legacy submission (ADR 0003) | built | `data/submissions/legacy__2026-07-25.json`; 33 emerging, 2 matured. |
| ADR template, ADR 0001 and 0002 | built | Also 0003 to 0005. |
| CI workflow (backend, frontend, end to end; no search network) | partial | Runs on GitHub but fails on a container certificate path (limit 11). |
| Hosting on Firebase, static site, API a development tool (ADR 0001) | built | Deployed to https://gwylio.web.app; cache headers checked on the live site. |
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
| Brave web and site collectors | built | First live run on 6 October 2026: 139 of 150 requests, budget not exhausted. |
| Feed collector (RSS 2.0 and Atom, malformed feed gives zero hits and a warning) | built | Run live: the Audit Wales feed was malformed and gave a warning, as designed (limit 2). |
| OpenAlex and Crossref behind `GWYLIO_ACADEMIC=1` | partial | Built on fixtures; never run live. |
| Sources transcribed from the old watchlist with reliability letters | built | 43 sources; 41 active. |
| One live RSS-only run committed as the first candidates file | built | Superseded by a full live run with web, site and feeds, `data/candidates/20261006T2155Z-6ae7.json`. |
| Discipline `geoint` and `sensor` | deferred | Reserved values; seam is the `Collector` port. |

### Intelligence, evaluation and dissemination

| Plan item | Status | Notes |
|---|---|---|
| `ingest`, `sweep`, `import-legacy`, canonical-URL matching | built | Reinforcements count only when a submission confirms them. |
| Funnel trends, yield per source, coverage audit, credibility spread | built | `gwylio audit`, `gwylio yield`. |
| Operational intelligence summary (INTSUM) and strategic renderers from `copy.json` | built | October 2026 INTSUM and the 2026 strategic product re-rendered after the first live scan. |
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
| `make deploy` | built | Run against project `gwylio` on 6 October 2026, before and after the scan. |
| README, GUIDE, ARCHITECTURE, CLAUDE.md | built | Plus DEPLOY and this page. |
| Scripted dry run (collect on cassettes, ingest, sweep, product, export, publish, rebuild) | built | Inside `make ci`; never touches the network. |
| Final whole-repo review against the plan | built | This page. |
| Access control for the hosted site | partial | ADR 0005 written, status proposed; nothing built, and the site is now public (limit 4). |

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

1. Fix the three test problems (limits 9 to 11) so `make ci` and the GitHub
   workflow pass again.
2. Decide ADR 0005 now that the site is public.
3. Review the grades of the 35 imported reports, and skim the 60 new
   promotions, especially the seven graded 3 on second-hand reporting.
4. Run the next scan with the skill (`skill/SKILL.md`) and redeploy with
   `make deploy`; the lifecycle and the fade rule start working from the
   second run.
5. Review the instrument against the evergreen noise (limit 3) and report the
   malformed Audit Wales feed (limit 2).
