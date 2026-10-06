"""Application services of the Collection context: ``RunScan`` and ``Probe``.

``RunScan`` executes the instrument once: it dispatches each query to the
collector for its discipline within the request budget, resolves each hit's
source, gates, deduplicates and matches against what is already known, builds
candidates and sightings, checks the funnel, completes the run and stores
everything through the repository ports. ``Probe`` runs one query text and
stores nothing. Neither performs input or output itself: collectors and
repositories do, behind their ports.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from gwylio.collection.dedup import SeenIndex, group_hits, match_known
from gwylio.collection.gates import GatingRules, gate
from gwylio.collection.model import (
    Candidate,
    CandidateStatus,
    Funnel,
    GateOutcome,
    Query,
    QueryInstrument,
    RawHit,
    Reinforcement,
    ScanRun,
    Sighting,
    Source,
)
from gwylio.collection.ports import (
    CandidateRepository,
    Collector,
    CollectResult,
    IdGenerator,
    InstrumentRepository,
    KnownReports,
    ScanRunRepository,
)
from gwylio.shared.clock import Clock
from gwylio.shared.errors import DomainError
from gwylio.shared.values import CleanText, KebabId
from gwylio.shared.vocabulary import Discipline

__all__ = [
    "PROBE_QUERY_ID",
    "Probe",
    "ProbeResult",
    "RunResult",
    "RunScan",
    "ScanAborted",
]

PROBE_QUERY_ID = KebabId("probe")
"""The query id every probe hit carries."""


class ScanAborted(DomainError):  # noqa: N818, an event-like name reads better here
    """A collector failed unexpectedly; the run was stored as aborted with a note."""

    def __init__(self, message: str, run: ScanRun) -> None:
        super().__init__(message, scope="scan_run")
        self.run = run


@dataclass(frozen=True, slots=True)
class RunResult:
    """Everything one completed scan run produced."""

    run: ScanRun
    candidates: tuple[Candidate, ...]
    sightings: tuple[Sighting, ...]
    reinforcements: tuple[Reinforcement, ...]
    warnings: tuple[CleanText, ...] = ()

    def status_of(self, candidate: Candidate) -> CandidateStatus:
        """New, seen before or reinforcement, derived from the run's facts."""
        if any(r.candidate_id == candidate.id for r in self.reinforcements):
            return CandidateStatus.REINFORCEMENT
        if candidate.first_seen_run_id != self.run.id:
            return CandidateStatus.SEEN_BEFORE
        return CandidateStatus.NEW


