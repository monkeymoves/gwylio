# Triage rubric and editorial contract

Rubric version `2026.10`. Every submission names the version it was judged
against in `rubric_version`.

This is the coding instrument for Gwylio, the Welsh environmental
open-source intelligence (OSINT) system. The collector gathers candidates and
never scores them; the analyst (the Claude Code skill, or a person) judges
them against this rubric and writes a submission; `gwylio ingest` validates
the submission and applies it, all or nothing. Keep the jobs apart: the
collector never judges, and the analyst never widens the search on a whim.
`skill/REFERENCE.md` lists every value a submission may use.

## Step 1: should a candidate become an intelligence report?

Open the page and read it. A candidate is promoted only if all four hold:

1. **External.** It is not a Natural Resources Wales (NRW) publication. The
   own-domain gate drops most of these; NRW's own releases belong to the
   evidence calendar, not the register.
2. **Consequential.** It plausibly moves, threatens or informs at least one
   requirement in a requirement set. "Interesting" is not enough: would
   anyone do or think anything differently because of it?
3. **Verifiable from the page.** The claim comes from the page you read, not
   from memory, the search snippet or the title alone. A generic page title
   ("Consultation display | Senedd") is not evidence of what the page says.
4. **New or moved.** It is not already in the register. A candidate whose
   canonical URL or exact title matches a report arrives with status
   `reinforcement`: confirm it in `reinforcements`, do not promote it again.
   Ingest refuses a promotion whose canonical URL already belongs to a report.

Every `new` candidate of the run gets exactly one disposition: `promoted`,
`rejected` (the reason names the test it failed), `duplicate`, `deferred` or
`reinforcement`. Every `reinforcement` candidate gets an entry in
`reinforcements`, or a disposition if the match was wrong. `seen_before`
candidates may have one. Use `--allow-deferred` only when a run genuinely
cannot be finished in one pass; the missing ones stay undisposed until a
later submission. A rejected candidate stays in its candidates file as the
audit trail; never promote noise just to park it.

## Step 2: grade it (Admiralty system)

The grading is a letter and a digit, such as B2. The letter belongs to the
source and the digit to the report.

**Reliability (the source, A to F).** It comes from `config/sources.json`,
never from the submission: ingest takes the source's letter and ignores
anything the file says. Only a promotion with no watched source gives
`reliability_if_unknown_source`.

| Letter | Anchor |
|---|---|
| A, completely reliable | The authoritative publisher of the record itself: legislation.gov.uk for an Act, StatsWales for an official statistic. |
| B, usually reliable | Government, regulators, the Senedd, audit and statutory bodies speaking about their own decisions. |
| C, fairly reliable | Established charities, unions, think tanks, research councils and news outlets with an editorial process. |
| D, not usually reliable | Campaign groups and parties to a dispute: often right, always arguing a case. |
| E, unreliable | A source with a record of getting this kind of thing wrong. |
| F, cannot be judged | A source new to the watchlist, or one with no track record yet. |

**Credibility (the information, 1 to 6).** Judge it from the page.

| Digit | Anchor |
|---|---|
| 1, confirmed | Settled fact confirmed by the primary record: the Act has Royal Assent, the figures are published. |
| 2, probably true | The publisher reports its own decision or data; consistent with what else we know. |
| 3, possibly true | Reported second hand, or a proposal, consultation or forecast whose outcome is open. |
| 4, doubtful | One claim against the weight of other evidence, or a report that hedges heavily. |
| 5, improbable | Contradicted by better evidence; record it only if the claim itself matters. |
| 6, cannot be judged | Nothing to test it against yet. |

Worked examples:

- **B1.** The Welsh Government announces that the Environment (Principles,
  Governance and Biodiversity Targets) (Wales) Act 2026 received Royal Assent,
  and legislation.gov.uk carries it. Watched government source (B); the fact
  is confirmed by the primary record (1).
- **C3.** Nation.Cymru reports that a council is dropping its 2030 net zero
  target, quoting officers. Established outlet (C); the decision is reported
  second hand and not yet minuted (3).
- **D2.** River Action announces it has been granted permission for a
  judicial review of NRW's permitting. Campaign group and party to the case
  (D); the permission is its own court news and easily checked (2). The
  low letter does not make the report unimportant: it says whose voice it is.

Grades inflate quietly. If most of a run's promotions are 1 or 2, look again:
a consultation is a 3, however official the page.

## Step 3: assess and tag it

- **Assessments.** One per requirement the report genuinely touches, each
  with a direction: `supports` (makes progress easier or faster),
  `threatens` (harder, slower or reversed), `neutral` (relevant, no clear
  push, or genuinely two-way: say so in the summary) or `informs_baseline`
  (new data or method that changes how we measure where the requirement
  stands). At least one; never the same requirement twice.
- **Topics, hazards and places.** Tag from the reference catalogues only.
  Tag what the page is about, not everything it mentions. Use `wales` when
  nothing narrower fits, and a region or river basin when the page names one.
- **Report type.** policy, legislation, research, data_release, funding,
  partnership, international, legal, environmental, market or incident.
- **Source, actor and lane.** Name the watched source when there is one; the
  lane and the actor then come from the source. For an unwatched source give
  `source_name`, a `lane` and, if catalogued, an `actor_id`.

## Step 4: score and bucket it

Scores are `low`, `medium` or `high`, except the time horizon:

- `evidence`: how settled is the underlying fact? A made Act is high, a
  consultation medium, an opinion piece low.
