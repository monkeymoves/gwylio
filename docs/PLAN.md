# Plan: Gwylio, a Welsh environmental OSINT system (new repo)

## Context

The existing NRW-Scan-Tool is a single-discipline open-source intelligence (OSINT)
tool that already runs the whole intelligence cycle at the strategic level, but it
is anchored on one requirement set (the NRW corporate plan SIs), stores its register
as hand-edited JSON, has no scan log (so its fade rule never worked), and its
dashboard is a hand-rolled single HTML file. Luke wants to start fresh in a new
repo, learning from that tool but reusing no code: a clean, domain-driven,
fully tested Welsh environmental OSINT system with an app front end, built by
Opus subagents with clean context, each package verified (tests plus Playwright
screenshots) before the next starts. Luke is asleep; the brief is "iterative,
test and work through this", and wake up to a working app.

Decisions already taken with Luke:

- Stack: Python backend (domain, collectors, CLI, small FastAPI read API) and a
  SvelteKit front end. Keep frameworks light.
- Domain anchored on the Welsh environment broadly (topics, hazards, places,
  actors, sources, requirement sets). The NRW framework is ONE requirement set
  loaded from config, not the schema's spine.
- Analysis (triage, tagging, grading) happens OUTSIDE the app via a Claude Code
  skill against a rubric. No LLM calls inside the app. The app exposes a file
  contract: candidates out, judged submissions in, validated on ingest.
- New private GitHub repo under monkeymoves, created by me.
- Hosting: Firebase Hosting. So production is a static SvelteKit site
  (adapter-static, prerendered) reading JSON snapshots the CLI publishes.
  FastAPI is a local dev and analyst tool serving the same JSON shapes. Cloud Run
  is a designed seam, not built.

Decisions I am making (change at approval if you disagree):

- Repo and package name `gwylio` (Welsh: to watch, to keep watch).
- Python 3.11 (container version), `uv`, `ruff`, `mypy --strict` on src, `pytest`
  with `hypothesis`, `respx` (HTTP cassettes) and `syrupy` (snapshots). Typer CLI,
  Pydantic v2 for config and contracts, plain `sqlite3` with hand-written
  repositories and numbered SQL migrations (no ORM: an aggregate spans several
  tables and an ORM fights that). Node 22, pnpm, Svelte 5, Vitest, Playwright.
  Makefile (no `just` in the container).
- **Files are the facts, the database is a projection.** `data/candidates/` and
  `data/submissions/` are append-only and committed; `gwylio rebuild`
  reconstructs SQLite from config plus those files. `data/exports/register.json`
  is a deterministic export committed after each ingest for readability. Git is
  the audit history. Hand edits to the database are lost on rebuild by design;
  edits go through a submission's `updates` block.
- Seed the register by importing the 35 verified signals from the old tool via a
  one-off `import-legacy` command that writes a legacy submission file (so the
  seed is itself a fact on disk). Imported reports get conservative grades
  (government B3, others C3) and a provenance history entry.
- No Brave key in this container and no Firebase login possible while Luke
  sleeps. Live scans run RSS-only; web search is exercised on recorded fixtures.
  Firebase config is written and deploy documented for Luke.

## Vocabulary (ubiquitous language, short list; full glossary generated in repo)

Contexts follow the intelligence cycle: **Direction**, **Collection**,
**Processing** (handoff), **Intelligence** (the register; analysis itself is the
skill), **Dissemination**, **Evaluation**, plus a **Reference** shared kernel.

- **Requirement set**: a Priority Intelligence Requirement list (the NRW corporate
  plan is one). **Requirement**: one PIR (an SI). **Scanability**: how far public
  sources can see it (high, medium, low, none). **Blind spot**: low or no
  scanability and no reports; never rendered as **quiet**.
- **Taxonomy**: axes with nodes; axis one is SoNaRR's eight ecosystems plus three
  resources, axis two is hazard families. **Topic, Hazard, Place, Actor**:
  reference catalogues. Hazards, not adversaries.
- **Discipline**: `osint_web`, `osint_feed`, `osint_site`, `osint_academic`;
  `geoint` and `sensor` reserved. **Collector**: adapter for one discipline.
  **Lane**: where we look. Lanes and requirements are never merged.
- **Source**: watchlist entry with a default **reliability** (Admiralty A to F).
  **Credibility** (1 to 6) is judged by the analyst per report. **Grading**: the
  pair, e.g. B2.
- **Instrument**: versioned query set with a content hash; **probe**: a query run
  that writes nothing. **Scan run**: one execution; the unit of time for
  lifecycle maths; owns the **funnel** and a **request budget**.
