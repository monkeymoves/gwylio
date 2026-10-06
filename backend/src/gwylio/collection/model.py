"""The Collection context: sources, the query instrument, scan runs, hits and candidates.

Pure, frozen domain objects with no input or output. Construction checks the
rules that concern one object alone; ``find_source_problems`` and
``QueryInstrument.find_problems`` check the rules that span objects (a query
names a known lane, a site query names sources that exist). Cross-context
identifiers (lanes, actors, requirements, topics) arrive as plain sets of
strings, so this context never imports Reference or Direction.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping, Set
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from typing import Any, Final

from gwylio.shared.errors import DomainError, DuplicateId, UnknownReference
from gwylio.shared.values import RUN_ID_PATTERN, CanonicalUrl, CleanText, IsoDate, KebabId, RunId
from gwylio.shared.vocabulary import CandidateStatus, Discipline, MatchedBy, Reliability

__all__ = [
    "RUN_ID_PATTERN",
    "Candidate",
    "CandidateStatus",
    "Discipline",
    "Funnel",
    "FunnelMismatch",
    "GateOutcome",
    "MatchedBy",
    "Query",
    "QueryInstrument",
    "RawHit",
    "Reinforcement",
    "Reliability",
    "RunId",
    "RunImmutable",
    "RunStatus",
    "ScanRun",
    "Sighting",
    "Source",
    "SourceStatus",
    "derive_candidate_id",
    "derive_sighting_id",
    "find_source_problems",
    "make_run_id",
    "run_short",
]

_HEX4_RE: Final[re.Pattern[str]] = re.compile(r"[0-9a-f]{4}")
_HASH_PREFIX: Final[str] = "sha256:"


class SourceStatus(StrEnum):
    """Whether a source is watched."""

    ACTIVE = "active"
    PARKED = "parked"
    RETIRED = "retired"


class RunStatus(StrEnum):
    """Where a scan run is in its life. A complete or aborted run never changes again."""

    RUNNING = "running"
    COMPLETE = "complete"
    ABORTED = "aborted"


class GateOutcome(StrEnum):
    """The fate of one raw hit at the gates, in the order the gates apply."""

    PASSED = "passed"
    DROPPED_OWN = "dropped_own"
    DROPPED_NEGATIVE = "dropped_negative"
    DROPPED_UNRELATED = "dropped_unrelated"


class RunImmutable(DomainError):  # noqa: N818, the name the brief and the domain use
    """Something tried to change a scan run that is complete or aborted."""


class FunnelMismatch(DomainError):  # noqa: N818, paired with RunImmutable
    """A funnel's counts do not add up."""


# Identifiers


def make_run_id(started_at: datetime, suffix: str) -> RunId:
    """The run id for a run that started at ``started_at`` (aware, UTC) with a four-hex suffix."""
    _require_aware(started_at, "started_at")
    if not _HEX4_RE.fullmatch(suffix):
        raise ValueError(f"run id suffix must be four lower-case hex characters, got {suffix!r}")
    return RunId(f"{started_at.strftime('%Y%m%dT%H%MZ')}-{suffix}")


def run_short(run_id: str) -> str:
    """The run id in kebab form, used inside candidate and sighting ids."""
    return RunId(run_id).lower()


def derive_candidate_id(run_id: str, canonical_url: CanonicalUrl, attempt: int = 0) -> KebabId:
    """``c-<run short>-<6 hex>``: stable for a run and canonical URL.

    ``attempt`` salts the hash when two canonical URLs in one run collide.
    """
    digest = hashlib.sha256(f"{run_id}\n{canonical_url.value}\n{attempt}".encode()).hexdigest()
    return KebabId(f"c-{run_short(run_id)}-{digest[:6]}")


def derive_sighting_id(run_id: str, index: int) -> KebabId:
    """``s-<run short>-<6 digits>``: the ``index``th sighting of the run, counting from 1."""
    if index < 1:
        raise ValueError("sighting index counts from 1")
    return KebabId(f"s-{run_short(run_id)}-{index:06d}")


