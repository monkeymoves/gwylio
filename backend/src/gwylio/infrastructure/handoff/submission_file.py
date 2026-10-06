"""Read, validate and ingest ``data/submissions/<stem>.json``.

The glue between the Processing context's submission contract and the
Intelligence context's ``IngestSubmission``: it builds the validator's
context from the database and the configuration, translates the file into
commands, and runs both inside one database transaction. Any problem, from
the file contract, the validator or the register, rolls everything back and
returns every problem; nothing is written. On success the submission file is
written into ``data/submissions/`` inside the transaction, before the commit,
so the fact on disk never lags the projection.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from gwylio.infrastructure.config.loaders import LoadedConfig
from gwylio.infrastructure.sqlite.db import Database
from gwylio.infrastructure.sqlite.repositories import (
    SqliteCandidateRepository,
    SqliteReportRepository,
    SqliteSightingLookup,
    SqliteSourceDirectory,
    SqliteSubmissionRepository,
)
from gwylio.intelligence.model import Assessment, Scores
from gwylio.intelligence.ports import DispositionRecord, SubmissionRecord
from gwylio.intelligence.service import (
    UNSET,
    IngestResult,
    IngestSubmission,
    PromotionCommand,
    ReinforcementCommand,
    SubmissionCommand,
    UpdateCommand,
    VerificationCommand,
)
from gwylio.processing.ingest import next_submission_stem, replay_key
from gwylio.processing.submission import (
    RunCandidate,
    Submission,
    SubmissionContext,
    parse_submission,
    parse_update,
    validate_submission,
)
from gwylio.shared.values import CleanText, IsoDate, KebabId, RunId
from gwylio.shared.vocabulary import CandidateStatus, IndicatorState

__all__ = [
    "IngestOutcome",
    "build_context",
    "ingest_file",
    "ingest_submission",
    "place_submission",
    "to_command",
]


@dataclass(frozen=True, slots=True)
class IngestOutcome:
    """What one ingest did: the result, or every problem and nothing written."""

    submission_id: str
    problems: tuple[str, ...] = ()
    result: IngestResult | None = None
    path: Path | None = None
    notes: tuple[str, ...] = field(default=())

    @property
    def ok(self) -> bool:
        """True when the submission was applied."""
        return not self.problems and self.result is not None


class _RollbackError(Exception):
    """Raised inside the ingest transaction to undo every write."""


def _run_candidates(db: Database, run_id: str) -> dict[str, RunCandidate] | None:
    if db.scalar("SELECT 1 FROM scan_run WHERE id = ?", (run_id,)) is None:
        return None
    repo = SqliteCandidateRepository(db)
    reinforced = {r.candidate_id: r.report_id for r in repo.reinforcements_for_run(run_id)}
    found: dict[str, RunCandidate] = {}
    for candidate in repo.candidates_for_run(run_id):
        if candidate.id in reinforced:
            status = CandidateStatus.REINFORCEMENT
        elif candidate.first_seen_run_id != run_id:
            status = CandidateStatus.SEEN_BEFORE
        else:
            status = CandidateStatus.NEW
        found[candidate.id] = RunCandidate(
            candidate.id, status, candidate.canonical_url.value, reinforced.get(candidate.id)
        )
    return found


def build_context(
    db: Database, config: LoadedConfig, submission: Submission, submission_id: str
) -> SubmissionContext:
    """What the validator needs, read from the database and the configuration."""
    reports = SqliteReportRepository(db)
    submissions = SqliteSubmissionRepository(db)
    history = submissions.all()
    last = max((replay_key(str(s.received_on), s.id) for s in history), default=None)
    catalogue = config.catalogue
    run_id = submission.run_id
    return SubmissionContext(
        submission_id=submission_id,
        run_candidates=None if run_id is None else _run_candidates(db, run_id),
        report_ids=reports.ids(),
        report_urls=reports.url_keys(),
        requirement_ids=frozenset(
            r for rs in config.requirement_sets for r in rs.requirement_ids()
        ),
        topic_ids=catalogue.topic_ids(),
        hazard_ids=catalogue.hazard_ids(),
        place_ids=catalogue.place_ids(),
        actor_ids=catalogue.actor_ids(),
        lane_ids=catalogue.lane_ids(),
        source_ids=frozenset(source.id for source in config.sources),
        earlier_dispositions=submissions.final_dispositions(),
        last_ingested=last,
        already_ingested=submissions.get(submission_id) is not None,
    )


def _opt_clean(value: str | None) -> CleanText | None:
    return None if value is None else CleanText(value)


def _opt_date(value: str | None) -> IsoDate | None:
    return None if value is None else IsoDate(value)


def to_command(submission: Submission, submission_id: str) -> SubmissionCommand:
    """The submission as the Intelligence context's commands. Call after validation passes."""
    received = IsoDate(submission.received_on)
    record = SubmissionRecord(
        id=submission_id,
        run_id=None if submission.run_id is None else RunId(submission.run_id),
        analyst=CleanText(submission.analyst),
        rubric_version=CleanText(submission.rubric_version),
        received_on=received,
        method_note=CleanText(submission.method_note),
    )
    promotions = tuple(
        PromotionCommand(
            id=KebabId(p.id),
            from_candidate=None if p.from_candidate is None else KebabId(p.from_candidate),
            title=CleanText(p.title),
            url=p.url,
            source_id=None if p.source_id is None else KebabId(p.source_id),
            source_name=CleanText(p.source_name),
            actor_id=None if p.actor_id is None else KebabId(p.actor_id),
            lane=None if p.lane is None else KebabId(p.lane),
            report_type=p.report_type,
            credibility=p.credibility,
            reliability_if_unknown_source=p.reliability_if_unknown_source,
            assessments=tuple(
                Assessment(KebabId(a.requirement_id), a.direction) for a in p.assessments
            ),
            topics=tuple(KebabId(t) for t in p.topics),
            hazards=tuple(KebabId(h) for h in p.hazards),
            places=tuple(KebabId(place) for place in p.places),
            scores=Scores(
                p.scores.evidence,
                p.scores.novelty,
                p.scores.confidence,
                p.scores.potential_impact,
                p.scores.time_horizon,
            ),
            bucket=p.bucket,
            event_horizon=_opt_date(p.event_horizon),
            last_verified=_opt_date(p.last_verified),
            summary=CleanText(p.summary),
            notes=CleanText(p.notes),
            owner=_opt_clean(p.owner),
            state_override=None
            if p.state_override is None
            else (
                IndicatorState.MATURED if p.state_override == "matured" else IndicatorState.PARKED
            ),
            prior_history=tuple((IsoDate(h.on), CleanText(h.change)) for h in p.prior_history),
            creation_note=_opt_clean(p.creation_note),
        )
        for p in submission.promotions
    )
    updates: list[UpdateCommand] = []
    for u, update in enumerate(submission.updates):
        parsed, problems = parse_update(update.set_, f"updates[{u}].set")
        if problems:
            raise ValueError("; ".join(str(problem) for problem in problems))
        updates.append(
            UpdateCommand(
                report_id=KebabId(update.report_id),
                change=CleanText(update.change),
                state=None
                if parsed.state is None
                else (
                    IndicatorState.MATURED
                    if parsed.state == IndicatorState.MATURED.value
                    else IndicatorState.PARKED
                ),
                bucket=parsed.bucket,
                title=parsed.title,
                summary=parsed.summary,
                notes=parsed.notes,
                owner=parsed.owner if parsed.owner_given else UNSET,
                event_horizon=parsed.event_horizon if parsed.event_horizon_given else UNSET,
                independent_confirmation=parsed.independent_confirmation,
            )
        )
    return SubmissionCommand(
        record=record,
        dispositions=tuple(
            DispositionRecord(
                KebabId(d.candidate_id),
                d.outcome,
                CleanText(d.reason),
                None if d.report_id is None else KebabId(d.report_id),
            )
            for d in submission.dispositions
        ),
        promotions=promotions,
        reinforcements=tuple(
            ReinforcementCommand(KebabId(r.report_id), KebabId(r.candidate_id))
            for r in submission.reinforcements
        ),
        updates=tuple(updates),
        verifications=tuple(
            VerificationCommand(KebabId(v.report_id), IsoDate(v.verified_on), CleanText(v.note))
            for v in submission.verifications
        ),
    )


