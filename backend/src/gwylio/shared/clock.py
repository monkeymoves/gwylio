"""The clock port: the only way domain code learns what time it is.

Domain logic that depends on today's date (event horizons, the date check,
lifecycle sweeps) takes a ``Clock`` so tests can pin time with ``FixedClock``.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Protocol, runtime_checkable

__all__ = ["Clock", "FixedClock", "SystemClock"]


@runtime_checkable
class Clock(Protocol):
    """Something that can say what the date and time are."""

    def today(self) -> date:
        """The current calendar date in UTC."""
        ...

    def now(self) -> datetime:
        """The current instant as a timezone-aware UTC datetime."""
        ...


class SystemClock:
    """The real clock, read from the operating system in UTC."""

    __slots__ = ()

    def today(self) -> date:
        """The current calendar date in UTC."""
        return self.now().date()

    def now(self) -> datetime:
        """The current instant as a timezone-aware UTC datetime."""
        return datetime.now(UTC)


class FixedClock:
    """A clock pinned to one instant, for tests and reproducible runs.

    Built from a ``date`` (taken as midnight UTC) or a timezone-aware
    ``datetime`` (converted to UTC). A naive ``datetime`` is refused because
    its meaning depends on the machine it runs on.
    """

    __slots__ = ("_instant",)

    def __init__(self, date_or_dt: date | datetime) -> None:
        if isinstance(date_or_dt, datetime):
            if date_or_dt.tzinfo is None or date_or_dt.utcoffset() is None:
                raise ValueError("FixedClock needs a timezone-aware datetime")
            instant = date_or_dt.astimezone(UTC)
        elif isinstance(date_or_dt, date):
            instant = datetime(date_or_dt.year, date_or_dt.month, date_or_dt.day, tzinfo=UTC)
        else:
            raise TypeError(f"FixedClock needs a date or datetime, got {type(date_or_dt).__name__}")
        self._instant = instant

    def today(self) -> date:
        """The pinned calendar date in UTC."""
        return self._instant.date()

    def now(self) -> datetime:
        """The pinned instant as a timezone-aware UTC datetime."""
        return self._instant

    def __repr__(self) -> str:
        return f"FixedClock({self._instant.isoformat()})"
