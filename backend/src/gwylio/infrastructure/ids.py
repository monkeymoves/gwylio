"""Identifier generators for the ``IdGenerator`` port.

Only the run id needs randomness (four hex characters after the start
minute). Candidate and sighting ids are derived from the run id, so a run's
ids are reproducible once its run id is known.
"""

from __future__ import annotations

import secrets
from datetime import datetime

from gwylio.collection.model import derive_candidate_id, derive_sighting_id, make_run_id
from gwylio.shared.values import CanonicalUrl, KebabId, RunId

__all__ = ["FixedIdGenerator", "RandomIdGenerator"]


class RandomIdGenerator:
    """Run ids with a random four-hex suffix."""

    def run_id(self, started_at: datetime) -> RunId:
        return make_run_id(started_at, secrets.token_hex(2))

    def candidate_id(self, run_id: RunId, canonical_url: CanonicalUrl, attempt: int) -> KebabId:
        return derive_candidate_id(run_id, canonical_url, attempt)

    def sighting_id(self, run_id: RunId, index: int) -> KebabId:
        return derive_sighting_id(run_id, index)


class FixedIdGenerator(RandomIdGenerator):
    """Run ids with a fixed suffix, for tests and reproducible runs."""

    def __init__(self, suffix: str = "0000") -> None:
        self._suffix = suffix

    def run_id(self, started_at: datetime) -> RunId:
        return make_run_id(started_at, self._suffix)
