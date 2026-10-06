"""Application services of the Intelligence context: ingest, sweep and known reports.

``IngestSubmission`` applies one analyst submission to the register, all or
nothing: it builds every change in memory, collects every problem, and
writes through the repositories only when there are none. ``Sweep`` applies
the fade rule. ``KnownReportsAdapter`` answers the Collection context's
``KnownReports`` port from the register, so a scan can spot reinforcements.

The submission arrives as plain commands (``SubmissionCommand``), not as the
file contract: the Processing context owns the file and its validator, and
the dependency rule keeps the two contexts apart. Infrastructure translates.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Final, Literal

from gwylio.intelligence.lifecycle import (
    ConfirmIndependently,
    Fade,
    MarkMatured,
    MarkParked,
    Sighted,
    SightingContext,
    Verify,
    transition,
)
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
    ReportRepository,
    RunFact,
    SightingFact,
    SightingLookup,
    SourceDirectory,
    SubmissionRecord,
    SubmissionRepository,
)
from gwylio.shared.errors import DomainError
from gwylio.shared.values import CanonicalUrl, CleanText, IsoDate, KebabId, RunId
from gwylio.shared.vocabulary import (
    Bucket,
    Credibility,
    IndicatorState,
    Reliability,
    ReportType,
)

__all__ = [
    "UNSET",
    "FadeDecision",
    "IngestProblem",
    "IngestResult",
    "IngestSubmission",
    "KnownReportsAdapter",
    "PromotionCommand",
    "ReinforcementCommand",
    "SubmissionCommand",
    "Sweep",
    "Unset",
    "UpdateCommand",
    "VerificationCommand",
    "derived_counts",
]


class Unset(Enum):
    """Marks an optional update field the analyst did not name (``None`` clears it)."""

    UNSET = "unset"


UNSET: Final = Unset.UNSET


@dataclass(frozen=True, slots=True)
class PromotionCommand:
    """A new report, as the analyst judged it. Reliability and lane come from the source."""

    id: KebabId
    from_candidate: KebabId | None
    title: CleanText
    url: str
    source_id: KebabId | None
    source_name: CleanText
    actor_id: KebabId | None
    lane: KebabId | None
    report_type: ReportType
    credibility: Credibility
    reliability_if_unknown_source: Reliability | None
    assessments: tuple[Assessment, ...]
    topics: tuple[KebabId, ...]
    hazards: tuple[KebabId, ...]
    places: tuple[KebabId, ...]
    scores: Scores
    bucket: Bucket
    event_horizon: IsoDate | None
    last_verified: IsoDate | None
    summary: CleanText
    notes: CleanText
    owner: CleanText | None
    state_override: Literal[IndicatorState.MATURED, IndicatorState.PARKED] | None = None
    prior_history: tuple[tuple[IsoDate, CleanText], ...] = ()
    creation_note: CleanText | None = None


@dataclass(frozen=True, slots=True)
class UpdateCommand:
    """Analyst changes to an existing report; only these fields are settable."""

    report_id: KebabId
    change: CleanText
    state: Literal[IndicatorState.MATURED, IndicatorState.PARKED] | None = None
    bucket: Bucket | None = None
    title: CleanText | None = None
    summary: CleanText | None = None
    notes: CleanText | None = None
    owner: CleanText | Unset | None = UNSET
    event_horizon: IsoDate | Unset | None = UNSET
    independent_confirmation: bool = False


@dataclass(frozen=True, slots=True)
class ReinforcementCommand:
    """Link a candidate's sightings to an existing report."""

    report_id: KebabId
    candidate_id: KebabId


@dataclass(frozen=True, slots=True)
class VerificationCommand:
    """The analyst checked a report against the world."""

    report_id: KebabId
    verified_on: IsoDate
    note: CleanText


@dataclass(frozen=True, slots=True)
class SubmissionCommand:
    """Everything one submission asks of the register, in the order it is applied."""

    record: SubmissionRecord
    dispositions: tuple[DispositionRecord, ...] = ()
    promotions: tuple[PromotionCommand, ...] = ()
    reinforcements: tuple[ReinforcementCommand, ...] = ()
    updates: tuple[UpdateCommand, ...] = ()
    verifications: tuple[VerificationCommand, ...] = ()


