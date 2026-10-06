"""The submission contract and its validator: one test per rule, each naming the culprit."""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from gwylio.processing.submission import (
    RunCandidate,
    Submission,
    SubmissionContext,
    SubmissionProblem,
    dumps_submission,
    parse_submission,
    parse_update,
    validate_submission,
)
from gwylio.shared.vocabulary import Bucket, CandidateStatus

RUN = "20261006T0215Z-3f9a"


def candidates() -> dict[str, RunCandidate]:
    return {
        "c-new-1": RunCandidate("c-new-1", CandidateStatus.NEW, "gov.wales/plan"),
        "c-new-2": RunCandidate("c-new-2", CandidateStatus.NEW, "gov.wales/viewer"),
        "c-seen": RunCandidate("c-seen", CandidateStatus.SEEN_BEFORE, "gov.wales/old-page"),
        "c-reinf": RunCandidate(
            "c-reinf", CandidateStatus.REINFORCEMENT, "nation.cymru/news/old", "r-old"
        ),
    }


def context(**changes: Any) -> SubmissionContext:
    base: dict[str, Any] = {
        "submission_id": f"{RUN}__1",
        "run_candidates": candidates(),
        "report_ids": frozenset({"r-old"}),
        "report_urls": {"nation.cymru/news/old": "r-old"},
        "requirement_ids": frozenset({"si1", "si4"}),
        "topic_ids": frozenset({"water-resources"}),
        "hazard_ids": frozenset({"drought-and-low-flows"}),
        "place_ids": frozenset({"wales"}),
        "actor_ids": frozenset({"welsh-government"}),
        "lane_ids": frozenset({"welsh-government", "independent-media"}),
        "source_ids": frozenset({"welsh-government"}),
    }
    base.update(changes)
    return SubmissionContext(**base)


def valid() -> dict[str, Any]:
    return {
        "schema": "gwylio.submission/1",
        "run_id": RUN,
        "analyst": "Analyst",
        "rubric_version": "2026.10",
        "received_on": "2026-10-06",
        "dispositions": [
            {
                "candidate_id": "c-new-1",
                "outcome": "promoted",
                "reason": "Passes the promotion test.",
                "report_id": "p-1",
            },
            {"candidate_id": "c-new-2", "outcome": "rejected", "reason": "A standing viewer."},
            {
                "candidate_id": "c-reinf",
                "outcome": "reinforcement",
                "reason": "Seen again.",
                "report_id": "r-old",
            },
        ],
        "promotions": [
            {
                "id": "p-1",
                "from_candidate": "c-new-1",
                "title": "A plan",
                "url": "https://www.gov.wales/plan",
                "source_id": "welsh-government",
                "source_name": "Welsh Government",
                "report_type": "policy",
                "credibility": 2,
                "assessments": [{"requirement_id": "si1", "direction": "supports"}],
                "topics": ["water-resources"],
                "hazards": ["drought-and-low-flows"],
                "places": ["wales"],
                "scores": {
                    "evidence": "high",
                    "novelty": "medium",
                    "confidence": "high",
                    "potential_impact": "medium",
                    "time_horizon": "near_term",
                },
                "bucket": "watch",
                "summary": "The plan.",
            }
        ],
        "updates": [
            {"report_id": "r-old", "set": {"bucket": "brief"}, "change": "Raised to brief."}
        ],
        "reinforcements": [{"report_id": "r-old", "candidate_id": "c-reinf"}],
        "verifications": [{"report_id": "r-old", "verified_on": "2026-10-06", "note": "Checked."}],
        "method_note": "Read every candidate.",
    }


def check(
    document: dict[str, Any], ctx: SubmissionContext | None = None, *, allow_deferred: bool = False
) -> list[str]:
    submission, problems = parse_submission(json.dumps(document, ensure_ascii=False))
    if submission is None:
        return [str(p) for p in problems]
    found = validate_submission(submission, ctx or context(), allow_deferred=allow_deferred)
    return [str(p) for p in found]


def edited(**changes: Any) -> dict[str, Any]:
    document = valid()
    document.update(copy.deepcopy(changes))
    return document


def test_a_valid_submission_has_no_problems_and_round_trips() -> None:
    assert check(valid()) == []
    submission, _ = parse_submission(json.dumps(valid()))
    assert isinstance(submission, Submission)
    text = dumps_submission(submission)
    assert json.loads(text)["schema"] == "gwylio.submission/1"
    assert parse_submission(text)[0] == submission


