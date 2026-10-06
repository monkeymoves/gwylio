"""``publish``: the snapshot equals the API, is deterministic, cleans up, and is only a mirror."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from gwylio.api import schemas
from gwylio.infrastructure.config.loaders import LoadedConfig
from gwylio.infrastructure.config.settings import Settings
from gwylio.infrastructure.readmodels import ReadModels
from gwylio.infrastructure.snapshot import (
    PublishError,
    publish,
    route_for,
    snapshot_entries,
)
from gwylio.infrastructure.sqlite.db import Database
from gwylio.shared.clock import FixedClock
from tests.api.conftest import CLOCK
from tests.support import PROJECT_ROOT

pytestmark = pytest.mark.integration

SITE_DATA = PROJECT_ROOT / "frontend" / "static" / "data"
DASHES = (chr(0x2013), chr(0x2014))


def published(
    root: Path,
    settings: Settings,
    db: Database,
    config: LoadedConfig,
    clock: FixedClock = CLOCK,
) -> dict[str, bytes]:
    publish(settings, [root], clock=clock, database=db, config=config)
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*.json"))}


def test_every_snapshot_file_equals_the_api_response(
    tmp_path: Path,
    client: TestClient,
    models: ReadModels,
    seed_settings: Settings,
    seed_db: Database,
    shipped_config: LoadedConfig,
) -> None:
    files = published(tmp_path, seed_settings, seed_db, shipped_config)
    entries = snapshot_entries(models)
    assert sorted(files) == [entry.path for entry in entries]
    assert len(files) == 28
    for entry in entries:
        response = client.get(entry.api_path)
        assert response.status_code == 200, entry.api_path
        assert json.loads(files[entry.path]) == response.json(), entry.path
        assert route_for(entry.path) == entry.route


def test_two_publishes_with_the_same_clock_are_byte_identical(
    tmp_path: Path, seed_settings: Settings, seed_db: Database, shipped_config: LoadedConfig
) -> None:
    first = published(tmp_path / "a", seed_settings, seed_db, shipped_config)
    second = published(tmp_path / "b", seed_settings, seed_db, shipped_config)
    again = published(tmp_path / "a", seed_settings, seed_db, shipped_config)
    assert first == second == again
    for name, data in first.items():
        text = data.decode("utf-8")
        assert text.endswith("}\n") or text.endswith("]\n"), name
        assert (
            text
            == json.dumps(json.loads(text), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        )
        assert not any(dash in text for dash in DASHES), name


def test_a_later_clock_on_the_same_day_changes_only_meta(
    tmp_path: Path, seed_settings: Settings, seed_db: Database, shipped_config: LoadedConfig
) -> None:
    morning = published(tmp_path / "a", seed_settings, seed_db, shipped_config)
    later = FixedClock(datetime(2026, 10, 6, 17, 30, tzinfo=UTC))
    evening = published(tmp_path / "b", seed_settings, seed_db, shipped_config, later)
    changed = sorted(name for name in morning if morning[name] != evening[name])
    assert changed == ["meta.json"]
    assert json.loads(evening["meta.json"])["generated_at"] == "2026-10-06T17:30:00Z"


def test_a_publish_removes_stale_json_and_nothing_else(
    tmp_path: Path, seed_settings: Settings, seed_db: Database, shipped_config: LoadedConfig
) -> None:
    (tmp_path / "reports").mkdir(parents=True)
    (tmp_path / "reports" / "a-report-since-removed.json").write_text("{}", encoding="utf-8")
    (tmp_path / "old_index.json").write_text("[]", encoding="utf-8")
    (tmp_path / "gone").mkdir()
    (tmp_path / "gone" / "x.json").write_text("{}", encoding="utf-8")
    (tmp_path / "README.txt").write_text("kept", encoding="utf-8")
    result = publish(
        seed_settings, [tmp_path], clock=CLOCK, database=seed_db, config=shipped_config
    )
    assert result.removed == 3
    assert not (tmp_path / "reports" / "a-report-since-removed.json").exists()
    assert not (tmp_path / "old_index.json").exists()
    assert not (tmp_path / "gone").exists(), "an emptied folder goes too"
    assert (tmp_path / "README.txt").read_text(encoding="utf-8") == "kept"
    assert (tmp_path / "reports" / "phosphate-welsh-rivers-2026.json").is_file()


def test_publish_writes_both_default_directories(
    tmp_path: Path, seed_db: Database, shipped_config: LoadedConfig
) -> None:
    root = tmp_path / "project"
    settings = Settings(
        root=root,
        data_dir=root / "data",
        config_dir=PROJECT_ROOT / "config",
        db_path=root / "data" / "gwylio.sqlite",
    )
    result = publish(settings, clock=CLOCK, database=seed_db, config=shipped_config)
    assert result.directories == (
        root / "frontend" / "static" / "data",
        root / "data" / "snapshots",
    )
    for directory in result.directories:
        assert (directory / "meta.json").is_file()
    site, kept = (
        {p.relative_to(d).as_posix(): p.read_bytes() for p in d.rglob("*.json")}
        for d in result.directories
    )
    assert site == kept


def test_publish_refuses_without_a_database(tmp_path: Path, shipped_config: LoadedConfig) -> None:
    settings = Settings(
        root=tmp_path,
        data_dir=tmp_path / "data",
        config_dir=PROJECT_ROOT / "config",
        db_path=tmp_path / "data" / "gwylio.sqlite",
    )
    with pytest.raises(PublishError, match="no database at"):
        publish(settings, [tmp_path / "out"], clock=CLOCK, config=shipped_config)
    assert not (tmp_path / "out").exists()


# The committed snapshot the static site is built from.

_MODELS: dict[str, tuple[type[BaseModel], bool]] = {
    "/meta": (schemas.Meta, False),
    "/meta/enums": (schemas.Enums, False),
    "/requirement-sets": (schemas.RequirementSetSummary, True),
    "/reports": (schemas.ReportSummary, True),
    "/sources": (schemas.SourceSummary, True),
    "/sources/health": (schemas.SourcesHealth, False),
    "/scan-runs": (schemas.RunSummary, True),
    "/datecheck": (schemas.DateCheck, False),
    "/products": (schemas.ProductSummary, True),
}
_PREFIXED: dict[str, type[BaseModel]] = {
    "/reports/": schemas.ReportDetail,
    "/scan-runs/": schemas.RunDetail,
    "/products/": schemas.ProductDetail,
    "/coverage/": schemas.Coverage,
}


def _model(route: str) -> tuple[type[BaseModel], bool]:
    if route in _MODELS:
        return _MODELS[route]
    if route.startswith("/requirement-sets/"):
        if route.endswith("/picture"):
            return schemas.Picture, False
        return schemas.RequirementSetDetail, False
    for prefix, model in _PREFIXED.items():
        if route.startswith(prefix):
            return model, False
    raise AssertionError(f"no model for {route}")


def test_the_site_snapshot_is_a_mirror_of_the_api_not_a_superset(client: TestClient) -> None:
    if not (SITE_DATA / "meta.json").is_file():
        pytest.skip("no snapshot published under frontend/static/data yet")
    templates = set(client.get("/api/v1/openapi.json").json()["paths"])
    for path in sorted(SITE_DATA.rglob("*")):
        if path.is_dir():
            continue
        relative = path.relative_to(SITE_DATA).as_posix()
        route = route_for(relative)
        assert route is not None, f"frontend/static/data/{relative} has no API route"
        segments = route.strip("/").split("/")
        assert any(
            len(t.strip("/").split("/")) == len(segments) + 2
            and all(
                a == b or (a.startswith("{") and a.endswith("}"))
                for a, b in zip(t.strip("/").split("/")[2:], segments, strict=True)
            )
            for t in templates
        ), f"no API route serves {route}"
        model, many = _model(route)
        document = json.loads(path.read_text(encoding="utf-8"))
        if many:
            assert isinstance(document, list), relative
            for item in document:
                model.model_validate(item)
        else:
            model.model_validate(document)
