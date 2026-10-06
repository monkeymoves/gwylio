# WP5 brief: Intelligence register, submissions, ingest, sweep, date check, legacy import

You are building work package 5 of the project described in `docs/PLAN.md`
(read it fully first). Then read `CLAUDE.md`, the briefs WP0 to WP4 under
`docs/briefs/`, and the code under `backend/src/gwylio/`: the value objects,
the `collection` models and ports (Candidate, Sighting, ScanRun,
`KnownReports`), `processing/candidates_file.py`, the SQLite layer
(`infrastructure/sqlite/`: db guard, migrations, repositories, export,
rebuild), the config loaders and `Settings`, and the Typer CLI. Follow their
conventions exactly. Project root is `gwylio/`. Do not touch anything outside
it except to READ the reference files below. Do not run git.

## Reference material (read, never reuse code)

- `/home/user/NRW-Scan-Tool/RUBRIC.md`: the old triage rubric, lifecycle rules,
  bias guards and editorial contract. You will rewrite it for the new model.
- `/home/user/NRW-Scan-Tool/data/signals.json`: the old register, 35 signals.
  Fields: id, title, url, source (an organisation name), signal_type,
  date_found, last_seen, appearances, sis[] {si, direction}, impacts[], lens,
  scan_lane, lifecycle, bucket, scores {evidence_strength, novelty, confidence,
  potential_impact, time_horizon}, event_horizon, last_verified, summary,
  notes, owner, history[] {date, change}.
- `/home/user/NRW-Scan-Tool/register.py` lines 360 to 470 for the old date
  check behaviours (patterns only).

## Domain (`backend/src/gwylio/intelligence/`, pure)

`model.py`

- Enums: `ReportType` (policy, legislation, research, data_release, funding,
  partnership, international, legal, environmental, market, incident),
  `Direction` (supports, threatens, neutral, informs_baseline),
  `IndicatorState` (emerging, tracking, reinforced, matured, faded, parked),
  `Bucket` (brief, follow_up, watch, park), `Level` (low, medium, high),
  `TimeHorizon` (immediate, near_term, medium_term, long_term),
  `Credibility` (1 to 6 with labels: confirmed, probably_true, possibly_true,
  doubtful, improbable, cannot_be_judged). Reuse `Reliability` from
  `collection.model` only if the import rules allow a context to import
  another context; they do not, so move `Reliability` into `gwylio.shared`
  (a shared value) and update collection to import it from there.
- `Grading(reliability, credibility)` with `__str__` like "B2".
- `Assessment(requirement_id, direction)`; `Scores(evidence, novelty,
  confidence, potential_impact, time_horizon)`; `HistoryEntry(on: IsoDate,
  kind: created|sighted|state_changed|verified|updated|imported|faded|revived,
  change: CleanText)`.
- `IntelligenceReport(id: KebabId, title, url, canonical_url, source_id |
  None, source_name, actor_id | None, report_type, grading, assessments
  (non-empty), topics, hazards, places, scores, state, bucket, event_horizon |
  None, last_verified | None, summary, notes, owner | None, created_on,
  created_run_id | None, independent_confirmation: bool, history: tuple[
  HistoryEntry, ...], sighting_ids: tuple[str, ...])`. Frozen; every mutation
  method returns a new instance with a history entry appended. `appearances`
  and `distinct_sources` are computed by the service from the sightings, never
  stored on the report.

`lifecycle.py`

- Events: `Sighted(run_id, source_id, on)`, `MarkMatured(on, change)`,
  `MarkParked(on, change)`, `Fade(on, change)`, `ConfirmIndependently(on,
  change)`, `Verify(on, note)`.
- `transition(report, event, context) -> IntelligenceReport` where context
  carries the derived counts (`appearances_after`, `distinct_sources_after`,
  `is_later_run`). Rules: emerging becomes tracking on a sighting from a
  strictly later run than `created_run_id` (or than the first sighting's run
  when created outside a run); emerging or tracking becomes reinforced when
  distinct sources reach 3 or on `ConfirmIndependently`; a sighting in the same
  run as an existing sighting changes nothing but is still recorded; matured
  and parked are reachable from any active state (emerging, tracking,
  reinforced) and only by analyst events; faded is reachable only via `Fade`
  from an active state; a sighting on a faded report revives it to tracking
  with a `revived` history entry; parked and matured ignore sightings except
  to record them. Nothing is deleted. Every transition appends history.
  Illegal events raise `IllegalTransition`.

