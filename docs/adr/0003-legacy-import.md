# ADR 0003: Seed the register from the old tool through a legacy submission

- Status: accepted
- Date: 2026-10-06
- Deciders: Luke Maggs, with the planning agent

## Context

The previous NRW SI horizon-scanning tool holds 35 verified signals in
`data/signals.json` (scan date 25 July 2026). Gwylio starts from a clean
schema and reuses no code, but the register should not start empty, and
whatever seeds it must be a fact on disk like everything else (ADR 0002).
The old signals carry fields Gwylio does not have (`lens`, `impacts`,
`appearances`, a single `source` name) and lack fields it needs (a watched
source, an Admiralty grading, tags from the reference catalogues).

## Decision

`gwylio import-legacy <signals.json> [--received-on DATE]` translates the
old file into one out-of-run submission,
`data/submissions/legacy__<received_on>.json` (default: the file's
`scan_date`, so `legacy__2026-07-25.json`), and ingests it through the same
validator and service as any analyst submission. The file is written inside
the ingest transaction, so it exists only if the ingest succeeds; an
identical file is reused and a different one is refused. The analyst is
`import-legacy (NRW SI horizon register)` and the rubric version the current
one.

The mapping, signal by signal:

| Old field | Gwylio field | Rule |
|---|---|---|
| `id` | `id` | Verbatim (every old id is already kebab-case). |
| `title`, `summary` | `title`, `summary` | Verbatim. |
| `notes` | `notes` | Verbatim, surrounding whitespace trimmed. |
| `url` | `url` | Verbatim; any non-ASCII character is percent-encoded. |
| URL host | `source_id`, `actor_id`, lane | The watched source whose domain the host equals or ends with (`research.senedd.wales` matches Senedd Research before the Senedd); the longest domain wins. Its actor and lane follow. |
| `source` | `source_name` | Used only when no watched source matches; otherwise the source's name. |
| `lens` | `reliability_if_unknown_source` | Only when no watched source matches: B for `government`, C otherwise. A matched source's own letter always wins. |
| `scores.evidence_strength` | `scores.evidence`, `credibility` | Verbatim score; credibility high 2, medium 3, low 4. |
| other `scores` | `scores` | Verbatim. |
| `signal_type` | `report_type` | Verbatim: the old types are a subset of the new. |
| `sis[]` `{si, direction}` | `assessments[]` | `SI4` becomes `si4`; direction verbatim. |
| `impacts`, `lens` | (none) | Groups are derived from the requirement set; the lens from the lane. |
| `scan_lane` | `lane` | By the lane table below; used only when no watched source gives the lane. |
| `lifecycle` | `state_override` | `matured` and `parked` carried; every other state left to the lifecycle, so the report lands `emerging`. |
| `appearances`, `last_seen` | (none) | Not recreated as sightings: the old counts were mostly index echo, recalibrated by hand in July 2026. |
| `bucket`, `event_horizon`, `last_verified` | same | Verbatim (a missing horizon or verification stays missing). |
| `owner` | `owner` | Verbatim; an empty owner becomes none. |
| `history[]` `{date, change}` | `prior_history` | Each entry carried verbatim as an `imported` history entry. |
| (none) | creation entry | "Imported from the NRW SI horizon register (signals.json, scan date 2026-07-25). Grading defaulted on import and awaits analyst review." |
| (none) | `places` | `wales` for every report. |

Lanes:

| Old `scan_lane` | Lane |
|---|---|
| `welsh_gov_policy` | `welsh-government` |
| `senedd_scrutiny` | `senedd` |
| `uk_gov_and_regulators` | `uk-government-and-regulators` |
| `research_evidence` | `research-evidence` |
| `legal_civil_society` | `partnership-and-civil-society` |
| `ecological_early_warning` | `ecological-surveillance` |
| `governance_capacity` | `governance-capacity` |
| `international` | `international` |

Topics and hazards come from a deliberately small keyword table over the
title only (`KEYWORD_TAGS` in `infrastructure/handoff/legacy.py`): a whole
word or phrase adds the listed tags, and a report matching nothing gets none.

| Phrase in the title | Topics | Hazards |
|---|---|---|
| drought | water-resources | drought-and-low-flows |
| flood | flood-risk | |
| flooding | flood-risk | river-and-surface-water-flooding |
| coastal erosion | flood-risk, marine-and-coastal | coastal-flooding-and-erosion |
| wildfire | | upland-wildfire |
| avian flu, avian influenza | biosecurity | avian-influenza |
| asian hornet | biosecurity | |
| air quality | air-quality | |
| carbon budget, net zero, emissions | climate-emissions | |
| adaptation | people-place-and-resilience | |
| agricultural pollution, poultry | pollution-water-and-land | agricultural-pollution |
| metal mines | pollution-water-and-land | metal-mine-pollution |
| pollution | pollution-water-and-land | |
| judicial review, sue | | legal-challenge |
| tree planting | woodland-and-forestry | |
| soil | soil-and-land | |
| peatland | peatland | |
| marine, seabird, fisheries | marine-and-coastal | |
| biodiversity, nature recovery, nature crisis, sssis | nature-and-ecosystems | |
| green spaces | people-place-and-resilience | |
| petition | partnership-and-society | |
| savings programme, budget reductions | governance-and-funding | public-funding-pressure |

## Consequences

- The seed is a fact: a rebuild replays `legacy__2026-07-25.json` like any
  other submission, and git shows exactly what was imported.
- Grades are conservative defaults (government sources mostly B2 or B3,
  others C2 or C3, campaign groups D) and every report says so in its
  history; the analyst should review them. Two old signals share one URL
  (the flood programme statement), so the register allows two reports on one
  page; a third promotion of that URL is refused as a reinforcement.
- Imported reports have no sightings, so they sit at `emerging` until a run
  finds them again and a submission confirms it. They fade only after two
  complete runs since 25 July 2026 miss them and nobody has touched them.
- Every imported report's verification is older than 45 days by October
  2026, so the first `gwylio datecheck` lists all 35 as stale: that is the
  honest state of the seed, not a fault.

## Alternatives considered

- **Insert the reports directly into SQLite.** Faster, but the seed would not
  be a fact on disk and a rebuild would lose it.
- **Recreate the old appearances as sightings.** The old counts were index
  echo by the old tool's own admission; inventing sightings would make the
  lifecycle lie from day one.
- **Map impacts and lenses into new fields.** Impacts are groups of the
  requirement set and lenses follow from lanes, so both are derived, not stored.
