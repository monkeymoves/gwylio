"""IngestSubmission, Sweep and KnownReportsAdapter over in-memory ports."""

from __future__ import annotations

from dataclasses import replace

import pytest

from gwylio.intelligence.model import Assessment, HistoryKind, IndicatorState, Scores
from gwylio.intelligence.ports import DispositionRecord, SightingFact, SubmissionRecord
from gwylio.intelligence.service import (
    UNSET,
    IngestSubmission,
    KnownReportsAdapter,
    PromotionCommand,
    ReinforcementCommand,
    SubmissionCommand,
    Sweep,
    UpdateCommand,
    VerificationCommand,
    derived_counts,
)
from gwylio.shared.errors import DomainError
from gwylio.shared.values import CanonicalUrl, CleanText, IsoDate, KebabId, RunId
from gwylio.shared.vocabulary import (
    Bucket,
    Credibility,
    Direction,
    DispositionOutcome,
    Level,
    Reliability,
    ReportType,
    TimeHorizon,
)
from tests.unit.intelligence.fakes import (
    MemoryLookup,
    MemoryReports,
    MemorySources,
    MemorySubmissions,
    report,
    run_fact,
    run_id,
)

RECEIVED = IsoDate("2026-09-02")


def record(sid: str = "20260901T0900Z-0000__1", run: RunId | None = None) -> SubmissionRecord:
    return SubmissionRecord(
        sid, run, CleanText("analyst"), CleanText("2026.10"), RECEIVED, CleanText("note")
    )


def promotion(pid: str = "new-report", **changes: object) -> PromotionCommand:
    base = PromotionCommand(
        id=KebabId(pid),
        from_candidate=None,
        title=CleanText("Drought declared"),
        url=f"https://nation.cymru/news/{pid}",
        source_id=KebabId("nation-cymru"),
        source_name=CleanText("Nation.Cymru"),
        actor_id=None,
        lane=None,
        report_type=ReportType.ENVIRONMENTAL,
        credibility=Credibility.PROBABLY_TRUE,
        reliability_if_unknown_source=None,
        assessments=(Assessment(KebabId("si1"), Direction.THREATENS),),
        topics=(),
        hazards=(),
        places=(KebabId("wales"),),
        scores=Scores(Level.HIGH, Level.LOW, Level.HIGH, Level.LOW, TimeHorizon.IMMEDIATE),
        bucket=Bucket.WATCH,
        event_horizon=None,
        last_verified=RECEIVED,
        summary=CleanText("A summary."),
        notes=CleanText(""),
        owner=None,
    )
    return replace(base, **changes)  # type: ignore[arg-type]


class World:
    def __init__(self, *stored: object) -> None:
        self.reports = MemoryReports(*stored)  # type: ignore[arg-type]
        self.submissions = MemorySubmissions()
        self.lookup = MemoryLookup([run_fact(1), run_fact(2), run_fact(3), run_fact(4)])
        self.sources = MemorySources()

    def ingest(self, command: SubmissionCommand):  # type: ignore[no-untyped-def]
        return IngestSubmission(
            reports=self.reports,
            submissions=self.submissions,
            sightings=self.lookup,
            sources=self.sources,
        ).execute(command)


def test_a_promotion_from_a_candidate_links_its_sightings_and_records_the_submission() -> None:
    world = World()
    world.lookup.sight("s-1", 1, "c-1", "nation-cymru")
    world.lookup.sight("s-2", 1, "c-1", "nation-cymru")
    command = SubmissionCommand(
        record(run=run_id(1)),
        dispositions=(
            DispositionRecord(
                KebabId("c-1"),
                DispositionOutcome.PROMOTED,
                CleanText("passes"),
                KebabId("new-report"),
            ),
        ),
        promotions=(promotion(from_candidate=KebabId("c-1")),),
    )
    result = world.ingest(command)
    assert result.ok, result.problems
    stored = world.reports.get("new-report")
    assert stored is not None
    assert stored.sighting_ids == ("s-1", "s-2")
    assert stored.created_run_id == run_id(1)
    assert stored.state is IndicatorState.EMERGING
    assert [h.kind for h in stored.history] == [HistoryKind.CREATED, HistoryKind.SIGHTED]
    assert stored.history[0].change == f"promoted from candidate c-1 in run {run_id(1)}"
    assert result.created == ("new-report",)
    assert result.sightings_linked == 2
    assert result.outcomes == {"promoted": 1}
    assert world.submissions.get(command.record.id) == command.record