`datecheck.py`

- `DateCheckFinding(report_id, kind: passed_horizon | future_language |
  stale_verification | never_verified, detail, severity: warn | act)`.
- `date_check(reports, today, phrases) -> list[DateCheckFinding]`:
  passed_horizon when `event_horizon < today` and no history entry dated on or
  after the horizon; future_language when an active report's title, summary
  or notes contains a configured future-framed phrase (`config/datecheck.json`
  holds the phrase list: upcoming, forthcoming, will be published, due to,
  expected to, consultation closes, later this year, next year, imminent,
  about to); stale_verification when `last_verified` is older than 45 days;
  never_verified when missing. Pure function taking `today`.

`ports.py`: `ReportRepository` (get, list, save, list_active, by canonical url,
by normalised title), `SubmissionRepository` (record submission and
dispositions), plus a `SightingLookup` to derive counts from the collection
tables (define the protocol here; implement in infrastructure).

`service.py`

- `IngestSubmission`: validates a `Submission` (see below) and applies it in
  one transaction: records the submission; records dispositions; creates
  promoted reports (reliability taken from the source when `source_id` is
  known, else from the submission's `reliability_if_unknown_source`, which the
  validator requires in that case); links candidate sightings to reports for
  promotions and reinforcements and runs `Sighted` transitions; applies
  `updates` (only matured, parked, bucket, owner, notes, summary, title,
  event_horizon are settable; anything else is refused); applies
  `verifications`. Any error anywhere means nothing is written and every
  error is returned.
- `Sweep(today)`: for every active report, take the two most recent complete
  runs that started after the report's creation; if both exist, neither has a
  sighting of the report, and no history entry is dated after the earlier run,
  apply `Fade`. Returns the list of faded ids. Log each in history.
- `KnownReportsAdapter` implementing the collection `KnownReports` port over
  `ReportRepository` (canonical URL first, then exact normalised title).

## Processing (`backend/src/gwylio/processing/submission.py`, `ingest.py`)

- Pydantic model `Submission` (`schema: "gwylio.submission/1"`): `run_id |
  None` (None for out-of-run submissions such as the legacy import or a direct
  analyst addition), `analyst`, `rubric_version`, `received_on`,
  `dispositions[]` {candidate_id, outcome: promoted | rejected | duplicate |
  deferred | reinforcement, reason, report_id | None}, `promotions[]` (the
  report shape minus derived and server-set fields: id, from_candidate | None,
  title, url, source_id | None, source_name, actor_id | None, report_type,
  credibility, reliability_if_unknown_source | None, assessments, topics,
  hazards, places, scores, bucket, event_horizon, last_verified, summary,
  notes, owner, state_override: matured | parked | None), `updates[]`
  {report_id, set: {...}, change}, `reinforcements[]` {report_id,
  candidate_id}, `verifications[]` {report_id, verified_on, note},
  `method_note`.
- Validator rules (every failure is collected, not raised one at a time):
  when `run_id` is set, every candidate in that run's candidates file has
  exactly one disposition unless `allow_deferred`; promoted dispositions name
  a promotion and vice versa; promotion ids are kebab-case and not already in
  the register; a promotion's canonical URL must not already belong to a
  report (that is a reinforcement); requirement ids, topic, hazard, place,
  actor and source ids exist; credibility in range; reliability provided when
  the source is unknown; `set` keys limited as above; dash rule via CleanText.
- Register the Submission model with `gwylio schema` (JSON Schema, TS type,
  REFERENCE.md). Extend the drift test fixtures.

## Infrastructure

- Migration `0002_intelligence.sql`: report, report_assessment, report_tag
  (kind: topic | hazard | place), report_history, report_sighting,
  submission, disposition. CHECK constraints on enums.
- SQLite `ReportRepository`, `SubmissionRepository`, `SightingLookup`.
- `export.py`: add `data/exports/register.json` (every report with history,
  sighting ids, derived appearances and distinct_sources, sorted by id;
  deterministic) and keep `runs.json`.
- `rebuild.py`: after replaying candidates files, replay
  `data/submissions/*.json` in `received_on` then filename order through
  `IngestSubmission` (with `allow_deferred` true during rebuild so historic
  files always replay). Rebuild equivalence test extended to reports.
- `KnownReportsAdapter` wired into `collect` so reinforcements are detected
  from WP5 onward.

## CLI

