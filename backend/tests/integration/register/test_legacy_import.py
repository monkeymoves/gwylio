"""``gwylio import-legacy`` over the real old register, when it is present."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from gwylio.infrastructure.config.loaders import LoadedConfig
from gwylio.infrastructure.handoff.legacy import (
    CREDIBILITY_BY_EVIDENCE,
    LegacyImportError,
    legacy_submission,
    match_source,
)
from gwylio.infrastructure.sqlite.db import Database
from gwylio.infrastructure.sqlite.rebuild import rebuild
from tests.integration.register.conftest import Cli, register
from tests.integration.sqlite.test_rebuild import assert_equivalent
from tests.support import PROJECT_ROOT

pytestmark = pytest.mark.integration

LEGACY = Path("/home/user/NRW-Scan-Tool/data/signals.json")
needs_legacy = pytest.mark.skipif(
    not LEGACY.is_file(), reason=f"the old register is not at {LEGACY}"
)
STEM = "legacy__2026-07-25"


def old_signals() -> dict[str, dict[str, Any]]:
    data = json.loads(LEGACY.read_text(encoding="utf-8"))
    return {signal["id"]: signal for signal in data["signals"]}


@needs_legacy
def test_the_old_register_imports_to_35_reports_with_no_problems(
    cli: Cli, data: Path, shipped_config: LoadedConfig
) -> None:
    result = cli("import-legacy", str(LEGACY))
    assert result.exit_code == 0, result.output
    assert result.stderr == ""
    path = data / "submissions" / f"{STEM}.json"
    assert result.stdout.splitlines()[0] == f"import-legacy: applied submission {STEM} ({path})"
    reports = register(data)
    assert len(reports) == 35
    signals = old_signals()
    assert set(reports) == set(signals)
    assert sorted(r for r, report in reports.items() if report["state"] == "matured") == [
        "carbon-budget-4-regulations-wales-2025",
        "environment-principles-governance-biodiversity-targets-wales-act-2026",
    ]
    assert {report["state"] for report in reports.values()} == {"emerging", "matured"}
    sources = {source.id: source for source in shipped_config.sources}
    for report_id, report in reports.items():
        old = signals[report_id]
        assert report["places"] == ["wales"]
        assert report["sighting_ids"] == [] and report["appearances"] == 0
        credibility = CREDIBILITY_BY_EVIDENCE[old["scores"]["evidence_strength"]]
        if report["source_id"] is None:
            letter = "B" if old["lens"] == "government" else "C"
        else:
            letter = sources[report["source_id"]].reliability.value
        assert report["grading"] == f"{letter}{credibility}", report_id
        assert [a["requirement_id"] for a in report["assessments"]] == [
            s["si"].lower() for s in old["sis"]
        ]
        assert [(h["on"], h["change"]) for h in report["history"][:-1]] == [
            (h["date"], h["change"]) for h in old["history"]
        ]
        assert {h["kind"] for h in report["history"][:-1]} <= {"imported"}
        assert report["history"][-1]["kind"] == "created"
        assert report["history"][-1]["change"].startswith(
            "Imported from the NRW SI horizon register (signals.json, scan date 2026-07-25). "
            "Grading defaulted on import and awaits analyst review."
        )
        assert report["event_horizon"] == old.get("event_horizon")
        assert report["last_verified"] == old.get("last_verified")
        assert report["report_type"] == old["signal_type"]
    unwatched = sorted(r for r, report in reports.items() if report["source_id"] is None)
    assert unwatched == [
        "first-asian-hornet-nest-wales-2026",
        "flood-re-ends-2039-insurance-affordability",
        "metal-mine-water-pollution-wales",
        "sonarr-2025-published",
    ]
    assert reports["nrw-funding-gap-savings-2026-27"]["source_id"] == "senedd-research"


@needs_legacy
def test_the_import_and_its_export_are_deterministic(cli: Cli, data: Path, tmp_path: Path) -> None:
    assert cli("import-legacy", str(LEGACY)).exit_code == 0
    export = data / "exports" / "register.json"
    first = export.read_bytes()
    assert cli("export").exit_code == 0
    assert export.read_bytes() == first
    other = tmp_path / "other"
    assert cli("import-legacy", str(LEGACY), GWYLIO_DATA_DIR=str(other)).exit_code == 0
    assert (other / "exports" / "register.json").read_bytes() == first
    assert (other / "submissions" / f"{STEM}.json").read_bytes() == (
        data / "submissions" / f"{STEM}.json"
    ).read_bytes()
    rebuilt = tmp_path / "rebuilt.sqlite"
    rebuild(data, PROJECT_ROOT / "config", rebuilt)
    with Database.open(data / "gwylio.sqlite") as a, Database.open(rebuilt) as b:
        assert_equivalent(a, b)


@needs_legacy
def test_a_second_import_is_refused_and_datecheck_runs_on_the_result(cli: Cli, data: Path) -> None:
    assert cli("import-legacy", str(LEGACY)).exit_code == 0
    again = cli("import-legacy", str(LEGACY))
    assert again.exit_code == 1
    assert f"submission {STEM} is already ingested" in again.stderr
    checked = cli("datecheck", "--today", "2026-10-06")
    assert checked.exit_code == 0
    assert checked.stdout.startswith("date check on 2026-10-06: ")
    assert "of 35 reports in the picture" in checked.stdout.splitlines()[0]
    assert "environmental-principles-statement-consultation-2026: event horizon 2026-09-11" in (
        checked.stdout
    )


@needs_legacy
def test_received_on_names_the_file_and_a_different_file_is_never_overwritten(
    cli: Cli, data: Path
) -> None:
    result = cli("import-legacy", str(LEGACY), "--received-on", "2026-07-26")
    assert result.exit_code == 0, result.output
    assert (data / "submissions" / "legacy__2026-07-26.json").is_file()
    clash = data / "submissions" / f"{STEM}.json"
    clash.write_text("{}", encoding="utf-8")
    refused = cli("import-legacy", str(LEGACY))
    assert refused.exit_code == 1
    assert "already exists with different content" in refused.stderr
    assert cli("import-legacy", str(LEGACY), "--received-on", "26 July").exit_code == 2


def test_bad_legacy_files_are_refused(shipped_config: LoadedConfig, tmp_path: Path) -> None:
    with pytest.raises(LegacyImportError, match="no signals list"):
        legacy_submission({"signals": []}, shipped_config)
    signal = {
        "id": "x",
        "title": "Drought",
        "url": "https://example.org/x",
        "source": "example.org",
        "scan_lane": "nowhere",
        "signal_type": "policy",
        "sis": [{"si": "SI1", "direction": "supports"}],
        "lens": "government",
        "scores": {"evidence_strength": "high"},
        "lifecycle": "emerging",
        "bucket": "watch",
        "summary": "S",
    }
    with pytest.raises(LegacyImportError, match="unmapped scan_lane 'nowhere'"):
        legacy_submission({"scan_date": "2026-07-25", "signals": [signal]}, shipped_config)
    with pytest.raises(LegacyImportError, match="no scan_date"):
        legacy_submission({"signals": [signal]}, shipped_config)


def test_sources_match_by_host_and_the_longest_domain_wins(shipped_config: LoadedConfig) -> None:
    sources = shipped_config.sources

    def matched(url: str) -> str | None:
        source = match_source(url, sources)
        return None if source is None else str(source.id)

    assert matched("https://www.gov.wales/x") == "welsh-government"
    assert matched("https://statswales.gov.wales/x") == "statswales"
    assert matched("https://research.senedd.wales/x") == "senedd-research"
    assert matched("https://laiddocuments.senedd.wales/x") == "senedd-cymru"
    assert matched("https://assets.publishing.service.gov.uk/x") == "uk-government"
    assert matched("https://planthealthportal.defra.gov.uk/x") == "plant-health-portal"
    assert matched("https://notgov.wales/x") is None
    assert matched("https://www.itv.com/news") is None
