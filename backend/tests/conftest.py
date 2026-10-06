"""Shared pytest fixtures for the whole backend suite."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from gwylio.shared.clock import FixedClock

FIXED_INSTANT = datetime(2026, 7, 23, 9, 30, tzinfo=UTC)


@pytest.fixture
def fixed_clock() -> FixedClock:
    """A clock pinned to 23 July 2026, 09:30 UTC."""
    return FixedClock(FIXED_INSTANT)
