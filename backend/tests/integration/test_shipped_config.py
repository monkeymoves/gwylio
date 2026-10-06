"""The shipped config/ loads through the real loaders and says what it should."""

from __future__ import annotations

import pytest

from gwylio.direction.model import GroupKind, Scanability
from gwylio.direction.scanability import CoverageStatus, coverage_status
from gwylio.infrastructure.config.loaders import LoadedConfig, check_config, load_config
from gwylio.reference.model import HAZARD_FAMILIES_AXIS, SONARR_AXIS, NodeKind
from tests.support import PROJECT_ROOT

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def config() -> LoadedConfig:
    return load_config(PROJECT_ROOT)


def test_check_reports_no_problems_and_one_summary_per_file() -> None:
    report = check_config(PROJECT_ROOT)
    assert report.ok, "\n".join(map(str, report.problems))
    assert [s.file for s in report.summaries] == [
        "config/taxonomy.json",
        "config/lanes.json",
        "config/reference/topics.json",
        "config/reference/hazards.json",
        "config/reference/places.json",
        "config/reference/actors.json",
        "config/requirement_sets/nrw-corporate-plan.json",
        "config/sources.json",
        "config/gating.json",
        "config/instrument.json",
        "config/datecheck.json",
        "config/copy.json",
    ]


def test_headline_counts(config: LoadedConfig) -> None:
    nrw = config.requirement_set("nrw-corporate-plan")
    assert len(nrw.requirements) == 12
    assert len(nrw.groups_of_kind(GroupKind.IMPACT)) == 6
    assert len(nrw.groups_of_kind(GroupKind.WBO)) == 3
    assert len(config.catalogue.taxonomy.axis(SONARR_AXIS).nodes) == 11
    assert len(config.catalogue.lanes) == 10


def test_sonarr_axis_has_eight_ecosystems_and_three_resources(config: LoadedConfig) -> None:
    nodes = config.catalogue.taxonomy.axis(SONARR_AXIS).nodes
    assert sum(n.kind is NodeKind.ECOSYSTEM for n in nodes) == 8
    assert {n.id for n in nodes if n.kind is NodeKind.RESOURCE} == {"air", "soils", "water"}


def test_every_hazard_family_is_used_by_at_least_one_hazard(config: LoadedConfig) -> None:
    families = config.catalogue.taxonomy.axis(HAZARD_FAMILIES_AXIS).node_ids()
    used = {hazard.family for hazard in config.catalogue.hazards}
    assert used == families


def test_every_lane_has_at_least_one_actor(config: LoadedConfig) -> None:
    assert {a.lane for a in config.catalogue.actors} == config.catalogue.lane_ids()


def test_places_hang_off_wales(config: LoadedConfig) -> None:
    catalogue = config.catalogue
    assert catalogue.place("wales").parent is None
    assert len(catalogue.children_of("wales")) == 12


def test_requirements_are_si1_to_si12_in_order(config: LoadedConfig) -> None:
    nrw = config.requirement_set("nrw-corporate-plan")
    assert [r.code for r in nrw.requirements] == [f"SI{n}" for n in range(1, 13)]
    assert [r.id for r in nrw.requirements] == [f"si{n}" for n in range(1, 13)]


def test_scanability_transcribed_from_the_old_framework(config: LoadedConfig) -> None:
    nrw = config.requirement_set("nrw-corporate-plan")
    expected = {
        "si1": "high",
        "si2": "medium",
        "si3": "high",
        "si4": "high",
        "si5": "high",
        "si6": "high",
        "si7": "medium",
        "si8": "high",
        "si9": "low",
        "si10": "medium",
        "si11": "low",
        "si12": "none",
    }
    assert {r.id: r.scanability.value for r in nrw.requirements} == expected


def test_si9_si11_and_si12_read_blind_spot_when_empty(config: LoadedConfig) -> None:
    nrw = config.requirement_set("nrw-corporate-plan")
    blind = [
        r.code
        for r in nrw.requirements
        if coverage_status(r.scanability, 0) is CoverageStatus.BLIND_SPOT
    ]
    assert blind == ["SI9", "SI11", "SI12"]


def test_impact_membership_inverts_each_indicator_impacts(config: LoadedConfig) -> None:
    nrw = config.requirement_set("nrw-corporate-plan")
    members = {g.id: list(g.members) for g in nrw.groups_of_kind(GroupKind.IMPACT)}
    assert members == {
        "i1": ["si1", "si2", "si3", "si4", "si7"],
        "i2": ["si1", "si2", "si5", "si6", "si7", "si8", "si10"],
        "i3": ["si4", "si5", "si6"],
        "i4": ["si7", "si8", "si9"],
        "i5": ["si3", "si9", "si10", "si11"],
        "i6": ["si12"],
    }


def test_wbo_groups_list_primary_indicators_and_their_impact(config: LoadedConfig) -> None:
    nrw = config.requirement_set("nrw-corporate-plan")
    wbos = {
        g.id: (list(g.members), list(g.related_groups)) for g in nrw.groups_of_kind(GroupKind.WBO)
    }
    assert wbos == {
        "nature-recovering": (["si1", "si2", "si3"], ["i1"]),
        "communities-resilient-climate": (["si6", "si7", "si8", "si10"], ["i2"]),
        "pollution-minimised": (["si4", "si5"], ["i3"]),
    }


def test_internal_indicator_has_no_keywords_and_no_coverage(config: LoadedConfig) -> None:
    si12 = config.requirement_set("nrw-corporate-plan").requirement("si12")
    assert si12.scanability is Scanability.NONE
    assert si12.keywords == ()
    assert si12.expected_coverage == ()
    assert si12.metric_sources == ("Ein Llais staff survey",)
