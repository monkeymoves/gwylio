"""Funnel trends across scan runs, and what the analyst did with each run's candidates.

Pure functions over plain inputs: the infrastructure layer reads the stored
runs and dispositions and hands them in as ``RunFunnel`` and
``DispositionOutcome`` values, so this context never imports Collection or
Intelligence.

``FunnelTrend`` orders runs by start instant (then id) and answers three
questions: what the latest run looked like, how one funnel count moved over
the runs, and how a run's candidates were disposed of. The promotion rate is
promotions over the run's ``new`` candidates: the candidates the analyst had
to judge.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, fields
from datetime import datetime
from typing import Final

from gwylio.shared.vocabulary import DispositionOutcome

__all__ = [
    "FUNNEL_FIELDS",
    "DispositionSummary",
    "FunnelCounts",
    "FunnelTrend",
    "RunFunnel",
]


@dataclass(frozen=True, slots=True)
class FunnelCounts:
    """How many hits survived each stage of one run, as the run recorded them."""

    raw: int = 0
    dropped_own: int = 0
    dropped_negative: int = 0
    dropped_unrelated: int = 0
    passed: int = 0
    unique: int = 0
    seen_before: int = 0
    new: int = 0
    reinforcements: int = 0

    def __post_init__(self) -> None:
        for item in fields(self):
            value = getattr(self, item.name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"funnel count {item.name} must be a non-negative int")


FUNNEL_FIELDS: Final[tuple[str, ...]] = tuple(item.name for item in fields(FunnelCounts))
"""Every funnel count, in the order a run passes through them."""


@dataclass(frozen=True, slots=True)
class RunFunnel:
    """One finished scan run as the trend sees it."""

    run_id: str
    started_at: datetime
    funnel: FunnelCounts
    requests_made: int
    budget_exhausted: bool

    @property
    def order(self) -> tuple[datetime, str]:
        """How runs sort: by start instant, then by id."""
        return (self.started_at, self.run_id)


@dataclass(frozen=True, slots=True)
class DispositionSummary:
    """What the analyst did with one run's candidates.

    ``counts`` holds every outcome, in the order the vocabulary declares them,
    zero included. ``promotion_rate`` is ``promoted / new``, or ``None`` when
    the run had no new candidates (a rate over nothing is not zero).
    """

    run_id: str
    counts: tuple[tuple[DispositionOutcome, int], ...]
    new: int
    undisposed: int

    @property
    def promoted(self) -> int:
        """Candidates promoted to new reports."""
        return dict(self.counts)[DispositionOutcome.PROMOTED]

    @property
    def disposed(self) -> int:
        """Candidates with any disposition other than deferred."""
        return sum(count for outcome, count in self.counts if outcome is not _DEFERRED)

    @property
    def promotion_rate(self) -> float | None:
        """Promotions over the run's new candidates, or ``None`` when there were none."""
        return None if self.new == 0 else self.promoted / self.new


_DEFERRED: Final = DispositionOutcome.DEFERRED


class FunnelTrend:
    """Every run's funnel, oldest first."""

    __slots__ = ("_runs",)

    def __init__(self, runs: Iterable[RunFunnel]) -> None:
        ordered = sorted(runs, key=lambda run: run.order)
        ids = [run.run_id for run in ordered]
        if len(set(ids)) != len(ids):
            raise ValueError("a funnel trend lists each run once")
        self._runs: tuple[RunFunnel, ...] = tuple(ordered)

    @property
    def runs(self) -> tuple[RunFunnel, ...]:
        """Every run, oldest first."""
        return self._runs

    def latest(self) -> RunFunnel | None:
        """The run that started last, or ``None`` when there are no runs."""
        return self._runs[-1] if self._runs else None

    def last(self, count: int) -> FunnelTrend:
        """The trend over the most recent ``count`` runs."""
        if count < 0:
            raise ValueError("count cannot be negative")
        return FunnelTrend(self._runs[len(self._runs) - count :] if count else ())

    def series(self, field: str) -> tuple[tuple[str, int], ...]:
        """``(run id, value)`` for one funnel count (or ``requests_made``), oldest first."""
        if field == "requests_made":
            return tuple((run.run_id, run.requests_made) for run in self._runs)
        if field not in FUNNEL_FIELDS:
            known = ", ".join((*FUNNEL_FIELDS, "requests_made"))
            raise ValueError(f"unknown funnel field {field!r}; expected one of {known}")
        return tuple((run.run_id, int(getattr(run.funnel, field))) for run in self._runs)

    def total(self, field: str) -> int:
        """The sum of one funnel count over every run."""
        return sum(value for _, value in self.series(field))

    def disposition_summary(
        self, run_id: str, dispositions: Sequence[DispositionOutcome]
    ) -> DispositionSummary:
        """Counts per outcome for one run's candidates, and its promotion rate.

        ``dispositions`` holds each disposed candidate's final outcome (one per
        candidate). ``undisposed`` is the run's new candidates the analyst has
        not judged yet: new minus every disposition that is not deferred, never
        below zero (seen-before and reinforcement candidates may be disposed of too).
        """
        run = next((r for r in self._runs if r.run_id == run_id), None)
        if run is None:
            raise KeyError(run_id)
        tally = Counter(dispositions)
        counts = tuple((outcome, tally[outcome]) for outcome in DispositionOutcome)
        disposed = sum(count for outcome, count in counts if outcome is not _DEFERRED)
        return DispositionSummary(
            run_id=run_id,
            counts=counts,
            new=run.funnel.new,
            undisposed=max(run.funnel.new - disposed, 0),
        )