def _require_aware(moment: datetime, name: str) -> None:
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError(f"{name} must be a timezone-aware datetime")


def _bare_host(domain: str, what: str) -> None:
    canonical = CanonicalUrl(domain)
    if canonical.value != domain or canonical.host != domain:
        raise ValueError(
            f"{what} '{domain}' must be a bare lower-case host such as 'gov.wales', "
            "with no scheme, 'www.', port, path or query"
        )


# Sources


@dataclass(frozen=True, slots=True)
class Source:
    """A watchlist entry: where hits come from, with a default reliability."""

    id: KebabId
    name: CleanText
    domain: str
    feed_url: str | None
    discipline: Discipline
    lane: KebabId
    actor: KebabId
    reliability: Reliability
    trusted: bool
    site_pass: bool
    status: SourceStatus
    added_on: IsoDate
    notes: CleanText | None = None

    def __post_init__(self) -> None:
        _bare_host(self.domain, "source domain")
        if self.feed_url is not None:
            if not self.feed_url.startswith(("https://", "http://")):
                raise ValueError(f"feed_url '{self.feed_url}' must be an http or https URL")
            CanonicalUrl(self.feed_url)
        if self.discipline is Discipline.OSINT_FEED and self.feed_url is None:
            raise ValueError(f"source '{self.id}' is an osint_feed source and needs a feed_url")

    @property
    def active(self) -> bool:
        """True when the source is watched."""
        return self.status is SourceStatus.ACTIVE


def find_source_problems(
    sources: Iterable[Source], *, lane_ids: Set[str], actor_ids: Set[str]
) -> tuple[DomainError, ...]:
    """Duplicate ids or domains, and lanes or actors that do not exist."""
    problems: list[DomainError] = []
    ids: set[str] = set()
    domains: dict[str, str] = {}
    for s, source in enumerate(sources):
        where = f"sources[{s}]"
        if source.id in ids:
            problems.append(
                DuplicateId(
                    f"source id '{source.id}' is used twice",
                    scope="sources",
                    location=f"{where}.id",
                )
            )
        ids.add(source.id)
        if source.domain in domains:
            problems.append(
                DuplicateId(
                    f"domain '{source.domain}' is already watched by source "
                    f"'{domains[source.domain]}'; hits are matched to sources by exact domain",
                    scope="sources",
                    location=f"{where}.domain",
                )
            )
        domains.setdefault(source.domain, source.id)
        if source.lane not in lane_ids:
            problems.append(
                UnknownReference(
                    f"source '{source.id}' names unknown lane '{source.lane}'",
                    scope="sources",
                    location=f"{where}.lane",
                )
            )
        if source.actor not in actor_ids:
            problems.append(
                UnknownReference(
                    f"source '{source.id}' names unknown actor '{source.actor}'",
                    scope="sources",
                    location=f"{where}.actor",
                )
            )
    return tuple(problems)


# The query instrument


@dataclass(frozen=True, slots=True)
class Query:
    """One query in the instrument, run by the collector for its discipline.

    ``site_source_ids`` is used only by ``osint_site`` queries, which must name
    at least one source; every other discipline leaves it empty.
    """

    id: KebabId
    discipline: Discipline
    lane: KebabId
    text: CleanText
    requirement_hints: tuple[KebabId, ...] = ()
    topic_hints: tuple[KebabId, ...] = ()
    negative_terms: tuple[CleanText, ...] = ()
    site_source_ids: tuple[KebabId, ...] = ()

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError(f"query '{self.id}' has no text")
        if any(not term.strip() for term in self.negative_terms):
            raise ValueError(f"query '{self.id}' has an empty negative term")
        if self.discipline is Discipline.OSINT_SITE and not self.site_source_ids:
            raise ValueError(f"site query '{self.id}' must name at least one source")
        if self.discipline is not Discipline.OSINT_SITE and self.site_source_ids:
            raise ValueError(
                f"query '{self.id}' is {self.discipline.value}; only osint_site queries name "
                "site sources"
            )
        for name, values in (
            ("requirement_hints", self.requirement_hints),
            ("topic_hints", self.topic_hints),
            ("site_source_ids", self.site_source_ids),
        ):
            if len(set(values)) != len(values):
                raise ValueError(f"query '{self.id}' repeats a value in {name}")

    def as_canonical(self) -> dict[str, Any]:
        """The query as plain JSON values, the form the content hash is computed over."""
        return {
            "id": str(self.id),
            "discipline": self.discipline.value,
            "lane": str(self.lane),
            "text": str(self.text),
            "requirement_hints": [str(hint) for hint in self.requirement_hints],
            "topic_hints": [str(hint) for hint in self.topic_hints],
            "negative_terms": [str(term) for term in self.negative_terms],
            "site_source_ids": [str(source) for source in self.site_source_ids],
        }


