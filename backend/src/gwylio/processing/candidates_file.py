"""The candidates file: the collector's half of the handoff to the analyst skill.

``data/candidates/<run_id>.json`` (format ``gwylio.candidates/1``) is a fact
on disk: append-only, committed, and enough on its own to rebuild the run, its
candidates, their sightings and the reinforcements spotted at collection. This
module holds the contract only (Pydantic models, pure text conversion and the
consistency rules); reading and writing the file is infrastructure's job.

A complete run's file lists every candidate of the run with its ``status``: ``new`` ones
are what the analyst triages; ``seen_before`` ones were recorded by an earlier
run; ``reinforcement`` ones matched an existing report, named in
``reinforcements``. Ordering is deterministic: candidates by canonical URL,
reinforcements by report id then candidate id, sightings by sighting id.

A run that aborted (a collector failed unexpectedly) is a fact too: its file
has ``run_status`` ``aborted``, no candidates, sightings or reinforcements, and
a funnel that counts only the raw hits collected before it stopped. Its last
note says why it stopped.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Annotated, Final, Literal

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from gwylio.shared.values import (
    KEBAB_MAX_LENGTH,
    KEBAB_PATTERN,
    RUN_ID_PATTERN,
    CanonicalUrl,
    CleanText,
    IsoDate,
)
from gwylio.shared.vocabulary import CandidateStatus, Discipline, MatchedBy

__all__ = [
    "CANDIDATES_FORMAT",
    "CandidateEntry",
    "CandidatesFile",
    "FunnelCounts",
    "ReinforcementEntry",
    "SightingEntry",
    "dumps_candidates",
    "loads_candidates",
]

CANDIDATES_FORMAT: Final = "gwylio.candidates/1"
"""The format identifier every candidates file carries."""


def _iso_date(value: str) -> str:
    IsoDate(value)
    return value


def _canonical(value: str) -> str:
    if CanonicalUrl(value).value != value:
        raise ValueError(f"'{value}' is not in canonical form")
    return value


Prose = Annotated[str, AfterValidator(CleanText)]
Id = Annotated[str, Field(pattern=KEBAB_PATTERN, max_length=KEBAB_MAX_LENGTH)]
RunIdText = Annotated[str, Field(pattern=RUN_ID_PATTERN, description="A scan run id.")]
DateText = Annotated[
    str,
    Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$", description="A date, YYYY-MM-DD."),
    AfterValidator(_iso_date),
]
CanonicalText = Annotated[
    str,
    Field(min_length=1, description="The canonical URL: no scheme, www, fragment or tracking."),
    AfterValidator(_canonical),
]
Count = Annotated[int, Field(ge=0)]


class _FileModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FunnelCounts(_FileModel):
    """How many hits survived each stage of the run.

    raw = dropped_own + dropped_negative + dropped_unrelated + passed, and
    unique = new + seen_before + reinforcements.
    """

    raw: Count
    dropped_own: Count
    dropped_negative: Count
    dropped_unrelated: Count
    passed: Count = Field(description="Hits that passed every gate and reached deduplication.")
    unique: Count = Field(description="Candidates: passed hits grouped by canonical URL.")
    seen_before: Count
    new: Count
    reinforcements: Count


class CandidateEntry(_FileModel):
    """One candidate: a gated, deduplicated hit, one per canonical URL in the run."""

    candidate_id: Id
    status: CandidateStatus
    url: str = Field(min_length=1, description="The URL as first found, before canonicalising.")
    canonical_url: CanonicalText
    title: Prose
    snippet: Prose
    published_on: DateText | None
    first_seen_run_id: RunIdText = Field(description="The run that first recorded this URL.")
    source_id: Id | None = Field(description="The watched source, or null for the open web.")
    lane: Id
    discipline: Discipline
    query_id: Id = Field(description="The query whose hit found this URL first.")
    requirement_hints: list[Id] = Field(description="Hints from the queries; not tags.")
    topic_hints: list[Id] = Field(description="Hints from the queries; not tags.")
    trusted: bool


class ReinforcementEntry(_FileModel):
    """A candidate that matched an existing intelligence report at collection time."""

    candidate_id: Id
    report_id: Id
    matched_by: MatchedBy


class SightingEntry(_FileModel):
    """One hit that became part of a candidate."""

    sighting_id: Id
    candidate_id: Id
    source_id: Id | None
    query_id: Id
    discipline: Discipline


class CandidatesFile(_FileModel):
    """data/candidates/<run_id>.json: everything one completed scan run found."""

    format: Literal["gwylio.candidates/1"] = Field(description="Always gwylio.candidates/1.")
    run_id: RunIdText
    run_status: Literal["complete", "aborted"] = Field(
        default="complete",
        description="complete, or aborted when a collector failed: then nothing was kept.",
    )
    instrument_version: Prose
    instrument_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    generated_at: AwareDatetime
    started_at: AwareDatetime
    finished_at: AwareDatetime
    disciplines_run: list[Discipline]
    max_requests_per_run: int = Field(ge=1)
    requests_made: Count
    budget_exhausted: bool
    funnel: FunnelCounts
    notes: list[Prose] = Field(description="What the run says about itself, such as the budget.")
    warnings: list[Prose] = Field(description="Soft failures the collectors reported.")
    candidates: list[CandidateEntry]
    reinforcements: list[ReinforcementEntry]
    sightings: list[SightingEntry]

    @model_validator(mode="after")
    def _consistent(self) -> CandidatesFile:
        problems = self.problems()
        if problems:
            raise ValueError("; ".join(problems))
        return self

    def problems(self) -> list[str]:
        """Every way the file contradicts itself, as sentences."""
        found: list[str] = []
        if self.run_status == "aborted":
            found.extend(self._aborted_problems())
        else:
            found.extend(_funnel_problems(self.funnel))
        if self.finished_at < self.started_at:
            found.append("finished_at is before started_at")
        if len(set(self.disciplines_run)) != len(self.disciplines_run):
            found.append("disciplines_run repeats a discipline")
        ids = Counter(c.candidate_id for c in self.candidates)
        found.extend(f"candidate id {i} appears {n} times" for i, n in ids.items() if n > 1)
        urls = Counter(c.canonical_url for c in self.candidates)
        found.extend(f"canonical URL {u} appears {n} times" for u, n in urls.items() if n > 1)
        reinforced = {r.candidate_id for r in self.reinforcements}
        if len(reinforced) != len(self.reinforcements):
            found.append("a candidate is reinforced more than once")
        sighted = Counter(s.candidate_id for s in self.sightings)
        for c in self.candidates:
            found.extend(self._candidate_problems(c, c.candidate_id in reinforced, sighted))
        found.extend(
            f"reinforcement names unknown candidate {r}" for r in sorted(reinforced - set(ids))
        )
        found.extend(
            f"sighting names unknown candidate {s}" for s in sorted(set(sighted) - set(ids))
        )
        sighting_ids = Counter(s.sighting_id for s in self.sightings)
        found.extend(f"sighting id {i} appears {n} times" for i, n in sighting_ids.items() if n > 1)
        statuses = Counter(c.status for c in self.candidates)
        expected = {
            "unique": len(self.candidates),
            "new": statuses[CandidateStatus.NEW],
            "seen_before": statuses[CandidateStatus.SEEN_BEFORE],
            "reinforcements": statuses[CandidateStatus.REINFORCEMENT],
            "passed": len(self.sightings),
        }
        for name, count in expected.items():
            if getattr(self.funnel, name) != count:
                found.append(
                    f"funnel {name} is {getattr(self.funnel, name)} but the file has {count}"
                )
        return found

    def _aborted_problems(self) -> list[str]:
        found: list[str] = []
        for name in ("candidates", "sightings", "reinforcements"):
            if getattr(self, name):
                found.append(f"an aborted run keeps no {name}")
        for name in FunnelCounts.model_fields:
            if name != "raw" and getattr(self.funnel, name) != 0:
                found.append(f"an aborted run's funnel counts only raw hits, but {name} is set")
        if not self.notes:
            found.append("an aborted run needs a note saying why it stopped")
        return found

    def _candidate_problems(
        self, entry: CandidateEntry, reinforced: bool, sighted: Counter[str]
    ) -> list[str]:
        found: list[str] = []
        name = f"candidate {entry.candidate_id}"
        if CanonicalUrl(entry.url).value != entry.canonical_url:
            found.append(f"{name} url does not canonicalise to its canonical_url")
        if reinforced != (entry.status is CandidateStatus.REINFORCEMENT):
            found.append(f"{name} has status {entry.status.value} but reinforced={reinforced}")
        if entry.status is CandidateStatus.SEEN_BEFORE and entry.first_seen_run_id == self.run_id:
            found.append(f"{name} is seen_before but was first seen in this run")
        if entry.status is CandidateStatus.NEW and entry.first_seen_run_id != self.run_id:
            found.append(f"{name} is new but was first seen in {entry.first_seen_run_id}")
        if sighted[entry.candidate_id] == 0:
            found.append(f"{name} has no sightings")
        return found

    def normalised(self) -> CandidatesFile:
        """The same file in the deterministic order every writer uses."""
        return self.model_copy(
            update={
                "candidates": sorted(self.candidates, key=lambda c: c.canonical_url),
                "reinforcements": sorted(
                    self.reinforcements, key=lambda r: (r.report_id, r.candidate_id)
                ),
                "sightings": sorted(self.sightings, key=lambda s: s.sighting_id),
            }
        )


def _funnel_problems(funnel: FunnelCounts) -> list[str]:
    found: list[str] = []
    dropped = funnel.dropped_own + funnel.dropped_negative + funnel.dropped_unrelated
    if funnel.raw != dropped + funnel.passed:
        found.append(f"funnel raw {funnel.raw} != drops {dropped} + passed {funnel.passed}")
    if funnel.unique != funnel.new + funnel.seen_before + funnel.reinforcements:
        found.append(
            f"funnel unique {funnel.unique} != new {funnel.new} + seen_before "
            f"{funnel.seen_before} + reinforcements {funnel.reinforcements}"
        )
    if funnel.unique > funnel.passed:
        found.append(f"funnel unique {funnel.unique} is more than passed {funnel.passed}")
    return found


def dumps_candidates(document: CandidatesFile) -> str:
    """The file's text: normalised order, two-space indent, UTF-8 characters, trailing newline."""
    data = document.normalised().model_dump(mode="json")
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def loads_candidates(text: str) -> CandidatesFile:
    """Parse and check a candidates file's text; raises ``pydantic.ValidationError``."""
    return CandidatesFile.model_validate_json(text)
