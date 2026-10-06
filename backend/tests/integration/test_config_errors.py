"""check_config on broken copies of the shipped config: every problem, with file and path."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from gwylio.infrastructure.config.loaders import ConfigInvalidError, check_config, load_config

pytestmark = pytest.mark.integration

EM_DASH = chr(0x2014)
EN_DASH = chr(0x2013)
SET_FILE = "config/requirement_sets/nrw-corporate-plan.json"


def edit(root: Path, relative: str, change: Callable[[Any], None]) -> None:
    path = root / relative
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def problems(root: Path) -> list[str]:
    report = check_config(root)
    assert not report.ok
    assert report.config is None
    return [str(problem) for problem in report.problems]


def test_the_copy_is_valid_before_editing(project_copy: Path) -> None:
    assert check_config(project_copy).ok


def test_em_dash_in_prose_is_refused_with_file_and_path(project_copy: Path) -> None:
    def change(data: Any) -> None:
        data["requirements"][3]["name"] = f"Pollution {EM_DASH} land"

    edit(project_copy, SET_FILE, change)
    [message, *_] = problems(project_copy)
    assert message.startswith(f"{SET_FILE}: requirements[3].name: ")
    assert "U+2014 EM DASH" in message


def test_en_dash_in_a_keyword_is_refused(project_copy: Path) -> None:
    edit(
        project_copy,
        "config/lanes.json",
        lambda d: d["lanes"][0].update(description=f"2024{EN_DASH}25"),
    )
    [message, *_] = problems(project_copy)
    assert message.startswith("config/lanes.json: lanes[0].description: ")
    assert "U+2013 EN DASH" in message


def test_unknown_hazard_family(project_copy: Path) -> None:
    edit(
        project_copy,
        "config/reference/hazards.json",
        lambda d: d["hazards"][2].update(family="space-weather"),
    )
    assert problems(project_copy)[0] == (
        "config/reference/hazards.json: hazards[2].family: hazard 'avian-influenza' names "
        "unknown family 'space-weather'; families are the nodes of the hazard-families axis"
    )


def test_unknown_place_parent(project_copy: Path) -> None:
    edit(
        project_copy,
        "config/reference/places.json",
        lambda d: d["places"][5].update(parent="england"),
    )
    assert problems(project_copy)[0] == (
        "config/reference/places.json: places[5].parent: place 'dee' names unknown parent 'england'"
    )


def test_unknown_actor_lane(project_copy: Path) -> None:
    edit(
        project_copy,
        "config/reference/actors.json",
        lambda d: d["actors"][0].update(lane="cardiff-bay"),
    )
    assert problems(project_copy)[0].startswith(
        "config/reference/actors.json: actors[0].lane: actor 'welsh-government' names unknown lane"
    )


def test_unknown_group_member(project_copy: Path) -> None:
    edit(project_copy, SET_FILE, lambda d: d["groups"][0]["members"].append("si13"))
    assert problems(project_copy)[0] == (
        f"{SET_FILE}: groups[0].members[5]: group 'i1' names unknown requirement 'si13'"
    )


def test_unknown_coverage_node(project_copy: Path) -> None:
    edit(
        project_copy, SET_FILE, lambda d: d["requirements"][0]["expected_coverage"].append("tundra")
    )
    assert problems(project_copy)[0].startswith(
        f"{SET_FILE}: requirements[0].expected_coverage[9]: requirement SI1 expects coverage"
    )


def test_duplicate_code(project_copy: Path) -> None:
    edit(project_copy, SET_FILE, lambda d: d["requirements"][1].update(code="SI1"))
    assert problems(project_copy)[0] == (
        f"{SET_FILE}: requirements[1].code: requirement code 'SI1' is used twice"
    )


def test_set_id_must_match_file_name(project_copy: Path) -> None:
    edit(project_copy, SET_FILE, lambda d: d.update(id="nrw"))
    assert f"{SET_FILE}: id: set id 'nrw' must match the file name 'nrw-corporate-plan'" in (
        problems(project_copy)
    )


def test_short_name_over_six_words(project_copy: Path) -> None:
    edit(
        project_copy,
        SET_FILE,
        lambda d: d["requirements"][0].update(short="one two three four five six seven"),
    )
    assert problems(project_copy)[0].startswith(f"{SET_FILE}: requirements[0]: requirement SI1")


def test_bad_enum_value_and_unknown_key(project_copy: Path) -> None:
    def change(data: Any) -> None:
        data["lanes"][1]["lens"] = "local"
        data["lanes"][2]["colour"] = "green"

    edit(project_copy, "config/lanes.json", change)
    found = problems(project_copy)
    assert any(p.startswith("config/lanes.json: lanes[1].lens: Input should be") for p in found)
    assert "config/lanes.json: lanes[2].colour: Extra inputs are not permitted" in found


def test_bad_id_and_bad_domain(project_copy: Path) -> None:
    def change(data: Any) -> None:
        data["actors"][0]["id"] = "Welsh_Government"
        data["actors"][1]["domain"] = "https://senedd.wales"

    edit(project_copy, "config/reference/actors.json", change)
    found = problems(project_copy)
    assert any(p.startswith("config/reference/actors.json: actors[0].id:") for p in found)
    assert any(p.startswith("config/reference/actors.json: actors[1].domain:") for p in found)


def test_invalid_json_and_missing_file_are_reported_together(project_copy: Path) -> None:
    (project_copy / "config/reference/topics.json").write_text("{ nope", encoding="utf-8")
    (project_copy / "config/taxonomy.json").unlink()
    found = problems(project_copy)
    assert "config/taxonomy.json: file not found" in found
    assert any(
        p.startswith("config/reference/topics.json: line 1 column 3: invalid JSON") for p in found
    )
    report = check_config(project_copy)
    assert report.notes == (
        "reference cross-checks skipped until the problems above are fixed",
        f"{SET_FILE}: taxonomy cross-checks skipped until the taxonomy loads",
    )


def test_no_requirement_sets(project_copy: Path) -> None:
    (project_copy / SET_FILE).unlink()
    assert "config/requirement_sets: no requirement set files found" in problems(project_copy)


def test_load_config_raises_with_every_problem(project_copy: Path) -> None:
    def change(data: Any) -> None:
        data["requirements"][0]["scanability"] = "perfect"
        data["requirements"][1]["scanability"] = "excellent"

    edit(project_copy, SET_FILE, change)
    with pytest.raises(ConfigInvalidError) as caught:
        load_config(project_copy)
    assert [p.location for p in caught.value.problems] == [
        "requirements[0].scanability",
        "requirements[1].scanability",
    ]
