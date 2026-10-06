"""Deduplication by canonical URL, and matching drafts against what is known."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from gwylio.collection.dedup import (
    CandidateDraft,
    SeenIndex,
    group_hits,
    match_known,
    normalise_title,
)
from gwylio.collection.model import CandidateStatus, MatchedBy
from gwylio.infrastructure.memory import NullKnownReports, StaticKnownReports
from gwylio.shared.values import CanonicalUrl, RunId
from tests.support import hit

EARLIER = RunId("20260901T0900Z-aaaa")


def test_tracking_parameters_and_www_collapse_to_one_candidate_with_two_sightings() -> None:
    drafts = group_hits(
        [
            hit("https://www.gov.wales/nature-bill?utm_source=newsletter", "Nature Bill"),
            hit("https://gov.wales/nature-bill", "Nature Bill | GOV.WALES", query_id="q2"),
        ]
    )
    [draft] = drafts
    assert draft.canonical_url.value == "gov.wales/nature-bill"
    assert len(draft.hits) == 2
    assert draft.title == "Nature Bill"
    assert draft.url == "https://www.gov.wales/nature-bill?utm_source=newsletter"


def test_senedd_urls_differing_by_query_id_stay_separate() -> None:
    drafts = group_hits(
        [
            hit("https://business.senedd.wales/mgIssueHistoryHome.aspx?IId=45001"),
            hit("https://business.senedd.wales/mgIssueHistoryHome.aspx?IId=45002"),
        ]
    )
    assert [d.canonical_url.value for d in drafts] == [
        "business.senedd.wales/mgIssueHistoryHome.aspx?IId=45001",
        "business.senedd.wales/mgIssueHistoryHome.aspx?IId=45002",
    ]


def test_identical_titles_with_different_urls_stay_separate() -> None:
    title = "Consultation display | Senedd"
    drafts = group_hits(
        [hit("https://senedd.wales/a", title), hit("https://senedd.wales/b", title)]
    )
    assert len(drafts) == 2


def test_draft_keeps_longest_snippet_and_earliest_date() -> None:
    [draft] = group_hits(
        [
            hit("https://gov.wales/a", "First", snippet="short", published_on="2026-09-30"),
            hit("https://gov.wales/a", "Second", snippet="a much longer snippet"),
            hit(
                "https://gov.wales/a",
                "Third",
                snippet="equal length snippet!",
                published_on="2026-09-28",
            ),
        ]
    )
    assert draft.title == "First"
    assert draft.snippet == "a much longer snippet"
    assert str(draft.published_on) == "2026-09-28"


def test_draft_without_dates_has_no_date_and_needs_a_hit() -> None:
    [draft] = group_hits([hit("https://gov.wales/a")])
    assert draft.published_on is None
    with pytest.raises(ValueError, match="at least one hit"):
        CandidateDraft(CanonicalUrl("gov.wales/a"), ())
    with pytest.raises(ValueError, match="share its canonical URL"):
        CandidateDraft(CanonicalUrl("gov.wales/a"), (hit("https://gov.wales/b"),))


def test_drafts_keep_first_found_order() -> None:
    drafts = group_hits(
        [hit("https://b.wales/1"), hit("https://a.wales/1"), hit("https://b.wales/1")]
    )
    assert [d.canonical_url.value for d in drafts] == ["b.wales/1", "a.wales/1"]


def test_normalise_title() -> None:
    assert normalise_title("  Drought   Declared\nin WALES ") == "drought declared in wales"


def _drafts() -> list[CandidateDraft]:
    return group_hits(
        [
            hit("https://nation.cymru/drought", "Drought declared"),
            hit("https://walesonline.co.uk/budget", "NRW faces budget cuts"),
            hit("https://gov.wales/survey", "National Survey for Wales"),
            hit("https://bbc.co.uk/new", "Something new in Wales"),
        ]
    )


def test_match_known_marks_reinforcement_seen_before_and_new() -> None:
    known = StaticKnownReports(
        by_url={"https://www.nation.cymru/drought/": "drought-2026"},
        by_title={"NRW  faces budget CUTS": "nrw-budget"},
    )
    seen = SeenIndex({"gov.wales/survey": EARLIER, "nation.cymru/drought": EARLIER})
    matches = match_known(_drafts(), seen, known)
    assert [(m.status, m.report_id, m.matched_by) for m in matches] == [
        (CandidateStatus.REINFORCEMENT, "drought-2026", MatchedBy.URL),
        (CandidateStatus.REINFORCEMENT, "nrw-budget", MatchedBy.TITLE),
        (CandidateStatus.SEEN_BEFORE, None, None),
        (CandidateStatus.NEW, None, None),
    ]
    assert [m.first_seen_run_id for m in matches] == [EARLIER, None, EARLIER, None]
    assert len(seen) == 2


def test_url_match_beats_title_match() -> None:
    known = StaticKnownReports(
        by_url={"nation.cymru/drought": "by-url"}, by_title={"Drought declared": "by-title"}
    )
    [first, *_] = match_known(_drafts(), SeenIndex(), known)
    assert (first.report_id, first.matched_by) == ("by-url", MatchedBy.URL)


def test_title_match_only_when_the_url_matches_no_report() -> None:
    known = StaticKnownReports(
        by_url={"nation.cymru/other": "other"}, by_title={"Drought declared": "t"}
    )
    [first, *_] = match_known(_drafts(), SeenIndex(), known)
    assert (first.report_id, first.matched_by) == ("t", MatchedBy.TITLE)


def test_a_report_less_index_yields_new() -> None:
    matches = match_known(_drafts(), SeenIndex(), NullKnownReports())
    assert {m.status for m in matches} == {CandidateStatus.NEW}


URLS = st.sampled_from(
    [
        "https://gov.wales/a",
        "https://www.gov.wales/a/",
        "https://gov.wales/a?utm_source=x",
        "https://gov.wales/a?id=1",
        "https://gov.wales/b",
        "https://senedd.wales/a#top",
    ]
)


@given(st.lists(URLS, max_size=12))
def test_grouping_keeps_every_hit_and_one_draft_per_canonical_url(urls: list[str]) -> None:
    drafts = group_hits(hit(url, "Same title") for url in urls)
    assert sum(len(d.hits) for d in drafts) == len(urls)
    canonical = [d.canonical_url for d in drafts]
    assert len(set(canonical)) == len(canonical)
    assert set(canonical) == {CanonicalUrl(url) for url in urls}
