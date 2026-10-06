# Gwylio: a plain-English guide

This guide is for colleagues who read Gwylio's output and do not write code.
Gwylio (Welsh: to watch, to keep watch) is an open-source intelligence (OSINT)
system for the Welsh environment: it watches public sources and keeps a
graded record of what it finds. You can read this page on its own. Every term
is explained where it first appears.

## What it is for

Natural Resources Wales (NRW) has a corporate plan with a performance
framework: six impact statements and twelve strategic indicators (SIs). Gwylio
asks, for each indicator, "what is happening outside NRW that might help or
hurt progress?" It looks at government, the Senedd (the Welsh Parliament),
regulators, researchers, campaigners, the press and international bodies. It
keeps the answers in one register and publishes them as a website and as
written summaries.

Each indicator is a **requirement**: a question the register exists to
answer. The NRW framework is the first **requirement set**. Others can be
added without changing how the tool works.

## Collect first, judge second

The work is split in two on purpose.

- **The collector** is a program. It searches, reads feeds, throws away what
  clearly does not belong (NRW's own pages, junk terms, anything unrelated to
  Wales) and merges duplicates. It writes the survivors to a file as
  **candidates**. It never decides what a candidate means, how good it is or
  which indicator it touches.
- **The analyst** is Claude Code working from a written skill and the rubric
  (`docs/RUBRIC.md`). It opens every candidate, reads the actual page, and
  decides its fate. It writes its decisions to a **submission** file.

The app then checks the submission against the rules and either accepts all
of it or none of it. If a single field is wrong, nothing changes and the
errors are listed. This split keeps the machine honest about what it
cannot know, and keeps the judgement visible and reviewable.

Every candidate gets a **disposition**: promoted (it becomes a report),
rejected (with the reason), duplicate, deferred (not finished yet) or
reinforcement (a new sighting of a report we already hold).

## What a report is

A promoted candidate becomes an **intelligence report**, an entry in the
register. A candidate is promoted only if it passes four tests: it is
external to NRW, it is consequential, the claim can be verified from the page
itself, and it is new or has moved. A report carries:

- a title, a short summary and a link to the source;
- one or more **assessments**, each saying how it bears on one indicator:
  *supports* (makes progress easier), *threatens* (makes it harder),
  *neutral* (relevant, no clear push, or genuinely two-way) or *informs
  baseline* (new data that changes how we measure where we stand);
- tags for topics, hazards (a named threat such as ash dieback) and places;
- scores for evidence, novelty, confidence and potential impact, a time
  horizon, and a **bucket**: brief (headline material), follow up (someone
  should act), watch, or park;
- a **grading** and a history of every change.

### How a report is graded

The grading is a letter and a digit, such as **B2**. The Admiralty system
(borrowed from military intelligence) judges the two halves separately.

- The **letter** (A to F) is **reliability**: how far the source can be
  trusted. It belongs to the source and is fixed on the watchlist. A is the
  authoritative record itself, such as legislation.gov.uk; B is government
  and regulators speaking about their own decisions; C is established
  charities, unions, think tanks and news outlets; D is campaign groups and
  parties to a dispute; E is a source with a poor record; F is a source with
  no track record yet.
- The **digit** (1 to 6) is **credibility**: how far this one piece of
  information is confirmed. 1 is confirmed by the primary record, 2 is
  probably true, 3 is possibly true (a consultation or forecast whose outcome
  is open), 4 is doubtful, 5 is improbable and 6 cannot be judged.

A low letter does not make a report unimportant. A campaign group's court
win may be graded D2: it says whose voice it is, and the digit says the fact
is easy to check. Grades tend to inflate, so the analyst looks again when
most of a run's reports score 1 or 2. A consultation is a 3, however official
the page looks.

## The life of a report

A report's **state** is derived from how often, and by how many sources, it
is seen across scan runs. The analyst cannot set most states by hand.

