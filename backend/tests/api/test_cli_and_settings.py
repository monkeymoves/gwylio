"""``gwylio publish``, ``gwylio serve``, ``collect --hits``, and the API reading Settings."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient
from typer.testing import CliRunner, Result

from gwylio.api.app import create_app
from gwylio.cli.main import app as cli_app
from gwylio.infrastructure.codegen.generate import OPENAPI_PATH
from gwylio.infrastructure.config.settings import (
    ACADEMIC_ENV_VAR,
    DATA_DIR_ENV_VAR,
    DB_PATH_ENV_VAR,
    Settings,
)
from gwylio.infrastructure.sqlite.db import Database
from tests.api.conftest import CLOCK, SEED
from tests.support import PROJECT_ROOT

pytestmark = pytest.mark.integration

FACTS = ("candidates", "instruments", "submissions", "sweeps", "products")


@pytest.fixture
def data(tmp_path: Path) -> Path:
    """A scratch data directory holding the seed's facts, not yet rebuilt."""
    target = tmp_path / "data"
    for folder in FACTS:
        shutil.copytree(SEED / folder, target / folder)
    return target


def gwylio(data: Path, *args: str) -> Result:
    environment = {DATA_DIR_ENV_VAR: str(data), DB_PATH_ENV_VAR: "", ACADEMIC_ENV_VAR: ""}
    return CliRunner().invoke(cli_app, [*args, "--root", str(PROJECT_ROOT)], env=environment)


def test_publish_prints_the_count_and_writes_a_reproducible_snapshot(
    data: Path, tmp_path: Path
) -> None:
    assert gwylio(data, "rebuild").exit_code == 0
    out = tmp_path / "site"
    at = ("--at", "2026-10-06T09:00:00+0000")
    first = gwylio(data, "publish", "--out", str(out), *at)
    assert first.exit_code == 0, first.output
    assert first.stdout.splitlines() == [
        "publish: 28 files into 1 directory",
        f"wrote  {out}",
    ]
    before = {p: p.read_bytes() for p in out.rglob("*.json")}
    assert gwylio(data, "publish", "--out", str(out), *at).exit_code == 0
    assert {p: p.read_bytes() for p in out.rglob("*.json")} == before
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert meta["generated_at"] == "2026-10-06T09:00:00Z"
    assert meta["counts"]["reports"] == 10


def test_publish_without_a_database_exits_1(data: Path, tmp_path: Path) -> None:
    result = gwylio(data, "publish", "--out", str(tmp_path / "site"))
    assert result.exit_code == 1
    assert "publish: no database at" in result.stderr
    assert "gwylio rebuild" in result.stderr


def test_publish_refuses_a_time_without_a_zone(data: Path, tmp_path: Path) -> None:
    result = gwylio(data, "publish", "--out", str(tmp_path), "--at", "2026-10-06T09:00:00")
    assert result.exit_code == 2


def test_serve_runs_uvicorn_on_the_api(data: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    def fake_run(app: FastAPI, **kwargs: Any) -> None:
        calls.append({"app": app, **kwargs})

    monkeypatch.setattr(uvicorn, "run", fake_run)
    result = gwylio(data, "serve", "--port", "8123")
    assert result.exit_code == 0, result.output
    assert "serve: http://127.0.0.1:8123/api/v1/meta" in result.stdout
    assert "no database at" in result.stderr, "it says requests answer 503 until a rebuild"
    [call] = calls
    assert isinstance(call["app"], FastAPI)
    assert (call["host"], call["port"]) == ("127.0.0.1", 8123)


def test_the_api_opens_the_settings_database_per_request(data: Path) -> None:
    settings = Settings.load(PROJECT_ROOT, {DATA_DIR_ENV_VAR: str(data)})
    with TestClient(create_app(settings, clock=CLOCK)) as client:
        missing = client.get("/api/v1/meta")
        assert missing.status_code == 503
        assert missing.json() == {
            "detail": f"no database at {settings.db_path}; run gwylio rebuild"
        }
        assert not settings.db_path.exists(), "a request never creates the database"
        assert gwylio(data, "rebuild").exit_code == 0
        meta = client.get("/api/v1/meta")
        assert meta.status_code == 200
        assert meta.json()["counts"]["runs"] == 4
        assert client.get("/api/v1/reports/phosphate-welsh-rivers-2026").status_code == 200


def test_an_unmigrated_database_answers_503(tmp_path: Path) -> None:
    settings = Settings.load(PROJECT_ROOT, {DATA_DIR_ENV_VAR: str(tmp_path)})
    Database.open(settings.db_path).close()
    with TestClient(create_app(settings, clock=CLOCK)) as client:
        response = client.get("/api/v1/datecheck")
    assert response.status_code == 503
    assert "needs gwylio migrate" in response.json()["detail"]


def test_the_served_openapi_document_is_the_committed_one(client: TestClient) -> None:
    committed = json.loads((PROJECT_ROOT / OPENAPI_PATH).read_text(encoding="utf-8"))
    committed["info"].pop("x-generated")
    assert client.get("/api/v1/openapi.json").json() == committed
    assert client.get("/api/v1/docs").status_code == 200


def test_collect_hits_needs_the_fake_collectors_and_an_existing_file(
    data: Path, tmp_path: Path
) -> None:
    hits = PROJECT_ROOT / "backend" / "tests" / "fixtures" / "seed_hits.json"
    real = gwylio(data, "collect", "--hits", str(hits))
    assert real.exit_code == 2
    assert "--hits goes with --fake or --dry-run" in real.stderr
    missing = gwylio(data, "collect", "--fake", "--hits", str(tmp_path / "none.json"))
    assert missing.exit_code == 2
    assert "no scripted hits file at" in missing.stderr
    out = tmp_path / "c.json"
    dry = gwylio(data, "collect", "--dry-run", "--hits", str(hits), "--out", str(out))
    assert dry.exit_code == 0, dry.output
    funnel = json.loads(out.read_text(encoding="utf-8"))["funnel"]
    assert (funnel["raw"], funnel["dropped_negative"], funnel["unique"]) == (13, 1, 12)