@dataclass(frozen=True, slots=True)
class IngestProblem:
    """One reason a submission was refused, located inside the submission."""

    location: str
    message: str

    def __str__(self) -> str:
        return f"{self.location}: {self.message}" if self.location else self.message


@dataclass(frozen=True, slots=True)
class IngestResult:
    """What an ingest did, or every reason it did nothing."""

    submission_id: str
    problems: tuple[IngestProblem, ...] = ()
    created: tuple[str, ...] = ()
    changed: tuple[str, ...] = ()
    sightings_linked: int = 0
    state_changes: tuple[tuple[str, str, str], ...] = ()
    outcomes: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """True when the submission was applied."""
        return not self.problems


class _RefusedError(Exception):
    """Raised inside one step to record a problem and move on to the next."""

    def __init__(self, problem: IngestProblem) -> None:
        super().__init__(str(problem))
        self.problem = problem


class IngestSubmission:
    """Apply one submission to the register, all or nothing."""

    def __init__(
        self,
        *,
        reports: ReportRepository,
        submissions: SubmissionRepository,
        sightings: SightingLookup,
        sources: SourceDirectory,
    ) -> None:
        self._reports = reports
        self._submissions = submissions
        self._sightings = sightings
        self._sources = sources

    def execute(self, command: SubmissionCommand) -> IngestResult:
        """Apply ``command``; write nothing and return every problem if there is any."""
        run = _Application(self._reports, self._sightings, self._sources, command)
        if self._submissions.get(command.record.id) is not None:
            run.problems.append(
                IngestProblem("", f"submission {command.record.id} is already ingested")
            )
        run.apply()
        if run.problems:
            return IngestResult(command.record.id, tuple(run.problems))
        for report_id in sorted(run.touched):
            self._reports.save(run.working[report_id])
        self._submissions.record(command.record, command.dispositions)
        outcomes = Counter(d.outcome.value for d in command.dispositions)
        return IngestResult(
            submission_id=command.record.id,
            created=tuple(run.created),
            changed=tuple(sorted(run.touched - set(run.created))),
            sightings_linked=run.linked,
            state_changes=tuple(run.state_changes),
            outcomes=dict(sorted(outcomes.items())),
        )