@dataclass(frozen=True, slots=True)
class QueryInstrument:
    """The versioned query set. Results are comparable only while it holds still.

    ``content_hash`` is ``sha256:`` and the hex digest of the canonical JSON of
    every other field, so any change to a query, a negative term or the budget
    changes the hash. Free-text notes in the configuration file are not part of
    the instrument and do not change it.
    """

    version: CleanText
    content_hash: str
    global_negative_terms: tuple[CleanText, ...]
    max_requests_per_run: int
    queries: tuple[Query, ...]
    _by_id: dict[str, Query] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise ValueError("the instrument needs a version")
        if self.max_requests_per_run < 1:
            raise ValueError("max_requests_per_run must be at least 1")
        if any(not term.strip() for term in self.global_negative_terms):
            raise ValueError("the instrument has an empty global negative term")
        index: dict[str, Query] = {}
        for query in self.queries:
            index.setdefault(query.id, query)
        object.__setattr__(self, "_by_id", index)

    @staticmethod
    def compute_hash(
        version: str,
        global_negative_terms: Iterable[str],
        max_requests_per_run: int,
        queries: Iterable[Query],
    ) -> str:
        """``sha256:<hex>`` of the canonical JSON (sorted keys, no spaces) of the instrument."""
        payload = {
            "version": str(version),
            "global_negative_terms": [str(term) for term in global_negative_terms],
            "max_requests_per_run": max_requests_per_run,
            "queries": [query.as_canonical() for query in queries],
        }
        text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return _HASH_PREFIX + hashlib.sha256(text.encode("utf-8")).hexdigest()

    @classmethod
    def build(
        cls,
        version: CleanText,
        global_negative_terms: tuple[CleanText, ...],
        max_requests_per_run: int,
        queries: tuple[Query, ...],
    ) -> QueryInstrument:
        """An instrument whose content hash is computed from its content."""
        digest = cls.compute_hash(version, global_negative_terms, max_requests_per_run, queries)
        return cls(version, digest, global_negative_terms, max_requests_per_run, queries)

    def expected_hash(self) -> str:
        """The hash this instrument's content should carry."""
        return self.compute_hash(
            self.version, self.global_negative_terms, self.max_requests_per_run, self.queries
        )

    def verify_hash(self) -> bool:
        """True when ``content_hash`` matches the content."""
        return self.content_hash == self.expected_hash()

    def query(self, query_id: str) -> Query:
        """The query with this identifier, or ``UnknownReference``."""
        try:
            return self._by_id[query_id]
        except KeyError:
            raise UnknownReference(
                f"instrument {self.version} has no query '{query_id}'", scope="instrument"
            ) from None

    def queries_for(self, disciplines: Iterable[Discipline]) -> tuple[Query, ...]:
        """The queries of these disciplines, in instrument order."""
        wanted = frozenset(disciplines)
        return tuple(query for query in self.queries if query.discipline in wanted)

    def negative_terms_for(self, query: Query) -> tuple[CleanText, ...]:
        """The global negative terms, then the query's own."""
        return (*self.global_negative_terms, *query.negative_terms)

    def find_problems(
        self,
        *,
        lane_ids: Set[str],
        requirement_ids: Set[str],
        topic_ids: Set[str],
        sources: Mapping[str, Source],
    ) -> tuple[DomainError, ...]:
        """Every broken rule across the instrument and the catalogues it names."""
        problems: list[DomainError] = []
        if not self.verify_hash():
            problems.append(
                DomainError(
                    f"content_hash is {self.content_hash} but the instrument hashes to "
                    f"{self.expected_hash()}; if the change is deliberate, bump the version "
                    "and store the new hash",
                    scope="instrument",
                    location="content_hash",
                )
            )
        feed_lanes = {
            source.lane for source in sources.values() if source.discipline is Discipline.OSINT_FEED
        }
        seen: set[str] = set()
        for q, query in enumerate(self.queries):
            problems.extend(
                self._query_problems(
                    q, query, seen, lane_ids, requirement_ids, topic_ids, sources, feed_lanes
                )
            )
            seen.add(query.id)
        return tuple(problems)

    def validate(
        self,
        *,
        lane_ids: Set[str],
        requirement_ids: Set[str],
        topic_ids: Set[str],
        sources: Mapping[str, Source],
    ) -> None:
        """Raise the first broken rule, if any."""
        problems = self.find_problems(
            lane_ids=lane_ids, requirement_ids=requirement_ids, topic_ids=topic_ids, sources=sources
        )
        if problems:
            raise problems[0]

    @staticmethod
    def _query_problems(
        q: int,
        query: Query,
        seen: Set[str],
        lane_ids: Set[str],
        requirement_ids: Set[str],
        topic_ids: Set[str],
        sources: Mapping[str, Source],
        feed_lanes: Set[str],
    ) -> list[DomainError]:
        where = f"queries[{q}]"
        problems: list[DomainError] = []

        def unknown(message: str, location: str) -> None:
            problems.append(UnknownReference(message, scope="instrument", location=location))

        if query.id in seen:
            problems.append(
                DuplicateId(
                    f"query id '{query.id}' is used twice",
                    scope="instrument",
                    location=f"{where}.id",
                )
            )
        if query.lane not in lane_ids:
            unknown(f"query '{query.id}' names unknown lane '{query.lane}'", f"{where}.lane")
        for h, hint in enumerate(query.requirement_hints):
            if hint not in requirement_ids:
                unknown(
                    f"query '{query.id}' hints unknown requirement '{hint}'",
                    f"{where}.requirement_hints[{h}]",
                )
        for t, topic in enumerate(query.topic_hints):
            if topic not in topic_ids:
                unknown(
                    f"query '{query.id}' hints unknown topic '{topic}'", f"{where}.topic_hints[{t}]"
                )
        for s, source_id in enumerate(query.site_source_ids):
            location = f"{where}.site_source_ids[{s}]"
            source = sources.get(source_id)
            if source is None:
                unknown(f"site query '{query.id}' names unknown source '{source_id}'", location)
            elif not source.site_pass:
                problems.append(
                    DomainError(
                        f"site query '{query.id}' names source '{source_id}', whose site_pass "
                        "is off",
                        scope="instrument",
                        location=location,
                    )
                )
            elif source.lane != query.lane:
                problems.append(
                    DomainError(
                        f"site query '{query.id}' is in lane '{query.lane}' but names source "
                        f"'{source_id}' from lane '{source.lane}'",
                        scope="instrument",
                        location=location,
                    )
                )
        if query.discipline is Discipline.OSINT_FEED and query.lane not in feed_lanes:
            problems.append(
                DomainError(
                    f"feed query '{query.id}' is in lane '{query.lane}', which has no feed sources",
                    scope="instrument",
                    location=f"{where}.lane",
                )
            )
        return problems


