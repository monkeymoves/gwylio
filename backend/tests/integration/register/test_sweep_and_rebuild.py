"""``gwylio sweep`` and ``datecheck``, and the whole register rebuilt from its files."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gwylio.infrastructure.sqlite.db import Database
from gwylio.infrastructure.sqlite.rebuild import RebuildError, rebuild
from gwylio.infrastructure.sqlite.repositories import SqliteReportRepository
from gwylio.shared.vocabulary import IndicatorState
from tests.integration.register.conftest import (
    FIRST,
    SECOND,
    SEED_SUBMISSIONS,
    Cli,
    register,
)
from tests.integration.sqlite.test_rebuild import assert_equivalent
from tests.support import PROJECT_ROOT

pytestmark = pytest.mark.integration

CONFIG = PROJECT_ROOT / "config"


def seeded(cli: Cli) -> None:
    """The seed's two runs and two submissions, as ``make seed`` builds them."""
    for args in (
        ("collect", "--fake", "--at", "2026-09-01T09:00:00+0000"),
        ("ingest", str(SEED_SUBMISSIONS / f"{FIRST}__1.json")),
        ("collect", "--fake", "--at", "2026-10-01T09:00:00+0000"),
        ("ingest", str(SEED_SUBMISSIONS / f"{SECOND}__1.json")),
    ):
        result = cli(*args)
        assert result.exit_code == 0, result.output


def quiet_runs(cli: Cli) -> None:
    """Two feed-only runs: only the two feed reports are found again."""
    for at in ("2026-10-03T09:00:00+0000", "2026-10-04T09:00:00+0000"):
        result = cli("collect", "--fake", "--discipline", "osint_feed", "--at", at)
        assert result.exit_code == 0, result.output


def test_the_seed_reaches_the_states_the_fixtures_describe(cli: Cli, data: Path) -> None:
    seeded(cli)
    reports = register(data)
    states = {report_id: report["state"] for report_id, report in reports.items()}
    assert states == {
        "avian-influenza-seabirds-2026": "tracking",
        "ccc-progress-report-2026": "matured",
        "domestic-solid-fuel-burning-emissions": "tracking",
        "nature-recovery-bill-consultation": "tracking",
        "nrw-funding-and-capacity-2026": "tracking",
        "phosphate-welsh-rivers-2026": "tracking",
        "river-action-judicial-review-permission": "tracking",
        "south-west-wales-drought-2026": "reinforced",
        "storm-claudia-monmouthshire-flooding": "tracking",
        "sustainable-farming-scheme-concerns": "parked",
    }
    funding = reports["nrw-funding-and-capacity-2026"]
    assert (funding["appearances"], funding["distinct_sources"]) == (2, 1)
    assert reports["south-west-wales-drought-2026"]["independent_confirmation"] is True
    assert reports["phosphate-welsh-rivers-2026"]["bucket"] == "brief"


def test_sweep_fades_quiet_reports_records_the_fact_and_rebuilds(
    cli: Cli, data: Path, tmp_path: Path
) -> None:
    seeded(cli)
    quiet_runs(cli)
    result = cli("sweep", "--today", "2026-10-05")
    assert result.exit_code == 0, result.output
    faded = sorted(
        line.split()[1].rstrip(":")
        for line in result.stdout.splitlines()
        if line.startswith("faded")
    )
    assert faded == [
        "avian-influenza-seabirds-2026",
        "domestic-solid-fuel-burning-emissions",
        "nature-recovery-bill-consultation",
        "nrw-funding-and-capacity-2026",
        "phosphate-welsh-rivers-2026",
        "river-action-judicial-review-permission",
        "south-west-wales-drought-2026",
        "storm-claudia-monmouthshire-flooding",
    ], "matured and parked reports never fade"
    sweep_file = data / "sweeps" / "2026-10-05__1.json"
    document = json.loads(sweep_file.read_text(encoding="utf-8"))
    assert document["after_submissions"] == 2
    assert [entry["report_id"] for entry in document["faded"]] == faded
    history = register(data)["storm-claudia-monmouthshire-flooding"]["history"]
    assert history[-1]["kind"] == "faded"
    assert history[-1]["on"] == "2026-10-05"
    again = cli("sweep", "--today", "2026-10-05")
    assert again.stdout.strip() == "sweep: nothing to fade on 2026-10-05"
    assert sorted(p.name for p in (data / "sweeps").iterdir()) == ["2026-10-05__1.json"]

    rebuilt = tmp_path / "rebuilt.sqlite"
    summary = rebuild(data, CONFIG, rebuilt)
    assert (summary.submission_files, summary.sweep_files) == (2, 1)
    with Database.open(data / "gwylio.sqlite") as a, Database.open(rebuilt) as b:
        assert_equivalent(a, b)
        storm = SqliteReportRepository(b).get("storm-claudia-monmouthshire-flooding")
        assert storm is not None
        assert storm.state is IndicatorState.FADED


