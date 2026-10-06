# WP1 brief: Reference and Direction contexts

You are building work package 1 of the project described in `docs/PLAN.md`
(read it first, fully). Then read `docs/briefs/WP0.md` and the code WP0
produced, so you follow its conventions (uv project under `backend/`, Typer CLI
in `backend/src/gwylio/cli/main.py`, value objects in
`backend/src/gwylio/shared/values.py`, import rules enforced by a test, the
repo-wide no-dash test). Project root is `gwylio/`. Do not touch anything
outside it except to READ the reference file named below. Do not run git.

## Reference material (read, do not reuse code)

- `/home/user/NRW-Scan-Tool/data/frameworks.json`: the old tool's transcription
  of the NRW corporate plan framework. You will transcribe its DATA into the
  new config format. Fields there: `strategic_indicators[]` {id, name, cluster,
  development, internal_only, impacts[], metric_sources[], keywords[],
  external_scanability (high|medium|low|none), scanability_note},
  `impacts[]` {id, short, statement}, `wbos[]` {id, name, impacts[],
  primary_sis[], note}, `lenses[]` {id, name, description}.
- `/home/user/NRW-Scan-Tool/RUBRIC.md` lines 170 to 192 for the SoNaRR axis.

## Domain (pure Python, no I/O, frozen dataclasses, full typing)

`backend/src/gwylio/reference/model.py`

- `TaxonomyAxis(id: KebabId, name: CleanText, nodes: tuple[TaxonomyNode, ...])`,
  `TaxonomyNode(id, name, note)`. `Taxonomy(axes)` with `node_ids()` and
  `require_node(id)` raising `UnknownReference`.
- `Topic(id, name, note)`, `Hazard(id, name, family: node id on the
  hazard_families axis, note)`, `Place(id, name, kind: nation|region|area|
  river_basin|settlement|site, parent: id | None, centroid: tuple[float, float]
  | None)`, `Actor(id, name, kind: government|legislature|regulator|
  public_body|research|ngo|business|union|media|international|other,
  lane: KebabId, domain: str | None)`.
- `ReferenceCatalogue(taxonomy, topics, hazards, places, actors, lanes)`
  with lookup methods and a `validate()` that raises `UnknownReference` when
  a hazard names an unknown family node, a place names an unknown parent, or an
  actor names an unknown lane.
- `Lane(id, name, lens: government|partnership_society|international,
  description)`.

`backend/src/gwylio/direction/model.py`

- `Scanability` enum: high, medium, low, none.
- `Requirement(code: str like "SI1", id: KebabId, name, short, scanability,
  scanability_note, keywords: tuple[str, ...], expected_coverage: tuple[node
  ids, ...], metric_sources: tuple[str, ...], development: bool)`.
- `RequirementGroup(id, kind: impact|wbo, name, statement, members: tuple[
  requirement ids], note)`.
- `RequirementSet(id, name, version, source_doc, requirements, groups)` with
  `requirement(id)`, `groups_of_kind(kind)`, `validate(taxonomy)` raising
  `UnknownReference` for unknown members or coverage nodes, and refusing
  duplicate codes or ids.

`backend/src/gwylio/direction/scanability.py`

- `CoverageStatus` enum: covered, thin, quiet, blind_spot.
- `coverage_status(scanability, active_report_count) -> CoverageStatus`:
  0 reports and scanability in (low, none) is blind_spot; 0 reports and
  scanability in (high, medium) is quiet; 1 or 2 reports is thin; 3 or more is
  covered. A blind spot is never rendered as quiet; this function is the single
  place that rule lives.

`backend/src/gwylio/shared/glossary.py`

- `GLOSSARY: tuple[tuple[str, str], ...]` holding the 40 ubiquitous-language
  terms from `docs/PLAN.md` (vocabulary section) plus any you need to add. The
  generated `docs/GLOSSARY.md` comes from this.

## Config files (JSON, under `config/`)

Pydantic v2 models in `backend/src/gwylio/infrastructure/config/schemas.py`
describe each file; loaders in `.../config/loaders.py` turn them into domain
objects and run the domain `validate()` methods. Every string field that is
prose must become `CleanText`.

- `config/taxonomy.json`: axis `sonarr_ecosystems` with eight nodes (marine,
  coastal margins, freshwaters, mountains moorlands and heaths, semi-natural
  grasslands, enclosed farmland, woodlands, urban) and three resource nodes
  (air, soils, water) flagged `kind: resource`; axis `hazard_families` with
  about ten nodes (plant and tree disease, animal disease, invasive species,
  drought and water scarcity, flood and storm, wildfire, pollution incident,
  climate extreme, funding and capacity, regulatory and legal change, market
  and land use change). Short notes on each.
