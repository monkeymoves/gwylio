"""``GET /api/v1/reports`` filters on the seed: each alone, two combined, the text search.

The expected ids are written out by hand from the seed's submissions
(``backend/tests/fixtures/seed_submissions``), not computed by the code
under test.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from gwylio.api.schemas import ReportSummary
from gwylio.infrastructure.readmodels import ReadModels, ReportFilter, filter_reports
from gwylio.shared.vocabulary import Direction

pytestmark = pytest.mark.integration

ALL = [
    "avian-influenza-seabirds-2026",
    "ccc-progress-report-2026",
    "domestic-solid-fuel-burning-emissions",
    "nature-recovery-bill-consultation",
    "nrw-funding-and-capacity-2026",
    "phosphate-welsh-rivers-2026",
    "river-action-judicial-review-permission",
    "south-west-wales-drought-2026",
    "storm-claudia-monmouthshire-flooding",
    "sustainable-farming-scheme-concerns",
]


def ids(client: TestClient, query: str) -> list[str]:
    response = client.get(f"/api/v1/reports{query}")
    assert response.status_code == 200, response.text
    return [report["id"] for report in response.json()]


def test_no_filter_lists_every_report_by_id(client: TestClient) -> None:
    assert ids(client, "") == ALL


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("?set=nrw-corporate-plan", ALL),
        ("?set=another-set", []),
        (
            "?requirement=si4",
            [
                "nrw-funding-and-capacity-2026",
                "phosphate-welsh-rivers-2026",
                "river-action-judicial-review-permission",
            ],
        ),
        (
            "?direction=supports",
            ["domestic-solid-fuel-burning-emissions", "nature-recovery-bill-consultation"],
        ),
        ("?direction=informs_baseline", ["ccc-progress-report-2026"]),
        (
            "?state=tracking",
            [
                "avian-influenza-seabirds-2026",
                "domestic-solid-fuel-burning-emissions",
                "nature-recovery-bill-consultation",
                "nrw-funding-and-capacity-2026",
                "river-action-judicial-review-permission",
            ],
        ),
        ("?state=faded", ["storm-claudia-monmouthshire-flooding"]),
        (
            "?bucket=brief",
            [
                "nrw-funding-and-capacity-2026",
                "phosphate-welsh-rivers-2026",
                "south-west-wales-drought-2026",
            ],
        ),
        (
            "?lane=independent-media",
            [
                "phosphate-welsh-rivers-2026",
                "south-west-wales-drought-2026",
                "storm-claudia-monmouthshire-flooding",
            ],
        ),
        (
            "?hazard=agricultural-pollution",
            ["phosphate-welsh-rivers-2026", "river-action-judicial-review-permission"],
        ),
        ("?place=south-east-wales", ["storm-claudia-monmouthshire-flooding"]),
        ("?place=wales", ALL),
        (
            "?topic=pollution-water-and-land",
            ["phosphate-welsh-rivers-2026", "river-action-judicial-review-permission"],
        ),
        ("?since=2026-10-05", ["storm-claudia-monmouthshire-flooding"]),
        ("?since=2026-10-04", ALL),
        (
            "?reliability=B",
            [
                "ccc-progress-report-2026",
                "domestic-solid-fuel-burning-emissions",
                "nature-recovery-bill-consultation",
                "nrw-funding-and-capacity-2026",
                "phosphate-welsh-rivers-2026",
                "storm-claudia-monmouthshire-flooding",
            ],
        ),
        ("?credibility=1", ["ccc-progress-report-2026", "nature-recovery-bill-consultation"]),
    ],
)
def test_each_filter_alone(client: TestClient, query: str, expected: list[str]) -> None:
    assert ids(client, query) == expected


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        (
            "?requirement=si4&direction=threatens",
            [
                "nrw-funding-and-capacity-2026",
                "phosphate-welsh-rivers-2026",
                "river-action-judicial-review-permission",
            ],
        ),
        # The direction applies to the named requirement's own assessment: the funding
        # report threatens SI1 too, but only the Nature Recovery Bill supports SI1.
        ("?requirement=si1&direction=supports", ["nature-recovery-bill-consultation"]),
        ("?requirement=si6&direction=neutral", ["sustainable-farming-scheme-concerns"]),
        ("?requirement=si6&direction=supports", []),
        (
            "?state=reinforced&bucket=brief",
            ["phosphate-welsh-rivers-2026", "south-west-wales-drought-2026"],
        ),
        ("?lane=independent-media&state=faded", ["storm-claudia-monmouthshire-flooding"]),
        (
            "?hazard=agricultural-pollution&credibility=2",
            ["river-action-judicial-review-permission"],
        ),
    ],
)
def test_two_filters_combined(client: TestClient, query: str, expected: list[str]) -> None:
    assert ids(client, query) == expected


@pytest.mark.parametrize(
    ("q", "expected"),
    [
        ("drought", ["south-west-wales-drought-2026"]),
        ("POULTRY", ["river-action-judicial-review-permission"]),
        ("  welsh   rivers ", ["phosphate-welsh-rivers-2026"]),
        ("no such words anywhere", []),
        ("", ALL),
    ],
)
def test_q_searches_title_and_summary_ignoring_case(
    client: TestClient, q: str, expected: list[str]
) -> None:
    response = client.get("/api/v1/reports", params={"q": q})
    assert [report["id"] for report in response.json()] == expected


@pytest.mark.parametrize(
    "query", ["?direction=sideways", "?state=asleep", "?since=yesterday", "?credibility=9"]
)
def test_a_value_outside_the_vocabulary_is_refused(client: TestClient, query: str) -> None:
    response = client.get(f"/api/v1/reports{query}")
    assert response.status_code == 422
    assert "detail" in response.json()


def test_the_filter_function_is_what_the_api_applies(models: ReadModels) -> None:
    summaries: list[ReportSummary] = models.reports()
    chosen = ReportFilter(requirement="si1", direction=Direction.THREATENS)
    assert [r.id for r in filter_reports(summaries, chosen)] == [
        "avian-influenza-seabirds-2026",
        "nrw-funding-and-capacity-2026",
        "south-west-wales-drought-2026",
    ]
    assert models.reports(chosen) == filter_reports(summaries, chosen)