def test_a_faded_report_revives_when_a_later_submission_sights_it(
    cli: Cli, data: Path, tmp_path: Path
) -> None:
    seeded(cli)
    quiet_runs(cli)
    assert cli("sweep", "--today", "2026-10-05").exit_code == 0
    feed = json.loads((data / "candidates" / "20261004T0900Z-0000.json").read_text("utf-8"))
    link = next(r for r in feed["reinforcements"] if r["report_id"].startswith("nrw-funding"))
    submission = {
        "schema": "gwylio.submission/1",
        "run_id": "20261004T0900Z-0000",
        "analyst": "Analyst",
        "rubric_version": "2026.10",
        "received_on": "2026-10-06",
        "reinforcements": [{"report_id": link["report_id"], "candidate_id": link["candidate_id"]}],
        "method_note": "Confirmed the feed reinforcements only.",
    }
    path = tmp_path / "revive.json"
    path.write_text(json.dumps(submission), encoding="utf-8")
    result = cli("ingest", "--allow-deferred", str(path))
    assert result.exit_code == 0, result.output
    assert "  nrw-funding-and-capacity-2026: faded to tracking" in result.stdout
    assert register(data)["nrw-funding-and-capacity-2026"]["history"][-1]["kind"] == "revived"
    rebuilt = tmp_path / "rebuilt.sqlite"
    rebuild(data, CONFIG, rebuilt)
    with Database.open(data / "gwylio.sqlite") as a, Database.open(rebuilt) as b:
        assert_equivalent(a, b)


def test_datecheck_groups_findings_and_always_exits_0(cli: Cli, data: Path) -> None:
    empty = cli("datecheck", "--today", "2026-10-06")
    assert empty.exit_code == 0
    assert "no database at" in empty.stdout
    seeded(cli)
    result = cli("datecheck", "--today", "2026-10-06")
    assert result.exit_code == 0
    assert result.stdout.splitlines() == [
        "date check on 2026-10-06: 2 findings on 1 of 9 reports in the picture",
        "",
        "passed_horizon (act, 1): The event horizon has passed and nobody has updated or "
        "verified the report since.",
        "  nature-recovery-bill-consultation: event horizon 2026-09-30 passed 6 days ago and "
        "nobody has updated or verified the report since",
        "",
        "future_language (warn, 1): The title, summary or notes use future-framed language "
        "that rots once the date passes.",
        "  nature-recovery-bill-consultation: summary uses future-framed language: "
        "'consultation closes'",
    ]
    bad = cli("datecheck", "--today", "soon")
    assert bad.exit_code == 0


def test_a_rebuild_refuses_a_submission_that_no_longer_ingests(
    cli: Cli, data: Path, tmp_path: Path
) -> None:
    seeded(cli)
    broken = data / "submissions" / "20261001T0900Z-0000__2.json"
    document = json.loads((SEED_SUBMISSIONS / f"{SECOND}__1.json").read_text("utf-8"))
    document["verifications"][0]["report_id"] = "ghost"
    broken.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(RebuildError, match="the submission no longer ingests") as raised:
        rebuild(data, CONFIG, tmp_path / "r.sqlite")
    assert "no report 'ghost' in the register" in str(raised.value)
    (data / "sweeps").mkdir()
    (data / "sweeps" / "2026-10-09__1.json").write_text(
        json.dumps(
            {
                "format": "gwylio.sweep/1",
                "on": "2026-10-09",
                "after_submissions": 9,
                "faded": [{"report_id": "x", "change": "quiet"}],
            }
        ),
        encoding="utf-8",
    )
    broken.unlink()
    with pytest.raises(RebuildError, match="ran after 9 submissions, but only 2 exist"):
        rebuild(data, CONFIG, tmp_path / "r.sqlite")