- `config/lanes.json`: ten lanes: welsh_government, senedd, uk_government_and_
  regulators, research_evidence, partnership_and_civil_society, legal_and_
  campaign, independent_media, ecological_surveillance, international,
  governance_capacity. Each with name, lens and a one-sentence description.
- `config/reference/topics.json` (about 15 topics drawn from the old query
  clusters: nature and ecosystems, pollution of water and land, air quality,
  climate emissions, people place and resilience, partnership and society,
  marine and coastal, soil and land, public behaviour, governance and funding,
  woodland and forestry, peatland, flood risk, water resources, biosecurity),
  `hazards.json` (about 12, each with a family), `places.json` (wales as
  nation; north_wales, mid_wales, south_west_wales, south_east_wales as
  regions with parent wales; the Dee, Severn, Wye, Usk, Tywi, Teifi, Conwy,
  Clwyd river basins as river_basin with parent wales), `actors.json` (about
  25 organisations: Welsh Government, Senedd, Audit Wales, Future Generations
  Commissioner, UK Government departments relevant to environment, Environment
  Agency, Climate Change Committee, JNCC, Office for Environmental Protection,
  UKRI, Wales Centre for Public Policy, NFU Cymru, FUW, Wales Environment Link,
  RSPB Cymru, WWF Cymru, River Action, Fish Legal, Afonydd Cymru, Dwr Cymru
  Welsh Water, Forest Research, Plant Health Portal (Defra), GB Non-native
  Species Secretariat, BTO, UNEP, EEA; each with kind, lane and domain).
- `config/requirement_sets/nrw-corporate-plan.json`: transcribe the old
  frameworks.json faithfully. Twelve requirements with code SI1 to SI12,
  id like `si1`, name verbatim, a `short` of at most six words you write,
  scanability from `external_scanability`, scanability_note verbatim,
  keywords verbatim, metric_sources verbatim, development flag verbatim,
  `expected_coverage` as your editorial mapping of each requirement to
  sonarr_ecosystems nodes (document the mapping in a `notes` field at the top
  of the file as an editorial judgement). Six groups of kind impact (I1 to I6,
  statement verbatim, members from each SI's `impacts` list inverted). Three
  groups of kind wbo (members from `primary_sis`, note verbatim).
  `source_doc`: "Impacts and SIs Doc-Master ENGLISH.pdf (NRW corporate plan
  performance framework, draft for testing through 2024-25)".

## CLI

- `gwylio check`: loads every config file, validates, prints a one-line summary
  per file (counts) and exits 0, or prints each error with file and path and
  exits 1. Also fails on any em or en dash (CleanText does this for you).
- `gwylio schema`: writes `docs/schema/<name>.schema.json` for every config
  model (JSON Schema from Pydantic), `docs/GLOSSARY.md` from the glossary,
  `skill/REFERENCE.md` (enums: Scanability, CoverageStatus, lane ids, lens
  ids, taxonomy node ids, and the list of CLI verbs registered on the Typer
  app), and `frontend/src/lib/data/types.generated.ts` with TypeScript
  interfaces for the config models. Generate TypeScript with a small Python
  generator over the JSON Schema (objects, arrays, enums, optionals, string,
  number, boolean, nested refs) rather than adding a Node dependency. Each
  generated file starts with a comment saying it is generated by `gwylio
  schema` and must not be edited by hand. Output must be deterministic
  (sorted keys where order is not meaningful).
- Wire `make check` to run `gwylio check` as well, and `make schema` to run
  `gwylio schema`.

## Tests

- Unit tests for every validate() path (unknown node, unknown parent, unknown
  lane, unknown member, duplicate code), for `coverage_status` as a full table,
  and for the glossary (no duplicates, every plan term present, no dashes).
- A test that loads the shipped `config/` through the real loaders and asserts
  12 requirements, 6 impact groups, 3 wbo groups, 11 sonarr nodes, 10 lanes.
- A drift test: run the schema generators into a temporary directory and
  assert byte equality with the committed files under `docs/schema/`,
  `docs/GLOSSARY.md`, `skill/REFERENCE.md`, and the generated TS file. Commit
  the generated files.
- A test that the generated TypeScript compiles: run `svelte-check` or `tsc
  --noEmit` through the frontend as part of `make check` (it already runs
  svelte-check; make sure the generated file is inside its include path).

## Style rules

- No em or en dashes anywhere. British English. Spell out acronyms on first
  use in docs and config notes. Domain code has no I/O.

## Definition of done

1. `make ci` exits 0 from `gwylio/`. `gwylio check` exits 0 on shipped config.
2. Report back: commands run with final status lines, test counts before and
   after, every deviation from this brief and why, and notes for WP2.
