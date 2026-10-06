# ADR 0002: Files are the facts; the database is a projection

- Status: accepted
- Date: 2026-10-06
- Deciders: Luke Maggs, with the planning agent

## Context

The previous tool stored its register as a hand-edited JavaScript Object
Notation (JSON) file with no scan log, so it could not reconstruct what had
been seen when, and its fade rule never worked. Gwylio needs relational
queries (reports by requirement, sightings by run, yield by source) but also
needs a history that a reviewer can read in git and that survives a corrupted
or deleted database.

## Decision

- `data/candidates/<run_id>.json` (what a scan run collected) and
  `data/submissions/<run_id>__<n>.json` (what the analyst judged) are the
  facts. They are append-only: never edited after they are written, only
  followed by later files. They are committed to git.
- SQLite (`data/gwylio.sqlite`) is a projection. `gwylio rebuild`
  reconstructs it from configuration plus the candidates and submissions on
  disk, in order. The database file is not committed.
- `data/exports/register.json` is a deterministic export of the register,
  committed after each ingest so the current state is readable in a diff. It
  is derived and is never read back as input.
- Changes to existing intelligence reports go through a submission's
  `updates` block, so they too are facts on disk. Hand edits to the database
  are lost on rebuild, by design.
- Git is the audit history: one commit per scan or ingest, with a dated message.

## Consequences

- The whole register can be rebuilt and checked at any time; a rebuild
  equivalence test proves the projection matches.
- Correcting a mistake means writing a new submission, never rewriting an old
  file. That is slower for small fixes but keeps the history honest.
- Ingest must be all or nothing: any validation error writes nothing.
- The data directory grows with every run; that is acceptable at a few runs a
  month and can be archived by year if it ever matters.
- Seeding from the previous tool also goes through a file: `import-legacy`
  writes a legacy submission and ingests it, so the seed is itself a fact.

## Alternatives considered

- **Database as the source of truth with backups.** Simpler writes, but no
  readable history and no way to see why a report changed.
- **JSON register edited in place.** What the previous tool did; it lost the
  scan log and mixed facts with derived state.
- **Event store with a framework.** More machinery than a few files per month
  need.

## Addendum: what persistence added (work package 3)

- `data/instruments/<version>.json` joins the facts. A candidates file names
  its instrument by version and hash only, and `config/instrument.json`
  holds only the current version, so `gwylio collect` archives each version
  it uses, once, in the same format. A rebuild stores every archived version.
- A run that aborts writes a candidates file too (`run_status: aborted`, no
  candidates, a note saying why), so the aborted run in the database can also
  be rebuilt.
- A stored run writes its files inside its database transaction, before the
  commit: if the commit fails the file stays and a rebuild restores the run,
  never the other way round.
- Rebuild replays runs in the order they started (run ids sort only to the
  minute) and builds into a scratch file, replacing the database only on success.

## Addendum: what the register added (work package 5)

- `data/submissions/<stem>.json` replay after every candidates file, in
  `received_on` then file name order, through the same ingest as `gwylio
  ingest`. Because the order is fixed by the files, ingest refuses a
  submission that would sort before one already ingested. A run submission
  is named `<run_id>__<n>`, an out-of-run one `direct__<received_on>__<n>`,
  and the legacy import `legacy__<received_on>` (ADR 0003).
- `data/sweeps/<on>__<n>.json` joins the facts. The fade rule depends on
  which runs and sightings existed when `gwylio sweep` ran, so a rebuild
  applies the fades a sweep recorded rather than re-running the rule; each
  file records how many submissions had been ingested, which places it among
  them. A sweep that fades nothing writes no file.
- A rebuild checks foreign keys at its commit, because a run can record a
  reinforcement of a report that a later-replayed submission created.
- A submission refused by ingest was never a fact: fix it (or remove it)
  before the next rebuild, which refuses any submission that does not ingest.
