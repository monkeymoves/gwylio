# WP8 brief: front end core, the picture and the reports

You are building work package 8 of the project described in `docs/PLAN.md`
(read it fully first). Then read `CLAUDE.md`, ADR 0001, the briefs WP0 and
WP7 under `docs/briefs/`, the WP7 report notes the orchestrator passes you,
and the front end as it stands: `frontend/svelte.config.js`,
`frontend/src/routes/+layout.svelte`, `frontend/src/lib/styles/tokens.css`,
`frontend/src/lib/data/types.generated.ts` (the generated TypeScript read
models: never edit), `frontend/e2e/`, `frontend/tests/`. Look at the
published snapshot under `frontend/static/data/` to see the real data shapes
and ids. Project root is `gwylio/`. Do not touch anything outside it except
the frontend and `docs/evidence/`. Do not run git.

Before writing any chart, tile, bar or colour: invoke the `dataviz` skill
(Skill tool) and follow its palette and accessibility guidance. Direction
colours (supports, threatens, neutral, informs_baseline) must be a
colour-blind-safe set and every colour is always paired with a text label.

## Architecture

- Svelte 5 runes, TypeScript strict, `@sveltejs/adapter-static`, every route
  prerendered. The built site has NO runtime dependency on the API: pages load
  data from `/data/*.json` (the snapshot in `static/data/`). Dynamic routes
  (`/picture/[setId]`, `/reports/[id]`) declare `entries` from the snapshot so
  every page exists as a static HTML file and deep links work on Firebase
  Hosting without a fallback.
- `src/lib/data/client.ts`: typed loaders (`loadMeta`, `loadPicture(setId)`,
  `loadReports`, `loadReport(id)`, ...) over a `base` that defaults to
  `/data` and can be switched to the API with `PUBLIC_GWYLIO_API_BASE`
  (`.env.example`); the type names come from `types.generated.ts`.
- Layout: header with the site name, a nav (Picture, Reports, Sources, Scans,
  Coverage, Verify, INTSUM, About; routes not yet built render a short
  "arrives in WP9" page so the nav is complete), a footer with generated_at
  and instrument version from meta. 16px side gutter at phone width, max
  content width about 1200px, no horizontal scroll at 390px. Light and dark
  via `prefers-color-scheme` using the tokens file; body background explicit.
- Shared components in `src/lib/components/`: `GradingBadge` (shows "B2"
  with a title attribute spelling out both labels), `DirectionBar` (stacked
  proportions with counts and labels), `StateChip`, `CoverageChip` (covered,
  thin, quiet, blind spot; blind spot visually distinct and labelled "blind
  spot: not scannable", never styled like quiet), `FilterBar`, `EmptyState`,
  `DataTable` (sortable headers, keyboard accessible).

## Pages

- `/` redirects to `/picture/nrw-corporate-plan` (prerendered redirect page
  with a meta refresh and a link, since static hosting has no server
  redirect).
- `/picture/[setId]`: date-check banner when findings exist (counts by kind,
  link to Verify); a tile per WBO group, then per impact group, then per
  requirement. A requirement tile shows code, short name, counts by direction
  as a `DirectionBar`, state mix as small chips, `CoverageChip`, latest
  horizon and verification dates; clicking a tile navigates to `/reports?
  requirement=<id>`. Groups show aggregated bars. Section headings explain
  what a WBO and an impact are in one line each (copy from the snapshot's
  requirement set names and the `about` text; no literal headings beyond
  these).
- `/reports`: `FilterBar` with requirement, direction, state, bucket, lane,
  hazard, topic, place, grade (reliability letter, credibility digit) and a
  text search; filters are synced to the URL query string and restored on
  load; filtering is client-side over `reports.json`; results in a
  `DataTable` with grading badge, title (link), directions, state, lane,
  source, last verified; a count line "N of M reports"; `EmptyState` when
  nothing matches.
- `/reports/[id]`: title, grading badge with both labels, report type, state
  and bucket chips, summary and notes as paragraphs, assessments as a list of
  requirement code plus name plus direction label, tags (topics, hazards,
  places), scores table, event horizon and verification with a "stale" mark
  when the date check flags it, sightings table (run, source, discipline),
  history timeline (date, kind, change), source link opening in a new tab
  with `rel="noopener"`.

## Tests

- Vitest with Testing Library for `GradingBadge`, `DirectionBar` (labels and
  counts present, zero handled), `CoverageChip` (blind spot text present and
  distinct class), `FilterBar` (emits a filter change, URL sync helper pure
  function tested), the client-side filter function (pure, table-driven), and
  the URL query parse and serialise round trip.
- Playwright (reuse the WP0 harness: `desktop` and `phone` projects): specs
  for `/picture/nrw-corporate-plan`, `/reports`, `/reports?requirement=si4&
  direction=threatens`, and one `/reports/<id>` taken from the snapshot. Each
  spec asserts a key element (the blind spot chip exists on SI12; the filter
  count line matches a computed expectation from the snapshot; the detail
  page shows the grading badge) and that there is no horizontal scroll, then
  screenshots full page to `docs/evidence/WP8/<route>__<viewport>.png`.
- `svelte-check` with `--fail-on-warnings` stays green; Vitest and e2e green.

## Style

British English in UI copy. No em or en dashes anywhere, including UI
strings and tests. Spell out acronyms once per page where they appear (WBO,
INTSUM). Numbers in tiles are the data, so no adjectives.

## Definition of done

1. `make ci` and `make e2e` exit 0 from `gwylio/`; PNGs exist under
   `docs/evidence/WP8/` for every spec and viewport.
2. Open each PNG yourself (Read tool) and confirm: readable at phone width,
   16px gutters, blind spot chip visibly distinct, no overlapping text.
   Mention anything that looks wrong and fix it before reporting.
3. Report back: commands with status lines, test counts before and after,
   deviations and why, and notes for WP9 (components available, data client
   functions, how filters and URL sync work).