- `gwylio ingest <file> [--allow-deferred]`: validate and apply; prints a
  summary table or the error list; exit 1 on any error. The file is expected
  to already sit under `data/submissions/`; if it is elsewhere, copy it there
  first (the file is the fact).
- `gwylio sweep`: apply the fade rule; print faded ids.
- `gwylio datecheck`: print findings grouped by kind; exit 0 always (it
  informs, it does not block).
- `gwylio import-legacy <signals.json> [--received-on DATE]`: writes
  `data/submissions/legacy__<received-on>.json` as an out-of-run submission
  and ingests it. Mapping (also write it up as `docs/adr/0003-legacy-import.md`):
  old `sis[].si` "SI4" to assessment requirement id "si4"; direction verbatim;
  `signal_type` to `report_type` (same names); `scores.evidence_strength` to
  `scores.evidence`; credibility from evidence_strength (high 2, medium 3,
  low 4); `source_id` by matching the URL host against `config/sources.json`
  domains (subdomains match), else None with `source_name` from the old
  `source` and `reliability_if_unknown_source` B when old `lens` is
  government, otherwise C; `scan_lane` to the WP1 lane ids (write the mapping
  table in the ADR); `lifecycle` matured to `state_override: matured`, parked
  to parked, everything else left to the lifecycle (so they land as emerging
  with no sightings; appearances from the old file are NOT recreated as
  sightings, because index echo was the old tool's lesson); topics and
  hazards: a small keyword mapping from old cluster hints and title words to
  WP1 topic and hazard ids, documented and conservative (empty is fine);
  places: `wales` for every report; old `history[]` carried as `imported`
  entries verbatim plus one final entry "Imported from the NRW SI horizon
  register (signals.json, scan date 2026-07-25). Grading defaulted on import
  and awaits analyst review." `last_verified` and `event_horizon` verbatim.
- `make seed`: migrate, `collect --fake` into `backend/tests/fixtures/seed/`,
  plus a hand-written fixture submission for that fake run under the same
  directory, ingested; this seed database is what WP7's API tests will use.
  Make the seed script idempotent (delete and recreate).

## Rubric (`docs/RUBRIC.md`)

Rewrite the old rubric for the new model, in the same plain voice, with:
the promotion test (external, consequential, verifiable from the page, new or
moved); Admiralty grading with one-line anchors for each reliability letter
and each credibility digit and three worked examples; the assessment and
tagging rules; scoring norms for weak signals; the three bias guards
(optimism, mainstream, streetlight) each as a question to ask before closing a
pass; the lifecycle rules as the code implements them; date sensitivity; the
editorial contract for products (10 to 12 promotions per run headline
throttle, non-government voices, quiet reported as quiet, blind spot never
reported as quiet, method note required). `rubric_version` "2026.10".

## Tests

- Lifecycle: an exhaustive table, every state by every event, asserting the
  resulting state or `IllegalTransition`; same-run second sighting is a no-op
  for state; three distinct sources reach reinforced, three sightings from one
  source do not; revival from faded.
- Date check: each finding kind triggers and does not trigger, with `today`
  fixed; a passed horizon with later history is not flagged.
- Submission validator: one test per rule above, each asserting the error
  text names the offending id or field; a valid submission passes with zero
  errors.
- Ingest: atomicity (a submission with one bad promotion writes nothing, not
  even the good ones); reliability taken from the source overrides anything in
  the file; `updates` with a forbidden key refused.
- Sweep: fades exactly when the rule says, with history; does not fade a
  report seen in one of the two runs; does not fade matured or parked.
- Legacy import: the real old `signals.json` imports to 35 reports with zero
  validation errors; two are matured; grades are B3 or C3 or derived as
  specified; every report has `wales` as a place; export is deterministic.
- Rebuild equivalence now covers submissions and reports.

## Style rules

No em or en dashes anywhere (the legacy file is clean; keep yours clean).
British English. Domain packages import only `gwylio.shared` and themselves.

## Definition of done

1. `make ci` exits 0 from `gwylio/`.
2. `gwylio import-legacy /home/user/NRW-Scan-Tool/data/signals.json` exits 0,
   leaves `data/submissions/legacy__2026-07-25.json`, `data/exports/
   register.json` shows 35 reports, and `gwylio datecheck` runs on them.
3. `make seed` exits 0 and produces the seed database and files.
4. Report back: commands with status lines, test counts before and after,
   deviations and why, and notes for WP6 (what evaluation and products can
   read from the repositories and exports).
