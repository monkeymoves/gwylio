# Gwylio

Gwylio (Welsh: to watch, to keep watch) is an open-source intelligence (OSINT)
system for the Welsh environment. It watches public sources for policy,
research, data and hazard signals, hands candidates to an analyst skill for
judgement, keeps the judged intelligence reports in a register, and publishes
a static site that shows the picture against requirement sets such as the
Natural Resources Wales (NRW) corporate plan. The architecture is described in
`docs/PLAN.md` and the operating rules in `CLAUDE.md`.

## Quick start

You need Python 3.11, [uv](https://docs.astral.sh/uv/), Node 22, pnpm 10 and
GNU Make.

```bash
make setup   # install backend and frontend dependencies from the lock files
make ci      # lint, type check, unit tests and the static build
make e2e     # Playwright smoke test with screenshots in docs/evidence/
uv run --directory backend gwylio version
```

## The database

SQLite under `data/gwylio.sqlite` is a projection of `config/` plus the
facts under `data/` (candidates files and archived instrument versions), and
can be rebuilt from them at any time (see `docs/adr/0002-files-are-facts.md`).

```bash
uv run --directory backend gwylio migrate          # create or upgrade the database
uv run --directory backend gwylio collect --fake   # a run on fake collectors, stored
uv run --directory backend gwylio export           # data/exports/runs.json
uv run --directory backend gwylio rebuild          # rebuild the database from the files
```

Paths come from environment variables: `GWYLIO_DATA_DIR` (default `data`),
`GWYLIO_CONFIG_DIR` (default `config`) and `GWYLIO_DB_PATH` (default
`<data_dir>/gwylio.sqlite`). Point `GWYLIO_DATA_DIR` at a scratch directory
when trying `collect --fake`, so no fake run lands in the real `data/`.