def test_a_run_submission_names_a_stored_run() -> None:
    assert check(valid(), context(run_candidates=None)) == [
        f"run_id: run {RUN} is not stored; collect or rebuild first"
    ]


def test_every_new_candidate_needs_a_disposition_unless_deferred_is_allowed() -> None:
    document = valid()
    document["dispositions"] = document["dispositions"][:1] + document["dispositions"][2:]
    assert check(document) == [
        "dispositions: new candidate 'c-new-2' (gov.wales/viewer) has no disposition; give it "
        "one, or ingest with --allow-deferred"
    ]
    assert check(document, allow_deferred=True) == []


def test_a_reinforcement_candidate_needs_a_reinforcement_entry_or_a_disposition() -> None:
    document = valid()
    document["dispositions"] = document["dispositions"][:2]
    document["reinforcements"] = []
    assert check(document) == [
        "reinforcements: candidate 'c-reinf' matched report 'r-old' at collection; confirm it "
        "in reinforcements or give it a disposition, or ingest with --allow-deferred"
    ]
    document["dispositions"].append(
        {"candidate_id": "c-reinf", "outcome": "rejected", "reason": "The title match was wrong."}
    )
    assert check(document) == []


def test_seen_before_candidates_need_nothing_but_may_have_a_disposition() -> None:
    document = valid()
    document["dispositions"].append(
        {"candidate_id": "c-seen", "outcome": "rejected", "reason": "Still nothing new."}
    )
    assert check(document) == []


def test_a_candidate_has_one_disposition_from_this_run() -> None:
    document = valid()
    document["dispositions"].append(
        {"candidate_id": "c-new-2", "outcome": "deferred", "reason": "Unsure."}
    )
    document["dispositions"].append(
        {"candidate_id": "c-elsewhere", "outcome": "rejected", "reason": "Off topic."}
    )
    assert check(document) == [
        "dispositions[1].candidate_id: candidate 'c-new-2' has more than one disposition",
        "dispositions[3].candidate_id: candidate 'c-new-2' has more than one disposition",
        f"dispositions[4].candidate_id: candidate 'c-elsewhere' is not in run {RUN}",
    ]


def test_promoted_dispositions_and_promotions_name_each_other() -> None:
    document = valid()
    document["dispositions"][0]["report_id"] = "p-other"
    assert check(document) == [
        "dispositions[0].report_id: promoted candidate 'c-new-1' must name one of this file's "
        "promotions",
        "promotions[0].from_candidate: promotion 'p-1' comes from candidate 'c-new-1', which "
        "needs a promoted disposition naming report 'p-1'",
    ]
    document = valid()
    document["promotions"][0]["from_candidate"] = None
    assert check(document) == [
        "dispositions[0].report_id: promotion 'p-1' must give from_candidate 'c-new-1'"
    ]


def test_a_reinforcement_disposition_needs_a_matching_entry_and_vice_versa() -> None:
    document = valid()
    document["reinforcements"][0]["report_id"] = "p-1"
    assert check(document) == [
        "dispositions[2].report_id: reinforcement 'c-reinf' of report 'r-old' needs a matching "
        "entry in reinforcements"
    ]
    document = valid()
    document["dispositions"][2] = {
        "candidate_id": "c-reinf",
        "outcome": "duplicate",
        "reason": "Same story.",
    }
    assert check(document) == [
        "dispositions[2].outcome: candidate 'c-reinf' is linked in reinforcements, so its "
        "outcome must be reinforcement"
    ]


def test_a_candidate_disposed_of_earlier_is_not_disposed_of_again() -> None:
    ctx = context(earlier_dispositions={"c-new-2": ("x__1", "rejected")})
    assert check(valid(), ctx) == [
        "dispositions[1].candidate_id: candidate 'c-new-2' was already disposed of as rejected "
        "in submission x__1"
    ]


def test_promotion_ids_are_new_and_unique() -> None:
    document = valid()
    document["promotions"].append(
        {**document["promotions"][0], "id": "p-1", "from_candidate": None, "url": "https://x.org/a"}
    )
    document["promotions"].append(
        {
            **document["promotions"][0],
            "id": "r-old",
            "from_candidate": None,
            "url": "https://x.org/b",
        }
    )
    assert check(document) == [
        "promotions[0].id: promotion id 'p-1' is used more than once",
        "promotions[1].id: promotion id 'p-1' is used more than once",
        "promotions[2].id: report 'r-old' already exists in the register",
    ]