# Hits, candidates and sightings


@dataclass(frozen=True, slots=True)
class RawHit:
    """One result exactly as a collector returned it, before gating.

    ``source_id`` is ``None`` when the collector did not know the source (open
    web search); the scan resolves it by exact domain match. Collectors build
    the title and snippet with ``CleanText.scrub`` because publishers use dashes.
    """

    url: str
    title: CleanText
    snippet: CleanText
    published_on: IsoDate | None
    discipline: Discipline
    query_id: KebabId
    source_id: KebabId | None
    fetched_at: datetime
    canonical_url: CanonicalUrl = field(init=False, repr=False)

    def __post_init__(self) -> None:
        _require_aware(self.fetched_at, "fetched_at")
        object.__setattr__(self, "canonical_url", CanonicalUrl(self.url))

    def with_source(self, source_id: KebabId | None) -> RawHit:
        """This hit with its source resolved."""
        return replace(self, source_id=source_id)


@dataclass(frozen=True, slots=True)
class Candidate:
    """A gated, deduplicated hit: one per canonical URL per run.

    ``first_seen_run_id`` is this run for a URL never seen before, or the
    earlier run that first recorded it. The collector never scores or tags; the
    hints are the union over every query that found the URL in this run, and
    are only hints. The first hit gives the source, query and discipline. The
    lane is the source's lane when the source is known, otherwise the lane of
    the query that found it first.
    """

    id: KebabId
    run_id: RunId
    canonical_url: CanonicalUrl
    url: str
    title: CleanText
    snippet: CleanText
    published_on: IsoDate | None
    first_seen_run_id: RunId
    trusted: bool
    source_id: KebabId | None
    lane: KebabId
    discipline: Discipline
    query_id: KebabId
    requirement_hints: tuple[KebabId, ...] = ()
    topic_hints: tuple[KebabId, ...] = ()

    def __post_init__(self) -> None:
        if CanonicalUrl(self.url) != self.canonical_url:
            raise ValueError(
                f"candidate '{self.id}' url does not canonicalise to its canonical_url"
            )


