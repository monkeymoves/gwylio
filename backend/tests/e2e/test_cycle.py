"""The end to end dry run: one whole scan cycle through the command line, on recorded HTTP.

This is the cycle ``skill/SKILL.md`` walks an analyst through, run verb by
verb with ``CliRunner`` in a throwaway project holding a copy of the shipped
``config/`` (with the small collector test instrument, so the funnel is known):

``migrate``, ``datecheck``, ``collect`` (Brave web and site search and two
feeds, every request answered from the WP4 cassettes by respx), ``ingest`` of
the hand-written submission ``tests/fixtures/e2e/20261005T0900Z-0000__1.json``,
``sweep``, ``product --level operational``, ``export`` and ``publish``. Then
the register export, the INTSUM and the snapshot are checked, and ``rebuild``
into a second database must reproduce every export byte for byte.

A real scan runs on the system clock with a random run id suffix; the test
pins both (as ``--at`` does for a fake scan), so the run id is
``20261005T0900Z-0000`` and the fixture can name its candidates. The second
test carries the cycle on through two quiet feed runs, a submission that
confirms the feed reinforcements, and the sweep that fades the rest.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import respx
from typer.testing import CliRunner, Result

from gwylio.cli import collect as collect_module
from gwylio.cli.main import app
from gwylio.infrastructure.collectors.brave_web import BRAVE_WEB_URL
from gwylio.infrastructure.config.loaders import load_config
from gwylio.infrastructure.config.settings import Settings
from gwylio.infrastructure.http.client import HttpClient
from gwylio.infrastructure.ids import FixedIdGenerator
from gwylio.processing.submission import RUBRIC_VERSION
from gwylio.shared.clock import FixedClock
from tests.integration.collectors.cassettes import FakeTime, client, response
from tests.integration.collectors.test_collect_end_to_end import (
    AUDIT_FEED,
    CCC_FEED,
    CLEAN_ENV,
    WITH_KEY,
    brave,
    write_small_instrument,
)
from tests.support import PROJECT_ROOT, submission_document

pytestmark = pytest.mark.integration

runner = CliRunner()
FIXTURE = PROJECT_ROOT / "backend" / "tests" / "fixtures" / "e2e" / "20261005T0900Z-0000__1.json"
RUN_ID = "20261005T0900Z-0000"
PROMOTED = {
    "audit-wales-flood-risk-follow-up-2026",
    "biodiversity-targets-inquiry-2026",
    "ccc-wales-progress-2026",
    "nature-recovery-action-plan-2026",
    "peatland-restoration-5000-hectares",
}
FEED_REPORTS = {"audit-wales-flood-risk-follow-up-2026", "ccc-wales-progress-2026"}
EXPORTS = ("register.json", "runs.json", "products.json")


@dataclass
class PinnedClock:
    """Stands in for ``SystemClock`` in the collect verb: every run starts at ``at``."""

    at: datetime

    def __call__(self) -> FixedClock:
        return FixedClock(self.at)


@pytest.fixture
def project(project_copy: Path) -> Path:
    write_small_instrument(project_copy)
    return project_copy


@pytest.fixture
def pinned(monkeypatch: pytest.MonkeyPatch) -> PinnedClock:
    """Real scans on a pinned clock, a fixed run id suffix and an HTTP client that never sleeps."""
    clock = PinnedClock(datetime(2026, 10, 5, 9, 0, tzinfo=UTC))
    time = FakeTime()

    def make(settings: Settings) -> HttpClient:
        return client(time)

    monkeypatch.setattr(collect_module, "make_http_client", make)
    monkeypatch.setattr(collect_module, "SystemClock", clock)
    monkeypatch.setattr(collect_module, "RandomIdGenerator", FixedIdGenerator)
    return clock


@pytest.fixture
def mocked() -> Iterator[respx.MockRouter]:
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        router.get(BRAVE_WEB_URL).mock(side_effect=brave)
        router.get(CCC_FEED).mock(return_value=response("feed", "rss_ccc.json"))
        router.get(AUDIT_FEED).mock(return_value=response("feed", "atom_audit_wales.json"))
        yield router


def gwylio(project: Path, *args: str, env: dict[str, str | None] | None = None) -> Result:
    """Run one verb against ``project``; fail the test unless it exits 0."""
    result = runner.invoke(app, [*args, "--root", str(project)], env=env or CLEAN_ENV)
    assert result.exit_code == 0, f"gwylio {' '.join(args)}:\n{result.output}"
    return result


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def run_first_cycle(project: Path, site: Path) -> None:
    """migrate, datecheck, collect, ingest, sweep, product, export and publish, in that order."""
    gwylio(project, "migrate")
    checked = gwylio(project, "datecheck", "--today", "2026-10-05")
    assert checked.stdout.startswith("date check on 2026-10-05: 0 findings")
    collected = gwylio(project, "collect", env=WITH_KEY)
    assert f"stored run {RUN_ID}" in collected.stdout
    ingested = gwylio(project, "ingest", str(FIXTURE))
    assert f"ingest: applied submission {RUN_ID}__1" in ingested.stdout
    swept = gwylio(project, "sweep", "--today", "2026-10-05")
    assert swept.stdout.strip() == "sweep: nothing to fade on 2026-10-05"
    rendered = gwylio(
        project, "product", "--level", "operational", "--period", "2026-10", "--today", "2026-10-06"
    )
    assert rendered.stdout.splitlines()[0].endswith("operational_2026-10.md")
    gwylio(project, "export")
    gwylio(project, "publish", "--out", str(site), "--at", "2026-10-06T09:00:00+0000")


def assert_rebuild_reproduces_the_exports(project: Path, tmp_path: Path) -> None:
    """Rebuild into a second database, export from it, and compare every export byte for byte."""
    exports = project / "data" / "exports"
    before = {name: (exports / name).read_bytes() for name in EXPORTS}
    second = {**CLEAN_ENV, "GWYLIO_DB_PATH": str(tmp_path / "second.sqlite")}
    rebuilt = gwylio(project, "rebuild", env=second)
    assert str(tmp_path / "second.sqlite") in rebuilt.stdout
    gwylio(project, "export", env=second)
    for name in EXPORTS:
        assert (exports / name).read_bytes() == before[name], name


def test_one_scan_cycle_end_to_end_on_cassettes(
    project: Path, pinned: PinnedClock, mocked: respx.MockRouter, tmp_path: Path
) -> None:
    site = tmp_path / "site"
    run_first_cycle(project, site)
    data = project / "data"

    # The facts on disk: one candidates file, the submission copied in, the product pair.
    candidates = read_json(data / "candidates" / f"{RUN_ID}.json")
    assert candidates["funnel"]["new"] == 10
    submitted = data / "submissions" / f"{RUN_ID}__1.json"
    assert submitted.read_bytes() == FIXTURE.read_bytes()
    assert not (data / "sweeps").exists()
    assert (data / "products" / "operational_2026-10.json").is_file()

    # The register export holds exactly the promoted reports, all emerging after one run.
    register = read_json(data / "exports" / "register.json")
    reports = {report["id"]: report for report in register["reports"]}
    assert set(reports) == PROMOTED
    assert {report["state"] for report in reports.values()} == {"emerging"}
    assert reports["peatland-restoration-5000-hectares"]["grading"] == "C3"
    assert reports["ccc-wales-progress-2026"]["grading"] == "B2"  # the source's letter

    # The INTSUM names every promoted report by its title.
    fixture = read_json(FIXTURE)
    intsum = (data / "products" / "operational_2026-10.md").read_text(encoding="utf-8")
    for promotion in fixture["promotions"]:
        assert promotion["title"] in intsum, promotion["title"]

    # The snapshot's counts match the register, the runs and the configuration.
    meta = read_json(site / "meta.json")
    config = load_config(project)
    counts = meta["counts"]
    assert counts["reports"] == len(PROMOTED) == len(read_json(site / "reports.json"))
    assert counts["reports_by_state"]["emerging"] == len(PROMOTED)
    assert counts["runs"] == 1 == len(read_json(site / "runs.json"))
    assert counts["submissions"] == 1
    assert counts["products"] == 1 == len(read_json(site / "products.json"))
    assert counts["sources"] == len(config.sources)
    assert meta["latest_run_id"] == RUN_ID
    assert meta["generated_at"] == "2026-10-06T09:00:00Z"
    for report_id in PROMOTED:
        assert (site / "reports" / f"{report_id}.json").is_file()
    assert (site / "runs" / f"{RUN_ID}.json").is_file()

    assert_rebuild_reproduces_the_exports(project, tmp_path)


def test_quiet_runs_fade_what_was_not_seen_and_rebuild_replays_the_sweep(
    project: Path, pinned: PinnedClock, mocked: respx.MockRouter, tmp_path: Path
) -> None:
    run_first_cycle(project, tmp_path / "site")
    # Two later feed-only runs: the Audit Wales and Climate Change Committee pages come back
    # as reinforcements of their reports; nothing else is seen.
    later = []
    for day in (12, 19):
        pinned.at = datetime(2026, 10, day, 9, 0, tzinfo=UTC)
        gwylio(project, "collect", "--discipline", "osint_feed")
        later.append(f"202610{day}T0900Z-0000")
    third = read_json(project / "data" / "candidates" / f"{later[-1]}.json")
    assert third["funnel"]["reinforcements"] == 2
    assert {r["report_id"] for r in third["reinforcements"]} == FEED_REPORTS

    # The analyst confirms the third run's reinforcements (the second run's stay unconfirmed,
    # so they never count) and adds a note to the inquiry.
    by_report = {r["report_id"]: r["candidate_id"] for r in third["reinforcements"]}
    document = submission_document(
        run_id=later[-1],
        received_on="2026-10-19",
        reinforcements=[
            {"report_id": report_id, "candidate_id": candidate_id}
            for report_id, candidate_id in sorted(by_report.items())
        ],
        updates=[
            {
                "report_id": "biodiversity-targets-inquiry-2026",
                "set": {"notes": "The evidence deadline is 1 December 2026."},
                "change": "Noted the evidence deadline from the terms of reference.",
            }
        ],
    )
    path = tmp_path / "second_submission.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    gwylio(project, "ingest", str(path))

    swept = gwylio(project, "sweep", "--today", "2026-10-20")
    lines = swept.stdout.splitlines()
    faded = {line.split()[1].rstrip(":") for line in lines if line.startswith("faded")}
    # The inquiry was updated on 19 October, after the earlier quiet run started, so it stays.
    assert faded == {"nature-recovery-action-plan-2026", "peatland-restoration-5000-hectares"}
    assert (project / "data" / "sweeps" / "2026-10-20__1.json").is_file()

    register = read_json(project / "data" / "exports" / "register.json")
    states = {report["id"]: report["state"] for report in register["reports"]}
    assert states == {
        "audit-wales-flood-risk-follow-up-2026": "tracking",
        "ccc-wales-progress-2026": "tracking",
        "biodiversity-targets-inquiry-2026": "emerging",
        "nature-recovery-action-plan-2026": "faded",
        "peatland-restoration-5000-hectares": "faded",
    }
    gwylio(project, "export")
    assert_rebuild_reproduces_the_exports(project, tmp_path)


def test_the_fixture_disposes_of_every_candidate_against_the_current_rubric() -> None:
    fixture = read_json(FIXTURE)
    assert fixture["rubric_version"] == RUBRIC_VERSION
    assert fixture["run_id"] == RUN_ID
    assert len(fixture["dispositions"]) == 10  # the funnel's new candidates, one each
    promoted = {d["report_id"] for d in fixture["dispositions"] if d["outcome"] == "promoted"}
    assert promoted == PROMOTED == {p["id"] for p in fixture["promotions"]}
