"""The registry: which real collectors exist with which settings, and why one is missing."""

from __future__ import annotations

from pathlib import Path

import pytest

from gwylio.collection.model import Discipline
from gwylio.collection.ports import Collector
from gwylio.infrastructure.collectors.brave_site import BraveSiteCollector
from gwylio.infrastructure.collectors.brave_web import BraveWebCollector
from gwylio.infrastructure.collectors.fake import FakeCollector
from gwylio.infrastructure.collectors.feed import FeedCollector
from gwylio.infrastructure.collectors.registry import (
    AcademicCollector,
    build_collectors,
    describe_collector,
    missing_disciplines,
)
from gwylio.infrastructure.config.settings import Settings
from gwylio.infrastructure.http.client import HttpClient

pytestmark = pytest.mark.integration

ALL = (
    Discipline.OSINT_WEB,
    Discipline.OSINT_SITE,
    Discipline.OSINT_FEED,
    Discipline.OSINT_ACADEMIC,
)


def settings(root: Path, **env: str) -> Settings:
    return Settings.load(root, environ=env)


def test_no_key_means_no_brave_collectors_and_a_reason(tmp_path: Path, http: HttpClient) -> None:
    collectors = build_collectors(settings(tmp_path), http)
    assert list(collectors) == [Discipline.OSINT_FEED]
    assert isinstance(collectors[Discipline.OSINT_FEED], FeedCollector)
    reasons = missing_disciplines(ALL, collectors)
    assert reasons[0].startswith("osint_web: no Brave Search API key")
    assert reasons[1].startswith("osint_site: no Brave Search API key")
    assert "GWYLIO_BRAVE_API_KEY" in reasons[0]


def test_flag_off_means_no_academic_collectors_and_a_reason(
    tmp_path: Path, http: HttpClient
) -> None:
    collectors = build_collectors(settings(tmp_path, GWYLIO_BRAVE_API_KEY="k"), http)
    assert Discipline.OSINT_ACADEMIC not in collectors
    assert missing_disciplines(ALL, collectors) == [
        "osint_academic: the academic indexes are off; set GWYLIO_ACADEMIC=1 or pass "
        "--discipline osint_academic"
    ]


def test_everything_with_a_key_and_the_flag(tmp_path: Path, http: HttpClient) -> None:
    collectors = build_collectors(settings(tmp_path, BRAVE_API_KEY="k", GWYLIO_ACADEMIC="1"), http)
    assert list(collectors) == [
        Discipline.OSINT_WEB,
        Discipline.OSINT_FEED,
        Discipline.OSINT_SITE,
        Discipline.OSINT_ACADEMIC,
    ]
    assert isinstance(collectors[Discipline.OSINT_WEB], BraveWebCollector)
    assert isinstance(collectors[Discipline.OSINT_SITE], BraveSiteCollector)
    assert isinstance(collectors[Discipline.OSINT_ACADEMIC], AcademicCollector)
    for discipline, collector in collectors.items():
        assert isinstance(collector, Collector)
        assert collector.discipline is discipline
        assert not isinstance(collector, FakeCollector)
    assert missing_disciplines(ALL, collectors) == []


def test_reserved_disciplines_have_a_reason(tmp_path: Path, http: HttpClient) -> None:
    collectors = build_collectors(settings(tmp_path), http)
    assert missing_disciplines([Discipline.GEOINT], collectors) == [
        "geoint: reserved; no collector serves it in version 1"
    ]
    assert describe_collector(Discipline.OSINT_FEED) == "RSS and Atom feeds"
