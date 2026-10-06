"""The submission: the analyst's half of the handoff, and its validator.

``data/submissions/<run_id>__<n>.json`` (format ``gwylio.submission/1``) is
what the analyst skill writes after judging a run's candidates: a disposition
for each candidate, the promotions (new intelligence reports), updates to
existing reports, reinforcements (candidates that are new sightings of
existing reports) and verifications. A submission with no ``run_id`` is an
out-of-run submission, such as the legacy import or a direct analyst addition.

This module holds the contract (Pydantic models) and ``validate_submission``,
a pure function that collects every problem rather than stopping at the first.
It checks everything a submission can get wrong on its own and against the
register, given as plain identifiers in a ``SubmissionContext`` (built by
infrastructure), so this context never imports Intelligence or Collection.

The rules:

- a run submission names a stored run; an out-of-run submission has no
  dispositions, reinforcements or promotions from candidates;
- every ``new`` candidate of the run has a disposition and every
  ``reinforcement`` candidate a reinforcement entry or a disposition, unless
  ``allow_deferred``; ``seen_before`` candidates may have one; no candidate has
  two, and none named is outside the run;
- a ``promoted`` disposition names a promotion from that candidate and every
  promotion from a candidate has one; a ``reinforcement`` disposition has a
  matching reinforcement entry;
- a candidate that an earlier submission already disposed of (other than
  deferred) is not disposed of again;
- promotion ids are new to the register and unique in the file; a
  promotion's canonical URL must not already belong to a report (that is a
  reinforcement);
- requirement, topic, hazard, place, actor, lane and source ids exist;
  credibility is 1 to 6; a promotion without a watched source gives
  ``reliability_if_unknown_source`` and a ``lane``;
- an update names an existing report and sets only ``state`` (matured or
  parked), ``bucket``, ``owner``, ``notes``, ``summary``, ``title``,
  ``event_horizon`` or ``independent_confirmation`` (true);
- reinforcements and verifications name existing reports (or this file's
  promotions); a verification is not dated after the submission was received;
- submissions replay in ``received_on`` then file name order, so a new one
  must sort after every submission already ingested;
- every text field obeys the dash rule (``CleanText``).
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass, field
from typing import Annotated, Any, Final, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, ValidationError

from gwylio.shared.values import (
    KEBAB_MAX_LENGTH,
    KEBAB_PATTERN,
    RUN_ID_PATTERN,
    CanonicalUrl,
    CleanText,
    IsoDate,
)
from gwylio.shared.vocabulary import (
    Bucket,
    CandidateStatus,
    Credibility,
    Direction,
    DispositionOutcome,
    IndicatorState,
    Level,
    Reliability,
    ReportType,
    TimeHorizon,
)

__all__ = [
    "RUBRIC_VERSION",
    "SUBMISSION_FORMAT",
    "UPDATABLE_FIELDS",
    "AssessmentEntry",
    "DispositionEntry",
    "ParsedUpdate",
    "PriorHistoryEntry",
    "PromotionEntry",
    "ReinforcementLink",
    "RunCandidate",
    "ScoresEntry",
    "Submission",
    "SubmissionContext",
    "SubmissionProblem",
    "UpdateEntry",
    "VerificationEntry",
    "dumps_submission",
    "parse_submission",
    "parse_update",
    "validate_submission",
]

SUBMISSION_FORMAT: Final = "gwylio.submission/1"
"""The format identifier every submission carries in its ``schema`` field."""

RUBRIC_VERSION: Final = "2026.10"
"""The version of docs/RUBRIC.md that submissions are judged against now."""

UPDATABLE_FIELDS: Final[tuple[str, ...]] = (
    "state",
    "bucket",
    "owner",
    "notes",
    "summary",
    "title",
    "event_horizon",
    "independent_confirmation",
)
"""The only keys an update's ``set`` may name."""

_SETTABLE_STATES: Final[tuple[str, ...]] = (
    IndicatorState.MATURED.value,
    IndicatorState.PARKED.value,
)


def _iso_date(value: str) -> str:
    IsoDate(value)
    return value