@dataclass(frozen=True, slots=True)
class Sighting:
    """One hit that became part of a candidate: who saw it, with which query, in which run."""

    id: KebabId
    run_id: RunId
    candidate_id: KebabId
    source_id: KebabId | None
    query_id: KebabId
    discipline: Discipline


@dataclass(frozen=True, slots=True)
class Reinforcement:
    """A candidate whose canonical URL or title matched an existing intelligence report."""

    candidate_id: KebabId
    report_id: KebabId
    matched_by: MatchedBy


# The funnel and the scan run


@dataclass(frozen=True, slots=True)
class Funnel:
    """How many hits survived each stage of a run.

    ``raw`` hits split into the three drops and ``passed`` (hits that reached
    deduplication); ``passed`` hits group into ``unique`` candidates, which
    split into ``new``, ``seen_before`` and ``reinforcements``.
    """

    raw: int = 0
    dropped_own: int = 0
    dropped_negative: int = 0
    dropped_unrelated: int = 0
    passed: int = 0
    unique: int = 0
    seen_before: int = 0
    new: int = 0
    reinforcements: int = 0

    @property
    def dropped(self) -> int:
        """Every hit the gates dropped."""
        return self.dropped_own + self.dropped_negative + self.dropped_unrelated

    def problems(self) -> tuple[str, ...]:
        """Every way the counts fail to add up, as sentences."""
        found: list[str] = []
        for name in (
            "raw",
            "dropped_own",
            "dropped_negative",
            "dropped_unrelated",
            "passed",
            "unique",
            "seen_before",
            "new",
            "reinforcements",
        ):
            if getattr(self, name) < 0:
                found.append(f"{name} is negative")
        if self.raw != self.dropped + self.passed:
            found.append(
                f"raw {self.raw} != dropped_own {self.dropped_own} + dropped_negative "
                f"{self.dropped_negative} + dropped_unrelated {self.dropped_unrelated} + "
                f"passed {self.passed}"
            )
        if self.unique != self.new + self.seen_before + self.reinforcements:
            found.append(
                f"unique {self.unique} != new {self.new} + seen_before {self.seen_before} + "
                f"reinforcements {self.reinforcements}"
            )
        if self.unique > self.passed:
            found.append(f"unique {self.unique} is more than passed {self.passed}")
        if (self.unique == 0) != (self.passed == 0):
            found.append("passed hits always make at least one candidate, and only they do")
        return tuple(found)

    def check(self) -> None:
        """Raise ``FunnelMismatch`` when the counts do not add up."""
        found = self.problems()
        if found:
            raise FunnelMismatch("funnel does not add up: " + "; ".join(found), scope="funnel")


