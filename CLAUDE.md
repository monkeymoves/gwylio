# Gwylio operating manual

Gwylio (Welsh: to watch, to keep watch) is a Welsh environmental open-source
intelligence (OSINT) system that runs the intelligence cycle from direction
through collection to dissemination. Analysis happens outside the app, in a
Claude Code skill working against a rubric; the app collects, validates,
stores and publishes.

## Scan cycle

To run a scan, follow `skill/SKILL.md` (skill name `gwylio-scan`). Install it
with `ln -s "$PWD/skill" ~/.claude/skills/gwylio-scan`. Start every session
with `gwylio check` then `gwylio rebuild`: the database is gitignored, so a
fresh clone has none. The cycle is datecheck, collect, judge (write
`data/submissions/<run_id>__<n>.json`), ingest, sweep, product, export,
publish, commit, report. Commit `data/candidates`, `data/instruments`,
`data/submissions`, `data/sweeps`, `data/products`, `data/exports`,
`data/snapshots` and `frontend/static/data`; never `data/gwylio.sqlite`.

## Run commands

Run everything from this directory (the repository root). `gwylio` below is
short for `uv run --directory backend gwylio`.

```bash
make setup     # uv sync and pnpm install, from the lock files
make check     # ruff, mypy, gwylio check, gwylio schema --check, svelte-check
make test      # pytest, vitest;  make ci = check, test, then the static frontend build
make e2e       # build the site, serve it with vite preview, run Playwright, write screenshots
make schema    # regenerate JSON Schema, TypeScript types, GLOSSARY.md and skill/REFERENCE.md
make seed      # recreate backend/tests/fixtures/seed; make seed-screenshots shows it as a site
make dev       # read API (port 8000) and Vite dev server together
make deploy    # publish, build, firebase deploy --only hosting (see docs/DEPLOY.md)
make site-password  # password screen for the hosted site; stores only a hash (gitignored)
gwylio check | rebuild | migrate | datecheck [--today D] | audit [--set ID] | yield
gwylio collect [--discipline D] [--dry-run --out F | --fake] [--at INSTANT]
gwylio probe "drought" --discipline osint_feed       # stores nothing
gwylio ingest data/submissions/<stem>.json [--allow-deferred]   # all or nothing
gwylio sweep [--today D]                             # fades quiet reports; writes data/sweeps/
gwylio product --level operational|strategic [--period P] [--today D]
gwylio export | publish [--out DIR] [--at INSTANT] | serve [--port 8000]
gwylio import-legacy <signals.json>                  # one-off seed from the old register
```

Exit codes: 0 done, 1 refused or invalid (nothing written), 2 usage, 3 no
discipline can run, 4 tactical product (not built). `--at` goes only with
`collect --fake`, `collect --dry-run` and `publish`; `datecheck`, `sweep` and
`product` take `--today`.

Without a Brave key (`GWYLIO_BRAVE_API_KEY`, `BRAVE_API_KEY`, or a gitignored
`search_keys.txt` at the root) only osint_feed runs: web and site print a skip
line, and exit 3 happens only when nothing can run. Academic indexes need
`GWYLIO_ACADEMIC=1` or `--discipline osint_academic`. `GWYLIO_CONTACT_EMAIL`
sets the User-Agent contact. Live network tests carry `@pytest.mark.live` and
run only with `pytest -m live`. Changing a query in `config/instrument.json`:
run `gwylio check`, which prints the new content hash, then bump the version
and store the hash. Runs are comparable only while the instrument holds still.

## Rules that are enforced, not just written down

- **Dependency rule.** `gwylio.shared` imports no other gwylio package. A
  context package (reference, direction, collection, processing, intelligence,
  dissemination, evaluation) imports only `gwylio.shared` and itself.
  `infrastructure`, `cli` and `api` may import contexts; no context imports
  them. Domain code has no input or output. Processing cannot import
  collection, so file handoff code lives in `infrastructure/handoff`. Enforced
  by `backend/tests/unit/test_import_rules.py`.
- **Dash rule.** No en dash (U+2013) or em dash (U+2014) anywhere: code,
  comments, docs, tests, data or rendered output. Use commas, colons or "to"
  for ranges. `CleanText` in `gwylio/shared/values.py` is the only code that
  implements the rule; persistence and the snapshot exporter accept only
  `CleanText`. `backend/tests/unit/test_no_dashes.py` scans the whole
  repository. In tests, build the characters with `chr(0x2013)` and `chr(0x2014)`.
- **Files are facts.** Candidates files, instrument archives, submissions,
  sweeps and products under `data/` are committed and replayed by rebuild.
  SQLite is a projection; hand edits to it are lost by design. Submissions
  replay in received_on then file name order, so ingest refuses an out-of-order
  file. A refused submission was never a fact: fix or remove it before the next
  rebuild. Sweeps and products are recorded fact files, never re-run or
  re-rendered on rebuild (ADR 0004). `data/exports/register.json` is derived.
  Settings come from `GWYLIO_DATA_DIR`, `GWYLIO_CONFIG_DIR`, `GWYLIO_DB_PATH`.
  The rubric is `docs/RUBRIC.md`, version 2026.10. See ADR 0002 and 0003.
- **Products hold no prose.** Every heading and standing sentence lives in
  `config/copy.json` (validated blanks, CleanText). A test refuses literal
  sentences in `dissemination/render_*.py`. Reliability, the coverage rule
  and the other shared vocabulary live in `gwylio/shared`.
- **Snapshot equals API.** `api/schemas.py` holds the read models,
  `infrastructure/readmodels.py` builds them, and `infrastructure/snapshot.py`
  and `api/app.py` serialise them through one function. A contract test checks
  every published file against its API response. After changing a read model
  run `make schema`, `pytest tests/api --snapshot-update`, then `gwylio publish`.
- **Generated files are never edited by hand.** `docs/schema/`,
  `docs/GLOSSARY.md`, `skill/REFERENCE.md` and
  `frontend/src/lib/data/types.generated.ts` come from `gwylio schema`. Change
  the Pydantic models in `infrastructure/config/schemas.py`, the glossary in
  `shared/glossary.py` or the files under `config/`, then run `make schema`.
  A drift test fails when they disagree.
- **Configuration is data, validated on load.** `config/` holds the taxonomy,
  lanes, catalogues and requirement sets. Every prose field is `CleanText`;
  every id is a kebab-case `KebabId` (enum values such as `river_basin` use
  underscores). `gwylio check` prints every problem with its file and path.
- **The collector never scores.** Collectors gate, deduplicate and record.
  Tagging, grading, lifecycle and buckets are analysis, done by the skill and
  validated on ingest. The analyst never edits the database.
- **The skill and the CLI agree.** A test checks every verb named in
  `skill/SKILL.md` exists, and every verb is named there.
- **Hosting.** `firebase.json` headers and the `make deploy` recipe are pinned
  by `backend/tests/integration/test_hosting.py`; no `.firebaserc` is committed.

## Style

British English in prose. Spell out acronyms on first use in every document.
Python 3.11, `mypy --strict` on `backend/src`, ruff at line length 100. Svelte 5
runes, TypeScript strict, vanilla CSS tokens in `frontend/src/lib/styles/tokens.css`.

## Where to read next

- `README.md`, `GUIDE.md`, `docs/ARCHITECTURE.md`, `docs/DEPLOY.md`, `docs/STATUS.md`.
- `docs/PLAN.md` (approved plan), `docs/adr/` (decisions; copy `0000-template.md`),
  `docs/GLOSSARY.md` and `skill/REFERENCE.md` (generated vocabulary and closed values).
