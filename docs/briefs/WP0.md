# WP0 brief: repo scaffold and guardrails

You are building work package 0 of the project described in `docs/PLAN.md`
(read it first, fully). Project root is this directory, `gwylio/`. It is a
standalone project that will later be split into its own git repository, so:

- Treat `gwylio/` as the repository root. Never read, import or modify anything
  outside it except the reference files the plan names in the old tool (for
  patterns only, never code reuse).
- Do not run git commands. The orchestrator commits.
- Paths below are relative to `gwylio/`.

## Environment facts

- Python 3.11.15, `uv` 0.8.17, Node 22, pnpm 10, `make`. No `just`.
- Chromium for Playwright is preinstalled at `/opt/pw-browsers`
  (`PLAYWRIGHT_BROWSERS_PATH` is set; `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1`).
  Never run `playwright install`.
- Outbound HTTPS goes through a proxy with a CA bundle at
  `/root/.ccr/ca-bundle.crt`. If `uv` or `pnpm` fail TLS, read
  `/root/.ccr/README.md` for the per-tool fix. Never disable TLS verification.
- No search API keys. Nothing in this package touches the network at runtime.

## Deliverables

### Backend (`backend/`)

- `pyproject.toml` managed by uv: package `gwylio`, src layout
  (`backend/src/gwylio/`), `requires-python = ">=3.11"`. Runtime deps: typer,
  pydantic>=2, fastapi, httpx, uvicorn. Dev deps: pytest, pytest-cov,
  hypothesis, respx, syrupy, ruff, mypy. Commit `uv.lock`.
- `ruff` configured for lint and format (line length 100, select E, F, I, B,
  UP, N, SIM, RUF). `mypy --strict` over `src/`, relaxed on `tests/`.
- Package skeleton with empty `__init__.py` for every context in the plan's
  layout: shared, reference, direction, collection, processing, intelligence,
  dissemination, evaluation, infrastructure (with sqlite, http, collectors,
  config subpackages), cli, api. Each context gets a one-paragraph module
  docstring in its `__init__.py` saying what belongs there.
- `src/gwylio/shared/values.py`: frozen value objects, all with `__slots__`
  or dataclass(frozen=True), full type hints, docstrings:
  - `CleanText(str)`: a `str` subclass whose constructor raises `ValueError`
    naming the offending code point if the text contains U+2013 or U+2014.
    Also normalises CRLF to LF and strips trailing whitespace per line. This is
    the ONLY place in the codebase that implements the dash rule.
  - `CanonicalUrl`: built from any URL string. Lower-cases scheme and host,
    drops the scheme, drops a leading `www.`, drops the fragment, drops a
    trailing slash on the path, removes tracking query parameters
    (`utm_*`, `fbclid`, `gclid`, `mc_cid`, `mc_eid`) but keeps every other
    query parameter in their original order, and keeps the port only if
    non-default. Exposes `.value` (the canonical string) and `.host`.
    Idempotent: `CanonicalUrl(c.value).value == c.value`.
  - `IsoDate`: wraps `datetime.date`, parses strictly `YYYY-MM-DD`, exposes
    `.value`, comparison operators and `__str__`.
  - `KebabId`: lowercase `[a-z0-9]+(-[a-z0-9]+)*`, max 80 chars, raises on
    anything else.
- `src/gwylio/shared/clock.py`: `Clock` Protocol with `today() -> date` and
  `now() -> datetime` (UTC, aware); `SystemClock` and `FixedClock(date_or_dt)`.
- `src/gwylio/cli/main.py`: Typer app named `gwylio` with a `version` command
  only (prints the package version). Registered as a console script.