| State | Meaning |
|---|---|
| Emerging | New to the register, seen in one run only. |
| Tracking | Seen again in a later run. |
| Reinforced | Seen by three different sources, or independently confirmed. |
| Matured | Settled context: the Act passed, the fund launched. Set by the analyst. |
| Faded | Not seen in the two most recent complete runs. Set only by the sweep. |
| Parked | Set aside on reflection and kept for memory. Set by the analyst. |

The same page found again in the same run is an **index echo**. It is not
evidence and changes nothing. If a faded report reappears, it returns to
tracking: the reappearance is itself information. Nothing is ever deleted.

## What the pages show

The site is a snapshot, rebuilt each time the register is published. It
changes nothing; it only reads published files.

- **Picture**: one tile per well-being objective, impact statement and
  indicator, with counts of reports by direction and a status chip (covered,
  thin, quiet or blind spot). A banner appears when the date check has
  findings.
- **Reports**: every report, with filters. Each report page shows its
  grading, assessments, tags, the sightings that support it and its history.
- **Sources**: the watchlist, each source's reliability and how productive it
  has been. Silent sources are listed so they are not forgotten.
- **Scans**: every scan run with its funnel (raw hits down to new
  candidates), what the analyst did with them and the credibility spread.
- **Coverage**: two tables, indicators by lane (where we look) and taxonomy
  nodes by count. They show where the register is thin.
- **Verify**: the date-check queue, the reports that need checking against
  the world.
- **INTSUM**: the latest monthly intelligence summary. The strategic
  assessment is the annual product.
- **About**: the method, covering the same ground as this guide.

## The honesty rules

**Quiet is not the same as blind.** Every indicator has a **scanability**:
how far public sources can see it at all (high, medium, low or none). An
indicator with no active reports reads *quiet* when sources could show
movement and there is none. It reads *blind spot* when sources could not show
movement anyway, because its evidence sits inside NRW or arrives only in
known release windows. A blind spot is never reported as quiet. Its silence
says nothing.

**Verify before you assert.** Every pass opens with the date check. It flags
events whose date has passed with nobody looking, wording such as
"forthcoming" about something that has now happened, and reports not
verified for 45 days or more. The analyst checks each against the world,
then writes a dated, past-tense correction: "the consultation closed on 11
September 2026", never "closes soon".

**Files are facts.** The record is a set of files in git: what each scan
collected and what each submission decided. The database behind the site is
rebuilt from those files, so a hand edit to it vanishes. A correction is a
new file, never a rewrite of an old one. Git shows what changed and when.

**Hunt for bad news.** Official sources announce what they are doing, so a
scan of them leans towards support. The analyst answers three **bias guard**
questions each pass. *Optimism*: what threatens an indicator, cuts funding or
could go either way? *Mainstream*: what did we promote that is not
government? *Streetlight*: what could move an indicator that this scan would
never find?

**Counts are not impact.** The register shows what surfaced publicly. It is
at least this much, and known to undercount.

## How a scan week goes

1. **Start.** The analyst checks the configuration and rebuilds the database
   from the files, then runs the date check and verifies each finding.
2. **Collect.** The scan runs. Without a Brave Search key only the feeds run;
   say so in the record. The file of candidates lands in `data/candidates/`.
3. **Judge.** The analyst reads every candidate's page and writes the
   submission: a disposition for every candidate, graded and assessed
   promotions, corrections from the date check, and a method note answering
   the three bias guards.
4. **Ingest.** The app checks the submission. Errors are fixed in the file and
   it is tried again. Nothing is written until it passes.
5. **Sweep.** Reports not seen in the two latest runs fade.
6. **Products.** The monthly summary is written; once a year, in autumn, the
   strategic assessment too.
7. **Publish and commit.** The snapshot for the site is written and the facts
   are committed with a dated message. The owner deploys the site.
8. **Report.** The analyst says what moved, what faded, what is quiet, what is
   a blind spot and what the method note says.

## Where to look when you want more

`README.md` for the commands, `docs/RUBRIC.md` for how reports are judged,
`docs/GLOSSARY.md` for every term, and `docs/STATUS.md` for what is built
today and what is not.
