# Gwylio

Gwylio (Welsh: to watch, to keep watch) is an open-source intelligence
(OSINT) system for the Welsh environment. It watches public sources for
policy, research, data and hazard signals, and hands what it finds to an
analyst skill for judgement. The judged intelligence reports sit in a
register and are published as a static site, shown against requirement sets
such as the Natural Resources Wales (NRW) corporate plan.

The app collects, validates, stores and publishes. It never judges: analysis
happens outside it, in a Claude Code skill working against `docs/RUBRIC.md`,
and comes back as a file. There are no calls to a language model inside the app.

## The cycle and its commands

`gwylio` below is short for `uv run --directory backend gwylio`.

| Stage | What happens | Command |
|---|---|---|
| Direction | Requirement sets, taxonomy and watchlist are loaded and checked | `gwylio check` |
| Collection | A scan run gathers, gates and deduplicates candidates | `gwylio datecheck`, `gwylio collect`, `gwylio probe` |
| Processing | Candidates go out as a file; the judged submission comes back | `gwylio ingest <file>` |
| Intelligence | The register holds graded reports; quiet ones fade | `gwylio sweep`, `gwylio rebuild` |
| Dissemination | The monthly summary and annual assessment are written | `gwylio product`, `gwylio export`, `gwylio publish` |
| Evaluation | Is the machinery finding what it should? | `gwylio audit`, `gwylio yield` |

The judging step sits between collect and ingest and is described in
`skill/SKILL.md`. Run a whole cycle by asking Claude Code to run a Gwylio scan
with that skill installed (see `docs/DEPLOY.md` for installation notes).

## Quick start

You need Python 3.11, [uv](https://docs.astral.sh/uv/), Node 22, pnpm 10 and
GNU Make.

```bash
make setup     # install backend and frontend dependencies from the lock files
make ci        # lint, type check, tests and the static build
uv run --directory backend gwylio rebuild   # the database is gitignored: build it from the files
make dev       # read API (application programming interface) on :8000, site on :5173
```

A fresh clone already holds the register: the 35 reports imported from the
previous tool are a committed fact under `data/submissions/`, so `rebuild`
restores them. To seed an empty data directory from the old register instead,
run `gwylio import-legacy <signals.json>` once. `make seed` recreates the test
fixture data (four fake runs) used by the suites, and `make seed-screenshots`
shows the site on that richer data, with screenshots under `docs/evidence/seed/`.

Other targets: `make e2e` (Playwright with screenshots), `make schema`
(regenerate generated files), `make publish` and `make deploy` (see
`docs/DEPLOY.md`). `make help` lists them all.

Scanning needs no key for the feeds. Web and site search need a Brave Search
key (`BRAVE_API_KEY`, or a gitignored `search_keys.txt` at the root).

## Layout

```text
config/     requirement sets, taxonomy, lanes, catalogues, sources, instrument, copy
data/       the facts: candidates, instruments, submissions, sweeps, products
            derived: exports, snapshots; gitignored: gwylio.sqlite
backend/    Python 3.11: src/gwylio/{shared,reference,direction,collection,
            processing,intelligence,dissemination,evaluation,infrastructure,cli,api}
frontend/   SvelteKit (Svelte 5), static adapter; Vitest and Playwright
skill/      SKILL.md (the scan cycle) and REFERENCE.md (generated closed values)
docs/       ARCHITECTURE, DEPLOY, STATUS, PLAN, RUBRIC, GLOSSARY, adr/, schema/, evidence/
firebase.json  Makefile  CLAUDE.md  GUIDE.md
```

## Where to read next

- `GUIDE.md`: a plain-English guide for colleagues who do not write code.
- `docs/ARCHITECTURE.md`: contexts, data flow, handoff contracts, seams.
- `docs/DEPLOY.md`: publishing the site on Firebase Hosting.
- `docs/STATUS.md`: what is built, partly built and deferred, with the known limits.
- `docs/RUBRIC.md` and `skill/SKILL.md`: how reports are judged, and the cycle.
- `docs/PLAN.md` and `docs/adr/`: the approved plan and the decisions behind it.
- `CLAUDE.md`: the operating manual and the rules the tests enforce.
