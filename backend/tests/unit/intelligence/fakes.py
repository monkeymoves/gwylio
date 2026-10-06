"""In-memory ports and builders for the Intelligence unit tests."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from gwylio.intelligence.model import (
    Assessment,
    Grading,
    HistoryEntry,
    HistoryKind,
    IntelligenceReport,
    Scores,
)
from gwylio.intelligence.ports import (
    DispositionRecord,
    RunFact,
    SightingFact,
    SourceInfo,
    SubmissionRecord,
)
from gwylio.shared.values import CanonicalUrl, CleanText, IsoDate, KebabId, RunId
from gwylio.shared.vocabulary import (
    Bucket,
    Credibility,
    Direction,
    IndicatorState,
    Level,
    Reliability,
    ReportType,
    TimeHorizon,
)

BASE = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)


def run_id(day: int) -> RunId:
    """The run that started at 09:00 UTC on ``day`` September 2026 (days past 30 roll on)."""
    moment = BASE + timedelta(days=day - 1)
    return RunId(moment.strftime("%Y%m%dT%H%MZ") + "-0000")


def run_fact(day: int, raw_hits: int = 10, complete: bool = True) -> RunFact:
    return RunFact(run_id(day), BASE + timedelta(days=day - 1), complete, raw_hits)


def report(
    report_id: str = "drought-2026",
    *,
    state: IndicatorState = IndicatorState.EMERGING,
    created_run: int | None = 1,
    created_on: str = "2026-09-01",
    sightings: tuple[str, ...] = (),
    event_horizon: str | None = None,
    last_verified: str | None = "2026-09-01",
    history: tuple[HistoryEntry, ...] | None = None,
    title: str = "Drought declared across South West Wales",
    summary: str = "Drought status declared.",
    notes: str = "",
    url: str = "https://nation.cymru/news/drought",
) -> IntelligenceReport:
    return IntelligenceReport(
        id=KebabId(report_id),
        title=CleanText(title),
        url=url,
        canonical_url=CanonicalUrl(url),
        source_id=KebabId("nation-cymru"),
        source_name=CleanText("Nation.Cymru"),
        actor_id=KebabId("nation-cymru"),
        lane=KebabId("independent-media"),
        report_type=ReportType.ENVIRONMENTAL,
        grading=Grading(Reliability.C, Credibility.POSSIBLY_TRUE),
        assessments=(Assessment(KebabId("si1"), Direction.THREATENS),),
        topics=(KebabId("water-resources"),),
        hazards=(KebabId("drought-and-low-flows"),),
        places=(KebabId("wales"),),
        scores=Scores(Level.HIGH, Level.MEDIUM, Level.HIGH, Level.MEDIUM, TimeHorizon.IMMEDIATE),
        state=state,
        bucket=Bucket.WATCH,
        event_horizon=None if event_horizon is None else IsoDate(event_horizon),
        last_verified=None if last_verified is None else IsoDate(last_verified),
        summary=CleanText(summary),
        notes=CleanText(notes),
        owner=None,
        created_on=IsoDate(created_on),
        created_run_id=None if created_run is None else run_id(created_run),
        history=history
        if history is not None
        else (HistoryEntry(IsoDate(created_on), HistoryKind.CREATED, CleanText("created")),),
        sighting_ids=tuple(KebabId(s) for s in sightings),
    )


class MemoryReports:
    def __init__(self, *reports: IntelligenceReport) -> None:
        self.stored: dict[str, IntelligenceReport] = {r.id: r for r in reports}
        self.saves = 0

    def get(self, report_id: str) -> IntelligenceReport | None:
        return self.stored.get(report_id)

    def list(self) -> tuple[IntelligenceReport, ...]:
        return tuple(self.stored[k] for k in sorted(self.stored))

    def list_active(self) -> tuple[IntelligenceReport, ...]:
        return tuple(r for r in self.list() if r.state.active)

    def save(self, report: IntelligenceReport) -> None:
        self.saves += 1
        self.stored[report.id] = report

    def by_canonical_url(self, canonical_url: CanonicalUrl) -> IntelligenceReport | None:
        for r in self.list():
            if r.canonical_url.match_key == canonical_url.match_key:
                return r
        return None

    def by_normalised_title(self, normalised_title: str) -> IntelligenceReport | None:
        for r in self.list():
            if " ".join(r.title.casefold().split()) == normalised_title:
                return r
        return None


class MemorySubmissions:
    def __init__(self) -> None:
        self.records: dict[str, tuple[SubmissionRecord, tuple[DispositionRecord, ...]]] = {}

    def record(
        self, submission: SubmissionRecord, dispositions: Sequence[DispositionRecord]
    ) -> None:
        self.records[submission.id] = (submission, tuple(dispositions))

    def get(self, submission_id: str) -> SubmissionRecord | None:
        found = self.records.get(submission_id)
        return None if found is None else found[0]

    def all(self) -> tuple[SubmissionRecord, ...]:
        return tuple(record for record, _ in self.records.values())

    def dispositions_for_candidate(
        self, candidate_id: str
    ) -> tuple[tuple[str, DispositionRecord], ...]:
        return tuple(
            (sid, d)
            for sid, (_, ds) in self.records.items()
            for d in ds
            if d.candidate_id == candidate_id
        )


class MemoryLookup:
    """Sightings by candidate; runs by id."""

    def __init__(self, runs: Sequence[RunFact] = ()) -> None:
        self._runs = {r.run_id: r for r in runs}
        self._sightings: dict[str, SightingFact] = {}
        self.linked: dict[str, str] = {}

    def add_run(self, run: RunFact) -> None:
        self._runs[run.run_id] = run

    def sight(self, sighting_id: str, day: int, candidate_id: str, source_id: str | None) -> None:
        run = self._runs.get(run_id(day)) or run_fact(day)
        self._runs[run.run_id] = run
        self._sightings[sighting_id] = SightingFact(
            KebabId(sighting_id),
            run.run_id,
            run.started_at,
            KebabId(candidate_id),
            None if source_id is None else KebabId(source_id),
        )

    def sightings_of_candidate(self, candidate_id: str) -> tuple[SightingFact, ...]:
        return tuple(
            s for k, s in sorted(self._sightings.items()) if s.candidate_id == candidate_id
        )

    def sightings(self, sighting_ids: Sequence[str]) -> tuple[SightingFact, ...]:
        return tuple(self._sightings[s] for s in sighting_ids if s in self._sightings)

    def run(self, run_id_: str) -> RunFact | None:
        return self._runs.get(RunId(run_id_))

    def runs(self) -> tuple[RunFact, ...]:
        return tuple(sorted(self._runs.values(), key=lambda r: r.order))

    def report_of_sighting(self, sighting_id: str) -> str | None:
        return self.linked.get(sighting_id)


class MemorySources:
    def __init__(self) -> None:
        self.sources = {
            "nation-cymru": SourceInfo(
                KebabId("nation-cymru"),
                CleanText("Nation.Cymru"),
                Reliability.C,
                KebabId("independent-media"),
                KebabId("nation-cymru"),
            ),
            "welsh-government": SourceInfo(
                KebabId("welsh-government"),
                CleanText("Welsh Government"),
                Reliability.B,
                KebabId("welsh-government"),
                KebabId("welsh-government"),
            ),
        }

    def get(self, source_id: str) -> SourceInfo | None:
        return self.sources.get(source_id)
