"""OpenAlex and Crossref against their cassettes, and the combined academic collector."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
import respx

from gwylio.collection.model import Discipline
from gwylio.infrastructure.collectors.crossref import CROSSREF_URL, CrossrefCollector
from gwylio.infrastructure.collectors.openalex import (
    OPENALEX_URL,
    OpenAlexCollector,
    rebuild_abstract,
)
from gwylio.infrastructure.collectors.registry import AcademicCollector
from gwylio.infrastructure.http.client import HttpClient
from gwylio.shared.clock import FixedClock
from gwylio.shared.values import IsoDate
from tests.integration.collectors.cassettes import CONTACT, request_params, response
from tests.support import query

pytestmark = pytest.mark.integration

CLOCK = FixedClock(datetime(2026, 10, 6, 2, 15, tzinfo=UTC))
PEAT = query(
    "academic-peat-01",
    discipline=Discipline.OSINT_ACADEMIC,
    lane="research-evidence",
    text="peatland restoration Wales",
)


def test_openalex_maps_the_cassette_to_raw_hits(http: HttpClient, mocked: respx.MockRouter) -> None:
    route = mocked.get(OPENALEX_URL).mock(return_value=response("openalex", "works.json"))
    result = OpenAlexCollector(http, CONTACT, CLOCK).collect(PEAT, (), 5)
    assert dict(route.calls.last.request.url.params) == request_params("openalex", "works.json")
    assert result.requests_used == 1
    assert result.warnings == ()
    welsh, scottish = result.hits
    assert welsh.url == "https://doi.org/10.1016/j.scitotenv.2026.170123"
    assert welsh.title == "Carbon outcomes of upland peatland restoration in Wales"
    assert welsh.snippet == "Rewetting upland blanket bog in Wales cut emissions."
    assert welsh.published_on == IsoDate("2026-03-14")
    assert welsh.discipline is Discipline.OSINT_ACADEMIC
    assert welsh.query_id == "academic-peat-01"
    assert welsh.source_id is None
    assert scottish.url == "https://www.example-journal.org/articles/peat-scotland-2025"
    assert scottish.title == "Peatland restoration outcomes, a Scottish case study"
    assert scottish.snippet == ""
    assert scottish.published_on == IsoDate("2025-11-02")


def test_crossref_maps_the_cassette_to_raw_hits(http: HttpClient, mocked: respx.MockRouter) -> None:
    route = mocked.get(CROSSREF_URL).mock(return_value=response("crossref", "works.json"))
    result = CrossrefCollector(http, CONTACT, CLOCK).collect(PEAT, (), 5)
    sent = route.calls.last.request
    assert dict(sent.url.params) == request_params("crossref", "works.json")
    assert "mailto:analyst@example.org" in sent.headers["User-Agent"]
    assert result.requests_used == 1
    cambrian, methane = result.hits
    assert cambrian.url == "https://doi.org/10.1111/1365-2664.14567"
    assert cambrian.title == (
        "Vegetation recovery after peatland rewetting in the Cambrian Mountains, Wales"
    )
    assert cambrian.snippet == "We surveyed 40 rewetted sites across mid Wales."
    assert cambrian.published_on == IsoDate("2026-02-03")
    assert methane.url == "https://doi.org/10.5194/bg-23-1001-2026"
    assert methane.snippet == "Biogeosciences"
    assert methane.published_on is None  # a year and month only: not guessed


def test_academic_failures_are_warnings(http: HttpClient, mocked: respx.MockRouter) -> None:
    mocked.get(OPENALEX_URL).mock(return_value=httpx.Response(400))
    mocked.get(CROSSREF_URL).mock(return_value=httpx.Response(200, text="not json"))
    openalex = OpenAlexCollector(http, CONTACT, CLOCK).collect(PEAT, (), 5)
    crossref = CrossrefCollector(http, CONTACT, CLOCK).collect(PEAT, (), 5)
    assert openalex.hits == crossref.hits == ()
    assert "OpenAlex query academic-peat-01 failed: HTTP 400" in openalex.warnings[0]
    assert "Crossref query academic-peat-01 failed" in crossref.warnings[0]
    assert OpenAlexCollector(http, CONTACT, CLOCK).collect(PEAT, (), 0).requests_used == 0


def test_the_combined_collector_runs_both_within_the_budget(
    http: HttpClient, mocked: respx.MockRouter
) -> None:
    mocked.get(OPENALEX_URL).mock(return_value=response("openalex", "works.json"))
    crossref = mocked.get(CROSSREF_URL).mock(return_value=response("crossref", "works.json"))
    combined = AcademicCollector(
        (OpenAlexCollector(http, CONTACT, CLOCK), CrossrefCollector(http, CONTACT, CLOCK))
    )
    both = combined.collect(PEAT, (), 5)
    assert both.requests_used == 2
    assert len(both.hits) == 4
    one = combined.collect(PEAT, (), 1)
    assert one.requests_used == 1
    assert len(one.hits) == 2
    assert crossref.call_count == 1
    assert "stopped at the request budget; Crossref skipped" in one.warnings[0]


def test_the_combined_collector_refuses_other_disciplines(http: HttpClient) -> None:
    with pytest.raises(ValueError):
        AcademicCollector(())


def test_rebuild_abstract_tolerates_junk() -> None:
    assert rebuild_abstract({"b": [1], "a": [0], "skip": ["x"]}) == "a b"
    assert rebuild_abstract(None) == ""
