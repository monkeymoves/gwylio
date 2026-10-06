"""The ubiquitous language of Gwylio, as data.

``GLOSSARY`` holds every term from the vocabulary section of ``docs/PLAN.md``
plus the terms the Reference and Direction contexts added. ``gwylio schema``
renders it to ``docs/GLOSSARY.md``; edit the terms here, never in that file.
Each entry is ``(term, definition)``; definitions are plain British English
sentences that spell out acronyms on first use.
"""

from __future__ import annotations

from typing import Final

__all__ = ["GLOSSARY"]

GLOSSARY: Final[tuple[tuple[str, str], ...]] = (
    # The intelligence cycle: one bounded context per stage, plus the shared kernel.
    (
        "Direction",
        "The stage of the intelligence cycle that says what to look for: requirement sets, "
        "their requirements and groups, and how far public sources can see each requirement.",
    ),
    (
        "Collection",
        "The stage of the intelligence cycle that gathers raw hits from sources, gates and "
        "deduplicates them, and records candidates and sightings. It never scores or tags.",
    ),
    (
        "Processing",
        "The handoff stage: candidates are written out as a file for the analyst skill, and "
        "the judged submission that comes back is validated and ingested.",
    ),
    (
        "Intelligence",
        "The stage that holds the register of intelligence reports. The analysis itself "
        "happens outside the app, in the analyst skill working against the rubric.",
    ),
    (
        "Dissemination",
        "The stage that turns the register into products: the strategic assessment, the "
        "monthly intelligence summary (INTSUM) and, later, tactical alerts.",
    ),
    (
        "Evaluation",
        "The stage that judges the system itself: funnel trends, yield per source and the "
        "coverage audit that separates a quiet requirement from a blind spot.",
    ),
    (
        "Reference",
        "The shared catalogues every other context points at: the taxonomy, topics, hazards, "
        "places, actors and lanes.",
    ),
    # Direction.
    (
        "Requirement set",
        "A list of Priority Intelligence Requirements (PIRs) that the system scans against. "
        "The Natural Resources Wales (NRW) corporate plan performance framework is one "
        "requirement set; others can be loaded from configuration.",
    ),
    (
        "Requirement",
        "One Priority Intelligence Requirement (PIR) in a requirement set, such as one NRW "
        "strategic indicator. It has a code, a name, keywords, metric sources, a scanability "
        "and the taxonomy nodes it is expected to cover.",
    ),
    (
        "Priority Intelligence Requirement",
        "A question the organisation needs answered, abbreviated PIR. In Gwylio each "
        "requirement in a requirement set is one PIR.",
    ),
    (
        "Strategic indicator",
        "A measure in the NRW corporate plan performance framework, abbreviated SI. The NRW "
        "requirement set holds the twelve strategic indicators SI1 to SI12 as requirements.",
    ),
    (
        "Requirement group",
        "A named set of requirements within a requirement set, of kind impact or well-being "
        "objective. Groups organise the picture; they never change what a requirement means.",
    ),
    (
        "Impact statement",
        "A requirement group of kind impact: one of the six outcomes for 2030 in the NRW "
        "corporate plan, each served by several strategic indicators.",
    ),
    (
        "Well-being objective",
        "A requirement group of kind wbo, abbreviated WBO: one of NRW's three well-being "
        "objectives, each with its primary strategic indicators.",
    ),
    (
        "Scanability",
        "How far public, indexed sources can see a requirement at all: high, medium, low or "
        "none. It separates nothing happening from this instrument cannot see it.",
    ),
    (
        "Expected coverage",
        "The taxonomy nodes a requirement is expected to touch, recorded as an editorial "
        "judgement so the coverage audit can show which parts of the environment the "
        "requirement set foregrounds and which it barely names.",
    ),
    (
        "Coverage status",
        "The state of one requirement in the picture, computed from its scanability and its "
        "count of active reports: covered, thin, quiet or blind spot.",
    ),
    (
        "Covered",
        "Coverage status of a requirement with three or more active reports.",
    ),
    (
        "Thin",
        "Coverage status of a requirement with one or two active reports.",
    ),
    (
        "Quiet",
        "Coverage status of a requirement with high or medium scanability and no active "
        "reports: the sources could see movement and there is none.",
    ),
    (
        "Blind spot",
        "Coverage status of a requirement with low or no scanability and no active reports. "
        "The absence is not evidence, so a blind spot is never rendered as quiet.",
    ),
    # Reference.
    (
        "Taxonomy",
        "The set of axes used to classify what a report is about. Axis one is the State of "
        "Natural Resources Report (SoNaRR) ecosystems and resources; axis two is the hazard "
        "families.",
    ),
    (
        "Taxonomy axis",
        "One dimension of the taxonomy, holding a flat list of nodes.",
    ),
    (
        "Taxonomy node",
        "One value on a taxonomy axis, such as freshwaters or plant and tree disease. Node "
        "identifiers are unique across the whole taxonomy.",
    ),
    (
        "SoNaRR",
        "The State of Natural Resources Report, NRW's statutory assessment of the natural "
        "resources of Wales. Its eight broad ecosystems and three cross-cutting resources (air, "
        "soils, water) form the first taxonomy axis.",
    ),
    (
        "Reference catalogue",
        "The validated bundle of taxonomy, topics, hazards, places, actors and lanes loaded "
        "from configuration.",
    ),
    (
        "Topic",
        "A subject area in the reference catalogue, such as peatland or air quality, used to "
        "hint what a query or report is about.",
    ),
    (
        "Hazard",
        "A named threat to the Welsh environment, such as ash dieback, belonging to one hazard "
        "family on the taxonomy. Gwylio watches hazards, not adversaries.",
    ),
    (
        "Place",
        "A named location in the reference catalogue: the nation, a region, a river basin, an "
        "area, a settlement or a site, with an optional parent place.",
    ),
    (
        "Actor",
        "An organisation that publishes or is reported on, such as Welsh Government or the "
        "Environment Agency, with its kind, its home lane and its web domain.",
    ),
    (
        "Lens",
        "One of the three viewpoints the commission asked for: government, partnership and "
        "wider society, and international. Every lane sits under one lens.",
    ),
    (
        "Lane",
        "Where we look: a grouping of sources such as the Senedd or ecological surveillance. "
        "Lanes say where a signal was found; requirements say what it means. The two are "
        "never merged.",
    ),
    (
        "OSINT",
        "Open-source intelligence: intelligence produced from publicly available sources.",
    ),
    # Collection.
    (
        "Discipline",
        "The kind of collection a collector performs: osint_web, osint_feed, osint_site or "
        "osint_academic, with geoint and sensor reserved for later.",
    ),
    (
        "Collector",
        "An adapter that performs one discipline of collection, such as reading Really Simple "
        "Syndication (RSS) feeds or querying a web search interface.",
    ),
    (
        "Source",
        "An entry on the watchlist: a publisher with a domain, an optional feed, a lane, an "
        "actor and a default reliability.",
    ),
    (
        "Reliability",
        "The Admiralty letter A to F for how far a source has proved trustworthy, set on the "
        "source and never by a submission.",
    ),
    (
        "Credibility",
        "The Admiralty digit 1 to 6 for how far one piece of information is confirmed, judged "
        "by the analyst for each report.",
    ),
    (
        "Grading",
        "The pair of reliability and credibility, written together, for example B2.",
    ),
    (
        "Instrument",
        "The versioned query set used for collection, identified by a content hash so that "
        "results are only compared between runs that used the same instrument.",
    ),
    (
        "Probe",
        "A query run that writes nothing, used to check the noise a new or widened query "
        "brings before the instrument changes.",
    ),
    (
        "Scan run",
        "One execution of collection. It is the unit of time for lifecycle maths and owns the "
        "funnel and the request budget. A complete run is immutable.",
    ),
    (
        "Funnel",
        "The counts a scan run keeps from raw hits through the gates and deduplication to new "
        "candidates, seen before and reinforcements.",
    ),
    (
        "Request budget",
        "The maximum number of requests a scan run may make. The run stops collecting when it "
        "is reached and says so.",
    ),
    (
        "Raw hit",
        "One result returned by a collector, before any gate or deduplication.",
    ),
    (
        "Gate",
        "A rule that drops a raw hit: the own-domain gate, the negative-term gate and the "
        "relevance gate, applied in that order.",
    ),
    (
        "Candidate",
        "A gated, deduplicated hit, one per canonical URL per scan run, waiting for the "
        "analyst's judgement.",
    ),
    (
        "Canonical URL",
        "The identity of a web address (uniform resource locator, URL) used for deduplication: "
        "no scheme, no www, no fragment, no trailing slash and no tracking parameters, with "
        "other query parameters kept.",
    ),
    (
        "Sighting",
        "A record that a source found a candidate in a scan run. Lifecycle maths counts "
        "sightings across runs.",
    ),
    (
        "Own domain",
        "A web domain belonging to the organisation the requirement set serves, such as "
        "Natural Resources Wales (NRW). Hits on own domains are dropped at the first gate, "
        "because the register tracks external signals only.",
    ),
    (
        "Relevance token",
        "A word or phrase, such as wales, senedd or the name of a Welsh river basin, that an "
        "untrusted hit must carry as a whole word to pass the relevance gate. A trusted source "
        "passes on its domain alone.",
    ),
    (
        "Content hash",
        "The sha256 digest of an instrument's canonical JSON, stored with its version. A "
        "changed query changes the hash, so a run always says exactly which instrument it used.",
    ),
    (
        "Seen before",
        "A candidate whose canonical URL an earlier scan run already recorded, and which "
        "matches no report. It is listed again but needs no fresh triage.",
    ),
    (
        "Reinforcement",
        "A candidate whose canonical URL, or failing that its exact title, matches an existing "
        "intelligence report. The analyst confirms it as a new sighting of that report.",
    ),
    (
        "Candidates file",
        "The file a scan run writes to data/candidates/<run_id>.json in the format "
        "gwylio.candidates/1: the run, its funnel, every candidate, every sighting and every "
        "reinforcement. It is an append-only fact from which the database can be rebuilt. A "
        "run that aborted writes one too, with no candidates and a note saying why it stopped.",
    ),
    (
        "Instrument archive",
        "The files under data/instruments/, one per instrument version a scan run used, in "
        "the format of config/instrument.json. Written once and never changed, so a run can be "
        "rebuilt after the instrument moves on.",
    ),
    (
        "Projection",
        "The SQLite database: a view of the configuration plus the facts under data/, never "
        "the record itself. Hand edits to it are lost on rebuild by design.",
    ),
    (
        "Rebuild",
        "Reconstructing the projection from config/ and the files under data/, replaying runs "
        "in the order they started. A rebuilt database equals the one the commands wrote.",
    ),
    (
        "Index echo",
        "The same canonical URL re-found in the same run or window. It is not evidence and "
        "does not move a report's lifecycle.",
    ),
    (
        "Distinct source",
        "A source with a different source identifier. Reinforcement needs sightings from "
        "distinct sources, not repeats from one.",
    ),
    # Processing.
    (
        "Submission",
        "The judged file the analyst skill writes back for a scan run: dispositions, "
        "promotions, updates, reinforcements, verifications and a method note.",
    ),
    (
        "Disposition",
        "The fate the analyst gives every candidate: promoted, rejected, duplicate, deferred "
        "or reinforcement.",
    ),
    # Intelligence.
    (
        "Intelligence report",
        "An entry in the register: a judged signal with its grading, assessments, tags, "
        "sightings and history.",
    ),
    (
        "Assessment",
        "A report's direction against one requirement: supports, threatens, neutral or "
        "informs_baseline.",
    ),
    (
        "Indicator state",
        "Where a report sits in the indications and warnings lifecycle: emerging, tracking, "
        "reinforced, matured, faded or parked. Nothing is ever deleted.",
    ),
    (
        "Bucket",
        "Where a report goes next: brief, follow_up, watch or park.",
    ),
    (
        "Event horizon",
        "The date by which a report's anticipated event should have happened, after which the "
        "date check asks for verification.",
    ),
    (
        "Last verified",
        "The date a report's claims were last checked against the world.",
    ),
    (
        "History",
        "The append-only record of every change to a report, with the date and the reason.",
    ),
    (
        "Rot",
        "A claim that was true when written and has since gone stale, such as future-tense "
        "framing of an event that has now passed.",
    ),
    # Dissemination.
    (
        "Product",
        "A finished output of the register at one level: strategic (annual), operational "
        "(monthly INTSUM) or tactical (alert).",
    ),
    (
        "INTSUM",
        "The intelligence summary, the monthly operational product.",
    ),
    (
        "Alert",
        "The tactical product for a single urgent report. In version 1 it is a designed seam only.",
    ),
    (
        "Snapshot",
        "The set of JavaScript Object Notation (JSON) files the static site reads, published "
        "by the command line tool from the register.",
    ),
)
