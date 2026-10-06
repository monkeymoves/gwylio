"""``gwylio collect`` and ``gwylio probe`` on the real collectors, with every request mocked.

The project is a copy of the shipped configuration with a small instrument:
one web query, one site query over the two Senedd sources, one feed query per
feed lane and one academic query. The funnel below is worked out by hand from
the cassettes:

- web (``brave_web/web_search.json``): 7 raw hits. naturalresources.wales is
  an own domain (dropped_own 1); the New South Wales page carries a global
  negative term (dropped_negative 1); the gardening page has no relevance
  token and no known source (dropped_unrelated 1); gov.wales, senedd.wales,
  bbc.co.uk ("wales") and nation.cymru pass: 4.
- site (``brave_site/site_search.json``): 3 raw hits, all on trusted Senedd
  sources: 3 pass. The inquiry page is the web hit's page without its
  trailing slash, so the two make one candidate with two sightings.
- feed: the Climate Change Committee RSS keeps 2 of 4 items ("wales" or
  "seventh carbon budget"), the Audit Wales Atom keeps 2 of 4 ("flood" or
  "natural resources"); trusted sources, so all 4 pass.

So raw 14 = 1 own + 1 negative + 1 unrelated + 11 passed; 11 passed hits make
10 unique candidates, all new in a fresh database. Requests: 1 web, 1 site,
2 feeds = 4 (each feed is fetched once although it could serve more queries).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from gwylio.cli import collect as collect_module
from gwylio.cli.main import app
from gwylio.collection.model import Discipline, Query, QueryInstrument
from gwylio.infrastructure.collectors.brave_web import BRAVE_WEB_URL
from gwylio.infrastructure.collectors.crossref import CROSSREF_URL
from gwylio.infrastructure.collectors.openalex import OPENALEX_URL
from gwylio.infrastructure.config.settings import Settings
from gwylio.infrastructure.handoff.candidates_file import read_candidates_file
from gwylio.infrastructure.http.client import HttpClient
from gwylio.processing.candidates_file import CandidatesFile
from gwylio.shared.values import CleanText
from tests.integration.collectors.cassettes import FakeTime, client, response
from tests.support import PROJECT_ROOT, query

pytestmark = pytest.mark.integration

runner = CliRunner()
CCC_FEED = "https://www.theccc.org.uk/feed/"
AUDIT_FEED = "https://www.audit.wales/rss.xml"
CLEAN_ENV: dict[str, str | None] = {
    "GWYLIO_BRAVE_API_KEY": None,
    "BRAVE_API_KEY": None,
    "GWYLIO_ACADEMIC": None,
    "GWYLIO_DATA_DIR": None,
    "GWYLIO_DB_PATH": None,
    "GWYLIO_CONFIG_DIR": None,
    "GWYLIO_ROOT": None,
}
WITH_KEY = {**CLEAN_ENV, "GWYLIO_BRAVE_API_KEY": "test-key-not-real"}

QUERIES: tuple[Query, ...] = (
    query(
        "web-habitat-01",
        lane="welsh-government",
        text="habitat restoration Wales",
        requirement_hints=("si1",),
        topic_hints=("nature-and-ecosystems",),
    ),
    query(
        "site-nature-senedd",
        discipline=Discipline.OSINT_SITE,
        lane="senedd",
        text='"nature recovery" OR "biodiversity targets"',
        requirement_hints=("si1",),
        site_source_ids=("senedd-cymru", "senedd-research"),
    ),
    query(
        "feed-ccc",
        discipline=Discipline.OSINT_FEED,
        lane="uk-government-and-regulators",
        text='"wales" OR "seventh carbon budget"',
        topic_hints=("climate-emissions",),
    ),
    query(
        "feed-audit",
        discipline=Discipline.OSINT_FEED,
        lane="governance-capacity",
        text='"flood" OR "natural resources"',
    ),
    query(
        "academic-peat-01",
        discipline=Discipline.OSINT_ACADEMIC,
        lane="research-evidence",
        text="peatland restoration Wales",
    ),
)


def write_small_instrument(project: Path) -> QueryInstrument:
    path = project / "config" / "instrument.json"
    shipped = json.loads(path.read_text(encoding="utf-8"))
    negatives = tuple(CleanText(term) for term in shipped["global_negative_terms"])
    built = QueryInstrument.build(CleanText("2026.10.90"), negatives, 150, QUERIES)
    document = {
        "notes": "A small instrument for the collector end to end test.",
        "version": str(built.version),
        "content_hash": built.content_hash,
        "global_negative_terms": [str(term) for term in negatives],
        "max_requests_per_run": built.max_requests_per_run,
        "queries": [q.as_canonical() for q in QUERIES],
    }
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")
    return built


@pytest.fixture
def project(project_copy: Path) -> Path:
    write_small_instrument(project_copy)
    return project_copy


@pytest.fixture
def never_sleeps(monkeypatch: pytest.MonkeyPatch) -> FakeTime:
    time = FakeTime()

    def make(settings: Settings) -> HttpClient:
        return client(time)

    monkeypatch.setattr(collect_module, "make_http_client", make)
    return time


def brave(request: httpx.Request) -> httpx.Response:
    q = request.url.params["q"]
    if q.startswith(("site:", "(site:")):
        return response("brave_site", "site_search.json")
    return response("brave_web", "web_search.json")


@pytest.fixture
def mocked() -> Iterator[respx.MockRouter]:
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        router.get(BRAVE_WEB_URL).mock(side_effect=brave)
        router.get(CCC_FEED).mock(return_value=response("feed", "rss_ccc.json"))
        router.get(AUDIT_FEED).mock(return_value=response("feed", "atom_audit_wales.json"))
        router.get(OPENALEX_URL).mock(return_value=response("openalex", "works.json"))
        router.get(CROSSREF_URL).mock(return_value=response("crossref", "works.json"))
        yield router


def only_candidates_file(project: Path) -> CandidatesFile:
    files = sorted((project / "data" / "candidates").glob("*.json"))
    assert len(files) == 1, files
    return read_candidates_file(files[0])


def test_collect_writes_a_candidates_file_whose_funnel_adds_up_by_hand(
    project: Path, never_sleeps: FakeTime, mocked: respx.MockRouter
) -> None:
    result = runner.invoke(app, ["collect", "--root", str(project)], env=WITH_KEY)
    assert result.exit_code == 0, result.output
    document = only_candidates_file(project)
    funnel = document.funnel
    assert (funnel.raw, funnel.dropped_own, funnel.dropped_negative, funnel.dropped_unrelated) == (
        14,
        1,
        1,
        1,
    )
    assert (funnel.passed, funnel.unique, funnel.new, funnel.seen_before) == (11, 10, 10, 0)
    assert funnel.reinforcements == 0
    assert document.requests_made == 4
    assert document.run_status == "complete"
    assert document.disciplines_run == [
        Discipline.OSINT_WEB,
        Discipline.OSINT_FEED,
        Discipline.OSINT_SITE,
    ]
    assert document.warnings == []
    by_url = {c.canonical_url: c for c in document.candidates}
    inquiry = by_url[
        "senedd.wales/committees/climate-change-environment-and-infrastructure-committee/"
        "biodiversity-targets-inquiry"
    ]
    sightings = [s for s in document.sightings if s.candidate_id == inquiry.candidate_id]
    assert sorted((s.query_id, s.discipline.value) for s in sightings) == [
        ("site-nature-senedd", "osint_site"),
        ("web-habitat-01", "osint_web"),
    ]
    assert inquiry.source_id == "senedd-cymru"
    assert inquiry.trusted
    nation = next(c for c in document.candidates if c.source_id == "nation-cymru")
    assert "%E2%80%93" in nation.url
    bbc = by_url["bbc.co.uk/news/articles/c4g7wales2026"]
    assert bbc.source_id is None
    assert not bbc.trusted
    assert bbc.lane == "welsh-government"  # the query's lane, the source being unknown
    feed_sources = sorted(
        str(c.source_id) for c in document.candidates if c.discipline is Discipline.OSINT_FEED
    )
    assert feed_sources == ["audit-wales"] * 2 + ["climate-change-committee"] * 2
    assert mocked.routes[0].call_count == 2  # Brave: one web and one site request
    assert never_sleeps.sleeps == [1.0]  # the Brave rate limit, and nothing else
    lines = result.stdout.splitlines()
    assert lines[0].startswith("wrote  ")
    assert "  raw hits                    14" in lines
    assert "requests made: 4 of 150; budget not exhausted" in lines
    assert lines[-1] == "feeds: 2 of 2 responded"
    assert (project / "data" / "exports" / "runs.json").is_file()
    assert (project / "data" / "instruments" / "2026.10.90.json").is_file()


def test_a_second_run_sees_the_same_urls_as_seen_before(
    project: Path, never_sleeps: FakeTime, mocked: respx.MockRouter
) -> None:
    args = ["collect", "--discipline", "osint_feed", "--root", str(project)]
    first = runner.invoke(app, args, env=CLEAN_ENV)
    assert first.exit_code == 0, first.output
    second = runner.invoke(app, args, env=CLEAN_ENV)
    assert second.exit_code == 0, second.output
    files = sorted((project / "data" / "candidates").glob("*.json"))
    assert len(files) == 2
    documents = [read_candidates_file(path) for path in files]
    by_new = sorted((d.funnel.new, d.funnel.seen_before) for d in documents)
    assert by_new == [(0, 4), (4, 0)]


def test_without_a_key_the_feeds_run_and_brave_is_named_as_missing(
    project: Path, never_sleeps: FakeTime, mocked: respx.MockRouter
) -> None:
    result = runner.invoke(app, ["collect", "--root", str(project)], env=CLEAN_ENV)
    assert result.exit_code == 0, result.output
    assert "skip   osint_web: no Brave Search API key" in result.stderr
    assert "skip   osint_site: no Brave Search API key" in result.stderr
    assert "osint_academic" not in result.stderr  # not requested, so not missing
    document = only_candidates_file(project)
    assert document.disciplines_run == [Discipline.OSINT_FEED]
    assert document.funnel.unique == 4
    assert mocked.routes[0].call_count == 0


def test_nothing_runnable_exits_3_and_writes_nothing(
    project: Path, never_sleeps: FakeTime, mocked: respx.MockRouter
) -> None:
    result = runner.invoke(
        app,
        [
            "collect",
            "--discipline",
            "osint_web",
            "--discipline",
            "osint_site",
            "--root",
            str(project),
        ],
        env=CLEAN_ENV,
    )
    assert result.exit_code == 3
    assert "none of the requested disciplines can run here" in result.stderr
    assert not (project / "data").exists()


def test_an_explicit_academic_discipline_switches_the_indexes_on(
    project: Path, never_sleeps: FakeTime, mocked: respx.MockRouter
) -> None:
    result = runner.invoke(
        app, ["collect", "--discipline", "osint_academic", "--root", str(project)], env=CLEAN_ENV
    )
    assert result.exit_code == 0, result.output
    document = only_candidates_file(project)
    assert document.disciplines_run == [Discipline.OSINT_ACADEMIC]
    # Two papers name Wales; the Scottish case study and the methane paper do not, and come
    # from no known source, so the relevance gate drops them.
    assert (document.funnel.raw, document.funnel.dropped_unrelated) == (4, 2)
    assert document.funnel.unique == 2
    assert document.requests_made == 2
    assert {c.canonical_url for c in document.candidates} == {
        "doi.org/10.1016/j.scitotenv.2026.170123",
        "doi.org/10.1111/1365-2664.14567",
    }


def test_unreachable_feeds_are_warnings_not_failures(project: Path, never_sleeps: FakeTime) -> None:
    with respx.mock(assert_all_mocked=True) as router:
        router.get(CCC_FEED).mock(side_effect=httpx.ProxyError("CONNECT tunnel failed, 403"))
        router.get(AUDIT_FEED).mock(return_value=httpx.Response(404))
        result = runner.invoke(
            app, ["collect", "--discipline", "osint_feed", "--root", str(project)], env=CLEAN_ENV
        )
    assert result.exit_code == 0, result.output
    document = only_candidates_file(project)
    assert document.run_status == "complete"
    assert document.funnel.raw == 0
    assert len(document.warnings) == 2
    assert result.stdout.splitlines()[-1] == (
        "feeds: 0 of 2 responded; failed: audit-wales, climate-change-committee"
    )


def test_probe_runs_a_real_feed_probe_and_writes_nothing(
    project: Path, never_sleeps: FakeTime, mocked: respx.MockRouter
) -> None:
    result = runner.invoke(
        app, ["probe", "flood", "--discipline", "osint_feed", "--root", str(project)], env=CLEAN_ENV
    )
    assert result.exit_code == 0, result.output
    lines = result.stdout.splitlines()
    assert lines[0] == "probe (osint_feed, RSS and Atom feeds): 1 hit, 2 requests, nothing stored"
    assert lines[1] == "  2026-09-10  Flood risk management in Wales: follow-up review"
    assert not (project / "data").exists()


def test_probe_web_needs_a_key(project: Path, never_sleeps: FakeTime) -> None:
    missing = runner.invoke(app, ["probe", "drought", "--root", str(project)], env=CLEAN_ENV)
    assert missing.exit_code == 3
    assert "probe: cannot run osint_web: no Brave Search API key" in missing.stderr


def test_probe_web_with_a_key(
    project: Path, never_sleeps: FakeTime, mocked: respx.MockRouter
) -> None:
    result = runner.invoke(
        app, ["probe", "habitat restoration Wales", "--root", str(project)], env=WITH_KEY
    )
    assert result.exit_code == 0, result.output
    assert result.stdout.splitlines()[0] == (
        "probe (osint_web, Brave web search): 7 hits, 1 request, nothing stored"
    )


def test_the_shipped_instrument_fits_the_budget_on_brave_limits() -> None:
    """Every web, site and feed request of a full scan fits in the request budget."""
    from gwylio.infrastructure.collectors.brave_site import site_queries
    from gwylio.infrastructure.config.loaders import load_config

    config = load_config(PROJECT_ROOT)
    by_id = {s.id: s for s in config.sources}
    web = len(config.instrument.queries_for([Discipline.OSINT_WEB]))
    site = sum(
        len(
            site_queries(
                [by_id[i].domain for i in q.site_source_ids if by_id[i].active], str(q.text)
            )
        )
        for q in config.instrument.queries_for([Discipline.OSINT_SITE])
    )
    feeds = sum(
        1
        for s in config.sources
        if s.active and s.discipline is Discipline.OSINT_FEED and s.feed_url
    )
    assert web + site + feeds <= config.instrument.max_requests_per_run