def test_reliability_comes_from_the_source_whatever_the_file_says() -> None:
    world = World()
    command = SubmissionCommand(
        record(),
        promotions=(
            promotion(reliability_if_unknown_source=Reliability.A, lane=KebabId("senedd")),
        ),
    )
    assert world.ingest(command).ok
    stored = world.reports.get("new-report")
    assert stored is not None
    assert str(stored.grading) == "C2"
    assert stored.lane == "independent-media"
    assert stored.actor_id == "nation-cymru"


def test_an_unwatched_source_takes_the_files_reliability_and_lane() -> None:
    world = World()
    command = SubmissionCommand(
        record(),
        promotions=(
            promotion(
                source_id=None,
                reliability_if_unknown_source=Reliability.B,
                lane=KebabId("independent-media"),
            ),
        ),
    )
    assert world.ingest(command).ok
    stored = world.reports.get("new-report")
    assert stored is not None
    assert (str(stored.grading), stored.actor_id) == ("B2", None)


def test_one_bad_promotion_writes_nothing_not_even_the_good_ones() -> None:
    world = World(report("existing"))
    command = SubmissionCommand(
        record(),
        promotions=(
            promotion("good-one"),
            promotion("bad-one", source_id=None, reliability_if_unknown_source=None),
            promotion("existing"),
        ),
        verifications=(VerificationCommand(KebabId("existing"), RECEIVED, CleanText("checked")),),
    )
    result = world.ingest(command)
    assert not result.ok
    messages = [str(p) for p in result.problems]
    assert messages == [
        "promotions[1].reliability_if_unknown_source: promotion 'bad-one' has no watched "
        "source, so it needs reliability_if_unknown_source",
        "promotions[2].id: report 'existing' already exists",
    ]
    assert world.reports.get("good-one") is None
    assert world.reports.saves == 0
    assert world.submissions.records == {}


def test_a_promotion_cannot_take_a_url_a_report_already_holds() -> None:
    world = World(report("existing", url="https://nation.cymru/news/new-report"))
    result = world.ingest(SubmissionCommand(record(), promotions=(promotion(),)))
    assert [str(p) for p in result.problems] == [
        "promotions[0].url: nation.cymru/news/new-report already belongs to report 'existing'; "
        "a new sighting of it is a reinforcement, not a promotion"
    ]


def test_a_reinforcement_from_a_later_run_moves_a_report_to_tracking() -> None:
    world = World(report("existing", sightings=("s-1",)))
    world.lookup.sight("s-1", 1, "c-1", "nation-cymru")
    world.lookup.sight("s-2", 2, "c-2", "bbc-wales")
    world.lookup.sight("s-3", 2, "c-2", "bbc-wales")
    result = world.ingest(
        SubmissionCommand(
            record(run=run_id(2)),
            reinforcements=(ReinforcementCommand(KebabId("existing"), KebabId("c-2")),),
        )
    )
    assert result.ok
    stored = world.reports.get("existing")
    assert stored is not None
    assert stored.state is IndicatorState.TRACKING
    assert stored.sighting_ids == ("s-1", "s-2", "s-3")
    assert result.state_changes == (("existing", "emerging", "tracking"),)
    sighted = [h for h in stored.history if h.kind is HistoryKind.SIGHTED]
    assert len(sighted) == 1, "the echo in the same run adds no history"
    assert derived_counts(world.lookup.sightings(stored.sighting_ids)) == (2, 2)