def ingest_submission(
    db: Database,
    config: LoadedConfig,
    submission: Submission,
    submission_id: str,
    *,
    allow_deferred: bool = False,
    before_commit: Callable[[], None] | None = None,
) -> IngestOutcome:
    """Validate and apply ``submission`` in one transaction; on any problem write nothing.

    ``before_commit`` runs inside the transaction once everything is applied
    (it writes the submission file); if it raises, the ingest rolls back.
    """
    problems: list[str] = []
    result: IngestResult | None = None
    try:
        with db.transaction():
            context = build_context(db, config, submission, submission_id)
            found = validate_submission(submission, context, allow_deferred=allow_deferred)
            if found:
                problems.extend(str(problem) for problem in found)
                raise _RollbackError
            service = IngestSubmission(
                reports=SqliteReportRepository(db),
                submissions=SqliteSubmissionRepository(db),
                sightings=SqliteSightingLookup(db),
                sources=SqliteSourceDirectory(db),
            )
            try:
                command = to_command(submission, submission_id)
            except ValueError as error:
                problems.append(str(error))
                raise _RollbackError from error
            result = service.execute(command)
            if not result.ok:
                problems.extend(str(problem) for problem in result.problems)
                raise _RollbackError
            if before_commit is not None:
                before_commit()
    except _RollbackError:
        return IngestOutcome(submission_id, tuple(problems))
    return IngestOutcome(submission_id, (), result)


def place_submission(
    path: Path, submissions_dir: Path, submission: Submission
) -> tuple[str, Path, bool]:
    """Where an ingested file lives: ``(stem, target path, already there)``.

    A file already under ``submissions_dir`` (or a byte-identical copy of one)
    keeps its name. Any other file is copied in as ``<run_id>__<n>.json`` or
    ``direct__<received_on>__<n>.json``.
    """
    resolved = path.resolve()
    if resolved.parent == submissions_dir.resolve():
        return path.stem, resolved, True
    data = path.read_bytes()
    existing = sorted(submissions_dir.glob("*.json")) if submissions_dir.is_dir() else []
    for other in existing:
        if other.read_bytes() == data:
            return other.stem, other, True
    stem = next_submission_stem(
        submission.run_id, submission.received_on, (other.stem for other in existing)
    )
    return stem, submissions_dir / f"{stem}.json", False


def ingest_file(
    db: Database,
    config: LoadedConfig,
    path: Path,
    submissions_dir: Path,
    *,
    allow_deferred: bool = False,
) -> IngestOutcome:
    """Ingest the submission file at ``path``, copying it into ``submissions_dir`` on success."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        return IngestOutcome(path.stem, (f"{path}: cannot read: {error}",))
    submission, problems = parse_submission(text)
    if submission is None:
        return IngestOutcome(path.stem, tuple(str(p) for p in problems))
    stem, target, present = place_submission(path, submissions_dir, submission)

    def write() -> None:
        if not present:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())

    outcome = ingest_submission(
        db, config, submission, stem, allow_deferred=allow_deferred, before_commit=write
    )
    return IngestOutcome(outcome.submission_id, outcome.problems, outcome.result, target)
