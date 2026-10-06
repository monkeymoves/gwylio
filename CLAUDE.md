# Gwylio operating manual

Gwylio (Welsh: to watch, to keep watch) is a Welsh environmental open-source
intelligence (OSINT) system that runs the intelligence cycle from direction
through collection to dissemination. Analysis happens outside the app, in a
Claude Code skill working against a rubric; the app collects, validates,
stores and publishes.

## Run commands

Run everything from this directory (the repository root).

```bash
make setup     # uv sync (backend) and pnpm install (frontend), from the lock files
make check     # ruff, mypy, gwylio check, gwylio schema --check, svelte-check
make test      # pytest, vitest
make ci        # check, then test, then the static frontend build
make e2e       # build the site, serve it with vite preview, run Playwright, write screenshots
make schema    # regenerate JSON Schema, TypeScript types, GLOSSARY.md and skill/REFERENCE.md
uv run --directory backend gwylio check     # validate every file under config/
uv run --directory backend gwylio collect --dry-run --out /tmp/c.json   # fake collectors, nothing persisted
uv run --directory backend gwylio migrate        # create or upgrade data/gwylio.sqlite
uv run --directory backend gwylio collect --fake # fake collectors with real persistence and a candidates file
uv run --directory backend gwylio export         # write data/exports/runs.json
uv run --directory backend gwylio rebuild        # rebuild the database from config plus data files
uv run --directory backend gwylio ingest data/submissions/<stem>.json [--allow-deferred]  # all or nothing
uv run --directory backend gwylio sweep [--today YYYY-MM-DD]   # fade quiet reports; writes data/sweeps/
uv run --directory backend gwylio datecheck                    # rot findings, always exit 0
uv run --directory backend gwylio import-legacy <signals.json> # one-off seed from the old register
make seed                                        # recreate backend/tests/fixtures/seed
uv run --directory backend gwylio probe "drought" --discipline osint_feed  # try a query, stores nothing
```

`dev` and `publish` are stubs until their work
packages land; each prints which one. `gwylio collect` (no flag) runs the real collectors: feeds always,
Brave web and site search when a key is set (`GWYLIO_BRAVE_API_KEY`,
`BRAVE_API_KEY`, or a gitignored `search_keys.txt` at the root), academic
indexes with `GWYLIO_ACADEMIC=1` or `--discipline osint_academic`. A
discipline that cannot run is named and skipped (exit 0); exit 3 when none can
run. `GWYLIO_CONTACT_EMAIL` sets the User-Agent contact. `gwylio probe` uses
the real collectors; add `--fake` for the scripted ones. Live network tests
carry `@pytest.mark.live` and run only with `pytest -m live`. A scan runs osint_web,
osint_site and osint_feed by default; set `GWYLIO_ACADEMIC=1` or pass
`--discipline osint_academic` to add the academic indexes.

The query instrument (`config/instrument.json`) carries a content hash. After
changing a query, run `gwylio check`: it prints the hash the content now has.
Bump the version and store that hash; runs are comparable only while the
instrument holds still.

## Rules that are enforced, not just written down

- **Dependency rule.** `gwylio.shared` imports no other gwylio package. A
  context package (reference, direction, collection, processing, intelligence,
  dissemination, evaluation) imports only `gwylio.shared` and itself.
  `infrastructure`, `cli` and `api` may import contexts; no context imports
  them. Domain code has no input or output. Enforced by
  `backend/tests/unit/test_import_rules.py`.
- **Dash rule.** No en dash (U+2013) or em dash (U+2014) anywhere: code,
  comments, docs, tests, data or rendered output. Use commas, colons or "to"
  for ranges. `CleanText` in `gwylio/shared/values.py` is the only code that
  implements the rule; persistence and the snapshot exporter accept only
  `CleanText`. `backend/tests/unit/test_no_dashes.py` scans the whole
  repository. In tests, build the characters with `chr(0x2013)` and
  `chr(0x2014)`.
- **Files are facts.** Candidates files and submissions under `data/` are
  append-only and committed. SQLite is a projection rebuilt from configuration
  plus those files; hand edits to the database are lost on rebuild by design.
  `data/instruments/<version>.json` archives each instrument version a run
  used, so a rebuild can restore it. `data/exports/register.json` is a
  derived export. Settings come from `GWYLIO_DATA_DIR`, `GWYLIO_CONFIG_DIR`
  and `GWYLIO_DB_PATH`. `data/submissions/` replays in received_on then
  file name order, so ingest refuses an out-of-order file; `data/sweeps/`
  records fades; run `sweep` after `ingest`. A refused submission was never a
  fact: fix or remove it before the next rebuild. The rubric is
  `docs/RUBRIC.md`, version 2026.10. See ADR 0002 and 0003.
- **Generated files are never edited by hand.** `docs/schema/`,
  `docs/GLOSSARY.md`, `skill/REFERENCE.md` and
  `frontend/src/lib/data/types.generated.ts` come from `gwylio schema`.
  Change the Pydantic models in `infrastructure/config/schemas.py`, the
  glossary in `shared/glossary.py` or the files under `config/`, then run
  `make schema`. A drift test fails when they disagree.
- **Configuration is data, validated on load.** `config/` holds the taxonomy,
  lanes, reference catalogues and requirement sets. Every prose field is
  `CleanText`; every id is a kebab-case `KebabId` (so lane and node ids use
  hyphens, while enum values such as `river_basin` use underscores).
  `gwylio check` prints every problem with its file and path.
- **The collector never scores.** Collectors gate, deduplicate and record what
  they found. Tagging, grading, lifecycle and buckets are analysis, done by
  the skill and validated on ingest.

## Style

British English in prose. Spell out acronyms on first use in every document.
Python 3.11, `mypy --strict` on `backend/src`, ruff at line length 100.
Svelte 5 runes, TypeScript strict, vanilla CSS tokens in
`frontend/src/lib/styles/tokens.css`.

## Where to read next

- `docs/PLAN.md`: the approved architecture plan and the work packages.
- `docs/GLOSSARY.md`: the ubiquitous language (generated from `shared/glossary.py`).
- `skill/REFERENCE.md`: every closed value and id the analyst skill may use (generated).
- `docs/adr/`: architecture decision records; copy `0000-template.md` for a new one.