def _plural(count: int, word: str, plural: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {plural}"


def _union(groups: Iterable[Iterable[KebabId]]) -> tuple[KebabId, ...]:
    seen: dict[KebabId, None] = {}
    for group in groups:
        for value in group:
            seen.setdefault(value, None)
    return tuple(seen)


class RunScan:
    """Execute the instrument once and store what it found."""

    def __init__(
        self,
        *,
        collectors: Mapping[Discipline, Collector],
        instruments: InstrumentRepository,
        runs: ScanRunRepository,
        candidates: CandidateRepository,
        known: KnownReports,
        rules: GatingRules,
        clock: Clock,
        ids: IdGenerator,
    ) -> None:
        for discipline, collector in collectors.items():
            if collector.discipline is not discipline:
                raise ValueError(
                    f"collector registered for {discipline.value} serves "
                    f"{collector.discipline.value}"
                )
        self._collectors = dict(collectors)
        self._instruments = instruments
        self._runs = runs
        self._candidates = candidates
        self._known = known
        self._rules = rules
        self._clock = clock
        self._ids = ids

    def execute(
        self,
        instrument: QueryInstrument,
        sources: Sequence[Source],
        disciplines: Iterable[Discipline],
    ) -> RunResult:
        """Run every query of the requested disciplines and return what the run produced."""
        wanted = tuple(d for d in Discipline if d in frozenset(disciplines))
        if not wanted:
            raise ValueError("a scan needs at least one discipline")
        missing = [d.value for d in wanted if d not in self._collectors]
        if missing:
            raise ValueError(f"no collector for {', '.join(missing)}")
        self._record_instrument(instrument)
        started = self._clock.now()
        run = ScanRun.start(self._ids.run_id(started), started, instrument, wanted)
        warnings: list[CleanText] = []
        try:
            run, collected = self._dispatch(run, instrument, sources, wanted, warnings)
        except Exception as error:
            note = CleanText.scrub(f"aborted: {type(error).__name__}: {error}")
            aborted = run.abort(self._clock.now(), note)
            self._runs.add(aborted)
            raise ScanAborted(f"run {run.id} aborted: {error}", aborted) from error
        return self._process(run, instrument, sources, collected, warnings)

    def _record_instrument(self, instrument: QueryInstrument) -> None:
        if not instrument.verify_hash():
            raise DomainError(
                f"instrument {instrument.version} content hash does not verify",
                scope="instrument",
                location="content_hash",
            )
        stored = self._instruments.get(instrument.version)
        if stored is None:
            self._instruments.add(instrument)
        elif stored.content_hash != instrument.content_hash:
            raise DomainError(
                f"instrument version {instrument.version} is already recorded with hash "
                f"{stored.content_hash}; a changed instrument needs a new version",
                scope="instrument",
                location="version",
            )

    @staticmethod
    def _targets(
        query: Query, sources: Sequence[Source], by_id: Mapping[str, Source]
    ) -> tuple[Source, ...]:
        """The sources a query runs on: named for site queries, the lane's feeds for feeds."""
        if query.discipline is Discipline.OSINT_SITE:
            return tuple(
                by_id[source_id]
                for source_id in query.site_source_ids
                if source_id in by_id and by_id[source_id].active
            )
        if query.discipline is Discipline.OSINT_FEED:
            return tuple(
                source
                for source in sources
                if source.active
                and source.lane == query.lane
                and source.discipline is Discipline.OSINT_FEED
                and source.feed_url is not None
            )
        return ()

    def _dispatch(
        self,
        run: ScanRun,
        instrument: QueryInstrument,
        sources: Sequence[Source],
        disciplines: tuple[Discipline, ...],
        warnings: list[CleanText],
    ) -> tuple[ScanRun, list[tuple[RawHit, Query]]]:
        budget = run.request_budget
        queries = instrument.queries_for(disciplines)
        by_id: dict[str, Source] = {source.id: source for source in sources}
        collected: list[tuple[RawHit, Query]] = []
        for index, query in enumerate(queries):
            if run.requests_made >= budget:
                unrun = queries[index:]
                run = run.exhaust_budget(
                    CleanText(
                        f"request budget of {budget} reached after {run.requests_made} "
                        f"requests; {_plural(len(unrun), 'query', 'queries')} not run: "
                        + ", ".join(query.id for query in unrun)
                    )
                )
                break
            needs_sources = query.discipline in (Discipline.OSINT_SITE, Discipline.OSINT_FEED)
            targets = self._targets(query, sources, by_id)
            if needs_sources and not targets:
                warnings.append(CleanText(f"query {query.id} skipped: no active sources to run on"))
                continue
            remaining = budget - run.requests_made
            result = self._collectors[query.discipline].collect(query, targets, remaining)
            self._check_result(query, result, remaining, warnings)
            run = run.add_hits(len(result.hits), result.requests_used)
            warnings.extend(result.warnings)
            collected.extend((hit, query) for hit in result.hits)
        return run, collected

    @staticmethod
    def _check_result(
        query: Query, result: CollectResult, remaining: int, warnings: list[CleanText]
    ) -> None:
        for hit in result.hits:
            if hit.query_id != query.id or hit.discipline is not query.discipline:
                raise ValueError(
                    f"collector returned a hit for query {hit.query_id} ({hit.discipline.value}) "
                    f"while running {query.id} ({query.discipline.value})"
                )
        if result.requests_used > remaining:
            warnings.append(
                CleanText(
                    f"query {query.id} used {result.requests_used} requests with only "
                    f"{remaining} left in the budget"
                )
            )

    @staticmethod
    def _resolve(
        hit: RawHit,
        by_id: Mapping[str, Source],
        by_domain: Mapping[str, Source],
        warnings: list[CleanText],
    ) -> Source | None:
        if hit.source_id is not None:
            source = by_id.get(hit.source_id)
            if source is not None:
                return source
            warnings.append(
                CleanText(
                    f"hit {hit.url} names unknown source {hit.source_id}; matched by domain instead"
                )
            )
        return by_domain.get(hit.canonical_url.host)

    def _process(
        self,
        run: ScanRun,
        instrument: QueryInstrument,
        sources: Sequence[Source],
        collected: list[tuple[RawHit, Query]],
        warnings: list[CleanText],
    ) -> RunResult:
        by_id: dict[str, Source] = {source.id: source for source in sources}
        by_domain: dict[str, Source] = {source.domain: source for source in sources}
        outcomes: Counter[GateOutcome] = Counter()
        passed: list[RawHit] = []
        for hit, query in collected:
            source = self._resolve(hit, by_id, by_domain, warnings)
            resolved = hit.with_source(None if source is None else source.id)
            outcome = gate(resolved, source, query, instrument, self._rules)
            outcomes[outcome] += 1
            if outcome is GateOutcome.PASSED:
                passed.append(resolved)

        drafts = group_hits(passed)
        seen = SeenIndex(self._candidates.canonical_urls_before(run.id))
        matches = match_known(drafts, seen, self._known)

        candidates: list[Candidate] = []
        sightings: list[Sighting] = []
        reinforcements: list[Reinforcement] = []
        used_ids: set[str] = set()
        for match in matches:
            draft = match.draft
            first = draft.first
            attempt = 0
            candidate_id = self._ids.candidate_id(run.id, draft.canonical_url, attempt)
            while candidate_id in used_ids:
                attempt += 1
                candidate_id = self._ids.candidate_id(run.id, draft.canonical_url, attempt)
            used_ids.add(candidate_id)
            queries = [instrument.query(hit.query_id) for hit in draft.hits]
            source = None if first.source_id is None else by_id.get(first.source_id)
            candidates.append(
                Candidate(
                    id=candidate_id,
                    run_id=run.id,
                    canonical_url=draft.canonical_url,
                    url=draft.url,
                    title=draft.title,
                    snippet=draft.snippet,
                    published_on=draft.published_on,
                    first_seen_run_id=match.first_seen_run_id or run.id,
                    trusted=source is not None and source.trusted,
                    source_id=first.source_id,
                    lane=source.lane if source is not None else queries[0].lane,
                    discipline=first.discipline,
                    query_id=first.query_id,
                    requirement_hints=_union(q.requirement_hints for q in queries),
                    topic_hints=_union(q.topic_hints for q in queries),
                )
            )
            for hit in draft.hits:
                sightings.append(
                    Sighting(
                        id=self._ids.sighting_id(run.id, len(sightings) + 1),
                        run_id=run.id,
                        candidate_id=candidate_id,
                        source_id=hit.source_id,
                        query_id=hit.query_id,
                        discipline=hit.discipline,
                    )
                )
            if match.report_id is not None and match.matched_by is not None:
                reinforcements.append(
                    Reinforcement(candidate_id, match.report_id, match.matched_by)
                )

        statuses = Counter(match.status for match in matches)
        funnel = Funnel(
            raw=run.funnel.raw,
            dropped_own=outcomes[GateOutcome.DROPPED_OWN],
            dropped_negative=outcomes[GateOutcome.DROPPED_NEGATIVE],
            dropped_unrelated=outcomes[GateOutcome.DROPPED_UNRELATED],
            passed=outcomes[GateOutcome.PASSED],
            unique=len(drafts),
            seen_before=statuses[CandidateStatus.SEEN_BEFORE],
            new=statuses[CandidateStatus.NEW],
            reinforcements=statuses[CandidateStatus.REINFORCEMENT],
        )
        run = run.complete(self._clock.now(), funnel)
        self._runs.add(run)
        self._candidates.add_candidates(candidates)
        self._candidates.add_sightings(sightings)
        self._candidates.add_reinforcements(reinforcements)
        return RunResult(
            run, tuple(candidates), tuple(sightings), tuple(reinforcements), tuple(warnings)
        )


@dataclass(frozen=True, slots=True)
class ProbeResult:
    """What a probe found. Nothing was stored."""

    query: Query
    hits: tuple[RawHit, ...]
    requests_used: int
    warnings: tuple[CleanText, ...] = ()


class Probe:
    """Run one query text through one collector, storing nothing.

    Used to try a query before it joins the instrument: the instrument is only
    comparable between runs while it holds still, so new queries are probed
    first and added deliberately.
    """

    def __init__(self, collectors: Mapping[Discipline, Collector]) -> None:
        self._collectors = dict(collectors)

    def run(
        self,
        text: str,
        discipline: Discipline,
        *,
        lane: str = "probe",
        sources: Sequence[Source] = (),
        budget: int = 1,
    ) -> ProbeResult:
        """The hits one query returns; ``budget`` caps the requests it may make."""
        collector = self._collectors.get(discipline)
        if collector is None:
            raise ValueError(f"no collector for {discipline.value}")
        if budget < 1:
            raise ValueError("a probe needs a budget of at least one request")
        query = Query(
            id=PROBE_QUERY_ID,
            discipline=discipline,
            lane=KebabId(lane),
            text=CleanText(text),
            site_source_ids=tuple(source.id for source in sources)
            if discipline is Discipline.OSINT_SITE
            else (),
        )
        result = collector.collect(query, tuple(sources), budget)
        return ProbeResult(query, result.hits, result.requests_used, result.warnings)
