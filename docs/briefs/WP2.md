# WP2 brief: Collection domain and processing (candidates out)

You are building work package 2 of the project described in `docs/PLAN.md`
(read it fully first). Then read `docs/briefs/WP0.md`, `docs/briefs/WP1.md`
and the code they produced under `backend/src/gwylio/` so you follow the
established conventions (value objects, config loaders, Typer CLI, import
rules, no-dash test, schema generation and its drift test). Project root is
`gwylio/`. Do not touch anything outside it except to READ the reference files
named below. Do not run git.

## Reference material (read for data and patterns, never reuse code)

- `/home/user/NRW-Scan-Tool/data/queries.json`: the old query instrument
  (`clusters[]` with `tight_queries`, `site_phrases`, `rss_keywords`,
  `academic_queries`, `negative_terms`; `global_negative_terms`). Transcribe
  its queries into the new instrument format below.
- `/home/user/NRW-Scan-Tool/collect.py` lines 190 to 240 and 410 to 445 for
  the gating order and the dedup lesson (generic titles must not suppress each
  other; dedup is by canonical URL).

## Domain (`backend/src/gwylio/collection/`, pure, no I/O)

`model.py`

- Enums: `Discipline` (osint_web, osint_feed, osint_site, osint_academic,
  geoint, sensor), `Reliability` (A to F, with a `label` property: A
  "completely reliable" through F "cannot be judged"), `SourceStatus` (active,
  parked, retired), `RunStatus` (running, complete, aborted), `GateOutcome`
  (passed, dropped_own, dropped_negative, dropped_unrelated).
- `Source(id, name, domain, feed_url, discipline, lane, actor, reliability,
  trusted, site_pass, status, added_on, notes)`.
- `Query(id, discipline, lane, text, requirement_hints, topic_hints,
  negative_terms, site_source_ids)`; `site_source_ids` is used only by
  osint_site queries and names the sources to restrict to.
- `QueryInstrument(version, content_hash, global_negative_terms,
  max_requests_per_run, queries)` with a static `compute_hash(...)` (sha256 of
  the canonical JSON of everything except the hash) and `verify_hash()`.
- `RawHit(url, title, snippet, published_on, discipline, query_id,
  source_id (may be None for open web), fetched_at)`.
- `Funnel(raw, dropped_own, dropped_negative, dropped_unrelated, unique,
  seen_before, new, reinforcements)` with `check()` enforcing
  `raw == dropped_own + dropped_negative + dropped_unrelated + passed` and
  `unique == new + seen_before + reinforcements`, where passed is the count of
  hits that reached dedup.
- `ScanRun(id, started_at, finished_at, instrument_version, disciplines,
  status, funnel, requests_made, budget_exhausted, notes)`; `complete(...)`
  returns a new frozen instance; any attempt to add hits to a complete run
  raises `RunImmutable`.
- `Candidate(id, run_id, canonical_url, url, title, snippet, published_on,
  first_seen_run_id, trusted, source_id, lane, discipline, query_id,
  requirement_hints, topic_hints)`.
- `Sighting(id, run_id, candidate_id, source_id, query_id, discipline)`.
- Run ids look like `20261006T0215Z-3f9a` (UTC minute plus 4 hex chars).
  Candidate ids `c-<run short>-<6 hex>`; sighting ids `s-...`.

`gates.py`

- `GatingRules(own_domains, relevance_tokens)` loaded from
  `config/gating.json` (own domains: naturalresources.wales,
  cyfoethnaturiol.cymru, naturalresourceswales.gov.uk; relevance tokens:
  wales, welsh, cymru, cymraeg, senedd, and the names of the four regions and
  the eight river basins in `config/reference/places.json`).
- `gate(hit, source, query, instrument, rules) -> GateOutcome`, applied in
  this order: own domain, negative term (global then query), relevance
  (untrusted or unknown source needs a relevance token in title or snippet or
  URL; a trusted source passes on domain alone).

`dedup.py`

- `group_hits(passed_hits) -> list[CandidateDraft]`: one draft per
  `CanonicalUrl`, keeping the earliest published_on, the longest snippet, the
  first title, and every hit as a sighting. Titles never participate in dedup.
- `match_known(drafts, seen: SeenIndex, known: KnownReports)`: marks each draft
  `new`, `seen_before` (canonical URL in an earlier run) or `reinforcement`
  (canonical URL matches a report, or, only when the URL does not match, a
  normalised title matches a report title exactly after lowercasing and
  collapsing whitespace).

`ports.py` (Protocols)

- `Collector`: `discipline` property and
  `collect(query, sources, remaining_budget) -> CollectResult(hits,
  requests_used, warnings)`.
- `SourceRepository`, `InstrumentRepository`, `ScanRunRepository`,
  `CandidateRepository` (add candidates and sightings; `canonical_urls_before(
  run_id)` for the SeenIndex), `KnownReports` (`report_id_for_url`,
  `report_id_for_title`; implemented by a null object for now because the
  Intelligence context arrives in WP5), `IdGenerator`.

`service.py`

