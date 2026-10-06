"""Helpers shared by test modules: project paths and small domain builders."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from gwylio.collection.gates import GatingRules
from gwylio.collection.model import (
    Candidate,
    Discipline,
    Query,
    QueryInstrument,
    RawHit,
    Reliability,
    Source,
    SourceStatus,
)
from gwylio.collection.service import RunResult, RunScan
from gwylio.direction.model import GroupKind, Requirement, RequirementGroup, Scanability
from gwylio.infrastructure.collectors.fake import FakeCollector, load_fake_hits
from gwylio.infrastructure.config.loaders import LoadedConfig
from gwylio.infrastructure.ids import FixedIdGenerator
from gwylio.infrastructure.memory import (
    MemoryCandidateRepository,
    MemoryInstrumentRepository,
    MemoryScanRunRepository,
    NullKnownReports,
    StaticKnownReports,
)
from gwylio.infrastructure.sqlite.db import Database
from gwylio.infrastructure.sqlite.repositories import (
    SqliteCandidateRepository,
    SqliteInstrumentRepository,
    SqliteScanRunRepository,
)
from gwylio.reference.model import (
    HAZARD_FAMILIES_AXIS,
    SONARR_AXIS,
    NodeKind,
    Taxonomy,
    TaxonomyAxis,
    TaxonomyNode,
)
from gwylio.shared.clock import FixedClock
from gwylio.shared.values import CanonicalUrl, CleanText, IsoDate, KebabId, RunId

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
"""The gwylio/ directory: the repository root holding config/ and backend/."""


def node(node_id: str, kind: NodeKind = NodeKind.ECOSYSTEM) -> TaxonomyNode:
    return TaxonomyNode(KebabId(node_id), CleanText(node_id.replace("-", " ").title()), kind)


def small_taxonomy() -> Taxonomy:
    """Two axes: three SoNaRR nodes and two hazard families."""
    return Taxonomy(
        (
            TaxonomyAxis(
                SONARR_AXIS,
                CleanText("SoNaRR"),
                (node("marine"), node("freshwaters"), node("soils", NodeKind.RESOURCE)),
            ),
            TaxonomyAxis(
                HAZARD_FAMILIES_AXIS,
                CleanText("Hazard families"),
                (
                    node("wildfire", NodeKind.HAZARD_FAMILY),
                    node("plant-tree-disease", NodeKind.HAZARD_FAMILY),
                ),
            ),
        )
    )


def requirement(
    code: str,
    *,
    scanability: Scanability = Scanability.HIGH,
    coverage: tuple[str, ...] = (),
    short: str = "A short name",
) -> Requirement:
    return Requirement(
        code=code,
        id=KebabId(code.lower()),
        name=CleanText(f"Requirement {code}"),
        short=CleanText(short),
        scanability=scanability,
        scanability_note=CleanText("A note."),
        expected_coverage=tuple(KebabId(c) for c in coverage),
    )


def group(
    group_id: str,
    members: tuple[str, ...],
    kind: GroupKind = GroupKind.IMPACT,
    related: tuple[str, ...] = (),
) -> RequirementGroup:
    return RequirementGroup(
        id=KebabId(group_id),
        kind=kind,
        name=CleanText(group_id.upper()),
        members=tuple(KebabId(m) for m in members),
        related_groups=tuple(KebabId(r) for r in related),
    )


# Collection builders.

FETCHED_AT: Final[datetime] = datetime(2026, 10, 6, 2, 15, tzinfo=UTC)
FAKE_HITS: Final[Path] = PROJECT_ROOT / "backend" / "tests" / "fixtures" / "fake_hits.json"


def source(
    source_id: str,
    domain: str,
    *,
    lane: str = "welsh-government",
    discipline: Discipline = Discipline.OSINT_SITE,
    trusted: bool = True,
    site_pass: bool = True,
    status: SourceStatus = SourceStatus.ACTIVE,
    feed_url: str | None = None,
    reliability: Reliability = Reliability.B,
) -> Source:
    return Source(
        id=KebabId(source_id),
        name=CleanText(source_id.replace("-", " ").title()),
        domain=domain,
        feed_url=feed_url,
        discipline=discipline,
        lane=KebabId(lane),
        actor=KebabId("welsh-government"),
        reliability=reliability,
        trusted=trusted,
        site_pass=site_pass,
        status=status,
        added_on=IsoDate("2026-07-16"),
    )


def query(
    query_id: str,
    *,
    discipline: Discipline = Discipline.OSINT_WEB,
    lane: str = "welsh-government",
    text: str = "nature recovery Wales",
    requirement_hints: tuple[str, ...] = (),
    topic_hints: tuple[str, ...] = (),
    negative_terms: tuple[str, ...] = (),
    site_source_ids: tuple[str, ...] = (),
) -> Query:
    return Query(
        id=KebabId(query_id),
        discipline=discipline,
        lane=KebabId(lane),
        text=CleanText(text),
        requirement_hints=tuple(KebabId(h) for h in requirement_hints),
        topic_hints=tuple(KebabId(t) for t in topic_hints),
        negative_terms=tuple(CleanText(t) for t in negative_terms),
        site_source_ids=tuple(KebabId(s) for s in site_source_ids),
    )


def instrument(
    *queries: Query,
    budget: int = 150,
    negatives: tuple[str, ...] = ("new south wales",),
    version: str = "2026.10.0",
) -> QueryInstrument:
    return QueryInstrument.build(
        CleanText(version), tuple(CleanText(n) for n in negatives), budget, tuple(queries)
    )


def hit(
    url: str,
    title: str = "A title about Wales",
    *,
    query_id: str = "q1",
    discipline: Discipline = Discipline.OSINT_WEB,
    snippet: str = "",
    published_on: str | None = None,
    source_id: str | None = None,
) -> RawHit:
    return RawHit(
        url=url,
        title=CleanText(title),
        snippet=CleanText(snippet),
        published_on=None if published_on is None else IsoDate(published_on),
        discipline=discipline,
        query_id=KebabId(query_id),
        source_id=None if source_id is None else KebabId(source_id),
        fetched_at=FETCHED_AT,
    )


def rules(
    tokens: tuple[str, ...] = ("wales", "welsh", "senedd", "dee", "north wales"),
) -> GatingRules:
    return GatingRules(frozenset({"naturalresources.wales", "cyfoethnaturiol.cymru"}), tokens)


# The shipped configuration run over the scripted hits.

ALL = (
    Discipline.OSINT_WEB,
    Discipline.OSINT_SITE,
    Discipline.OSINT_FEED,
    Discipline.OSINT_ACADEMIC,
)
DEFAULT = ALL[:3]
EARLIER = RunId("20260901T0900Z-aaaa")
CLOCK = FixedClock(datetime(2026, 10, 6, 2, 15, 42, tzinfo=UTC))


def scan(
    config: LoadedConfig,
    disciplines: tuple[Discipline, ...],
    candidates: MemoryCandidateRepository | None = None,
    known: StaticKnownReports | NullKnownReports | None = None,
) -> RunResult:
    hits = load_fake_hits(FAKE_HITS)
    return RunScan(
        collectors={d: FakeCollector(d, hits) for d in disciplines},
        instruments=MemoryInstrumentRepository(),
        runs=MemoryScanRunRepository(),
        candidates=candidates or MemoryCandidateRepository(),
        known=known or NullKnownReports(),
        rules=config.gating,
        clock=CLOCK,
        ids=FixedIdGenerator("3f9a"),
    ).execute(config.instrument, config.sources, disciplines)


def earlier_candidate() -> Candidate:
    url = "https://www.gov.wales/national-survey-wales-results-viewer"
    return Candidate(
        id=KebabId("c-20260901t0900z-aaaa-000001"),
        run_id=EARLIER,
        canonical_url=CanonicalUrl(url),
        url=url,
        title=CleanText("National Survey for Wales: results viewer"),
        snippet=CleanText(""),
        published_on=None,
        first_seen_run_id=EARLIER,
        trusted=True,
        source_id=KebabId("welsh-government"),
        lane=KebabId("welsh-government"),
        discipline=Discipline.OSINT_WEB,
        query_id=KebabId("web-partnership-society-02"),
    )


# The same scan with SQLite persistence (work package 3).


def sqlite_scan(
    db: Database,
    config: LoadedConfig,
    disciplines: tuple[Discipline, ...] = DEFAULT,
    *,
    clock: FixedClock = CLOCK,
    suffix: str = "3f9a",
    known: StaticKnownReports | NullKnownReports | None = None,
) -> RunResult:
    """Run the fake hits through ``RunScan`` with the SQLite repositories, in one transaction."""
    hits = load_fake_hits(FAKE_HITS)
    scan = RunScan(
        collectors={d: FakeCollector(d, hits) for d in disciplines},
        instruments=SqliteInstrumentRepository(db),
        runs=SqliteScanRunRepository(db),
        candidates=SqliteCandidateRepository(db),
        known=known or NullKnownReports(),
        rules=config.gating,
        clock=clock,
        ids=FixedIdGenerator(suffix),
    )
    with db.transaction():
        return scan.execute(config.instrument, config.sources, disciplines)


# The register (work package 5).

DROUGHT_URL: Final[str] = "https://nation.cymru/news/drought-declared-across-south-west-wales"
"""A fake hit's URL: a report holding it makes that hit a reinforcement."""