def _words(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be blank")
    return value


def _http_url(value: str) -> str:
    if not value.startswith(("https://", "http://")):
        raise ValueError("must be an http or https URL")
    CanonicalUrl(value)
    return value


Prose = Annotated[str, AfterValidator(CleanText)]
"""Human-readable text, free of en and em dashes."""
Words = Annotated[str, AfterValidator(CleanText), AfterValidator(_words)]
"""Prose that must not be blank."""
Id = Annotated[str, Field(pattern=KEBAB_PATTERN, max_length=KEBAB_MAX_LENGTH)]
RunIdText = Annotated[str, Field(pattern=RUN_ID_PATTERN, description="A scan run id.")]
DateText = Annotated[
    str,
    Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$", description="A date, YYYY-MM-DD."),
    AfterValidator(_iso_date),
]
UrlText = Annotated[
    str,
    Field(min_length=1, pattern=r"^https?://[^\s]+$", description="The http or https URL."),
    AfterValidator(_http_url),
]


class _FileModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class AssessmentEntry(_FileModel):
    """Which way the report bears on one requirement."""

    requirement_id: Id = Field(description="A requirement id from skill/REFERENCE.md, such as si4.")
    direction: Direction


class ScoresEntry(_FileModel):
    """The analyst's scores for a report."""

    evidence: Level = Field(description="How strong the evidence on the page is.")
    novelty: Level
    confidence: Level
    potential_impact: Level
    time_horizon: TimeHorizon


class PriorHistoryEntry(_FileModel):
    """One line of history the report had before it entered Gwylio (the legacy import)."""

    on: DateText
    change: Words


class DispositionEntry(_FileModel):
    """The fate of one candidate."""

    candidate_id: Id
    outcome: DispositionOutcome
    reason: Words = Field(description="One sentence: which part of the promotion test decided.")
    report_id: Id | None = Field(
        default=None,
        description="promoted: the new report; reinforcement: the report it reinforces; "
        "duplicate: optionally, the report it duplicates.",
    )


class PromotionEntry(_FileModel):
    """A new intelligence report. Reliability, lane and appearances are not the analyst's."""

    id: Id = Field(description="A new kebab-case report id.")
    from_candidate: Id | None = Field(
        default=None, description="The candidate this report was promoted from, if any."
    )
    title: Words
    url: UrlText
    source_id: Id | None = Field(description="The watched source, or null when unwatched.")
    source_name: Words = Field(description="Who published it, as a reader would name them.")
    actor_id: Id | None = Field(default=None, description="The actor, when catalogued.")
    lane: Id | None = Field(
        default=None,
        description="Where it was found; required when source_id is null, else the source's.",
    )
    report_type: ReportType
    credibility: Credibility = Field(description="Admiralty credibility, 1 to 6.")
    reliability_if_unknown_source: Reliability | None = Field(
        default=None,
        description="Required when source_id is null; ignored otherwise (the source decides).",
    )
    assessments: list[AssessmentEntry] = Field(min_length=1)
    topics: list[Id] = Field(default_factory=list)
    hazards: list[Id] = Field(default_factory=list)
    places: list[Id] = Field(default_factory=list)
    scores: ScoresEntry
    bucket: Bucket
    event_horizon: DateText | None = None
    last_verified: DateText | None = None
    summary: Words
    notes: Prose = ""
    owner: Words | None = None
    state_override: Literal["matured", "parked"] | None = Field(
        default=None, description="Create the report as matured or parked instead of emerging."
    )
    prior_history: list[PriorHistoryEntry] = Field(
        default_factory=list,
        description="History from before Gwylio, carried as imported entries (legacy import).",
    )
    creation_note: Words | None = Field(
        default=None, description="The text of the creation history entry, if not the default."
    )


class UpdateEntry(_FileModel):
    """Analyst changes to an existing report."""

    report_id: Id
    set_: dict[str, Any] = Field(
        alias="set",
        min_length=1,
        description="Only state (matured or parked), bucket, owner, notes, summary, title, "
        "event_horizon and independent_confirmation (true) may be set.",
    )
    change: Words = Field(description="Why: the history entry text.")


class ReinforcementLink(_FileModel):
    """A candidate whose sightings count for an existing report."""

    report_id: Id
    candidate_id: Id


class VerificationEntry(_FileModel):
    """The analyst checked the report's claims against the world."""

    report_id: Id
    verified_on: DateText
    note: Words


class Submission(_FileModel):
    """data/submissions/<run_id>__<n>.json: the analyst's judgements on one run, or none."""

    schema_: Literal["gwylio.submission/1"] = Field(
        alias="schema", description="Always gwylio.submission/1."
    )
    run_id: RunIdText | None = Field(description="The run judged, or null for out-of-run.")
    analyst: Words
    rubric_version: str = Field(pattern=r"^[0-9]{4}\.[0-9]{1,2}$", description="Such as 2026.10.")
    received_on: DateText
    dispositions: list[DispositionEntry] = Field(default_factory=list)
    promotions: list[PromotionEntry] = Field(default_factory=list)
    updates: list[UpdateEntry] = Field(default_factory=list)
    reinforcements: list[ReinforcementLink] = Field(default_factory=list)
    verifications: list[VerificationEntry] = Field(default_factory=list)
    method_note: Words = Field(description="How the run was judged: what was read and skipped.")


# Problems and the validation context.


@dataclass(frozen=True, slots=True)
class SubmissionProblem:
    """One thing wrong with a submission, located by a path inside it."""

    location: str
    message: str

    def __str__(self) -> str:
        return f"{self.location}: {self.message}" if self.location else self.message


@dataclass(frozen=True, slots=True)
class RunCandidate:
    """One candidate of the judged run, as its candidates file records it."""

    candidate_id: str
    status: CandidateStatus
    canonical_url: str
    reinforces: str | None = None


@dataclass(frozen=True, slots=True)
class SubmissionContext:
    """What the validator needs to know about the world, as plain identifiers.

    ``run_candidates`` is ``None`` when the submission names a run that is not
    stored. ``report_urls`` maps a canonical URL's ``match_key`` to the report
    holding it. ``earlier_dispositions`` maps a candidate id to the submission
    and outcome of its last final (not deferred) disposition. ``last_ingested``
    is the replay key, ``(received_on, file stem)``, of the latest submission.
    """

    submission_id: str
    run_candidates: Mapping[str, RunCandidate] | None = None
    report_ids: Set[str] = frozenset()
    report_urls: Mapping[str, str] = field(default_factory=dict)
    requirement_ids: Set[str] = frozenset()
    topic_ids: Set[str] = frozenset()
    hazard_ids: Set[str] = frozenset()
    place_ids: Set[str] = frozenset()
    actor_ids: Set[str] = frozenset()
    lane_ids: Set[str] = frozenset()
    source_ids: Set[str] = frozenset()
    earlier_dispositions: Mapping[str, tuple[str, str]] = field(default_factory=dict)
    last_ingested: tuple[str, str] | None = None
    already_ingested: bool = False


# Parsing.


def _location(loc: Sequence[int | str]) -> str:
    out = ""
    for part in loc:
        name = "set" if part == "set_" else ("schema" if part == "schema_" else part)
        out += f"[{name}]" if isinstance(name, int) else (f".{name}" if out else str(name))
    return out


def parse_submission(text: str) -> tuple[Submission | None, list[SubmissionProblem]]:
    """The submission in ``text``, or ``None`` and every problem the contract finds."""
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as error:
        return None, [
            SubmissionProblem(
                f"line {error.lineno} column {error.colno}", f"invalid JSON: {error.msg}"
            )
        ]
    try:
        return Submission.model_validate(raw), []
    except ValidationError as error:
        return None, [
            SubmissionProblem(_location(detail["loc"]), detail["msg"])
            for detail in error.errors(include_url=False)
        ]


def dumps_submission(submission: Submission) -> str:
    """The file's text: field names as the contract spells them, two-space indent, newline."""
    data = submission.model_dump(mode="json", by_alias=True)
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


@dataclass(frozen=True, slots=True)
class ParsedUpdate:
    """An update's ``set`` block, checked and typed. ``*_given`` say whether a key was named."""

    state: str | None = None
    bucket: Bucket | None = None
    title: CleanText | None = None
    summary: CleanText | None = None
    notes: CleanText | None = None
    owner_given: bool = False
    owner: CleanText | None = None
    event_horizon_given: bool = False
    event_horizon: IsoDate | None = None
    independent_confirmation: bool = False


def _text(value: Any, key: str, where: str, problems: list[SubmissionProblem]) -> CleanText | None:
    if not isinstance(value, str) or not value.strip():
        problems.append(SubmissionProblem(f"{where}.{key}", f"{key} must be non-empty text"))
        return None
    try:
        return CleanText(value)
    except ValueError as error:
        problems.append(SubmissionProblem(f"{where}.{key}", str(error)))
        return None


def parse_update(
    values: Mapping[str, Any], where: str
) -> tuple[ParsedUpdate, list[SubmissionProblem]]:
    """The typed form of an update's ``set``, with a problem for every key or value refused."""
    problems: list[SubmissionProblem] = []
    parsed: dict[str, Any] = {}
    for key, value in values.items():
        here = f"{where}.{key}"
        if key not in UPDATABLE_FIELDS:
            problems.append(
                SubmissionProblem(
                    here,
                    f"'{key}' cannot be set by an update; settable keys are "
                    + ", ".join(UPDATABLE_FIELDS),
                )
            )
        elif key == "state":
            if value not in _SETTABLE_STATES:
                problems.append(
                    SubmissionProblem(
                        here,
                        f"state may be set to matured or parked only, not {value!r}; the "
                        "lifecycle sets every other state",
                    )
                )
            else:
                parsed["state"] = value
        elif key == "bucket":
            try:
                parsed["bucket"] = Bucket(value)
            except ValueError:
                problems.append(SubmissionProblem(here, f"unknown bucket {value!r}"))
        elif key in ("title", "summary"):
            parsed[key] = _text(value, key, where, problems)
        elif key == "notes":
            if not isinstance(value, str):
                problems.append(SubmissionProblem(here, "notes must be text"))
            else:
                try:
                    parsed["notes"] = CleanText(value)
                except ValueError as error:
                    problems.append(SubmissionProblem(here, str(error)))
        elif key == "owner":
            parsed["owner_given"] = True
            parsed["owner"] = None if value is None else _text(value, key, where, problems)
        elif key == "event_horizon":
            parsed["event_horizon_given"] = True
            if value is not None:
                try:
                    parsed["event_horizon"] = IsoDate(value)
                except (ValueError, TypeError):
                    problems.append(SubmissionProblem(here, f"not a YYYY-MM-DD date: {value!r}"))
        elif value is not True:
            problems.append(
                SubmissionProblem(
                    here, "independent_confirmation can only be set to true; it is never undone"
                )
            )
        else:
            parsed["independent_confirmation"] = True
    return ParsedUpdate(**parsed), problems


# Validation.


class _Checker:
    def __init__(self, submission: Submission, context: SubmissionContext) -> None:
        self.s = submission
        self.c = context
        self.problems: list[SubmissionProblem] = []

    def add(self, location: str, message: str) -> None:
        self.problems.append(SubmissionProblem(location, message))

    def known(self, value: str, ids: Set[str], kind: str, location: str) -> None:
        if value not in ids:
            self.add(location, f"unknown {kind} '{value}'")

    def run(self, allow_deferred: bool) -> list[SubmissionProblem]:
        self.header()
        promoted = self.promotions()
        reports = set(self.c.report_ids) | promoted
        self.dispositions(allow_deferred)
        for u, update in enumerate(self.s.updates):
            where = f"updates[{u}]"
            if update.report_id not in self.c.report_ids:
                self.add(f"{where}.report_id", f"no report '{update.report_id}' in the register")
            self.problems.extend(parse_update(update.set_, f"{where}.set")[1])
        for r, link in enumerate(self.s.reinforcements):
            if link.report_id not in reports:
                self.add(
                    f"reinforcements[{r}].report_id",
                    f"no report '{link.report_id}' in the register or this submission",
                )
        received = IsoDate(self.s.received_on)
        for v, check in enumerate(self.s.verifications):
            where = f"verifications[{v}]"
            if check.report_id not in reports:
                self.add(f"{where}.report_id", f"no report '{check.report_id}' in the register")
            if IsoDate(check.verified_on) > received:
                self.add(
                    f"{where}.verified_on",
                    f"verified_on {check.verified_on} is after received_on {received}",
                )
        return self.problems

    def header(self) -> None:
        s, c = self.s, self.c
        if c.already_ingested:
            self.add("", f"submission {c.submission_id} is already ingested")
        key = (s.received_on, c.submission_id)
        if c.last_ingested is not None and key <= c.last_ingested:
            self.add(
                "received_on",
                f"submissions replay in received_on then file name order, and "
                f"{c.last_ingested[1]} (received {c.last_ingested[0]}) is already ingested; "
                f"this one ({c.submission_id}, received {s.received_on}) would replay before it",
            )
        if s.run_id is None:
            if s.dispositions:
                self.add("dispositions", "an out-of-run submission has no candidates to dispose of")
            if s.reinforcements:
                self.add("reinforcements", "an out-of-run submission has no candidates to link")
            for p, promotion in enumerate(s.promotions):
                if promotion.from_candidate is not None:
                    self.add(
                        f"promotions[{p}].from_candidate",
                        f"an out-of-run submission cannot promote candidate "
                        f"'{promotion.from_candidate}'",
                    )
        elif c.run_candidates is None:
            self.add("run_id", f"run {s.run_id} is not stored; collect or rebuild first")

    def promotions(self) -> set[str]:
        ids = Counter(p.id for p in self.s.promotions)
        for p, promotion in enumerate(self.s.promotions):
            where = f"promotions[{p}]"
            if promotion.id in self.c.report_ids:
                self.add(f"{where}.id", f"report '{promotion.id}' already exists in the register")
            if ids[promotion.id] > 1:
                self.add(f"{where}.id", f"promotion id '{promotion.id}' is used more than once")
            key = CanonicalUrl(promotion.url).match_key
            holder = self.c.report_urls.get(key)
            if holder is not None:
                self.add(
                    f"{where}.url",
                    f"{CanonicalUrl(promotion.url).value} already belongs to report '{holder}': "
                    "a new sighting of it is a reinforcement, not a promotion",
                )
            for a, assessment in enumerate(promotion.assessments):
                self.known(
                    assessment.requirement_id,
                    self.c.requirement_ids,
                    "requirement",
                    f"{where}.assessments[{a}].requirement_id",
                )
            required = Counter(a.requirement_id for a in promotion.assessments)
            for requirement, count in sorted(required.items()):
                if count > 1:
                    self.add(f"{where}.assessments", f"requirement '{requirement}' assessed twice")
            for kind, values, ids_known in (
                ("topic", promotion.topics, self.c.topic_ids),
                ("hazard", promotion.hazards, self.c.hazard_ids),
                ("place", promotion.places, self.c.place_ids),
            ):
                for t, value in enumerate(values):
                    self.known(value, ids_known, kind, f"{where}.{kind}s[{t}]")
                for value, count in sorted(Counter(values).items()):
                    if count > 1:
                        self.add(f"{where}.{kind}s", f"{kind} '{value}' is listed twice")
            if promotion.actor_id is not None:
                self.known(promotion.actor_id, self.c.actor_ids, "actor", f"{where}.actor_id")
            if promotion.lane is not None:
                self.known(promotion.lane, self.c.lane_ids, "lane", f"{where}.lane")
            if promotion.source_id is not None:
                self.known(promotion.source_id, self.c.source_ids, "source", f"{where}.source_id")
            else:
                if promotion.reliability_if_unknown_source is None:
                    self.add(
                        f"{where}.reliability_if_unknown_source",
                        f"promotion '{promotion.id}' has no watched source, so "
                        "reliability_if_unknown_source is required",
                    )
                if promotion.lane is None:
                    self.add(
                        f"{where}.lane",
                        f"promotion '{promotion.id}' has no watched source, so lane is required",
                    )
        return set(ids)

    def dispositions(self, allow_deferred: bool) -> None:
        s, c = self.s, self.c
        if s.run_id is None or c.run_candidates is None:
            return
        candidates = c.run_candidates
        seen = Counter(d.candidate_id for d in s.dispositions)
        links = {link.candidate_id: link for link in s.reinforcements}
        link_counts = Counter(link.candidate_id for link in s.reinforcements)
        promotions: dict[str, PromotionEntry] = {}
        for promotion in s.promotions:
            promotions.setdefault(promotion.id, promotion)
        for d, disposition in enumerate(s.dispositions):
            where = f"dispositions[{d}]"
            cid = disposition.candidate_id
            if cid not in candidates:
                self.add(f"{where}.candidate_id", f"candidate '{cid}' is not in run {s.run_id}")
                continue
            if seen[cid] > 1:
                self.add(
                    f"{where}.candidate_id", f"candidate '{cid}' has more than one disposition"
                )
            earlier = c.earlier_dispositions.get(cid)
            if earlier is not None:
                self.add(
                    f"{where}.candidate_id",
                    f"candidate '{cid}' was already disposed of as {earlier[1]} in submission "
                    f"{earlier[0]}",
                )
            self.outcome(where, disposition, promotions, links)
        for p, promotion in enumerate(s.promotions):
            source = promotion.from_candidate
            if source is None:
                continue
            where = f"promotions[{p}].from_candidate"
            if source not in candidates:
                self.add(where, f"candidate '{source}' is not in run {s.run_id}")
            elif not any(
                d.candidate_id == source
                and d.outcome is DispositionOutcome.PROMOTED
                and d.report_id == promotion.id
                for d in s.dispositions
            ):
                self.add(
                    where,
                    f"promotion '{promotion.id}' comes from candidate '{source}', which needs a "
                    f"promoted disposition naming report '{promotion.id}'",
                )
        for r, link in enumerate(s.reinforcements):
            where = f"reinforcements[{r}].candidate_id"
            if link.candidate_id not in candidates:
                self.add(where, f"candidate '{link.candidate_id}' is not in run {s.run_id}")
            elif link_counts[link.candidate_id] > 1:
                self.add(where, f"candidate '{link.candidate_id}' is linked more than once")
        if allow_deferred:
            return
        for cid in sorted(candidates):
            candidate = candidates[cid]
            if seen[cid] or cid in c.earlier_dispositions:
                continue
            if candidate.status is CandidateStatus.NEW:
                self.add(
                    "dispositions",
                    f"new candidate '{cid}' ({candidate.canonical_url}) has no disposition; "
                    "give it one, or ingest with --allow-deferred",
                )
            elif candidate.status is CandidateStatus.REINFORCEMENT and cid not in links:
                self.add(
                    "reinforcements",
                    f"candidate '{cid}' matched report '{candidate.reinforces}' at collection; "
                    "confirm it in reinforcements or give it a disposition, or ingest with "
                    "--allow-deferred",
                )

    def outcome(
        self,
        where: str,
        disposition: DispositionEntry,
        promotions: Mapping[str, PromotionEntry],
        links: Mapping[str, ReinforcementLink],
    ) -> None:
        cid = disposition.candidate_id
        report = disposition.report_id
        outcome = disposition.outcome
        if outcome is DispositionOutcome.PROMOTED:
            promotion = None if report is None else promotions.get(report)
            if promotion is None:
                self.add(
                    f"{where}.report_id",
                    f"promoted candidate '{cid}' must name one of this file's promotions",
                )
            elif promotion.from_candidate != cid:
                self.add(
                    f"{where}.report_id",
                    f"promotion '{report}' must give from_candidate '{cid}'",
                )
        elif outcome is DispositionOutcome.REINFORCEMENT:
            link = links.get(cid)
            if report is None:
                self.add(f"{where}.report_id", f"reinforcement '{cid}' must name its report")
            elif link is None or link.report_id != report:
                self.add(
                    f"{where}.report_id",
                    f"reinforcement '{cid}' of report '{report}' needs a matching entry in "
                    "reinforcements",
                )
        elif outcome is DispositionOutcome.DEFERRED and report is not None:
            self.add(f"{where}.report_id", f"deferred candidate '{cid}' names no report")
        elif (
            outcome is DispositionOutcome.DUPLICATE
            and report is not None
            and report not in self.c.report_ids
            and report not in promotions
        ):
            self.add(f"{where}.report_id", f"no report '{report}' in the register")
        if outcome is not DispositionOutcome.REINFORCEMENT and cid in links:
            self.add(
                f"{where}.outcome",
                f"candidate '{cid}' is linked in reinforcements, so its outcome must be "
                "reinforcement",
            )


def validate_submission(
    submission: Submission, context: SubmissionContext, *, allow_deferred: bool = False
) -> list[SubmissionProblem]:
    """Every problem with ``submission`` in ``context``; none means it may be applied."""
    return _Checker(submission, context).run(allow_deferred)