- **Raw hit**, **gate** (own-domain, negative term, relevance), **candidate** (a
  gated, deduped hit per **canonical URL** per run), **sighting** (candidate seen
  by a source in a run). **Index echo**: same URL re-found in the same run or
  window; not evidence. **Distinct source**: different source id.
- **Submission**: the skill's judged file. **Disposition**: fate of every
  candidate (promoted, rejected, duplicate, deferred, reinforcement).
- **Intelligence report**: the register entry. **Assessment**: direction against
  one requirement (supports, threatens, neutral, informs_baseline).
  **Indicator state** (I&W lifecycle): emerging, tracking, reinforced, matured,
  faded, parked. **Bucket**: brief, follow_up, watch, park. **Event horizon**,
  **last verified**, **history** (append-only). **Rot**: a claim that was true
  when written.
- **Product**: strategic (annual), operational **INTSUM** (monthly), tactical
  **alert** (seam only in v1). **Snapshot**: the published JSON the site reads.

## Repo layout

```
gwylio/
  Makefile  README.md  GUIDE.md  CLAUDE.md  firebase.json  .github/workflows/ci.yml
  config/   requirement_sets/nrw-corporate-plan.json  taxonomy.json  lanes.json
            reference/{topics,hazards,places,actors}.json  sources.json
            instrument.json  copy.json  settings.example.toml
  data/     gwylio.sqlite (gitignored)  candidates/<run_id>.json  submissions/<run_id>__<n>.json
            exports/register.json  products/<level>_<period>.md  snapshots/ (latest published)
  docs/     ARCHITECTURE.md  RUBRIC.md  GLOSSARY.md (generated)  adr/  schema/ (generated)
            evidence/<WPn>/*.png
  skill/    SKILL.md  REFERENCE.md (generated)
  backend/  pyproject.toml  src/gwylio/  tests/{unit,integration,api,fixtures}
     src/gwylio/shared/        values.py (CanonicalUrl, CleanText, IsoDate, KebabId), clock.py
     src/gwylio/reference/     model.py loader.py
     src/gwylio/direction/     model.py loader.py scanability.py
     src/gwylio/collection/    model.py gates.py dedup.py ports.py service.py
     src/gwylio/processing/    candidates_file.py submission.py ingest.py
     src/gwylio/intelligence/  model.py lifecycle.py datecheck.py ports.py service.py
     src/gwylio/dissemination/ model.py render_intsum.py render_strategic.py copy.py
     src/gwylio/evaluation/    funnel.py yield_.py coverage.py
     src/gwylio/infrastructure/ sqlite/{db.py,migrations/,repositories.py,export.py,rebuild.py}
                                http/client.py  collectors/{brave_web,brave_site,feed,openalex,crossref,registry}.py
                                config/  snapshot.py (publish)
     src/gwylio/cli/           main.py plus one module per verb
     src/gwylio/api/           app.py routes/ schemas.py
  frontend/ SvelteKit, Svelte 5, adapter-static; src/lib/data/ (client + generated types)
            src/routes/**  tests/ (vitest)  e2e/ (playwright)
```

Dependency rule, enforced by a test: `shared` imports nothing; context packages
import only `shared` and their own `ports`; `infrastructure`, `cli`, `api` import
contexts; no context imports `infrastructure`. `CleanText` is the only place the
em/en dash rule is implemented; persistence and the snapshot exporter accept only
`CleanText`. `CanonicalUrl` strips scheme, `www.`, fragment, trailing slash and a
known tracking-parameter list (`utm_*`, `fbclid`, `gclid`) but keeps other query
parameters (Senedd ids live there).

## Data contracts

Config (Pydantic, JSON Schema generated to `docs/schema/`, cross-references
validated by `gwylio check`):

- `requirement_sets/*.json`: id, name, version, source_doc, requirements[]
  {code, name, short, scanability, scanability_note, keywords[], expected_coverage[]},
  groups[] {id, kind (impact|wbo), name, members[]}.
- `taxonomy.json`: axes[] {id, name, nodes[] {id, name}}.
- `sources.json`: sources[] {id, name, domain, feed_url, discipline, lane, actor,
  reliability, trusted, site_pass, status, added_on, notes}.
- `instrument.json`: version, global_negative_terms[], max_requests_per_run,
  queries[] {id, discipline, lane, text, requirement_hints[], topic_hints[], negative_terms[]}.
- `copy.json`: every standing sentence and heading in products and the site.

SQLite tables (enums are TEXT validated in the domain): requirement_set,
requirement, requirement_group, requirement_group_member,
requirement_expected_coverage, taxonomy_axis, taxonomy_node, topic, hazard, place,
actor, source, instrument_version, instrument_query, scan_run, candidate,
sighting, submission, disposition, report, report_assessment, report_tag,
report_history, report_sighting, product, schema_migrations.

Handoff files:

