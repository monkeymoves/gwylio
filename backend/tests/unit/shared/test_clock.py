"""Tests for the clock port and its two implementations."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from gwylio.shared.clock import Clock, FixedClock, SystemClock


def test_fixed_clock_from_date_is_midnight_utc() -> None:
    clock = FixedClock(date(2026, 8, 15))
    assert clock.today() == date(2026, 8, 15)
    assert clock.now() == datetime(2026, 8, 15, tzinfo=UTC)


def test_fixed_clock_converts_aware_datetimes_to_utc() -> None:
    bst = timezone(timedelta(hours=1))
    clock = FixedClock(datetime(2026, 8, 15, 0, 30, tzinfo=bst))
    assert clock.now() == datetime(2026, 8, 14, 23, 30, tzinfo=UTC)
    assert clock.now().tzinfo == UTC
    assert clock.today() == date(2026, 8, 14)


def test_fixed_clock_refuses_naive_datetimes() -> None:
    with pytest.raises(ValueError):
        FixedClock(datetime(2026, 8, 15, 12, 0))


def test_fixed_clock_refuses_other_types() -> None:
    with pytest.raises(TypeError):
        FixedClock("2026-08-15")  # type: ignore[arg-type]


def test_system_clock_is_aware_utc() -> None:
    now = SystemClock().now()
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)
    assert SystemClock().today() in {now.date(), now.date() + timedelta(days=1)}


def test_both_clocks_satisfy_the_protocol(fixed_clock: FixedClock) -> None:
    assert isinstance(SystemClock(), Clock)
    assert isinstance(fixed_clock, Clock)
    assert fixed_clock.today() == date(2026, 7, 23)
