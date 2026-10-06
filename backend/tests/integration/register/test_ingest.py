"""``gwylio ingest``: validate, apply all or nothing, keep the file as the fact."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gwylio.infrastructure.sqlite.db import Database
from gwylio.infrastructure.sqlite.repositories import table_counts
from tests.integration.register.conftest import (
    FIRST,
    SEED_SUBMISSIONS,
    Cli,
    register,
    seed_document,
    write,
)

pytestmark = pytest.mark.integration

COUNTED = ("report", "submission", "disposition", "report_sighting", "report_history")


def counts(data: Path) -> dict[str, int]:
    with Database.open(data / "gwylio.sqlite") as db:
        found = table_counts(db)
    return {table: found[table] for table in COUNTED}


def test_the_seed_submission_ingests_and_is_copied_in_as_the_fact(
    first_run: Cli, data: Path
) -> None:
    source = SEED_SUBMISSIONS / f"{FIRST}__1.json"
    result = first_run("ingest", str(source))
    assert result.exit_code == 0, result.output
    target = data / "submissions" / f"{FIRST}__1.json"
    assert target.read_bytes() == source.read_bytes()
    lines = result.stdout.splitlines()
    assert lines[0] == f"ingest: applied submission {FIRST}__1 ({target})"
    assert "  disposition: promoted          10" in lines
    assert "  reports created                10" in lines
    assert lines[-2:] == [
        f"wrote  {data / 'exports' / 'register.json'}",
        f"wrote  {data / 'exports' / 'runs.json'}",
    ]
    reports = register(data)
    assert len(reports) == 10
    funding = reports["nrw-funding-and-capacity-2026"]
    assert funding["grading"] == "B2"
    assert (funding["appearances"], funding["distinct_sources"]) == (1, 1)
    assert len(funding["sighting_ids"]) == 2, "the walesonline reinforcement is linked too"
    assert reports["ccc-progress-report-2026"]["state"] == "matured"
    again = first_run("ingest", str(source))
    assert again.exit_code == 1
    assert f"submission {FIRST}__1 is already ingested" in again.stderr


def test_one_bad_promotion_writes_nothing_not_even_the_good_ones(
    first_run: Cli, data: Path, tmp_path: Path
) -> None:
    document = seed_document()
    document["promotions"][3]["hazards"] = ["meteor-strike"]
    path = write(tmp_path / "bad.json", document)
    before = counts(data)
    result = first_run("ingest", str(path))
    assert result.exit_code == 1
    assert "error  promotions[3].hazards[0]: unknown hazard 'meteor-strike'" in result.stderr
    assert "ingest: refused, nothing written: 1 problem" in result.stderr
    assert counts(data) == before
    assert not (data / "submissions").exists()


def test_a_refusal_from_the_register_also_writes_nothing(
    first_run: Cli, data: Path, tmp_path: Path
) -> None:
    document = seed_document()
    first = write(tmp_path / "one.json", document)
    assert first_run("ingest", str(first)).exit_code == 0
    before = counts(data)
    follow_up = {
        "schema": "gwylio.submission/1",
        "run_id": None,
        "analyst": "Analyst",
        "rubric_version": "2026.10",
        "received_on": "2026-09-03",
        "promotions": [
            {
                **document["promotions"][1],
                "id": "a-good-new-report",
                "from_candidate": None,
                "url": "https://www.bbc.co.uk/news/articles/another",
            }
        ],
        "updates": [
            {
                "report_id": "ccc-progress-report-2026",
                "set": {"state": "matured"},
                "change": "Matured again.",
            }
        ],
        "method_note": "A direct addition.",
    }
    path = write(tmp_path / "two.json", follow_up)
    result = first_run("ingest", str(path))
    assert result.exit_code == 1
    assert (
        "error  updates[0].state: report 'ccc-progress-report-2026' is matured; MarkMatured is "
        "not allowed from that state" in result.stderr
    )
    assert counts(data) == before
    assert sorted(p.name for p in (data / "submissions").iterdir()) == [f"{FIRST}__1.json"]


def test_reliability_comes_from_the_source_not_the_file(
    first_run: Cli, data: Path, tmp_path: Path
) -> None:
    document = seed_document()
    for promotion in document["promotions"]:
        promotion["reliability_if_unknown_source"] = "E"
    assert first_run("ingest", str(write(tmp_path / "s.json", document))).exit_code == 0
    reports = register(data)
    assert reports["nature-recovery-bill-consultation"]["grading"] == "B1"
    assert reports["river-action-judicial-review-permission"]["grading"] == "D2"
    assert reports["phosphate-welsh-rivers-2026"]["grading"] == "E3", "no watched source"


def test_an_update_with_a_forbidden_key_is_refused(
    first_run: Cli, data: Path, tmp_path: Path
) -> None:
    document = seed_document()
    document["updates"] = [
        {"report_id": "ccc-progress-report-2026", "set": {"grading": "A1"}, "change": "x"}
    ]
    result = first_run("ingest", str(write(tmp_path / "s.json", document)))
    assert result.exit_code == 1
    assert "updates[0].set.grading: 'grading' cannot be set by an update" in result.stderr
    assert "updates[0].report_id: no report 'ccc-progress-report-2026'" in result.stderr


def test_missing_dispositions_need_allow_deferred(
    first_run: Cli, data: Path, tmp_path: Path
) -> None:
    document = seed_document()
    document["dispositions"] = [
        d for d in document["dispositions"] if d["outcome"] in ("promoted", "reinforcement")
    ]
    path = write(tmp_path / "s.json", document)
    refused = first_run("ingest", str(path))
    assert refused.exit_code == 1
    assert refused.stderr.count("has no disposition") == 6
    accepted = first_run("ingest", "--allow-deferred", str(path))
    assert accepted.exit_code == 0, accepted.output


def test_a_refused_file_inside_submissions_is_named_as_not_yet_a_fact(
    first_run: Cli, data: Path
) -> None:
    document = seed_document()
    document["promotions"][0]["topics"] = ["nowhere"]
    path = write(data / "submissions" / f"{FIRST}__1.json", document)
    result = first_run("ingest", str(path))
    assert result.exit_code == 1
    assert "was never ingested, so it is not yet a fact" in result.stderr
    assert path.exists(), "ingest never deletes a file it did not write"


def test_a_missing_file_exits_2(first_run: Cli, tmp_path: Path) -> None:
    result = first_run("ingest", str(tmp_path / "nothing.json"))
    assert result.exit_code == 2
    assert "no file at" in result.stderr


def test_collect_spots_reinforcements_once_reports_exist(first_run: Cli, data: Path) -> None:
    assert first_run("ingest", str(SEED_SUBMISSIONS / f"{FIRST}__1.json")).exit_code == 0
    second = first_run("collect", "--fake", "--at", "2026-10-01T09:00:00+0000")
    assert second.exit_code == 0, second.output
    assert "    reinforcements            10" in second.stdout
    candidates = json.loads(
        (data / "candidates" / "20261001T0900Z-0000.json").read_text(encoding="utf-8")
    )
    assert {r["matched_by"] for r in candidates["reinforcements"]} == {"url"}