- `novelty`: how new is this to the register and to its readers?
- `confidence`: how sure are we of our reading of it?
- `potential_impact`: if it plays out, how much does it matter?
- `time_horizon`: `immediate` (this quarter), `near_term` (within a year),
  `medium_term` (one to three years), `long_term` (more than three).

**Scoring norms for weak signals.** Low or medium evidence with high novelty
is a valid promotion, not a failed one: that combination is the point of
horizon scanning. Score confidence honestly, bucket it `watch` or
`follow_up`, write the summary as early and unconfirmed, and let the
lifecycle do the work. Never hold an early signal to the evidence standard of
an Act; by the time it clears that bar it is no longer on the horizon.

Buckets: `brief` (headline material for the next product), `follow_up`
(someone should act: set `owner` and say what in `notes`), `watch` (keep an
eye on it), `park` (marginal but worth remembering).

## The lifecycle, as the code applies it

The analyst does not set states, except `matured` and `parked`. Everything
else is derived from sightings, counted as distinct runs and distinct source
ids, never raw sightings.

- A new report is `emerging`, unless the promotion's `state_override` creates
  it `matured` or `parked`.
- `emerging` becomes `tracking` on a sighting from a run that started
  strictly after the run that created it (for a report created outside a
  run, after the run of its first sighting).
- `emerging` or `tracking` becomes `reinforced` when distinct sources reach
  three, or when an update sets `independent_confirmation: true` (the
  analyst confirmed it independently; say how in `change`).
- A second sighting in a run that already sighted the report is index echo:
  it is linked to the report and changes nothing else, not even the history.
  A third distinct source still counts, whichever run it arrives in.
- `matured` (settled context: the Act passed, the fund launched) and
  `parked` (out of scope on reflection, kept for memory) are set by the
  analyst, in an update's `set.state` or a promotion's `state_override`, and
  only from an active state (emerging, tracking, reinforced). They record
  later sightings and ignore them.
- `faded` is set only by `gwylio sweep`: an active report with no sighting in
  the two most recent complete runs since it was created (runs that
  collected nothing do not count), and no history entry after the earlier of
  them. The sweep records what it faded in `data/sweeps/`.
- A sighting on a `faded` report revives it to `tracking`, with a `revived`
  history entry. The reappearance is itself information.
- Nothing is ever deleted. Every change appends a dated history entry.

Run `gwylio sweep` after ingesting, never before: a reinforcement found at
collection counts only once a submission confirms it.

## Date sensitivity

A report that hinges on a dated event (a vote, a ruling, a consultation
close, a scheduled publication) carries `event_horizon`, the date it
happens. Every pass opens with `gwylio datecheck`. It flags a passed horizon
that nobody has looked at since (a sighting is not a look; an update or a
verification is), future-framed language in a report still in the picture
(`config/datecheck.json` lists the phrases), a verification older than 45
days and a report never verified. Fix rot before triaging anything new:
check what actually happened, then send an update that rewrites title,
summary or notes in dated past-tense terms and moves or clears the horizon,
and a verification for what you checked. Write "the consultation closed on
11 September 2026", never "the consultation closes soon". A register that
still says "forthcoming" after the event loses its reader at the first line.

## Three bias guards

Ask each question before closing a pass, and answer it in the method note.

1. **Optimism.** What in this pool threatens a requirement, cuts funding,
   weakens a regime or could go either way? Government sources announce what
   they are doing, so a scan of them surfaces support. Reviews, budgets,
   legal challenges and deregulation are what a board most needs and a
   press-release scan least surfaces. A register where everything supports
   everything is a symptom, not a finding.
2. **Mainstream.** What did we promote that is not government, a regulator
   or NRW itself? The earliest signals often arrive as litigation,
   petitions, campaigns, market moves and independent reporting. If the
   answer is nothing, say so rather than let the register skew official.
3. **Streetlight.** What could move a requirement that this instrument would
   never find? The scan only finds what already talks like the requirements.
   Name the biophysical, market, technological and institutional pressures
   the queries miss, and the requirements whose scanability is `low` or
   `none`. A gap you can name is a probe to run; a gap you cannot see is a
   blind spot to declare.

## Editorial contract for products

1. Headline about 10 to 12 promotions per run. This throttles the product,
   not the register: the register holds everything that qualifies. If far
   more qualify, the bar rises, not the count.
2. Include non-government voices deliberately: unions, challenge
   organisations, think tanks, business bodies and international sources,
   when they bear on a requirement.
3. Never manufacture certainty. "Consultation open, direction unclear" when
   that is the truth.
4. A quiet requirement is reported as quiet, in a sentence, without padding.
5. A blind spot is never reported as quiet. A requirement with `low` or
   `none` scanability and no reports is invisible to this tool, not calm.
6. Every product carries a method note: runs and their funnels, candidates
   disposed of, promotions, the non-government share, the credibility spread,
   the instrument version and the known blind spots.
7. Counts of reports are not counts of impact: the register shows what
   surfaced publicly, at least this much and known to undercount.
8. No en dashes or em dashes anywhere. Use commas, colons, brackets or two
   sentences; ranges use "to".

## Changing the instrument

`config/instrument.json` is the measurement instrument. Runs are comparable
only while it holds still. Probe a query (`gwylio probe`) before adding it,
check the noise it brings, then bump the version and store the new content
hash. At least once a year, audit coverage down both axes: the requirement
sets, and the taxonomy (the eight ecosystems and three resources of the State
of Natural Resources Report (SoNaRR), and the hazard families). A gap closed
by audit is worth more than one found by luck.