- `RunScan` application service. Inputs: instrument, sources, collectors by
  discipline, repositories, `KnownReports`, clock, id generator, requested
  disciplines. Behaviour: creates a running `ScanRun`; for each query of a
  requested discipline, resolves the sources (site queries use
  `site_source_ids`, feed queries use the active feed sources of the query's
  lane, web and academic queries use none), calls the collector with the
  remaining request budget, stops dispatching when `requests_made >=
  max_requests_per_run` and sets `budget_exhausted` with a note; resolves each
  hit's source by exact domain match when the collector returned none; applies
  gates; dedups; matches known; builds candidates and sightings; computes and
  checks the funnel; completes the run; persists everything; returns a
  `RunResult(run, candidates, sightings, reinforcements, warnings)`.
- `Probe` service: runs one query text through one collector and returns hits
  without persisting anything.

## Processing (`backend/src/gwylio/processing/candidates_file.py`)

- Pydantic model for the file (schema id `gwylio.candidates/1`) exactly as in
  `docs/PLAN.md` "Handoff files", plus `generated_at`, `disciplines_run`,
  `requests_made`, `budget_exhausted`, `warnings[]`. Deterministic ordering:
  candidates sorted by canonical_url, reinforcements by report_id.
- `write_candidates_file(result, path)` and `read_candidates_file(path)`.
- Register this model with `gwylio schema` so its JSON Schema and TypeScript
  type are generated (extend the drift test fixtures accordingly).

## Infrastructure (this package only)

- `infrastructure/memory/`: in-memory implementations of every repository
  port and a `NullKnownReports`. Used by tests and by `collect --dry-run`.
- `infrastructure/collectors/fake.py`: `FakeCollector(discipline, hits)` that
  returns scripted hits and reports one request per call.
- `infrastructure/config/`: loaders for `config/instrument.json`,
  `config/sources.json` and `config/gating.json` following WP1 patterns, with
  cross-reference validation (sources name known lanes and actors; queries
  name known lanes, requirements and topics; site queries name known sources).
  Extend `gwylio check` to cover them.

## Config

- `config/instrument.json`: version "2026.10.0", `max_requests_per_run` 150,
  global negatives from the old file, and the old tight queries transcribed as
  osint_web queries with `requirement_hints` from the old cluster's `si_hints`
  (lowercased ids like `si4`) and `topic_hints` mapped to WP1 topics; the old
  `site_phrases` become osint_site queries pointing at the trusted site_pass
  sources of the matching lane; the old `rss_keywords` become osint_feed
  queries per lane; the old `academic_queries` become osint_academic queries.
  Compute and store the content hash. Add a `notes` field explaining
  provenance in one sentence.
- `config/sources.json`: transcribe the old watchlist
  (`/home/user/NRW-Scan-Tool/data/sources.json`) into the new shape, mapping
  old lanes to the WP1 lane ids, adding `discipline` (osint_site for
  search_domain, osint_feed for rss, osint_academic for api), an `actor` id
  from WP1 actors (add actors if needed), and a `reliability` letter: A for
  legislation.gov.uk and official statistics publishers, B for government
  departments, regulators and Parliament, C for research bodies and
  established NGOs, D for campaign groups and law firms, E for unknown. Keep
  `notes` and `added_on`. Carry `status` (active, parked).
- `config/gating.json` as described.

## CLI

- `gwylio collect --dry-run [--out PATH] [--discipline D ...]`: in-memory
  repositories, fake collectors fed from `backend/tests/fixtures/fake_hits.json`
  (write about 30 varied hits covering every gate outcome, a duplicate URL
  with different tracking params, an untrusted hit without a relevance token,
  and a trusted hit without one), writes the candidates file to `--out` or
  prints it to stdout, and prints the funnel as a table.
- `gwylio probe "<text>" --discipline D`: runs Probe with the fake collector in
  this package (the real ones arrive in WP4); prints hits; writes nothing.
- Without `--dry-run`, `collect` must exit 2 with "real collectors arrive in
  WP4" so the seam is explicit.

## Tests

- Gates: a table test over every outcome including order of precedence (an
  own-domain hit with a negative term is `dropped_own`).
- Dedup: two URLs differing only by `utm_source` and `www.` become one
  candidate with two sightings; two different Senedd URLs differing by query
  id stay separate; identical titles with different URLs stay separate.
- Known matching: URL match beats title match; title match only when URL does
  not match; a report-less index yields `new`.
- Funnel: `check()` passes on a real run and fails on a hand-broken funnel.
- Budget: with `max_requests_per_run` 3 and five queries, the run completes
  with `budget_exhausted` true, `requests_made` 3, and a note naming the
  unrun queries.
- Immutability: adding to a complete run raises.
- Service: an end-to-end run on the fake hits yields the expected funnel
  numbers (write the expected numbers in the test from the fixture by hand,
  not by calling the code).
- Candidates file: write then read round-trips; schema drift test extended.
- Shipped config: `gwylio check` passes; instrument hash verifies; every
  site query names existing sources.

## Style rules

No em or en dashes anywhere. British English. Domain code has no I/O.

## Definition of done

1. `make ci` exits 0 from `gwylio/`.
2. `uv run --project backend gwylio collect --dry-run --out /tmp/c.json`
   exits 0, the file validates through `read_candidates_file`, and the funnel
   table prints.
3. Report back: commands run with status lines, test counts before and after,
   deviations and why, and notes for WP3 (what the SQLite repositories need to
   persist, any shape decisions you made that persistence must honour).