def promotion(
    report_id: str = "drought-2026",
    url: str = DROUGHT_URL,
    **overrides: object,
) -> dict[str, object]:
    """A valid promotion with no watched source, as a submission file spells it."""
    base: dict[str, object] = {
        "id": report_id,
        "title": "Drought declared across South West Wales",
        "url": url,
        "source_id": None,
        "source_name": "Nation.Cymru",
        "lane": "independent-media",
        "report_type": "environmental",
        "credibility": 2,
        "reliability_if_unknown_source": "C",
        "assessments": [{"requirement_id": "si1", "direction": "threatens"}],
        "topics": ["water-resources"],
        "hazards": ["drought-and-low-flows"],
        "places": ["wales"],
        "scores": {
            "evidence": "high",
            "novelty": "medium",
            "confidence": "high",
            "potential_impact": "medium",
            "time_horizon": "immediate",
        },
        "bucket": "watch",
        "summary": "NRW declared drought status for South West Wales.",
    }
    base.update(overrides)
    return base


def submission_document(
    *,
    run_id: str | None = None,
    received_on: str = "2026-10-01",
    **lists: object,
) -> dict[str, object]:
    """A valid submission document; keyword arguments replace its lists."""
    document: dict[str, object] = {
        "schema": "gwylio.submission/1",
        "run_id": run_id,
        "analyst": "test analyst",
        "rubric_version": "2026.10",
        "received_on": received_on,
        "dispositions": [],
        "promotions": [],
        "updates": [],
        "reinforcements": [],
        "verifications": [],
        "method_note": "Judged in a test.",
    }
    document.update(lists)
    return document


def add_reports(
    db: Database,
    config: LoadedConfig,
    *promotions: dict[str, object],
    stem: str = "direct__2026-10-01__1",
    received_on: str = "2026-10-01",
    data_dir: Path | None = None,
) -> None:
    """Ingest an out-of-run submission adding ``promotions``; with ``data_dir``, keep its file."""
    from gwylio.infrastructure.handoff.submission_file import ingest_submission
    from gwylio.processing.submission import Submission, dumps_submission

    submission = Submission.model_validate(
        submission_document(received_on=received_on, promotions=list(promotions or [promotion()]))
    )
    outcome = ingest_submission(db, config, submission, stem)
    assert outcome.ok, outcome.problems
    if data_dir is not None:
        path = data_dir / "submissions" / f"{stem}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dumps_submission(submission), encoding="utf-8")
