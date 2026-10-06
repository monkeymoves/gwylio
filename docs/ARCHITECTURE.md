# Gwylio architecture

Gwylio (Welsh: to watch, to keep watch) is a Welsh environmental open-source
intelligence (OSINT) system. This document explains how it is built and why.
It reads on its own. The approved plan is `docs/PLAN.md`, the decisions are in
`docs/adr/`, and what is built today is in `docs/STATUS.md`.

## The shape in one paragraph

A backend in Python 3.11 holds the domain, the collectors, the command line
interface (CLI) and a small read application programming interface (API). A
front end in SvelteKit is a static site. Analysis never runs inside the app:
a Claude Code skill judges candidates against a rubric and hands its
decisions back as files. Files on disk are the facts. SQLite is a projection
rebuilt from them. The site reads JavaScript Object Notation (JSON) snapshots
that the CLI publishes.

## Bounded contexts

The contexts follow the intelligence cycle, plus a shared kernel. Each is a
Python package under `backend/src/gwylio/` and holds pure domain code with no
input or output.

- **Shared kernel** (`shared`). Small frozen value objects and the closed
  vocabularies every context uses: `CleanText` (the only place the dash rule
  is implemented), `CanonicalUrl`, `IsoDate`, `KebabId`, the clock, the
  enumerations (Discipline, Reliability, Direction, IndicatorState, Bucket and
  the rest) and the coverage rule that separates a blind spot from quiet.
  Reliability and the coverage rule live here so two contexts can apply them
  without importing each other.
- **Reference** (`reference`). The catalogues other contexts point at:
  taxonomy axes and nodes, topics, hazards, places, actors and lanes. The
  aggregate is the `ReferenceCatalogue`, a validated bundle that refuses
  duplicate or dangling ids.
- **Direction** (`direction`). What the system is asked to watch. The
  aggregate is the `RequirementSet`: a list of Priority Intelligence
  Requirements (PIRs), each a `Requirement` with a code, keywords, a
  scanability and the taxonomy nodes it is expected to cover, plus
  `RequirementGroup`s such as impact statements and well-being objectives. The
  Natural Resources Wales (NRW) corporate plan is one set loaded from
  configuration, not the spine of the schema.
- **Collection** (`collection`). Where we look and what we found. The
  aggregate is the `ScanRun`, which owns its funnel and request budget and is
  immutable once complete. Around it sit the `Source` watchlist entry, the
  versioned `QueryInstrument` with its content hash, the gates (own domain,
  negative term, relevance), deduplication by canonical URL, `Candidate`,
  `Sighting` and `Reinforcement`. Collectors satisfy the `Collector` port. They
  never score, tag or grade.
- **Processing** (`processing`). The file handoff. It holds the candidates
  file contract (`gwylio.candidates/1`), the submission contract
  (`gwylio.submission/1`), the validator that collects every problem rather
  than stopping at the first, and the ingest rules: every candidate in a run
  needs exactly one disposition, and any error writes nothing.
- **Intelligence** (`intelligence`). The register. The aggregate is the
  `IntelligenceReport`: a frozen entry with its `Grading` (reliability letter
  and credibility digit), `Assessment`s against requirements, `Scores`, tags,
  state, bucket, event horizon and an append-only history. The lifecycle
  transition table (emerging, tracking, reinforced, matured, faded, parked) and
  the date check live here. Appearances and distinct sources are derived from
  sightings, never stored by hand. Reports are never deleted.
- **Dissemination** (`dissemination`). The products: the strategic assessment
  (annual), the monthly operational intelligence summary (INTSUM) and the
  tactical alert seam. The aggregate is the `Product`, a structured document of
  sections and tables. Renderer modules hold structure only and no prose:
  every heading and standing sentence comes from `config/copy.json`.
- **Evaluation** (`evaluation`). How well the collection works: funnel trends,
  yield per source, the coverage audit (requirement by lane, taxonomy node by
  count, credibility spread) and a summary of date-check findings. Every
  function is pure and takes plain records.
- **Infrastructure, CLI and API** (`infrastructure`, `cli`, `api`). Everything
  with input or output: SQLite repositories and migrations, the Hypertext
  Transfer Protocol (HTTP) client, the concrete collectors (Brave web and site
  search, Really Simple Syndication (RSS) and Atom feeds, OpenAlex, Crossref),
  configuration loading, the file handoff code, the read models, the snapshot
  publisher, the Typer CLI (one module per verb) and the FastAPI read API.

## The dependency rule

`shared` imports no other gwylio package. A context imports only `shared`
and itself. `infrastructure`, `cli` and `api` import contexts. No context
imports `infrastructure`, `cli` or `api`. A test
(`backend/tests/unit/test_import_rules.py`) enforces this.

One consequence: processing cannot import collection, and intelligence cannot
import either. Where a file contract meets a context, the glue lives in
`infrastructure/handoff`. Facts that a context needs from another arrive as
small frozen records defined in its own `ports.py`, such as `SightingFact`
and `RunFact` in Intelligence. A second test refuses literal sentences in
the dissemination renderers, and `CleanText` is the only code that knows the
dash rule.

## Data flow

