# WP9 brief: front end evaluation views

You are building work package 9 of the project described in `docs/PLAN.md`
(read it fully first). Then read `CLAUDE.md`, ADR 0001, the briefs WP7 and
WP8 under `docs/briefs/`, the WP8 report notes the orchestrator passes you,
and the front end as built: `frontend/src/lib/data/client.ts`,
`frontend/src/lib/data/types.generated.ts` (never edit), every component
under `frontend/src/lib/components/`, the routes, `frontend/e2e/`, and the
snapshot under `frontend/static/data/`. Project root is `gwylio/`. Do not
touch anything outside it except the frontend and `docs/evidence/`. Do not
run git.

Before writing any chart or heatmap: invoke the `dataviz` skill (Skill tool)
and follow its guidance on sequential palettes, legends, and labelling. Every
colour is paired with a number or label; the heatmap legend distinguishes
four statuses (covered, thin, quiet, blind spot) and blind spot is never a
shade of the quiet colour.

## Pages (replace the WP8 placeholders)

- `/sources`: watchlist `DataTable` (name, lane, discipline, reliability with
  label on hover, status, trusted, raw hits, unique candidates, promoted,
  promotion rate, last productive run, reading) sortable, with a lane filter;
  a "silent sources" section listing active sources with no hits; a funnel
  trend panel for the last N runs (small multiples or one grouped bar per run:
  raw, unique, new, reinforcements) with labelled axes and a source line
  "Source: gwylio scan runs".
- `/scans`: run list table (run id, started, instrument version,
  disciplines, raw, unique, new, reinforcements, requests, budget exhausted
  flag, status); `/scans/[id]`: funnel diagram (horizontal bars from raw down
  to new, each labelled with count and the drop reason), per-source counts
  table, disposition summary (counts per outcome and promotion rate), the
  credibility distribution for promotions in this run (small bar chart, digits
  1 to 6 with labels), warnings list.
- `/coverage/[setId]`: two heatmaps as accessible tables (each cell a `<td>`
  with the count as text and a background from a sequential scale; row header
  with the requirement code and `CoverageChip` for the row status; column
  headers the lane names), with a legend; a short note under each table
  explaining in one sentence what the axis is (from the `about` copy in the
  snapshot where available).
- `/verify`: date-check queue grouped by kind (passed horizon, future
  language, stale verification, never verified), each row linking to the
  report, with the detail text; a count line per group; `EmptyState` when
  clean.
- `/intsum`: the latest operational product rendered from its sections
  (headings, paragraphs, bullets, simple tables); a selector for other
  products in `products.json`; a link to the Markdown file path.
- `/about`: the method: what the system is, the collect-then-judge split,
  Admiralty grading explained with both scales, the lifecycle states, the
  three bias guards, the two horizons, and the "blind spot is not quiet"
  rule; sourced from a `frontend/src/lib/content/about.ts` constant (plain
  strings) so it can be edited without touching components.

## Tests

- Vitest: `Heatmap` (renders rows and columns, cell text equals count,
  legend lists four statuses), `FunnelDiagram` (bars ordered raw to new,
  labels present), `CredibilityBars` (six digits), the sources sort and
  filter helpers (pure).
- Playwright specs for `/sources`, `/scans`, one `/scans/<id>` from the
  snapshot, `/coverage/nrw-corporate-plan`, `/verify`, `/intsum`, `/about`,
  each asserting a key element and no horizontal scroll, screenshotting full
  page to `docs/evidence/WP9/<route>__<viewport>.png`.
- `svelte-check --fail-on-warnings`, Vitest and e2e green.

## Style

British English. No em or en dashes anywhere. Spell out acronyms once per
page. Numbers carry themselves; no adjectives.

## Definition of done

1. `make ci` and `make e2e` exit 0 from `gwylio/`; PNGs exist under
   `docs/evidence/WP9/` for every spec and viewport.
2. Open each PNG yourself and confirm legibility at phone width (tables may
   scroll horizontally INSIDE their own container, never the page), legend
   present, blind spot distinct. Fix anything wrong before reporting.
3. Report back: commands with status lines, test counts before and after,
   deviations and why, and notes for WP10.