class _Application:
    """One submission being applied in memory."""

    def __init__(
        self,
        reports: ReportRepository,
        lookup: SightingLookup,
        sources: SourceDirectory,
        command: SubmissionCommand,
    ) -> None:
        self.reports = reports
        self.lookup = lookup
        self.sources = sources
        self.command = command
        self.on = command.record.received_on
        self.working: dict[str, IntelligenceReport] = {}
        self.touched: set[str] = set()
        self.created: list[str] = []
        self.linked = 0
        self.linked_now: dict[str, str] = {}
        self.state_changes: list[tuple[str, str, str]] = []
        self.problems: list[IngestProblem] = []

    # Plumbing.

    def report(self, report_id: str, location: str) -> IntelligenceReport:
        if report_id in self.working:
            return self.working[report_id]
        stored = self.reports.get(report_id)
        if stored is None:
            raise _RefusedError(IngestProblem(location, f"no report '{report_id}' in the register"))
        self.working[report_id] = stored
        return stored

    def put(self, before: IntelligenceReport | None, after: IntelligenceReport) -> None:
        if before is not None and before.state is not after.state:
            self.state_changes.append((after.id, before.state.value, after.state.value))
        self.working[after.id] = after
        self.touched.add(after.id)

    def attempt(self, location: str, step: Callable[..., None], *args: object) -> None:
        try:
            step(*args)
        except _RefusedError as refused:
            self.problems.append(refused.problem)
        except DomainError as error:
            where = f"{location}.{error.location}" if error.location else location
            self.problems.append(IngestProblem(where, error.message))
        except ValueError as error:
            self.problems.append(IngestProblem(location, str(error)))

    def apply(self) -> None:
        c = self.command
        for p, promotion in enumerate(c.promotions):
            self.attempt(f"promotions[{p}]", self.promote, promotion, f"promotions[{p}]")
        for r, link in enumerate(c.reinforcements):
            self.attempt(f"reinforcements[{r}]", self.reinforce, link, f"reinforcements[{r}]")
        for u, update in enumerate(c.updates):
            self.attempt(f"updates[{u}]", self.update, update, f"updates[{u}]")
        for v, verification in enumerate(c.verifications):
            self.attempt(f"verifications[{v}]", self.verify, verification, f"verifications[{v}]")

    # Steps.

    def promote(self, p: PromotionCommand, where: str) -> None:
        if p.id in self.working or self.reports.get(p.id) is not None:
            raise _RefusedError(IngestProblem(f"{where}.id", f"report '{p.id}' already exists"))
        canonical = CanonicalUrl(p.url)
        holder = self.reports.by_canonical_url(canonical)
        if holder is not None:
            raise _RefusedError(
                IngestProblem(
                    f"{where}.url",
                    f"{canonical.value} already belongs to report '{holder.id}'; a new sighting "
                    "of it is a reinforcement, not a promotion",
                )
            )
        source = None if p.source_id is None else self.sources.get(p.source_id)
        if p.source_id is not None and source is None:
            raise _RefusedError(
                IngestProblem(f"{where}.source_id", f"unknown source '{p.source_id}'")
            )
        actor: KebabId | None
        if source is not None:
            reliability = source.reliability
            lane = source.lane
            actor = p.actor_id or source.actor_id
        else:
            if p.reliability_if_unknown_source is None:
                raise _RefusedError(
                    IngestProblem(
                        f"{where}.reliability_if_unknown_source",
                        f"promotion '{p.id}' has no watched source, so it needs "
                        "reliability_if_unknown_source",
                    )
                )
            if p.lane is None:
                raise _RefusedError(
                    IngestProblem(
                        f"{where}.lane",
                        f"promotion '{p.id}' has no watched source, so it needs a lane",
                    )
                )
            reliability = p.reliability_if_unknown_source
            lane = p.lane
            actor = p.actor_id
        candidate_run: RunId | None = None
        facts: tuple[SightingFact, ...] = ()
        if p.from_candidate is not None:
            facts = self.lookup.sightings_of_candidate(p.from_candidate)
            if not facts:
                raise _RefusedError(
                    IngestProblem(
                        f"{where}.from_candidate",
                        f"candidate '{p.from_candidate}' has no stored sightings",
                    )
                )
            candidate_run = facts[0].run_id
        history = tuple(
            HistoryEntry(on, HistoryKind.IMPORTED, change) for on, change in p.prior_history
        )
        state = p.state_override or IndicatorState.EMERGING
        note = p.creation_note or CleanText(
            f"promoted from candidate {p.from_candidate} in run {candidate_run}"
            if p.from_candidate is not None
            else "added directly by the analyst, outside a scan run"
        )
        if p.state_override is not None:
            note = CleanText(f"{note}; created as {state.value} by analyst override")
        report = IntelligenceReport(
            id=p.id,
            title=p.title,
            url=p.url,
            canonical_url=canonical,
            source_id=p.source_id,
            source_name=p.source_name,
            actor_id=actor,
            lane=lane,
            report_type=p.report_type,
            grading=Grading(reliability, p.credibility),
            assessments=p.assessments,
            topics=p.topics,
            hazards=p.hazards,
            places=p.places,
            scores=p.scores,
            state=state,
            bucket=p.bucket,
            event_horizon=p.event_horizon,
            last_verified=p.last_verified,
            summary=p.summary,
            notes=p.notes,
            owner=p.owner,
            created_on=self.on,
            created_run_id=candidate_run,
            history=(*history, HistoryEntry(self.on, HistoryKind.CREATED, note)),
        )
        self.put(None, report)
        self.created.append(report.id)
        for fact in facts:
            self.sight(report.id, fact, f"{where}.from_candidate")

    def reinforce(self, link: ReinforcementCommand, where: str) -> None:
        self.report(link.report_id, f"{where}.report_id")
        facts = self.lookup.sightings_of_candidate(link.candidate_id)
        if not facts:
            raise _RefusedError(
                IngestProblem(
                    f"{where}.candidate_id",
                    f"candidate '{link.candidate_id}' has no stored sightings",
                )
            )
        for fact in facts:
            self.sight(link.report_id, fact, f"{where}.candidate_id")

    def sight(self, report_id: str, fact: SightingFact, where: str) -> None:
        report = self.working[report_id]
        if fact.sighting_id in report.sighting_ids:
            return
        owner = self.linked_now.get(fact.sighting_id) or self.lookup.report_of_sighting(
            fact.sighting_id
        )
        if owner is not None and owner != report_id:
            raise _RefusedError(
                IngestProblem(
                    where,
                    f"sighting '{fact.sighting_id}' of candidate '{fact.candidate_id}' already "
                    f"belongs to report '{owner}'",
                )
            )
        existing = self.lookup.sightings(report.sighting_ids)
        anchor: tuple[datetime, str] | None = None
        if report.created_run_id is not None:
            created = self.lookup.run(report.created_run_id)
            if created is not None:
                anchor = created.order
        if anchor is None and existing:
            anchor = min(e.run_order for e in existing)
        runs_before = {e.run_id for e in existing}
        sources = {e.source_id for e in existing if e.source_id is not None}
        if fact.source_id is not None:
            sources.add(fact.source_id)
        context = SightingContext(
            appearances_after=len(runs_before | {fact.run_id}),
            distinct_sources_after=len(sources),
            is_later_run=anchor is not None and fact.run_order > anchor,
            is_new_run=fact.run_id not in runs_before,
        )
        event = Sighted(fact.run_id, fact.source_id, self.on, fact.sighting_id)
        self.put(report, transition(report, event, context))
        self.linked_now[fact.sighting_id] = report_id
        self.linked += 1

    def update(self, u: UpdateCommand, where: str) -> None:
        report = self.report(u.report_id, f"{where}.report_id")
        edits = (
            u.title is not None
            or u.summary is not None
            or u.notes is not None
            or u.bucket is not None
            or u.owner is not UNSET
            or u.event_horizon is not UNSET
        )
        if not edits and u.state is None and not u.independent_confirmation:
            raise _RefusedError(
                IngestProblem(f"{where}.set", "an update must set at least one field")
            )
        after = report
        if edits:
            after = after.updated(
                self.on,
                u.change,
                title=u.title,
                summary=u.summary,
                notes=u.notes,
                bucket=u.bucket,
                owner=None if isinstance(u.owner, Unset) else u.owner,
                clear_owner=u.owner is None,
                event_horizon=None if isinstance(u.event_horizon, Unset) else u.event_horizon,
                clear_event_horizon=u.event_horizon is None,
            )
        if u.independent_confirmation:
            after = transition(after, ConfirmIndependently(self.on, u.change))
        if u.state is IndicatorState.MATURED:
            after = transition(after, MarkMatured(self.on, u.change))
        elif u.state is IndicatorState.PARKED:
            after = transition(after, MarkParked(self.on, u.change))
        self.put(report, after)

    def verify(self, v: VerificationCommand, where: str) -> None:
        report = self.report(v.report_id, f"{where}.report_id")
        if v.verified_on > self.on:
            raise _RefusedError(
                IngestProblem(
                    f"{where}.verified_on",
                    f"verified_on {v.verified_on} is after the submission was received ({self.on})",
                )
            )
        self.put(report, transition(report, Verify(v.verified_on, v.note)))