def test_a_sighting_already_linked_to_another_report_is_refused() -> None:
    world = World(report("a"), report("b", url="https://nation.cymru/b"))
    world.lookup.sight("s-1", 2, "c-1", "bbc-wales")
    world.lookup.linked["s-1"] = "a"
    result = world.ingest(
        SubmissionCommand(
            record(run=run_id(2)),
            reinforcements=(ReinforcementCommand(KebabId("b"), KebabId("c-1")),),
        )
    )
    assert "sighting 's-1' of candidate 'c-1' already belongs to report 'a'" in str(
        result.problems[0]
    )


def test_updates_set_fields_and_analyst_states_and_an_illegal_one_is_refused() -> None:
    world = World(report("a"), report("b", state=IndicatorState.FADED, url="https://x.org/b"))
    result = world.ingest(
        SubmissionCommand(
            record(),
            updates=(
                UpdateCommand(
                    KebabId("a"),
                    CleanText("settled"),
                    state=IndicatorState.MATURED,
                    bucket=Bucket.BRIEF,
                    owner=CleanText("Luke"),
                ),
            ),
        )
    )
    assert result.ok
    stored = world.reports.get("a")
    assert stored is not None
    assert (stored.state, stored.bucket, stored.owner) == (
        IndicatorState.MATURED,
        Bucket.BRIEF,
        "Luke",
    )
    assert [h.kind for h in stored.history[-2:]] == [HistoryKind.UPDATED, HistoryKind.STATE_CHANGED]
    refused = world.ingest(
        SubmissionCommand(
            record("x__1"),
            updates=(UpdateCommand(KebabId("b"), CleanText("park"), state=IndicatorState.PARKED),),
        )
    )
    assert str(refused.problems[0]) == (
        "updates[0].state: report 'b' is faded; MarkParked is not allowed from that state"
    )
    empty = world.ingest(
        SubmissionCommand(record("y__1"), updates=(UpdateCommand(KebabId("a"), CleanText("x")),))
    )
    assert str(empty.problems[0]) == "updates[0].set: an update must set at least one field"
    assert UNSET is not None


def test_verifications_cannot_postdate_the_submission_and_unknown_reports_are_named() -> None:
    world = World(report("a"))
    result = world.ingest(
        SubmissionCommand(
            record(),
            verifications=(
                VerificationCommand(KebabId("a"), IsoDate("2026-09-03"), CleanText("x")),
                VerificationCommand(KebabId("ghost"), RECEIVED, CleanText("x")),
            ),
        )
    )
    assert [str(p) for p in result.problems] == [
        "verifications[0].verified_on: verified_on 2026-09-03 is after the submission was "
        "received (2026-09-02)",
        "verifications[1].report_id: no report 'ghost' in the register",
    ]


def test_a_submission_is_ingested_once() -> None:
    world = World()
    assert world.ingest(SubmissionCommand(record())).ok
    again = world.ingest(SubmissionCommand(record()))
    assert str(again.problems[0]) == "submission 20260901T0900Z-0000__1 is already ingested"


# Sweep.


def sweep_world(*reports: object, runs: tuple[int, ...] = (1, 2, 3)) -> tuple[Sweep, MemoryReports]:
    stored = MemoryReports(*reports)  # type: ignore[arg-type]
    lookup = MemoryLookup([run_fact(day) for day in runs])
    lookup.sight("s-1", 1, "c-1", "nation-cymru")
    lookup.sight("s-2", 2, "c-2", "nation-cymru")
    return Sweep(reports=stored, sightings=lookup), stored


