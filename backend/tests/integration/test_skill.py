"""The analyst skill (``skill/SKILL.md``) names real verbs and ships a valid submission skeleton.

The skill is the analyst's half of the system, so it must not drift from the
command line or the submission contract: every ``gwylio <verb>`` it names in
code must exist on the Typer app, every verb on the app must be named at
least once, and the JSON skeleton must parse as ``gwylio.submission/1`` and
validate against the shipped configuration's ids.
"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from gwylio.cli.main import cli_verbs
from gwylio.infrastructure.config.loaders import LoadedConfig
from gwylio.processing.submission import (
    RUBRIC_VERSION,
    SUBMISSION_FORMAT,
    RunCandidate,
    SubmissionContext,
    parse_submission,
    validate_submission,
)
from gwylio.shared.vocabulary import CandidateStatus
from tests.support import PROJECT_ROOT

pytestmark = pytest.mark.integration

SKILL = PROJECT_ROOT / "skill" / "SKILL.md"
FENCE = re.compile(r"^```([a-z]*)\n(.*?)^```", re.MULTILINE | re.DOTALL)
INLINE = re.compile(r"`([^`\n]+)`")
VERB = re.compile(r"(?:^|[\s(])gwylio\s+([a-z][a-z-]*)")


def skill_text() -> str:
    return SKILL.read_text(encoding="utf-8")


def code_in(text: str) -> list[str]:
    """Every fenced block and inline code span in ``text``."""
    blocks = [match.group(2) for match in FENCE.finditer(text)]
    prose = FENCE.sub("", text)
    return blocks + INLINE.findall(prose)


def verbs_named(text: str) -> set[str]:
    return {verb for code in code_in(text) for verb in VERB.findall(code)}


def skeleton(text: str) -> str:
    blocks = [match.group(2) for match in FENCE.finditer(text) if match.group(1) == "json"]
    assert len(blocks) == 1, "the skill holds exactly one JSON block: the submission skeleton"
    return blocks[0]


def test_the_skill_has_its_frontmatter() -> None:
    text = skill_text()
    assert text.startswith("---\n")
    front = text.split("---\n")[1]
    fields = dict(line.split(": ", 1) for line in front.strip().splitlines())
    assert fields["name"] == "gwylio-scan"
    assert len(fields["description"]) > 100


def test_every_verb_the_skill_names_exists_and_every_verb_is_named() -> None:
    named = verbs_named(skill_text())
    existing = {name for name, _ in cli_verbs()}
    assert named - existing == set(), f"the skill names verbs that do not exist: {named - existing}"
    assert existing - named == set(), f"the skill never names: {existing - named}"


def test_the_verb_finder_reads_code_only() -> None:
    text = "Gwylio collects.\n\nRun `gwylio sweep`, then:\n\n```bash\nuv run gwylio publish\n```\n"
    assert verbs_named(text) == {"sweep", "publish"}
    assert verbs_named("the gwylio-scan skill, gwylio ingest in prose") == set()


def test_the_skill_names_the_cycle_in_order() -> None:
    text = skill_text()
    cycle = text[text.index("## The cycle") :]
    steps = [
        "gwylio datecheck",
        "gwylio collect",
        "gwylio ingest",
        "gwylio sweep",
        "gwylio product --level operational",
        "gwylio export",
        "gwylio publish",
    ]
    positions = [cycle.index(f"`{step}") for step in steps]
    assert positions == sorted(positions)
    assert "data/gwylio.sqlite" in text and "Never commit" in text


def test_the_skill_points_at_files_that_exist() -> None:
    text = skill_text()
    for path in ("docs/RUBRIC.md", "skill/REFERENCE.md", "config/sources.json"):
        assert path in text
        assert (PROJECT_ROOT / path).is_file(), path


def _context(document: dict[str, Any], config: LoadedConfig) -> SubmissionContext:
    links = {link["candidate_id"]: link["report_id"] for link in document["reinforcements"]}
    candidates = {
        d["candidate_id"]: RunCandidate(
            d["candidate_id"],
            CandidateStatus.REINFORCEMENT if d["candidate_id"] in links else CandidateStatus.NEW,
            f"example.org/{d['candidate_id']}",
            links.get(d["candidate_id"]),
        )
        for d in document["dispositions"]
    }
    existing = {u["report_id"] for u in document["updates"]} | set(links.values())
    catalogue = config.catalogue
    return SubmissionContext(
        submission_id=f"{document['run_id']}__1",
        run_candidates=candidates,
        report_ids=frozenset(existing),
        requirement_ids=frozenset(
            r for rs in config.requirement_sets for r in rs.requirement_ids()
        ),
        topic_ids=catalogue.topic_ids(),
        hazard_ids=catalogue.hazard_ids(),
        place_ids=catalogue.place_ids(),
        actor_ids=catalogue.actor_ids(),
        lane_ids=catalogue.lane_ids(),
        source_ids=frozenset(source.id for source in config.sources),
    )


def test_the_submission_skeleton_validates_against_the_shipped_config(
    shipped_config: LoadedConfig,
) -> None:
    text = skeleton(skill_text())
    submission, problems = parse_submission(text)
    assert problems == []
    assert submission is not None
    document = json.loads(text)
    assert document["schema"] == SUBMISSION_FORMAT
    assert document["rubric_version"] == RUBRIC_VERSION
    found = validate_submission(submission, _context(document, shipped_config))
    assert [str(problem) for problem in found] == []
    # The skeleton shows every outcome, a watched and an unwatched promotion, an update,
    # a reinforcement and a verification.
    outcomes = {d["outcome"] for d in document["dispositions"]}
    assert outcomes == {"promoted", "rejected", "duplicate", "deferred", "reinforcement"}
    assert {p["source_id"] is None for p in document["promotions"]} == {True, False}
    assert document["updates"] and document["reinforcements"] and document["verifications"]
    for guard in ("Optimism", "Mainstream", "Streetlight"):
        assert guard in document["method_note"]


def test_a_skeleton_with_an_unknown_id_is_caught(shipped_config: LoadedConfig) -> None:
    document = json.loads(skeleton(skill_text()))
    document["promotions"][0]["hazards"] = ["regulatory-legal-change"]  # a family, not a hazard
    submission, problems = parse_submission(json.dumps(document))
    assert submission is not None and problems == []
    found = validate_submission(submission, _context(document, shipped_config))
    assert [str(p) for p in found] == [
        "promotions[0].hazards[0]: unknown hazard 'regulatory-legal-change'"
    ]
