"""End to end: the shipped configuration, the scripted hits and in-memory storage.

Every expected number below was counted by hand from the notes on each hit in
``tests/fixtures/fake_hits.json``, not computed by the code under test.
"""

from __future__ import annotations

import pytest

from gwylio.collection.model import CandidateStatus, Discipline, MatchedBy, RunStatus
from gwylio.infrastructure.collectors.fake import load_fake_hits
from gwylio.infrastructure.config.loaders import LoadedConfig
from gwylio.infrastructure.memory import MemoryCandidateRepository, StaticKnownReports
from tests.support import ALL, DEFAULT, EARLIER, FAKE_HITS, earlier_candidate, scan

pytestmark = pytest.mark.integration


def test_default_disciplines_on_an_empty_register(shipped_config: LoadedConfig) -> None:
    result = scan(shipped_config, DEFAULT)
    funnel = result.run.funnel
    assert (funnel.raw, funnel.dropped_own, funnel.dropped_negative, funnel.dropped_unrelated) == (
        30,
        2,
        5,
        3,
    )
    assert (funnel.passed, funnel.unique, funnel.new) == (20, 17, 17)
    assert (funnel.seen_before, funnel.reinforcements) == (0, 0)
    assert result.run.requests_made == 148
    assert not result.run.budget_exhausted
    assert result.warnings == ()


def test_every_discipline_with_history_and_known_reports(shipped_config: LoadedConfig) -> None:
    repository = MemoryCandidateRepository()
    repository.add_candidates([earlier_candidate()])
    known = StaticKnownReports(
        by_url={
            "https://nation.cymru/news/drought-declared-across-south-west-wales/": "drought-2026"
        },
        by_title={"Natural Resources Wales faces budget cuts": "nrw-budget-pressure"},
    )
    result = scan(shipped_config, ALL, repository, known)
    run = result.run
    assert run.status is RunStatus.COMPLETE
    assert run.id == "20261006T0215Z-3f9a"

    funnel = run.funnel
    assert funnel.raw == 32
    assert (funnel.dropped_own, funnel.dropped_negative, funnel.dropped_unrelated) == (2, 5, 4)
    assert funnel.passed == 21
    assert funnel.unique == 18
    assert (funnel.new, funnel.seen_before, funnel.reinforcements) == (15, 1, 2)
    funnel.check()

    # The budget: 148 web, site and feed queries, then two of the 14 academic ones.
    assert run.requests_made == 150
    assert run.budget_exhausted
    [note] = run.notes
    assert note.startswith("request budget of 150 reached after 150 requests; 12 queries not run: ")
    assert "academic-pollution-water-land-01" in note
    assert "academic-nature-ecosystems-02" not in note

    assert len(result.sightings) == 21
    assert len(result.candidates) == 18
    by_url = {c.canonical_url.value: c for c in result.candidates}

    nature = by_url["gov.wales/nature-recovery-bill-consultation"]
    assert nature.title == "Consultation on a Nature Recovery Bill for Wales"
    assert nature.snippet.startswith("The Welsh Government is consulting")
    assert str(nature.published_on) == "2026-09-29"
    assert (nature.source_id, nature.lane, nature.trusted) == (
        "welsh-government",
        "welsh-government",
        True,
    )
    assert nature.query_id == "web-nature-ecosystems-04"
    assert nature.requirement_hints == ("si1", "si2", "si3")
    assert nature.topic_hints == ("nature-and-ecosystems", "woodland-and-forestry")
    assert sum(s.candidate_id == nature.id for s in result.sightings) == 2

    river_action = by_url[
        "riveractionuk.com/news/judicial-review-against-natural-resources-wales-granted"
    ]
    assert river_action.title == "River Action wins permission for judicial review"
    assert river_action.lane == "legal-and-campaign"

    phosphate = by_url["bbc.co.uk/news/articles/cx2phosphate"]
    assert (phosphate.source_id, phosphate.trusted) == (None, False)

    petition = by_url["business.senedd.wales/mgIssueHistoryHome.aspx?IId=45001"]
    assert petition.lane == "senedd"
    assert "business.senedd.wales/mgIssueHistoryHome.aspx?IId=45002" in by_url

    survey = by_url["gov.wales/national-survey-wales-results-viewer"]
    assert result.status_of(survey) is CandidateStatus.SEEN_BEFORE
    assert survey.first_seen_run_id == EARLIER

    reinforced = {(r.report_id, r.matched_by) for r in result.reinforcements}
    assert reinforced == {("drought-2026", MatchedBy.URL), ("nrw-budget-pressure", MatchedBy.TITLE)}
    drought = by_url["nation.cymru/news/drought-declared-across-south-west-wales"]
    assert result.status_of(drought) is CandidateStatus.REINFORCEMENT

    academic = by_url["doi.org/10.1111/1365-2664.14567"]
    assert (academic.discipline, academic.lane) == (Discipline.OSINT_ACADEMIC, "research-evidence")


def test_every_scripted_hit_names_a_query_of_its_discipline(shipped_config: LoadedConfig) -> None:
    for raw in load_fake_hits(FAKE_HITS):
        assert shipped_config.instrument.query(raw.query_id).discipline is raw.discipline