- Tests (`backend/tests/`):
  - `unit/shared/test_values.py`: table tests plus Hypothesis property tests
    (CanonicalUrl idempotence; CleanText accepts any text without the two
    dashes; KebabId round-trips). The test must build the dash characters
    with `chr(0x2013)` and `chr(0x2014)` so the file itself stays clean.
  - `unit/test_import_rules.py`: AST-based check over `src/gwylio` enforcing:
    `shared` imports no other gwylio package; a context package (reference,
    direction, collection, processing, intelligence, dissemination,
    evaluation) imports only `gwylio.shared` and itself; `infrastructure`,
    `cli`, `api` may import contexts; no context imports `infrastructure`,
    `cli` or `api`.
  - `unit/test_no_dashes.py`: walks the project tree from `gwylio/` root
    (skip `.git`, `node_modules`, `.venv`, `build`, `.svelte-kit`, binary
    files, `uv.lock`, `pnpm-lock.yaml`) and fails naming file and line for any
    U+2013 or U+2014. Build the characters with `chr()`.
  - `conftest.py` with a `fixed_clock` fixture.

### Frontend (`frontend/`)

- SvelteKit with Svelte 5 (runes), TypeScript strict, `@sveltejs/adapter-static`
  with `prerender = true` in the root layout and `fallback` unset. Package
  manager pnpm; commit `pnpm-lock.yaml`. Use `pnpm dlx sv create` or write the
  files directly, whichever is more reliable offline-ish; no demo app content.
- Vitest configured with `@testing-library/svelte` and jsdom; one passing
  component test for a trivial `Badge.svelte` in `src/lib/components/`.
- Playwright config at `frontend/e2e/` using `webServer` that runs
  `pnpm build && pnpm preview --port 4173`, project `chromium` only, two
  viewports named `desktop` (1280x800) and `phone` (390x844). One smoke spec
  that loads `/` and screenshots to `../docs/evidence/WP0/home__<viewport>.png`.
  Point `executablePath` or `channel` at the preinstalled Chromium if the
  default resolution fails.
- A minimal root layout with a header reading "Gwylio" and a `+page.svelte`
  with a one-line placeholder. CSS tokens file `src/lib/styles/tokens.css`
  with light and dark values (prefers-color-scheme), body background set
  explicitly, 16px side gutter at phone width, no horizontal scroll.
- `svelte-check` passes.

### Root

- `Makefile` with phony targets: `setup` (uv sync, pnpm install),
  `check` (ruff check, ruff format --check, mypy, svelte-check),
  `test` (pytest, vitest run), `e2e` (playwright test), `ci` (check then test
  then frontend build), `schema seed dev collect ingest publish` as stubs
  that echo "not yet implemented (WPn)" and exit 0. Backend commands run via
  `uv run --project backend`; frontend via `pnpm -C frontend`.
- `.github/workflows/ci.yml`: jobs `backend` (uv sync, ruff, mypy, pytest),
  `frontend` (pnpm install, svelte-check, vitest, build), `e2e` (needs both,
  installs Playwright chromium with `pnpm exec playwright install chromium
  --with-deps`, runs the spec, uploads `docs/evidence` as an artifact).
  No secrets referenced.
- `.gitignore` (Python, Node, `.venv`, `data/gwylio.sqlite`, `.svelte-kit`,
  `build`, `test-results`, `playwright-report`).
- `CLAUDE.md`: short operating manual for this repo: what it is (two
  sentences), the run commands, the dependency rule, the dash rule, the
  "files are facts" rule, the "collector never scores" rule, and a pointer to
  `docs/PLAN.md`, `docs/GLOSSARY.md` (to come) and `docs/adr/`.
- `docs/adr/0000-template.md`, `docs/adr/0001-static-site-on-firebase.md`
  (static SvelteKit on Firebase Hosting reading published snapshots; FastAPI
  is a dev and analyst tool; Cloud Run is a seam), `docs/adr/0002-files-are-facts.md`
  (candidates and submissions are append-only facts; SQLite is a projection
  rebuilt from them; register.json is a derived export).
- `README.md`: one paragraph and the quick start.

## Style rules for everything you write

- No em dashes or en dashes anywhere, including comments, docs and tests.
  Use commas, colons, or "to" for ranges.
- British English in prose. Spell out acronyms on first use in docs.
- Domain code has no I/O. Infrastructure has the I/O.

## Definition of done

1. `make ci` exits 0 from `gwylio/`.
2. `make e2e` exits 0 and the two PNGs exist under `docs/evidence/WP0/`.
3. Report back: the exact commands you ran with their final status lines,
   the test counts, every deviation from this brief and why, and anything the
   next package should know (tool quirks, versions pinned).
