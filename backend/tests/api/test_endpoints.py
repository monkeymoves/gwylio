"""Every read API endpoint on the seed, pinned with syrupy snapshots, plus 404s and CORS.

The snapshots under ``__snapshots__/test_endpoints/`` are the API's contract
with the front end: a change to a read model shows up as a diff there. To
accept an intended change, run ``uv run --directory backend pytest
tests/api --snapshot-update`` and review the diff.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from syrupy.assertion import SnapshotAssertion
from syrupy.extensions.json import JSONSnapshotExtension

from tests.api.conftest import SET_ID

pytestmark = pytest.mark.integration

ENDPOINTS = {
    "meta": "/api/v1/meta",
    "meta_enums": "/api/v1/meta/enums",
    "requirement_sets": "/api/v1/requirement-sets",
    "requirement_set": f"/api/v1/requirement-sets/{SET_ID}",
    "picture": f"/api/v1/requirement-sets/{SET_ID}/picture",
    "reports": "/api/v1/reports",
    "report_reinforced_by_three_sources": "/api/v1/reports/phosphate-welsh-rivers-2026",
    "report_faded": "/api/v1/reports/storm-claudia-monmouthshire-flooding",
    "report_matured": "/api/v1/reports/ccc-progress-report-2026",
    "report_passed_horizon": "/api/v1/reports/nature-recovery-bill-consultation",
    "sources": "/api/v1/sources",
    "sources_health": "/api/v1/sources/health",
    "source_yield": "/api/v1/sources/audit-wales/yield",
    "scan_runs": "/api/v1/scan-runs",
    "scan_run_first": "/api/v1/scan-runs/20260901T0900Z-0000",
    "scan_run_judged": "/api/v1/scan-runs/20261003T0900Z-0000",
    "scan_run_unjudged": "/api/v1/scan-runs/20261004T0900Z-0000",
    "coverage": f"/api/v1/coverage/{SET_ID}",
    "datecheck": "/api/v1/datecheck",
    "products": "/api/v1/products",
    "product_operational": "/api/v1/products/operational-2026-10",
    "product_strategic": "/api/v1/products/strategic-2026",
}


@pytest.fixture
def json_snapshot(snapshot: SnapshotAssertion) -> SnapshotAssertion:
    return snapshot.use_extension(JSONSnapshotExtension)


@pytest.mark.parametrize("path", list(ENDPOINTS.values()), ids=list(ENDPOINTS))
def test_endpoint_matches_its_snapshot(
    client: TestClient, json_snapshot: SnapshotAssertion, path: str
) -> None:
    response = client.get(path)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    assert response.json() == json_snapshot


def test_the_openapi_document_lists_exactly_the_planned_routes(client: TestClient) -> None:
    documented = set(client.get("/api/v1/openapi.json").json()["paths"])
    patterns = {
        "/api/v1/meta",
        "/api/v1/meta/enums",
        "/api/v1/requirement-sets",
        "/api/v1/requirement-sets/{set_id}",
        "/api/v1/requirement-sets/{set_id}/picture",
        "/api/v1/reports",
        "/api/v1/reports/{report_id}",
        "/api/v1/sources",
        "/api/v1/sources/health",
        "/api/v1/sources/{source_id}/yield",
        "/api/v1/scan-runs",
        "/api/v1/scan-runs/{run_id}",
        "/api/v1/coverage/{set_id}",
        "/api/v1/datecheck",
        "/api/v1/products",
        "/api/v1/products/{product_id}",
    }
    assert documented == patterns


def test_the_picture_shows_the_blind_spot_and_the_quiet_requirement(client: TestClient) -> None:
    picture = client.get(f"/api/v1/requirement-sets/{SET_ID}/picture").json()
    tiles = {tile["code"]: tile for tile in picture["requirements"]}
    assert tiles["SI12"]["status"] == "blind_spot"
    assert tiles["SI12"]["scanability"] == "none"
    assert tiles["SI3"]["status"] == "quiet"
    assert tiles["SI4"]["status"] == "covered"
    assert tiles["SI4"]["active"] == 3
    assert sum(tiles["SI4"]["directions"].values()) == tiles["SI4"]["active"]
    assert tiles["SI8"]["states"]["faded"] == 1
    assert picture["datecheck"]["passed_horizon"] == 1
    assert [g["group_id"] for g in picture["wbo_groups"]] == [
        "nature-recovering",
        "communities-resilient-climate",
        "pollution-minimised",
    ]


def test_a_report_seen_by_three_sources_shows_them(client: TestClient) -> None:
    report = client.get("/api/v1/reports/phosphate-welsh-rivers-2026").json()
    assert report["state"] == "reinforced"
    assert report["distinct_sources"] == 3
    sources = {s["source_id"] for s in report["sightings"]} - {None}
    assert sources == {"dwr-cymru-welsh-water", "surfers-against-sewage", "wildlife-trusts-wales"}
    assert report["grading"] == "B3"
    assert report["cited_in"] == ["operational-2026-10", "strategic-2026"]


@pytest.mark.parametrize(
    ("path", "detail"),
    [
        ("/api/v1/reports/no-such-report", "no report 'no-such-report'"),
        ("/api/v1/scan-runs/20990101T0000Z-0000", "no scan run '20990101T0000Z-0000'"),
        ("/api/v1/products/no-such-product", "no product 'no-such-product'"),
        ("/api/v1/requirement-sets/nope", "no requirement set 'nope'"),
        ("/api/v1/requirement-sets/nope/picture", "no requirement set 'nope'"),
        ("/api/v1/coverage/nope", "no requirement set 'nope'"),
        ("/api/v1/sources/nope/yield", "no source 'nope'"),
        ("/api/v1/nothing-here", "Not Found"),
    ],
)
def test_unknown_ids_answer_404_with_a_json_body(
    client: TestClient, path: str, detail: str
) -> None:
    response = client.get(path)
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"detail": detail}


def test_the_api_is_read_only(client: TestClient) -> None:
    assert client.post("/api/v1/reports", json={}).status_code == 405
    assert client.delete("/api/v1/reports/phosphate-welsh-rivers-2026").status_code == 405


def test_cors_allows_the_vite_dev_origin(client: TestClient) -> None:
    response = client.get("/api/v1/meta", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    other = client.get("/api/v1/meta", headers={"Origin": "https://example.org"})
    assert "access-control-allow-origin" not in other.headers
