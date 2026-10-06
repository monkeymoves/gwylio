"""The gwylio.candidates/1 contract: consistency rules and deterministic text."""

from __future__ import annotations

import json
import re
from typing import Any

import pytest
from pydantic import ValidationError

from gwylio.processing.candidates_file import (
    CANDIDATES_FORMAT,
    CandidatesFile,
    dumps_candidates,
    loads_candidates,
)

RUN = "20261006T0215Z-3f9a"
EARLIER = "20260901T0900Z-aaaa"


def candidate(cid: str, url: str, status: str = "new", first_seen: str = RUN) -> dict[str, Any]:
    return {
        "candidate_id": cid,
        "status": status,
        "url": f"https://www.{url}?utm_source=x",
        "canonical_url": url,
        "title": "A title",
        "snippet": "",
        "published_on": "2026-09-30",
        "first_seen_run_id": first_seen,
        "source_id": None,
        "lane": "welsh-government",
        "discipline": "osint_web",
        "query_id": "q1",
        "requirement_hints": ["si1"],
        "topic_hints": [],
        "trusted": False,
    }


def sighting(sid: str, cid: str) -> dict[str, Any]:
    return {
        "sighting_id": sid,
        "candidate_id": cid,
        "source_id": None,
        "query_id": "q1",
        "discipline": "osint_web",
    }


def document() -> dict[str, Any]:
    return {
        "format": CANDIDATES_FORMAT,
        "run_id": RUN,
        "instrument_version": "2026.10.0",
        "instrument_hash": "sha256:" + "a" * 64,
        "generated_at": "2026-10-06T02:16:00Z",
        "started_at": "2026-10-06T02:15:42Z",
        "finished_at": "2026-10-06T02:16:00Z",
        "disciplines_run": ["osint_web"],
        "max_requests_per_run": 150,
        "requests_made": 3,
        "budget_exhausted": False,
        "funnel": {
            "raw": 6,
            "dropped_own": 1,
            "dropped_negative": 1,
            "dropped_unrelated": 0,
            "passed": 4,
            "unique": 3,
            "seen_before": 1,
            "new": 1,
            "reinforcements": 1,
        },
        "notes": [],
        "warnings": [],
        "candidates": [
            candidate("c-b", "gov.wales/b", "seen_before", EARLIER),
            candidate("c-a", "gov.wales/a"),
            candidate("c-c", "gov.wales/c", "reinforcement"),
        ],
        "reinforcements": [{"candidate_id": "c-c", "report_id": "r-1", "matched_by": "url"}],
        "sightings": [
            sighting("s-3", "c-b"),
            sighting("s-1", "c-a"),
            sighting("s-2", "c-a"),
            sighting("s-4", "c-c"),
        ],
    }


def test_a_consistent_document_parses() -> None:
    parsed = CandidatesFile.model_validate(document())
    assert parsed.problems() == []


def test_dumps_is_normalised_and_round_trips() -> None:
    parsed = CandidatesFile.model_validate(document())
    text = dumps_candidates(parsed)
    data = json.loads(text)
    assert [c["canonical_url"] for c in data["candidates"]] == [
        "gov.wales/a",
        "gov.wales/b",
        "gov.wales/c",
    ]
    assert [s["sighting_id"] for s in data["sightings"]] == ["s-1", "s-2", "s-3", "s-4"]
    assert list(data)[:2] == ["format", "run_id"]
    assert text.endswith("}\n")
    assert loads_candidates(text) == parsed.normalised()
    assert dumps_candidates(loads_candidates(text)) == text