def test_a_promotions_url_must_not_belong_to_a_report() -> None:
    document = valid()
    document["promotions"][0]["url"] = "https://nation.cymru/news/old/?utm_source=x"
    assert check(document) == [
        "promotions[0].url: nation.cymru/news/old already belongs to report 'r-old': a new "
        "sighting of it is a reinforcement, not a promotion"
    ]


@pytest.mark.parametrize(
    ("path", "value", "expected"),
    [
        (
            ("assessments", 0, "requirement_id"),
            "si99",
            "assessments[0].requirement_id: unknown requirement 'si99'",
        ),
        (("topics", 0), "gardening", "topics[0]: unknown topic 'gardening'"),
        (("hazards", 0), "meteor", "hazards[0]: unknown hazard 'meteor'"),
        (("places", 0), "atlantis", "places[0]: unknown place 'atlantis'"),
        (("actor_id",), "nobody", "actor_id: unknown actor 'nobody'"),
        (("lane",), "nowhere", "lane: unknown lane 'nowhere'"),
        (("source_id",), "rumour-mill", "source_id: unknown source 'rumour-mill'"),
    ],
)
def test_every_catalogue_id_must_exist(path: tuple[Any, ...], value: str, expected: str) -> None:
    document = valid()
    target: Any = document["promotions"][0]
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    assert check(document) == [f"promotions[0].{expected}"]


def test_a_repeated_assessment_or_tag_is_refused() -> None:
    document = valid()
    promotion = document["promotions"][0]
    promotion["assessments"].append({"requirement_id": "si1", "direction": "threatens"})
    promotion["places"].append("wales")
    assert check(document) == [
        "promotions[0].assessments: requirement 'si1' assessed twice",
        "promotions[0].places: place 'wales' is listed twice",
    ]


@pytest.mark.parametrize("credibility", [0, 7, "B"])
def test_credibility_is_a_digit_from_one_to_six(credibility: object) -> None:
    document = valid()
    document["promotions"][0]["credibility"] = credibility
    [problem] = check(document)
    assert problem.startswith("promotions[0].credibility: ")


def test_an_unwatched_source_needs_reliability_and_lane() -> None:
    document = valid()
    document["promotions"][0]["source_id"] = None
    assert check(document) == [
        "promotions[0].reliability_if_unknown_source: promotion 'p-1' has no watched source, "
        "so reliability_if_unknown_source is required",
        "promotions[0].lane: promotion 'p-1' has no watched source, so lane is required",
    ]
    document["promotions"][0]["reliability_if_unknown_source"] = "C"
    document["promotions"][0]["lane"] = "independent-media"
    assert check(document) == []


def test_updates_name_a_report_and_set_only_the_allowed_keys() -> None:
    document = valid()
    document["updates"] = [
        {"report_id": "ghost", "set": {"bucket": "brief"}, "change": "x"},
        {
            "report_id": "r-old",
            "set": {
                "grading": "A1",
                "state": "reinforced",
                "bucket": "soon",
                "independent_confirmation": False,
                "summary": " ",
                "event_horizon": "next week",
            },
            "change": "x",
        },
    ]
    assert check(document) == [
        "updates[0].report_id: no report 'ghost' in the register",
        "updates[1].set.grading: 'grading' cannot be set by an update; settable keys are state, "
        "bucket, owner, notes, summary, title, event_horizon, independent_confirmation",
        "updates[1].set.state: state may be set to matured or parked only, not 'reinforced'; "
        "the lifecycle sets every other state",
        "updates[1].set.bucket: unknown bucket 'soon'",
        "updates[1].set.independent_confirmation: independent_confirmation can only be set to "
        "true; it is never undone",
        "updates[1].set.summary: summary must be non-empty text",
        "updates[1].set.event_horizon: not a YYYY-MM-DD date: 'next week'",
    ]


def test_parse_update_types_every_allowed_key() -> None:
    parsed, problems = parse_update(
        {
            "state": "parked",
            "bucket": "brief",
            "title": "T",
            "summary": "S",
            "notes": "",
            "owner": None,
            "event_horizon": None,
            "independent_confirmation": True,
        },
        "set",
    )
    assert problems == []
    assert parsed.state == "parked"
    assert parsed.bucket is Bucket.BRIEF
    assert (parsed.owner_given, parsed.owner) == (True, None)
    assert (parsed.event_horizon_given, parsed.event_horizon) == (True, None)
    assert parsed.independent_confirmation
    assert parse_update({"title": "a " + chr(0x2014) + " b"}, "set")[1] == [
        SubmissionProblem(
            "set.title",
            "text contains U+2014 EM DASH at index 2; use a comma, a colon or 'to' instead",
        )
    ]


