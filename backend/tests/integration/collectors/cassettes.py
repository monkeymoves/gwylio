"""Recorded HTTP exchanges for the collector tests, and a clock that sleeping moves.

A cassette is a JSON file under ``backend/tests/fixtures/http/<collector>/``
holding ``notes``, the ``request`` the collector should make (method, url and,
where it matters, params) and the ``response`` to give it (status, headers and
either ``json`` or ``text``). Dash characters appear only as JSON escapes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import httpx

from gwylio.infrastructure.http.client import HttpClient
from tests.support import PROJECT_ROOT

CASSETTES: Final[Path] = PROJECT_ROOT / "backend" / "tests" / "fixtures" / "http"
CONTACT: Final[str] = "analyst@example.org"


def cassette(collector: str, name: str) -> dict[str, Any]:
    """The parsed cassette file."""
    data: dict[str, Any] = json.loads((CASSETTES / collector / name).read_text(encoding="utf-8"))
    return data


def response(collector: str, name: str) -> httpx.Response:
    """The cassette's recorded response."""
    recorded = cassette(collector, name)["response"]
    headers = dict(recorded.get("headers", {}))
    if "json" in recorded:
        return httpx.Response(recorded["status"], headers=headers, json=recorded["json"])
    return httpx.Response(
        recorded["status"], headers=headers, content=recorded["text"].encode("utf-8")
    )


def request_params(collector: str, name: str) -> dict[str, str]:
    """The query parameters the cassette says the collector sends."""
    params: dict[str, str] = cassette(collector, name)["request"]["params"]
    return params


@dataclass
class FakeTime:
    """A monotonic clock that only moves when something sleeps, recording every sleep."""

    now: float = 1000.0
    sleeps: list[float] = field(default_factory=list)

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def client(time: FakeTime | None = None, *, jitter: float = 0.5) -> HttpClient:
    """An ``HttpClient`` that never really sleeps, with a fixed jitter fraction."""
    clock = time or FakeTime()
    return HttpClient(
        contact_email=CONTACT,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        jitter=lambda: jitter,
    )
