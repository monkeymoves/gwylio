"""Write a run's candidates file, read it back, and rebuild the run from it."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gwylio.collection.service import RunResult
from gwylio.infrastructure.config.loaders import LoadedConfig
from gwylio.infrastructure.handoff.candidates_file import (
    CandidatesFileError,
    candidates_document,
    read_candidates_file,
    result_from_document,
    write_candidates_file,
)
from gwylio.infrastructure.memory import MemoryCandidateRepository, StaticKnownReports
from gwylio.processing.candidates_file import dumps_candidates
from tests.support import ALL, earlier_candidate, scan

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def result(shipped_config: LoadedConfig) -> RunResult:
    repository = MemoryCandidateRepository()
    repository.add_candidates([earlier_candidate()])
    known = StaticKnownReports(
        by_url={"nation.cymru/news/drought-declared-across-south-west-wales": "drought-2026"}
    )
    return scan(shipped_config, ALL, repository, known)


def test_write_then_read_round_trips(result: RunResult, tmp_path: Path) -> None:
    path = write_candidates_file(result, tmp_path / "data" / "candidates" / f"{result.run.id}.json")
    document = read_candidates_file(path)
    assert document == candidates_document(result)
    assert document.run_id == result.run.id
    assert [c.canonical_url for c in document.candidates] == sorted(
        c.canonical_url.value for c in result.candidates
    )
    rebuilt = result_from_document(document)
    assert rebuilt.run == result.run
    assert sorted(rebuilt.candidates, key=lambda c: c.id) == sorted(
        result.candidates, key=lambda c: c.id
    )
    assert sorted(rebuilt.sightings, key=lambda s: s.id) == sorted(
        result.sightings, key=lambda s: s.id
    )
    assert rebuilt.reinforcements == result.reinforcements
    assert rebuilt.warnings == result.warnings
    assert dumps_candidates(candidates_document(rebuilt)) == path.read_text(encoding="utf-8")


def test_the_file_states_every_status(result: RunResult, tmp_path: Path) -> None:
    path = write_candidates_file(result, tmp_path / "c.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert {c["status"] for c in data["candidates"]} == {"new", "seen_before", "reinforcement"}
    assert data["budget_exhausted"] is True
    assert data["requests_made"] == 150
    assert data["max_requests_per_run"] == 150
    assert len(data["notes"]) == 1


def test_an_existing_file_is_never_replaced_unless_asked(result: RunResult, tmp_path: Path) -> None:
    path = write_candidates_file(result, tmp_path / "c.json")
    with pytest.raises(CandidatesFileError, match="never replaced"):
        write_candidates_file(result, path)
    write_candidates_file(result, path, overwrite=True)


def test_reading_a_broken_file_names_the_problem(result: RunResult, tmp_path: Path) -> None:
    path = write_candidates_file(result, tmp_path / "c.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["funnel"]["passed"] += 1
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(CandidatesFileError, match=r"not a valid candidates file: .*funnel raw"):
        read_candidates_file(path)
    with pytest.raises(CandidatesFileError, match="cannot read"):
        read_candidates_file(tmp_path / "missing.json")
