"""The rules for ingesting submissions and replaying the register's facts.

Two kinds of file change the register, and both are append-only facts:

- ``data/submissions/<stem>.json``: the analyst's submissions. A run
  submission is named ``<run_id>__<n>``, an out-of-run one
  ``direct__<received_on>__<n>`` (the legacy import writes
  ``legacy__<received_on>``). They replay in ``received_on`` then file name
  order, which is why ingest refuses one that would sort before a submission
  already ingested.
- ``data/sweeps/<on>__<n>.json`` (format ``gwylio.sweep/1``): what one
  ``gwylio sweep`` faded and when. The fade rule depends on which runs and
  sightings existed at the time, so a rebuild applies the recorded fades
  rather than re-running the rule; ``after_submissions`` places the sweep
  among the submissions (it ran after that many had been ingested).

This module holds the sweep file contract and the pure naming and ordering
rules; reading and writing files is infrastructure's job.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Sequence
from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from gwylio.processing.submission import DateText, Words
from gwylio.shared.values import KEBAB_MAX_LENGTH, KEBAB_PATTERN

__all__ = [
    "SWEEP_FORMAT",
    "FadeEntry",
    "ReplayStep",
    "SweepFile",
    "dumps_sweep",
    "loads_sweep",
    "next_submission_stem",
    "next_sweep_stem",
    "replay_key",
    "replay_order",
]

SWEEP_FORMAT: Final = "gwylio.sweep/1"
"""The format identifier every sweep file carries."""

_NUMBERED_RE: Final[re.Pattern[str]] = re.compile(r"(?P<prefix>.+)__(?P<n>[1-9][0-9]*)")

Id = Annotated[str, Field(pattern=KEBAB_PATTERN, max_length=KEBAB_MAX_LENGTH)]


def _stem(value: str) -> str:
    if not _NUMBERED_RE.fullmatch(value):
        raise ValueError(f"not a numbered file stem: {value!r}")
    return value


class _FileModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FadeEntry(_FileModel):
    """One report the sweep faded, and the reason recorded in its history."""

    report_id: Id
    change: Words


class SweepFile(_FileModel):
    """data/sweeps/<on>__<n>.json: the reports one sweep faded."""

    format: Literal["gwylio.sweep/1"] = Field(description="Always gwylio.sweep/1.")
    on: DateText = Field(description="The day the sweep ran: the date of each fade.")
    after_submissions: int = Field(
        ge=0, description="How many submissions had been ingested when the sweep ran."
    )
    faded: list[FadeEntry] = Field(min_length=1)


def dumps_sweep(document: SweepFile) -> str:
    """The sweep file's text: two-space indent, UTF-8 characters, trailing newline."""
    return json.dumps(document.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n"


def loads_sweep(text: str) -> SweepFile:
    """Parse a sweep file's text; raises ``pydantic.ValidationError``."""
    return SweepFile.model_validate_json(text)


def _next(prefix: str, existing: Iterable[str]) -> str:
    used = [0]
    for stem in existing:
        match = _NUMBERED_RE.fullmatch(stem)
        if match is not None and match.group("prefix") == prefix:
            used.append(int(match.group("n")))
    return f"{prefix}__{max(used) + 1}"


def next_submission_stem(run_id: str | None, received_on: str, existing: Iterable[str]) -> str:
    """``<run_id>__<n>`` or ``direct__<received_on>__<n>``, with ``n`` the next free number."""
    prefix = run_id if run_id is not None else f"direct__{received_on}"
    return _next(prefix, existing)


def next_sweep_stem(on: str, existing: Iterable[str]) -> str:
    """``<on>__<n>`` with ``n`` the next free number for that day."""
    return _stem(_next(on, existing))


def replay_key(received_on: str, stem: str) -> tuple[str, str]:
    """The order submissions replay in: by received date, then by file stem."""
    return (received_on, stem)


ReplayStep = tuple[Literal["submission", "sweep"], str]
"""One file to replay: its kind and its stem."""


def replay_order(
    submissions: Sequence[tuple[str, str]], sweeps: Sequence[tuple[int, str]]
) -> list[ReplayStep]:
    """Every submission and sweep in the order a rebuild applies them.

    ``submissions`` are ``(received_on, stem)`` pairs and ``sweeps``
    ``(after_submissions, stem)`` pairs. Submissions go in replay key order; a
    sweep goes after the number of submissions it records. Raises
    ``ValueError`` for a sweep that claims more submissions than exist.
    """
    ordered = sorted(submissions, key=lambda item: replay_key(*item))
    pending = sorted(sweeps)
    steps: list[ReplayStep] = []
    for index in range(len(ordered) + 1):
        while pending and pending[0][0] == index:
            steps.append(("sweep", pending.pop(0)[1]))
        if index < len(ordered):
            steps.append(("submission", ordered[index][1]))
    if pending:
        after, stem = pending[0]
        raise ValueError(
            f"sweep {stem} ran after {after} submissions, but only {len(ordered)} exist"
        )
    return steps
