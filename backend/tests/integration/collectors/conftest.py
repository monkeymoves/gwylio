"""Fixtures for the collector tests: a fake clock, a client on it, and respx with no passthrough."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
import respx

from gwylio.infrastructure.http.client import HttpClient
from tests.integration.collectors.cassettes import FakeTime, client


@pytest.fixture
def fake_time() -> FakeTime:
    return FakeTime()


@pytest.fixture
def http(fake_time: FakeTime) -> Iterator[HttpClient]:
    with client(fake_time) as made:
        yield made


@pytest.fixture
def mocked() -> Iterator[respx.MockRouter]:
    """Every request must match a route; anything unmatched fails the test."""
    with respx.mock(assert_all_called=False, assert_all_mocked=True) as router:
        yield router