- `data/candidates/<run_id>.json` (`gwylio.candidates/1`): run_id,
  instrument_version, funnel {raw, dropped_own, dropped_negative,
  dropped_unrelated, unique, seen_before, new, reinforcements}, candidates[]
  {candidate_id, url, canonical_url, title, snippet, published_on, source_id,
  lane, discipline, query_id, requirement_hints[], topic_hints[], trusted},
  reinforcements[] {candidate_id, report_id, matched_by}.
- `data/submissions/<run_id>__<n>.json` (`gwylio.submission/1`): run_id, analyst,
  rubric_version, dispositions[], promotions[] (full report shape minus derived
  fields), updates[] {report_id, set{}, change}, reinforcements[], verifications[],
  method_note. Ingest rules: every candidate in the run needs exactly one
  disposition (else refuse, unless `--allow-deferred`); reliability comes from
  the source, never the submission; lifecycle is recomputed from sightings, the
  analyst may only set `matured` or `parked`; any error writes nothing, exit 1.

Snapshot (`gwylio publish` -> `frontend/static/data/` and `data/snapshots/`):
`meta.json`, `requirement_sets.json`, `picture_<set>.json`, `reports.json`,
`sources.json`, `runs.json`, `coverage_<set>.json`, `datecheck.json`,
`products.json`. FastAPI serves identical shapes at `/api/v1/<name>`; a contract
test asserts exporter output equals API output on the seed database. TypeScript
types for the front end are generated from the Pydantic models by `gwylio schema`.

## Invariants the domain enforces (all tested)

- No em or en dash in any stored or rendered text (CleanText).
- Report ids kebab-case and unique; at least one assessment; enums closed;
  grading letters A to F and digits 1 to 6; dates ISO.
- Lifecycle is a transition table: `tracking` needs a sighting from a strictly
  later run; `reinforced` needs three distinct source ids or an explicit
  independent-confirmation flag; `faded` only after two consecutive quiet runs
  via `sweep`; a second sighting in the same run changes nothing; nothing is
  deleted; every mutation appends history.
- `appearances` and `distinct_sources` are derived from sightings, never stored by hand.
- A run is immutable once complete; a canonical URL appears once per run; the
  run stops collecting when `max_requests_per_run` is reached and says so.
- A `none` or `low` scanability requirement with no reports reads blind spot, not quiet.

## CLI and API

CLI verbs: `check`, `schema`, `collect [--discipline] [--dry-run]`, `probe`,
`datecheck`, `ingest <file>`, `sweep`, `export`, `rebuild`, `audit [set]`,
`yield`, `product --level --period`, `publish`, `import-legacy <signals.json>`,
`serve`.

API (GET only, `/api/v1`): `meta/enums`, `requirement-sets`,
`requirement-sets/{id}/picture`, `reports` (filters: set, requirement,
direction, state, bucket, lane, hazard, place, since, q), `reports/{id}`,
`sources`, `sources/{id}/yield`, `scan-runs`, `scan-runs/{id}`,
`coverage/{set}`, `datecheck`, `products`.

## Front end pages (v1, read-mostly, Svelte 5 runes, vanilla CSS tokens)

- `/` redirects to `/picture/nrw-corporate-plan`.
- `/picture/[setId]`: WBO, impact and requirement tiles with direction counts,
  lifecycle mix and a status chip (covered, thin, quiet, blind spot); date-check banner.
- `/reports` with URL-synced filters, client-side over the snapshot; `/reports/[id]`
  with grading badge, assessments, tags, sightings table, history timeline.
- `/sources`: watchlist, reliability, status, yield, last productive run, funnel trend.
- `/scans`, `/scans/[id]`: run list, funnel diagram, disposition breakdown.
- `/coverage/[setId]`: two heatmaps (requirement by lane; taxonomy node by count).
- `/verify`: date-check queue. `/intsum`: latest operational product. `/about`: method.

## Work packages

Each WP: I write a self-contained brief (reference files from the old tool named
for patterns only); an Opus agent with clean context builds it and runs the
suite; a second Opus verifier agent with clean context re-runs `make ci`, opens
the Playwright PNGs for UI work and reports against the brief; I review, commit
with a dated message, push. Repo green after every WP. Sonnet only for the
mechanical docs package (marked S).

- **WP0 Repo, scaffold, guardrails.** Create private `monkeymoves/gwylio`, clone to
  `/home/user/gwylio`. Monorepo layout, uv project, ruff, mypy strict, pytest,
  SvelteKit scaffold with Vitest and Playwright, Makefile (`setup check test
  e2e ci schema seed dev collect ingest publish`), CI workflow (backend,
  frontend, e2e jobs; no search network), `shared/values.py` with property
  tests, import-rule test, repo-wide dash grep test, CLAUDE.md, ADR template,
  ADR-0001 (static site on Firebase, API dev-only), ADR-0002 (files are facts).
  Done: `make ci` green on an empty domain.
