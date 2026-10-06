"""Read and write ``data/candidates/<run_id>.json``.

Converts a ``RunResult`` from the Collection context to the
``gwylio.candidates/1`` contract in the Processing context and back, and does
the file input and output that neither context may do itself.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from gwylio.collection.model import (
    Candidate,
    Funnel,
    Reinforcement,
    RunStatus,
    ScanRun,
    Sighting,
)
from gwylio.collection.service import RunResult
from gwylio.processing.candidates_file import (
    CANDIDATES_FORMAT,
    CandidateEntry,
    CandidatesFile,
    FunnelCounts,
    ReinforcementEntry,
    SightingEntry,
    dumps_candidates,
    loads_candidates,
)
from gwylio.shared.values import CanonicalUrl, CleanText, IsoDate, KebabId, RunId

__all__ = [
    "CandidatesFileError",
    "candidates_document",
    "read_candidates_file",
    "result_from_document",
    "write_candidates_file",
]


class CandidatesFileError(ValueError):
    """A candidates file could not be read, or would overwrite a fact."""


def _funnel_counts(funnel: Funnel) -> FunnelCounts:
    return FunnelCounts(
        raw=funnel.raw,
        dropped_own=funnel.dropped_own,
        dropped_negative=funnel.dropped_negative,
        dropped_unrelated=funnel.dropped_unrelated,
        passed=funnel.passed,
        unique=funnel.unique,
        seen_before=funnel.seen_before,
        new=funnel.new,
        reinforcements=funnel.reinforcements,
    )


def candidates_document(result: RunResult) -> CandidatesFile:
    """The candidates file for a finished (complete or aborted) run, in normalised order."""
    run = result.run
    if run.status is RunStatus.RUNNING or run.finished_at is None:
        raise CandidatesFileError(
            f"run {run.id} is {run.status.value}; only finished runs are written"
        )
    if run.status is RunStatus.ABORTED and (
        result.candidates or result.sightings or result.reinforcements
    ):
        raise CandidatesFileError(f"run {run.id} aborted, so it keeps no candidates")
    candidates = [
        CandidateEntry(
            candidate_id=c.id,
            status=result.status_of(c),
            url=c.url,
            canonical_url=c.canonical_url.value,
            title=c.title,
            snippet=c.snippet,
            published_on=None if c.published_on is None else str(c.published_on),
            first_seen_run_id=c.first_seen_run_id,
            source_id=c.source_id,
            lane=c.lane,
            discipline=c.discipline,
            query_id=c.query_id,
            requirement_hints=list(c.requirement_hints),
            topic_hints=list(c.topic_hints),
            trusted=c.trusted,
        )
        for c in result.candidates
    ]
    document = CandidatesFile(
        format=CANDIDATES_FORMAT,
        run_id=run.id,
        run_status="aborted" if run.status is RunStatus.ABORTED else "complete",
        instrument_version=run.instrument_version,
        instrument_hash=run.instrument_hash,
        generated_at=run.finished_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        disciplines_run=list(run.disciplines),
        max_requests_per_run=run.request_budget,
        requests_made=run.requests_made,
        budget_exhausted=run.budget_exhausted,
        funnel=_funnel_counts(run.funnel),
        notes=list(run.notes),
        warnings=list(result.warnings),
        candidates=candidates,
        reinforcements=[
            ReinforcementEntry(
                candidate_id=r.candidate_id, report_id=r.report_id, matched_by=r.matched_by
            )
            for r in result.reinforcements
        ],
        sightings=[
            SightingEntry(
                sighting_id=s.id,
                candidate_id=s.candidate_id,
                source_id=s.source_id,
                query_id=s.query_id,
                discipline=s.discipline,
            )
            for s in result.sightings
        ],
    )
    return document.normalised()


def result_from_document(document: CandidatesFile) -> RunResult:
    """The run, candidates, sightings and reinforcements a candidates file records.

    This is what a rebuild reads back: the file is the fact, the database the
    projection.
    """
    run_id = RunId(document.run_id)
    f = document.funnel
    run = ScanRun(
        id=run_id,
        started_at=document.started_at,
        instrument_version=CleanText(document.instrument_version),
        instrument_hash=document.instrument_hash,
        disciplines=tuple(document.disciplines_run),
        request_budget=document.max_requests_per_run,
        status=RunStatus(document.run_status),
        finished_at=document.finished_at,
        funnel=Funnel(
            f.raw,
            f.dropped_own,
            f.dropped_negative,
            f.dropped_unrelated,
            f.passed,
            f.unique,
            f.seen_before,
            f.new,
            f.reinforcements,
        ),
        requests_made=document.requests_made,
        budget_exhausted=document.budget_exhausted,
        notes=tuple(CleanText(note) for note in document.notes),
    )
    candidates = tuple(
        Candidate(
            id=KebabId(c.candidate_id),
            run_id=run_id,
            canonical_url=CanonicalUrl(c.canonical_url),
            url=c.url,
            title=CleanText(c.title),
            snippet=CleanText(c.snippet),
            published_on=None if c.published_on is None else IsoDate(c.published_on),
            first_seen_run_id=RunId(c.first_seen_run_id),
            trusted=c.trusted,
            source_id=None if c.source_id is None else KebabId(c.source_id),
            lane=KebabId(c.lane),
            discipline=c.discipline,
            query_id=KebabId(c.query_id),
            requirement_hints=tuple(KebabId(h) for h in c.requirement_hints),
            topic_hints=tuple(KebabId(h) for h in c.topic_hints),
        )
        for c in document.candidates
    )
    sightings = tuple(
        Sighting(
            id=KebabId(s.sighting_id),
            run_id=run_id,
            candidate_id=KebabId(s.candidate_id),
            source_id=None if s.source_id is None else KebabId(s.source_id),
            query_id=KebabId(s.query_id),
            discipline=s.discipline,
        )
        for s in document.sightings
    )
    reinforcements = tuple(
        Reinforcement(KebabId(r.candidate_id), KebabId(r.report_id), r.matched_by)
        for r in document.reinforcements
    )
    warnings = tuple(CleanText(warning) for warning in document.warnings)
    return RunResult(run, candidates, sightings, reinforcements, warnings)


def write_candidates_file(result: RunResult, path: Path, *, overwrite: bool = False) -> Path:
    """Write the run's candidates file; refuse to replace an existing file unless told to.

    Candidates files under ``data/candidates/`` are append-only facts, so the
    default never overwrites. A dry run writing to a scratch path passes
    ``overwrite=True``.
    """
    text = dumps_candidates(candidates_document(result))
    if path.exists() and not overwrite:
        raise CandidatesFileError(f"{path} already exists; candidates files are never replaced")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def read_candidates_file(path: Path) -> CandidatesFile:
    """Parse and check a candidates file, or raise ``CandidatesFileError`` naming every problem."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise CandidatesFileError(f"{path}: cannot read: {error}") from error
    try:
        return loads_candidates(text)
    except ValidationError as error:
        details = "; ".join(
            f"{'.'.join(str(part) for part in detail['loc']) or 'file'}: {detail['msg']}"
            for detail in error.errors(include_url=False)
        )
        raise CandidatesFileError(f"{path}: not a valid candidates file: {details}") from error