def test_sweep_fades_a_report_quiet_in_the_two_latest_runs_with_history() -> None:
    sweep, stored = sweep_world(report("quiet", sightings=("s-1",)))
    assert sweep.execute(IsoDate("2026-09-10")) == ("quiet",)
    faded = stored.get("quiet")
    assert faded is not None
    assert faded.state is IndicatorState.FADED
    assert faded.history[-1].kind is HistoryKind.FADED
    assert faded.history[-1].change == (
        f"emerging to faded: no sighting in the two most recent complete runs, {run_id(2)} "
        f"and {run_id(3)}"
    )


def test_sweep_spares_a_report_seen_in_one_of_the_two_runs() -> None:
    sweep, _ = sweep_world(report("seen", sightings=("s-1", "s-2")))
    assert sweep.plan() == ()


def test_sweep_needs_two_complete_runs_with_hits_after_creation() -> None:
    sweep, _ = sweep_world(report("young", created_run=2), runs=(1, 2, 3))
    assert sweep.plan() == ()
    empty_runs, _ = sweep_world(report("quiet"), runs=(1,))
    lookup = MemoryLookup([run_fact(1), run_fact(2, raw_hits=0), run_fact(3)])
    blind = Sweep(reports=MemoryReports(report("quiet")), sightings=lookup)
    assert blind.plan() == (), "a run that collected nothing cannot vouch for silence"
    assert empty_runs.plan() == ()
    aborted = MemoryLookup([run_fact(1), run_fact(2, complete=False), run_fact(3)])
    assert Sweep(reports=MemoryReports(report("quiet")), sightings=aborted).plan() == ()


def test_sweep_spares_matured_parked_and_faded_reports() -> None:
    sweep, _ = sweep_world(
        report("m", state=IndicatorState.MATURED),
        report("p", state=IndicatorState.PARKED, url="https://x.org/p"),
        report("f", state=IndicatorState.FADED, url="https://x.org/f"),
    )
    assert sweep.plan() == ()


def test_sweep_spares_a_report_someone_touched_after_the_earlier_run() -> None:
    touched = report("touched").verified(IsoDate("2026-09-03"), "checked")
    sweep, _ = sweep_world(touched)
    assert sweep.plan() == ()


def test_a_report_created_outside_a_run_counts_runs_after_its_creation_date() -> None:
    legacy = report("legacy", created_run=None, created_on="2026-08-31")
    sweep, _ = sweep_world(legacy)
    assert [d.report_id for d in sweep.plan()] == ["legacy"]
    late = report("late", created_run=None, created_on="2026-09-02")
    sweep, _ = sweep_world(late)
    assert sweep.plan() == ()


def test_applying_a_fade_to_an_unknown_report_is_refused() -> None:
    sweep, _ = sweep_world()
    with pytest.raises(DomainError, match="no report 'ghost' to fade"):
        sweep.apply([_decision("ghost")], IsoDate("2026-09-10"))


def _decision(report_id: str):  # type: ignore[no-untyped-def]
    from gwylio.intelligence.service import FadeDecision

    return FadeDecision(KebabId(report_id), CleanText("quiet"))


# Known reports.


def test_known_reports_match_by_url_then_exact_normalised_title() -> None:
    adapter = KnownReportsAdapter(
        MemoryReports(report("a", url="https://gov.wales/plan-2026%e2%80%9327", title="A Plan"))
    )
    assert adapter.report_id_for_url(CanonicalUrl("www.gov.wales/plan-2026%E2%80%9327/")) == "a"
    assert adapter.report_id_for_url(CanonicalUrl("gov.wales/other")) is None
    assert adapter.report_id_for_title("a plan") == "a"
    assert adapter.report_id_for_title("a plan!") is None
    assert adapter.report_id_for_title("") is None


def test_derived_counts_count_runs_and_named_sources_never_raw_sightings() -> None:
    facts = [
        SightingFact(KebabId(f"s-{i}"), run_id(day), run_fact(day).started_at, KebabId("c"), src)
        for i, (day, src) in enumerate(
            [(1, KebabId("a")), (1, KebabId("a")), (2, None), (2, KebabId("b"))]
        )
    ]
    assert derived_counts(facts) == (2, 2)
