"""coverage_status as a full table: the single home of the blind spot rule."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from gwylio.direction.model import Scanability
from gwylio.direction.scanability import CoverageStatus, coverage_status

H, M, L, N = Scanability.HIGH, Scanability.MEDIUM, Scanability.LOW, Scanability.NONE
COVERED, THIN = CoverageStatus.COVERED, CoverageStatus.THIN
QUIET, BLIND = CoverageStatus.QUIET, CoverageStatus.BLIND_SPOT

TABLE = [
    (H, 0, QUIET),
    (M, 0, QUIET),
    (L, 0, BLIND),
    (N, 0, BLIND),
    (H, 1, THIN),
    (M, 1, THIN),
    (L, 1, THIN),
    (N, 1, THIN),
    (H, 2, THIN),
    (M, 2, THIN),
    (L, 2, THIN),
    (N, 2, THIN),
    (H, 3, COVERED),
    (M, 3, COVERED),
    (L, 3, COVERED),
    (N, 3, COVERED),
    (H, 40, COVERED),
    (N, 40, COVERED),
]


@pytest.mark.parametrize(("scanability", "count", "expected"), TABLE)
def test_coverage_status_table(
    scanability: Scanability, count: int, expected: CoverageStatus
) -> None:
    assert coverage_status(scanability, count) is expected


def test_the_table_covers_every_scanability_at_every_boundary() -> None:
    seen = {(s, c) for s, c, _ in TABLE}
    assert {(s, c) for s in Scanability for c in (0, 1, 2, 3)} <= seen


@given(st.sampled_from(list(Scanability)), st.integers(min_value=0, max_value=10_000))
def test_a_blind_spot_is_never_quiet(scanability: Scanability, count: int) -> None:
    status = coverage_status(scanability, count)
    if scanability in (Scanability.LOW, Scanability.NONE):
        assert status is not CoverageStatus.QUIET
    else:
        assert status is not CoverageStatus.BLIND_SPOT


@given(st.sampled_from(list(Scanability)), st.integers(min_value=1, max_value=10_000))
def test_any_report_means_the_requirement_is_not_silent(
    scanability: Scanability, count: int
) -> None:
    assert coverage_status(scanability, count) in (THIN, COVERED)


def test_negative_count_is_refused() -> None:
    with pytest.raises(ValueError, match="negative"):
        coverage_status(H, -1)


@pytest.mark.parametrize("count", [True, 1.0, "1"])
def test_non_integer_count_is_refused(count: object) -> None:
    with pytest.raises(TypeError):
        coverage_status(H, count)  # type: ignore[arg-type]


def test_coverage_status_values_and_meanings() -> None:
    assert [c.value for c in CoverageStatus] == ["covered", "thin", "quiet", "blind_spot"]
    assert "never call it quiet" in CoverageStatus.BLIND_SPOT.meaning