def broken(change: str) -> dict[str, Any]:
    doc = document()
    if change == "funnel raw":
        doc["funnel"]["raw"] = 7
    elif change == "funnel unique":
        doc["funnel"]["new"] = 2
    elif change == "unknown reinforced":
        doc["reinforcements"].append({"candidate_id": "c-z", "report_id": "r", "matched_by": "url"})
    elif change == "status":
        doc["candidates"][1]["status"] = "reinforcement"
    elif change == "seen in this run":
        doc["candidates"][0]["first_seen_run_id"] = RUN
    elif change == "new from earlier":
        doc["candidates"][1]["first_seen_run_id"] = EARLIER
    elif change == "no sightings":
        doc["sightings"] = [s for s in doc["sightings"] if s["candidate_id"] != "c-b"]
    elif change == "duplicate url":
        doc["candidates"][1]["canonical_url"] = "gov.wales/b"
        doc["candidates"][1]["url"] = "https://gov.wales/b"
    elif change == "not canonical":
        doc["candidates"][1]["canonical_url"] = "www.gov.wales/a"
    elif change == "url mismatch":
        doc["candidates"][1]["url"] = "https://gov.wales/z"
    elif change == "time":
        doc["finished_at"] = "2026-10-06T02:00:00Z"
    elif change == "naive time":
        doc["started_at"] = "2026-10-06T02:15:42"
    elif change == "dash":
        doc["candidates"][1]["title"] = "A " + chr(0x2014) + " title"
    elif change == "format":
        doc["format"] = "gwylio.candidates/2"
    elif change == "extra key":
        doc["score"] = 5
    return doc


@pytest.mark.parametrize(
    ("change", "fragment"),
    [
        ("funnel raw", "funnel raw 7"),
        ("funnel unique", "funnel unique 3 != new 2"),
        ("unknown reinforced", "unknown candidate c-z"),
        ("status", "has status reinforcement but reinforced=False"),
        ("seen in this run", "seen_before but was first seen in this run"),
        ("new from earlier", "is new but was first seen"),
        ("no sightings", "has no sightings"),
        ("duplicate url", "appears 2 times"),
        ("not canonical", "not in canonical form"),
        ("url mismatch", "does not canonicalise"),
        ("time", "finished_at is before started_at"),
        ("naive time", "timezone"),
        ("dash", "U+2014 EM DASH"),
        ("format", "gwylio.candidates/1"),
        ("extra key", "Extra inputs are not permitted"),
    ],
)
def test_inconsistent_documents_are_refused(change: str, fragment: str) -> None:
    with pytest.raises(ValidationError, match=re.escape(fragment)):
        CandidatesFile.model_validate(broken(change))


def aborted_document() -> dict[str, Any]:
    doc = document()
    doc["run_status"] = "aborted"
    doc["funnel"] = {name: 0 for name in doc["funnel"]} | {"raw": 6}
    doc["notes"] = ["aborted: ConnectionError: network down"]
    doc["candidates"] = []
    doc["reinforcements"] = []
    doc["sightings"] = []
    return doc


def test_a_complete_run_is_the_default_status() -> None:
    assert CandidatesFile.model_validate(document()).run_status == "complete"


def test_an_aborted_run_keeps_only_its_raw_count_and_a_note() -> None:
    parsed = CandidatesFile.model_validate(aborted_document())
    assert parsed.run_status == "aborted"
    assert parsed.funnel.raw == 6
    assert json.loads(dumps_candidates(parsed))["run_status"] == "aborted"


@pytest.mark.parametrize(
    ("change", "fragment"),
    [
        ("candidates", "an aborted run keeps no candidates"),
        ("funnel", "counts only raw hits, but passed is set"),
        ("notes", "needs a note saying why it stopped"),
        ("status", "Input should be 'complete' or 'aborted'"),
    ],
)
def test_an_aborted_run_that_kept_something_is_refused(change: str, fragment: str) -> None:
    doc = aborted_document()
    if change == "candidates":
        doc["candidates"] = [candidate("c-a", "gov.wales/a")]
        doc["sightings"] = [sighting("s-1", "c-a")]
    elif change == "funnel":
        doc["funnel"]["passed"] = 1
    elif change == "notes":
        doc["notes"] = []
    elif change == "status":
        doc["run_status"] = "running"
    with pytest.raises(ValidationError, match=re.escape(fragment)):
        CandidatesFile.model_validate(doc)