```text
 config/ (requirement sets, taxonomy, lanes, catalogues, sources, instrument, copy)
    |  gwylio check
    v
 gwylio datecheck  ---- findings ----> analyst verifies against the world
    |
    v
 gwylio collect
    |   collectors: osint_feed (always), osint_web and osint_site (Brave key),
    |   osint_academic (opt in); gates, dedup, funnel, budget
    v
 data/candidates/<run_id>.json   +   data/instruments/<version>.json
    |
    v   ANALYST (Claude Code skill, rubric 2026.10): reads every page, judges
 data/submissions/<run_id>__<n>.json
    |
    v   gwylio ingest   (validate everything; all or nothing; exit 1 writes nothing)
 SQLite register  (data/gwylio.sqlite, gitignored, a projection)
    |
    +--> gwylio sweep ----> data/sweeps/<date>__<n>.json
    +--> gwylio product --> data/products/<level>_<period>.{md,json}
    +--> gwylio export ---> data/exports/{runs,register,products}.json
    |
    v   gwylio publish
 frontend/static/data/*.json  +  data/snapshots/*.json   (same documents)
    |
    v   pnpm build (SvelteKit, adapter-static, every page prerendered)
 frontend/build  --->  firebase deploy --only hosting

 gwylio rebuild: config/ + candidates + instruments + submissions + sweeps
                 + products  --->  a fresh SQLite database
 gwylio serve:   the same read models as GET /api/v1/<name>  (development tool)
```

Everything above the SQLite box is a file on disk and is committed. The
database is rebuilt, never copied.

## Handoff contracts

Two files carry the intelligence across the boundary of the app.

- **Candidates file** (`data/candidates/<run_id>.json`, `gwylio.candidates/1`).
  Written by `collect`. It holds the run, its instrument version and hash, the
  funnel (raw hits, drops at each gate, unique, seen before, new,
  reinforcements), every candidate with its status (`new`, `seen_before` or
  `reinforcement`), every sighting and every reinforcement. Ordering is
  deterministic. A run that aborts still writes a file, with no candidates and
  a note saying why. A run that collected nothing writes a file but does not
  count towards fading. Its last printed line is `feeds: N of M responded`.
- **Submission file** (`data/submissions/<run_id>__<n>.json`,
  `gwylio.submission/1`). Written by the analyst. It holds the analyst, the
  rubric version, a disposition for every candidate, promotions (full report
  shape without derived fields), updates, reinforcements, verifications and a
  method note. An out-of-run submission has `run_id` null and is saved as
  `direct__<date>__<n>.json`. Reliability comes from the watched source,
  never from the submission. The analyst may set a state only to `matured` or
  `parked`. Hazards are hazard ids, never family ids.

Three further files record facts that cannot be re-derived on a rebuild:

- `data/instruments/<version>.json`: each instrument version a run used, once.
- `data/sweeps/<date>__<n>.json` (`gwylio.sweep/1`): what a sweep faded, and
  after how many submissions it ran.
- `data/products/<level>_<period>.json` (`gwylio.product/1`) with its
  Markdown: what a reader was told. ADR 0004 explains why a rebuild stores
  these and never renders them again.

JSON Schema for every contract is generated into `docs/schema/`, and the
analyst's closed values are generated into `skill/REFERENCE.md`. A drift test
fails when the generated files and the models disagree.

## Storage decision

Files are the facts and the database is a projection (ADR 0002). The
previous tool kept a hand-edited register and had no scan log, so its fade
rule never worked. Gwylio wants relational queries and a history a reviewer
can read in git. So candidates, instruments, submissions, sweeps and products
are committed and append-only (products are replaced per period and git keeps
the earlier version). SQLite holds the queryable view, through hand-written
repositories and three numbered migrations; there is no object-relational
mapper, because an aggregate spans several tables.

`gwylio rebuild` migrates a scratch database, loads configuration, stores
instruments, replays candidates files in the order runs started, then
submissions in `received_on` then file name order, then sweeps at the point
they ran, then products. It replaces the database only on success. A rebuilt
database reproduces every export byte for byte, which the end to end test
proves. A hand edit to the database is lost by design; a correction goes in a
later submission's `updates`.

The register was seeded from the previous tool through a legacy submission
(ADR 0003), so even the seed is a fact on disk.

## Publishing and hosting

`gwylio publish` builds every read model once and writes it twice, to
`frontend/static/data/` (what the site is built from) and `data/snapshots/`.
Serialisation is deterministic. The read API serves the same documents at
`/api/v1/<name>` through one serialising function, and a contract test checks
every published file against its API response. Production is the static site
on Firebase Hosting (ADR 0001); the API is a development and analyst tool.
The site is public by URL, which is why version 1 publishes only the
register. ADR 0005 (proposed) covers access control.

## The two horizons

Gwylio is the near-field horizon: monitoring anchored on the requirements,
verified to source and kept as a trend line. By design it finds what already
talks like the requirements. An ecological surveillance lane stretches that
reach to tree and plant disease, invasive species, avian influenza and
drought, and the third bias guard (streetlight) makes the analyst name what
the queries miss.

The far-field horizon of surprise, discontinuity and wildcards is deliberately
out of scope. It is a separate foresight exercise, kept out of the register so
speculation never dilutes the verified trend line. It would share only the
requirement sets with this system.

## Seams left for later

- **Tactical alerts.** `ProductLevel` already has a tactical level, and
  `gwylio product --level tactical` exits 4 with a "not implemented in version
  1" message. The renderer module `render_tactical.py` is the seam.
- **Geospatial and sensor disciplines.** `geoint` (geospatial intelligence)
  and `sensor` are reserved values of `Discipline`. No collector exists; a
  `Collector` adapter and, for geometry, a richer `Place`, would add them.
- **Cloud Run.** If a live API is ever needed, the FastAPI application can be
  containerised and placed behind Firebase Hosting rewrites without changing
  the data shapes (ADR 0001).
- **Firebase Authentication.** Access control is proposed in ADR 0005. A
  client-side login over static files is not access control, because the
  files stay fetchable. Real control needs the data served only after a check
  by a server or by database security rules.
- **More requirement sets.** A second set is a new file under
  `config/requirement_sets/`; products and pages already key on the set id.
- **Hosted scheduled agent.** The cycle is a skill run by hand today; nothing
  in the design prevents scheduling it.
