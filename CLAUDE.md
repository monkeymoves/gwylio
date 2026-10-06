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
make check     # ruff check, ruff format --check, mypy, svelte-check
make test      # pytest, vitest
make ci        # check, then test, then the static frontend build
make e2e       # build the site, serve it with vite preview, run Playwright, write screenshots
uv run --directory backend gwylio version   # the command line tool
```

`schema`, `seed`, `dev`, `collect`, `ingest` and `publish` are stubs until
their work packages land; each prints which one.

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
  `data/exports/register.json` is a derived export. See ADR 0002.
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
- `docs/GLOSSARY.md`: the ubiquitous language (generated, arrives in WP1).
- `docs/adr/`: architecture decision records; copy `0000-template.md` for a new one.