def derived_counts(facts: Iterable[SightingFact]) -> tuple[int, int]:
    """``(appearances, distinct_sources)``: distinct runs and distinct non-null source ids.

    Never raw sightings: one page found by several queries in one run is index
    echo, not evidence.
    """
    listed = list(facts)
    runs = {fact.run_id for fact in listed}
    sources = {fact.source_id for fact in listed if fact.source_id is not None}
    return len(runs), len(sources)


# The sweep.


@dataclass(frozen=True, slots=True)
class FadeDecision:
    """One report the sweep fades, and why."""

    report_id: KebabId
    change: CleanText


class Sweep:
    """The fade rule: an active report quiet in the two most recent complete runs fades.

    For each active report, take the complete runs that started after the
    report was created (after its creating run, or after its creation date for
    a report created outside a run) and that collected at least one raw hit (a
    run that saw nothing cannot vouch for silence). When there are at least
    two, the two most recent both lack a sighting of the report, and no
    history entry is dated after the earlier of them, the report fades.
    """

    def __init__(self, *, reports: ReportRepository, sightings: SightingLookup) -> None:
        self._reports = reports
        self._sightings = sightings

    def plan(self) -> tuple[FadeDecision, ...]:
        """Which active reports the rule fades now, by report id."""
        runs = [run for run in self._sightings.runs() if run.complete and run.raw_hits > 0]
        decisions: list[FadeDecision] = []
        for report in self._reports.list_active():
            decision = self._decide(report, runs)
            if decision is not None:
                decisions.append(decision)
        return tuple(sorted(decisions, key=lambda d: d.report_id))

    def _decide(self, report: IntelligenceReport, runs: Sequence[RunFact]) -> FadeDecision | None:
        created = (
            None if report.created_run_id is None else self._sightings.run(report.created_run_id)
        )
        if created is not None:
            after = [run for run in runs if run.order > created.order]
        else:
            after = [run for run in runs if run.started_at.date() > report.created_on.value]
        recent = sorted(after, key=lambda run: run.order)[-2:]
        if len(recent) < 2:
            return None
        seen = {fact.run_id for fact in self._sightings.sightings(report.sighting_ids)}
        if any(run.run_id in seen for run in recent):
            return None
        earlier = recent[0].started_at.date()
        if any(entry.on.value > earlier for entry in report.history):
            return None
        return FadeDecision(
            report.id,
            CleanText(
                f"no sighting in the two most recent complete runs, {recent[0].run_id} and "
                f"{recent[1].run_id}"
            ),
        )

    def apply(
        self, decisions: Iterable[FadeDecision], on: IsoDate
    ) -> tuple[IntelligenceReport, ...]:
        """Fade each named report on ``on``; any refusal raises ``DomainError``, saving nothing."""
        faded: list[IntelligenceReport] = []
        for decision in decisions:
            report = self._reports.get(decision.report_id)
            if report is None:
                raise DomainError(
                    f"no report '{decision.report_id}' to fade", scope="report", location="id"
                )
            faded.append(transition(report, Fade(on, decision.change)))
        for report in faded:
            self._reports.save(report)
        return tuple(faded)

    def execute(self, today: IsoDate) -> tuple[KebabId, ...]:
        """Plan and apply the fade rule; return the faded report ids."""
        faded = self.apply(self.plan(), today)
        return tuple(report.id for report in faded)


# Known reports for collection.


class KnownReportsAdapter:
    """The Collection context's ``KnownReports`` port over the register.

    Matches a candidate by canonical URL first (percent escapes compared
    without regard to case, so a dash a publisher wrote into a URL matches
    however it was encoded), then by exact normalised title.
    """

    def __init__(self, reports: ReportRepository) -> None:
        self._reports = reports

    def report_id_for_url(self, canonical_url: CanonicalUrl) -> str | None:
        """The report whose canonical URL matches, or ``None``."""
        report = self._reports.by_canonical_url(canonical_url)
        return None if report is None else str(report.id)

    def report_id_for_title(self, normalised_title: str) -> str | None:
        """The report whose normalised title is exactly this, or ``None``."""
        if not normalised_title:
            return None
        report = self._reports.by_normalised_title(normalised_title)
        return None if report is None else str(report.id)