def test_reinforcements_and_verifications_name_existing_reports() -> None:
    document = valid()
    document["reinforcements"].append({"report_id": "ghost", "candidate_id": "c-seen"})
    document["verifications"] = [
        {"report_id": "p-1", "verified_on": "2026-10-06", "note": "New and checked."},
        {"report_id": "ghost", "verified_on": "2026-10-07", "note": "Checked."},
    ]
    assert check(document) == [
        "reinforcements[1].report_id: no report 'ghost' in the register or this submission",
        "verifications[1].report_id: no report 'ghost' in the register",
        "verifications[1].verified_on: verified_on 2026-10-07 is after received_on 2026-10-06",
    ]


def test_a_candidate_is_linked_once_and_from_the_run() -> None:
    document = valid()
    document["reinforcements"].append({"report_id": "r-old", "candidate_id": "c-reinf"})
    document["reinforcements"].append({"report_id": "r-old", "candidate_id": "c-gone"})
    assert check(document) == [
        "reinforcements[0].candidate_id: candidate 'c-reinf' is linked more than once",
        "reinforcements[1].candidate_id: candidate 'c-reinf' is linked more than once",
        f"reinforcements[2].candidate_id: candidate 'c-gone' is not in run {RUN}",
    ]


def test_an_out_of_run_submission_has_no_candidates() -> None:
    document = valid()
    document["run_id"] = None
    assert check(document, context(run_candidates=None)) == [
        "dispositions: an out-of-run submission has no candidates to dispose of",
        "reinforcements: an out-of-run submission has no candidates to link",
        "promotions[0].from_candidate: an out-of-run submission cannot promote candidate 'c-new-1'",
    ]


def test_submissions_must_replay_in_the_order_they_are_ingested() -> None:
    ctx = context(last_ingested=("2026-10-06", f"{RUN}__2"))
    assert check(valid(), ctx) == [
        f"received_on: submissions replay in received_on then file name order, and {RUN}__2 "
        f"(received 2026-10-06) is already ingested; this one ({RUN}__1, received "
        "2026-10-06) would replay before it"
    ]
    assert check(valid(), context(last_ingested=("2026-10-05", "zzz"))) == []


def test_a_submission_is_ingested_once() -> None:
    assert check(valid(), context(already_ingested=True)) == [
        f"submission {RUN}__1 is already ingested"
    ]


def test_deferred_names_no_report_and_a_duplicate_names_a_real_one() -> None:
    document = valid()
    document["dispositions"][1] = {
        "candidate_id": "c-new-2",
        "outcome": "deferred",
        "reason": "Later.",
        "report_id": "r-old",
    }
    document["dispositions"].append(
        {"candidate_id": "c-seen", "outcome": "duplicate", "reason": "Dup.", "report_id": "ghost"}
    )
    assert check(document) == [
        "dispositions[1].report_id: deferred candidate 'c-new-2' names no report",
        "dispositions[3].report_id: no report 'ghost' in the register",
    ]


@pytest.mark.parametrize(
    ("field", "location"),
    [("summary", "promotions[0].summary"), ("title", "promotions[0].title")],
)
def test_the_dash_rule_holds_in_every_text_field(field: str, location: str) -> None:
    document = valid()
    document["promotions"][0][field] = "Plan 2026 " + chr(0x2013) + " 27"
    [problem] = check(document)
    assert problem.startswith(f"{location}: Value error, text contains U+2013 EN DASH")


def test_contract_errors_are_located() -> None:
    document = valid()
    document["schema"] = "gwylio.submission/2"
    document["promotions"][0]["report_type"] = "rumour"
    document["updates"][0]["set"] = {}
    del document["method_note"]
    document["extra"] = 1
    problems = check(document)
    assert [p.split(":")[0] for p in problems] == [
        "schema",
        "promotions[0].report_type",
        "updates[0].set",
        "method_note",
        "extra",
    ]
    assert check({"schema": 1})[0].startswith("schema: ")
    assert parse_submission("{")[1][0].location == "line 1 column 2"