- **WP1 Reference and Direction.** Catalogues, RequirementSet, Taxonomy, loaders,
  full NRW set transcribed from the old frameworks.json (data, not code),
  SoNaRR axis, lanes, `check`, `schema` (JSON Schema, TS types, GLOSSARY.md,
  REFERENCE.md generated), drift test. Done: `gwylio check` exits 0 on shipped config.
- **WP2 Collection domain.** Source, Instrument (hash), ScanRun, Candidate,
  Sighting, gates, dedup, funnel, request budget, Collector port, in-memory
  repos, RunScan with a FakeCollector, candidates file writer. Done:
  `collect --dry-run` writes a valid candidates file from fakes.
- **WP3 SQLite persistence.** db wrapper (foreign keys on, CleanText refusal),
  migration 0001, repositories for reference, direction, collection, `export`,
  `rebuild` skeleton, round-trip and rebuild-equivalence tests.
- **WP4 Collectors.** HTTP client (3 retries, exponential backoff with jitter on
  429 and 5xx, 1 request per second token bucket), brave_web, brave_site, feed
  (RSS 2.0 and Atom, stdlib XML, malformed feed yields zero hits plus a warning),
  openalex and crossref behind `GWYLIO_ACADEMIC=1`, registry. Cassette tests
  including 429 then 200. Then one live RSS-only run committed as the first real
  candidates file. Sources transcribed from the old watchlist with reliability letters.
- **WP5 Intelligence and handoff.** IntelligenceReport, Grading, lifecycle table
  (exhaustive state by event tests), datecheck, submission schema and
  validator, `ingest`, `sweep`, migration 0002, canonical-URL matching,
  `import-legacy` producing a legacy submission and ingesting it (35 reports).
  `docs/RUBRIC.md` with credibility anchors per digit and the three bias guards.
- **WP6 Evaluation and dissemination.** Funnel trends, yield, coverage audit
  with the quiet vs blind spot rule, `audit`, `yield`; Product model, INTSUM
  and strategic Markdown renderers from `copy.json`, method note reconciled to
  the run, tactical seam returning "not implemented in v1".
- **WP7 Read API and publish.** FastAPI routes and read models, seed fixture
  database, syrupy contract snapshots, OpenAPI export, `publish` snapshot
  exporter, exporter-equals-API contract test. Publish the legacy-seeded
  snapshot into `frontend/static/data/`.
- **WP8 Front end: picture and reports.** Data client over snapshots (base URL
  switchable to the API in dev), layout and tokens, `/picture/[setId]`,
  `/reports`, `/reports/[id]`, Vitest for tiles, filter bar and grading badge,
  Playwright against `vite preview` with screenshots at desktop and phone widths
  under `docs/evidence/WP8/`. Phone width: 16px gutters, no horizontal scroll.
- **WP9 Front end: health, scans, coverage, verify, intsum, about.** Heatmap and
  funnel components with Vitest, screenshots under `docs/evidence/WP9/`.
- **WP10 Skill, hosting, docs, dry run (S for docs).** `skill/SKILL.md` (datecheck,
  collect, read candidates, write submission, ingest, sweep, product, publish,
  commit) with a test that every CLI verb it names exists; `firebase.json`
  (public `frontend/build`, clean URLs) and deploy notes; README, GUIDE,
  ARCHITECTURE, CLAUDE.md operating manual; scripted dry run test (collect on
  cassettes, ingest fixture submission, product, publish) and a final
  whole-repo verifier pass against this plan.

## Verification

- `make ci` at every commit: ruff, mypy, pytest (unit, cassette integration, API
  contract, drift, import rules, dash grep), svelte-check, vitest, frontend build.
- `make e2e`: build the static site from the committed snapshot, Playwright on
  `vite preview`, screenshots written and committed; verifier agent reads the
  PNGs against the brief (empty states, blind-spot chip, phone width).
- WP10 dry run proves the whole cycle on fixtures; the legacy import plus one live
  RSS run prove it on real data.
- Final message to Luke: repo URL, what is built, how to run and deploy, what is
  left (Brave key, Firebase login, access control).

## Risks and open questions

- Firebase Hosting is public by URL; v1 publishes only the register. Firebase
  Auth is the later answer (ADR).
- Credibility grade inflation by the skill: rubric anchors per digit plus a
  credibility distribution per run on the scans page.
- A report may carry assessments against several requirement sets; the picture
  page filters by set.
- mypy strict on untyped API JSON pushes to TypedDicts in WP4; budgeted.
- Place carries name, kind, parent and optional centroid only; geometry arrives
  with a GEOINT discipline.
- Container Python is 3.11; nothing 3.12-only.
