"""``gwylio collect`` and ``gwylio probe`` through the Typer application."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gwylio.cli.collect import ACADEMIC_ENV_VAR, default_disciplines
from gwylio.cli.main import app
from gwylio.collection.model import Discipline
from gwylio.infrastructure.handoff.candidates_file import read_candidates_file
from tests.support import PROJECT_ROOT

pytestmark = pytest.mark.integration

runner = CliRunner()
ROOT = ["--root", str(PROJECT_ROOT)]


def test_dry_run_writes_a_valid_candidates_file_and_prints_the_funnel(tmp_path: Path) -> None:
    out = tmp_path / "c.json"
    result = runner.invoke(app, ["collect", "--dry-run", "--out", str(out), *ROOT])
    assert result.exit_code == 0, result.output
    document = read_candidates_file(out)
    assert document.funnel.raw == 30
    assert document.funnel.unique == 17
    assert len(document.candidates) == 17
    assert document.disciplines_run == [
        Discipline.OSINT_WEB,
        Discipline.OSINT_FEED,
        Discipline.OSINT_SITE,
    ]
    lines = result.stdout.splitlines()
    assert lines[0] == f"wrote  {out}"
    assert lines[1].startswith(f"Funnel for run {document.run_id} (instrument 2026.10.0)")
    assert "  raw hits                    30" in lines
    assert "  dropped: own domain          2" in lines
    assert "  dropped: negative term       5" in lines
    assert "  dropped: unrelated           3" in lines
    assert "  passed the gates            20" in lines
    assert "  unique candidates           17" in lines
    assert lines[-1] == "requests made: 148 of 150; budget not exhausted"


def test_dry_run_overwrites_its_scratch_output(tmp_path: Path) -> None:
    out = tmp_path / "c.json"
    out.write_text("stale", encoding="utf-8")
    result = runner.invoke(app, ["collect", "--dry-run", "--out", str(out), *ROOT])
    assert result.exit_code == 0, result.output
    assert read_candidates_file(out).funnel.passed == 20


def test_dry_run_to_stdout_keeps_the_table_on_stderr() -> None:
    result = runner.invoke(app, ["collect", "--dry-run", *ROOT])
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["format"] == "gwylio.candidates/1"
    assert "Funnel for run" in result.stderr


def test_dry_run_with_one_discipline(tmp_path: Path) -> None:
    out = tmp_path / "feed.json"
    result = runner.invoke(
        app, ["collect", "--dry-run", "--discipline", "osint_feed", "--out", str(out), *ROOT]
    )
    assert result.exit_code == 0, result.output
    document = read_candidates_file(out)
    assert document.disciplines_run == [Discipline.OSINT_FEED]
    assert document.requests_made == 14
    assert {c.source_id for c in document.candidates} == {"audit-wales", "climate-change-committee"}


def test_academic_runs_when_asked_and_exhausts_the_budget(tmp_path: Path) -> None:
    out = tmp_path / "all.json"
    result = runner.invoke(
        app,
        ["collect", "--dry-run", "--out", str(out), *ROOT],
        env={ACADEMIC_ENV_VAR: "1"},
    )
    assert result.exit_code == 0, result.output
    document = read_candidates_file(out)
    assert Discipline.OSINT_ACADEMIC in document.disciplines_run
    assert document.budget_exhausted
    assert document.funnel.raw == 32
    assert "budget exhausted" in result.stdout
    assert "12 queries not run" in result.stdout


def test_default_disciplines_follow_the_academic_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ACADEMIC_ENV_VAR, raising=False)
    assert Discipline.OSINT_ACADEMIC not in default_disciplines()
    assert default_disciplines(True)[-1] is Discipline.OSINT_ACADEMIC
    monkeypatch.setenv(ACADEMIC_ENV_VAR, "1")
    assert default_disciplines()[-1] is Discipline.OSINT_ACADEMIC
    assert Discipline.OSINT_ACADEMIC not in default_disciplines(False)


def test_reserved_discipline_exits_2() -> None:
    result = runner.invoke(app, ["collect", "--dry-run", "--discipline", "geoint", *ROOT])
    assert result.exit_code == 2
    assert "no collector serves geoint" in result.stderr


def test_collect_on_invalid_config_exits_1(project_copy: Path) -> None:
    (project_copy / "config/instrument.json").write_text("{}", encoding="utf-8")
    result = runner.invoke(app, ["collect", "--dry-run", "--root", str(project_copy)])
    assert result.exit_code == 1
    assert "configuration is invalid" in result.stderr


def test_probe_prints_matching_hits_and_writes_nothing(tmp_path: Path) -> None:
    result = runner.invoke(app, ["probe", "drought", "--fake", *ROOT])
    assert result.exit_code == 0, result.output
    assert result.stdout.splitlines() == [
        "probe (osint_web, fake collector): 1 hit, 1 request, nothing stored",
        "  2026-09-02  Drought declared across South West Wales",
        "              https://nation.cymru/news/drought-declared-across-south-west-wales",
    ]


def test_probe_site_needs_known_sources() -> None:
    assert runner.invoke(app, ["probe", "x", "--discipline", "osint_site", *ROOT]).exit_code == 2
    unknown = runner.invoke(
        app, ["probe", "x", "--discipline", "osint_site", "--source", "nobody", *ROOT]
    )
    assert unknown.exit_code == 2
    assert "unknown source nobody" in unknown.stderr
    found = runner.invoke(
        app,
        [
            "probe",
            "judicial review",
            "--discipline",
            "osint_site",
            "--source",
            "river-action",
            "--fake",
            *ROOT,
        ],
    )
    assert found.exit_code == 0, found.output
    assert "1 hit, 1 request, nothing stored" in found.stdout
    assert runner.invoke(app, ["probe", "x", "--discipline", "sensor", *ROOT]).exit_code == 2
