"""``gwylio audit`` and ``gwylio yield`` on the seed and on the legacy register."""

from __future__ import annotations

import pytest

from tests.integration.products.conftest import Cli

pytestmark = pytest.mark.integration


def test_audit_prints_both_matrices_statuses_and_credibility(seeded: Cli) -> None:
    result = seeded("audit")
    assert result.exit_code == 0, result.output
    lines = result.stdout.splitlines()
    assert lines[0].startswith("coverage audit: nrw-corporate-plan")
    assert "requirements by lane" in lines
    si12 = next(line for line in lines if "SI12 NRW colleague engagement" in line)
    assert si12.rstrip().endswith("blind_spot")
    si3 = next(line for line in lines if "SI3 Nature recovery in public services" in line)
    assert si3.rstrip().endswith("quiet")
    assert "taxonomy: sonarr-ecosystems (SoNaRR ecosystems and resources)" in lines
    assert "taxonomy: hazard-families (Hazard families)" in lines
    assert any(line.startswith("  row statuses: ") for line in lines)
    assert "credibility distribution (active reports assessed against the set)" in lines
    assert sum(1 for line in lines if line.strip().startswith(("1 ", "6 "))) == 2


def test_audit_refuses_an_unknown_set(seeded: Cli) -> None:
    result = seeded("audit", "--set", "nope")
    assert result.exit_code == 2
    assert "no requirement set 'nope'; configured: nrw-corporate-plan" in result.stderr


def test_audit_and_yield_need_a_database(cli: Cli) -> None:
    for verb in ("audit", "yield"):
        result = cli(verb)
        assert result.exit_code == 1
        assert "no database at" in result.stderr


def test_yield_lists_silent_sources_last(seeded: Cli) -> None:
    result = seeded("yield")
    assert result.exit_code == 0, result.output
    lines = result.stdout.splitlines()
    assert lines[0] == "yield of 43 sources over 4 runs"
    rows = lines[2:-2]
    readings = [row.split()[-1] for row in rows]
    assert readings[0] == "earning_its_place"
    first_silent = readings.index("silent")
    assert all(reading == "silent" for reading in readings[first_silent:])
    assert "earning_its_place" not in readings[first_silent:]
    assert lines[-1].startswith("silent sources (")
    assert lines[-2].startswith("readings: earning_its_place ")
    welsh_government = next(row for row in rows if row.startswith("  welsh-government "))
    assert "20260901T0900Z-0000" in welsh_government


def test_audit_and_yield_run_on_the_legacy_register(legacy: Cli) -> None:
    audit = legacy("audit")
    assert audit.exit_code == 0, audit.output
    assert "row statuses: covered 7, thin 3, blind_spot 2" in audit.stdout
    result = legacy("yield")
    assert result.exit_code == 0, result.output
    assert result.stdout.splitlines()[0] == "yield of 43 sources over 0 runs"
