"""Optional live checks against the real network. Excluded by default; run with ``pytest -m live``.

They prove the shipped feeds still parse and the HTTP client gets through the
local proxy. A failure here is news about the world (a feed moved, a proxy
refused a host), not a bug in the suite, which is why they never run in CI.
"""

from __future__ import annotations

import pytest

from gwylio.infrastructure.collectors.feed import parse_feed
from gwylio.infrastructure.config.loaders import load_config
from gwylio.infrastructure.http.client import HttpClient
from gwylio.shared.vocabulary import Discipline
from tests.support import PROJECT_ROOT

pytestmark = pytest.mark.live


def test_every_active_shipped_feed_answers_and_parses() -> None:
    config = load_config(PROJECT_ROOT)
    feeds = [
        s
        for s in config.sources
        if s.active and s.discipline is Discipline.OSINT_FEED and s.feed_url is not None
    ]
    assert feeds
    with HttpClient(contact_email="gwylio@example.invalid") as http:
        for source in feeds:
            assert source.feed_url is not None
            items = parse_feed(http.get_bytes(source.feed_url), source.feed_url)
            assert items, f"feed {source.id} parsed but carried no items"