@dataclass(frozen=True, slots=True)
class ScanRun:
    """One execution of the instrument: the unit of time for lifecycle maths.

    The run owns its funnel and its request budget (the instrument's
    ``max_requests_per_run`` when the run started).

    A running run accumulates requests and raw hits through methods that return
    a new instance. Once complete or aborted it never changes: every method
    that would change it raises ``RunImmutable``.
    """

    id: RunId
    started_at: datetime
    instrument_version: CleanText
    instrument_hash: str
    disciplines: tuple[Discipline, ...]
    request_budget: int
    status: RunStatus = RunStatus.RUNNING
    finished_at: datetime | None = None
    funnel: Funnel = field(default_factory=Funnel)
    requests_made: int = 0
    budget_exhausted: bool = False
    notes: tuple[CleanText, ...] = ()

    def __post_init__(self) -> None:
        _require_aware(self.started_at, "started_at")
        if self.finished_at is not None:
            _require_aware(self.finished_at, "finished_at")
            if self.finished_at < self.started_at:
                raise ValueError("a run cannot finish before it starts")
        if (self.status is RunStatus.RUNNING) != (self.finished_at is None):
            raise ValueError("a running run has no finished_at; a finished run must have one")
        if self.requests_made < 0:
            raise ValueError("requests_made cannot be negative")
        if self.request_budget < 1:
            raise ValueError("request_budget must be at least 1")
        if self.status is RunStatus.COMPLETE:
            self.funnel.check()

    @classmethod
    def start(
        cls,
        run_id: RunId,
        started_at: datetime,
        instrument: QueryInstrument,
        disciplines: Iterable[Discipline],
    ) -> ScanRun:
        """A new running run of ``instrument`` over ``disciplines``."""
        wanted = frozenset(disciplines)
        return cls(
            id=run_id,
            started_at=started_at,
            instrument_version=instrument.version,
            instrument_hash=instrument.content_hash,
            disciplines=tuple(d for d in Discipline if d in wanted),
            request_budget=instrument.max_requests_per_run,
            funnel=Funnel(),
        )

    @property
    def finished(self) -> bool:
        """True once the run is complete or aborted."""
        return self.status is not RunStatus.RUNNING

    def _require_running(self, action: str) -> None:
        if self.finished:
            raise RunImmutable(
                f"run {self.id} is {self.status.value}; cannot {action}", scope="scan_run"
            )

    def add_hits(self, hits: int, requests: int) -> ScanRun:
        """Record one dispatch: ``requests`` made and ``hits`` raw hits returned."""
        self._require_running("add hits")
        if hits < 0 or requests < 0:
            raise ValueError("hits and requests cannot be negative")
        return replace(
            self,
            requests_made=self.requests_made + requests,
            funnel=replace(self.funnel, raw=self.funnel.raw + hits),
        )

    def add_note(self, note: CleanText) -> ScanRun:
        """Append a note to the running run."""
        self._require_running("add a note")
        return replace(self, notes=(*self.notes, note))

    def exhaust_budget(self, note: CleanText) -> ScanRun:
        """Mark the request budget as reached, with a note naming what did not run."""
        self._require_running("exhaust the budget")
        return replace(self, budget_exhausted=True, notes=(*self.notes, note))

    def complete(self, finished_at: datetime, funnel: Funnel) -> ScanRun:
        """The completed run with its final funnel, which must add up and match the raw count."""
        self._require_running("complete it")
        if funnel.raw != self.funnel.raw:
            raise FunnelMismatch(
                f"final funnel counts {funnel.raw} raw hits but the run recorded {self.funnel.raw}",
                scope="funnel",
            )
        funnel.check()
        return replace(self, status=RunStatus.COMPLETE, finished_at=finished_at, funnel=funnel)

    def abort(self, finished_at: datetime, note: CleanText) -> ScanRun:
        """The aborted run, with a note saying why."""
        self._require_running("abort it")
        return replace(
            self,
            status=RunStatus.ABORTED,
            finished_at=finished_at,
            notes=(*self.notes, note),
        )
