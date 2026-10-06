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
