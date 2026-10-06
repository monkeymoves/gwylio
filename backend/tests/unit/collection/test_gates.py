"""The three gates, as a table over every outcome and the order of precedence."""

from __future__ import annotations

import pytest

from gwylio.collection.gates import GatingRules, gate, relevance_tokens
from gwylio.collection.model import GateOutcome, Source
from tests.support import hit, instrument, query, rules, source

TRUSTED = source("gov-wales", "gov.wales", trusted=True)
UNTRUSTED = source("openalex", "api.openalex.org", trusted=False)
QUERY = query("q1", negative_terms=("us epa",))
INSTRUMENT = instrument(QUERY, negatives=("new south wales", "jimmy wales", "epa.gov"))
OWN = "https://naturalresources.wales/news/river-update"


@pytest.mark.parametrize(
    ("url", "title", "snippet", "src", "expected"),
    [
        # Own domain beats everything, including a negative term and a trusted source.
        (OWN, "River update for Wales", "", None, GateOutcome.DROPPED_OWN),
        (OWN, "New South Wales comparison", "", TRUSTED, GateOutcome.DROPPED_OWN),
        ("https://www.cyfoethnaturiol.cymru/x", "Y", "", None, GateOutcome.DROPPED_OWN),
        ("https://news.naturalresources.wales/x", "Y", "", None, GateOutcome.DROPPED_OWN),
        # Negative terms, global then the query's own, beat relevance and trust.
        (
            "https://example.com/a",
            "Pollution in New South Wales",
            "",
            None,
            GateOutcome.DROPPED_NEGATIVE,
        ),
        ("https://gov.wales/a", "Jimmy Wales visits", "", TRUSTED, GateOutcome.DROPPED_NEGATIVE),
        ("https://www.epa.gov/a", "Welsh air", "", None, GateOutcome.DROPPED_NEGATIVE),
        (
            "https://example.com/b",
            "Welsh view",
            "The US EPA rollback",
            None,
            GateOutcome.DROPPED_NEGATIVE,
        ),
        # Relevance: trusted passes on domain alone; others need a token.
        ("https://gov.wales/c", "Storm overflow plan", "", TRUSTED, GateOutcome.PASSED),
        ("https://example.com/c", "Storm overflow plan", "", None, GateOutcome.DROPPED_UNRELATED),
        (
            "https://api.openalex.org/w1",
            "Peat carbon",
            "",
            UNTRUSTED,
            GateOutcome.DROPPED_UNRELATED,
        ),
        ("https://api.openalex.org/w2", "Peat carbon in Wales", "", UNTRUSTED, GateOutcome.PASSED),
        ("https://example.com/d", "Storm overflow plan", "Welsh rivers", None, GateOutcome.PASSED),
        ("https://example.com/senedd-inquiry", "Inquiry", "", None, GateOutcome.PASSED),
        ("https://example.com/e", "Floods on the River Dee", "", None, GateOutcome.PASSED),
        (
            "https://example.com/f",
            "Deep water in the deer park",
            "",
            None,
            GateOutcome.DROPPED_UNRELATED,
        ),
        ("https://example.com/north-wales-floods", "Floods", "", None, GateOutcome.PASSED),
    ],
)
def test_gate_outcomes(
    url: str, title: str, snippet: str, src: Source | None, expected: GateOutcome
) -> None:
    raw = hit(url, title, snippet=snippet)
    assert gate(raw, src, QUERY, INSTRUMENT, rules()) is expected


def test_matching_is_case_insensitive() -> None:
    raw = hit("https://example.com/a", "POLLUTION IN NEW SOUTH WALES")
    assert gate(raw, None, QUERY, INSTRUMENT, rules()) is GateOutcome.DROPPED_NEGATIVE
    assert gate(hit("https://example.com/b", "WALES"), None, QUERY, INSTRUMENT, rules()) is (
        GateOutcome.PASSED
    )


def test_a_negative_term_of_another_query_does_not_apply() -> None:
    other = query("q2")
    raw = hit("https://example.com/b", "Welsh view", snippet="The US EPA rollback")
    assert gate(raw, None, other, instrument(QUERY, other), rules()) is GateOutcome.PASSED


def test_relevance_tokens_match_whole_words_and_phrases_across_separators() -> None:
    gates = rules(("dee", "north wales"))
    assert gates.is_relevant(["The River Dee"])
    assert gates.is_relevant(["/news/north-wales/"])
    assert gates.is_relevant(["north_wales"])
    assert gates.is_relevant(["North   Wales"])
    assert not gates.is_relevant(["deep", "deer", "dee2", "northwales"])
    assert gates.relevance_tokens_in("Dee and North Wales") == ("dee", "north wales")


def test_rules_validate_domains_and_tokens() -> None:
    with pytest.raises(ValueError, match="bare lower-case host"):
        GatingRules(frozenset({"https://naturalresources.wales"}), ("wales",))
    with pytest.raises(ValueError, match="lower case"):
        GatingRules(frozenset(), ("Wales",))
    with pytest.raises(ValueError, match="one space"):
        GatingRules(frozenset(), ("north  wales",))
    with pytest.raises(ValueError, match="repeat"):
        GatingRules(frozenset(), ("wales", "wales"))
    nothing = GatingRules(frozenset(), ())
    assert not nothing.is_relevant(["wales"])


def test_relevance_tokens_from_place_names() -> None:
    tokens = relevance_tokens(
        ["Wales", "welsh"],
        ["Wales", "Cymru", "River Dee", "Afon Dyfrdwy", "Gogledd Cymru", "Afon Teifi", "River"],
    )
    assert tokens == (
        "wales",
        "welsh",
        "cymru",
        "dee",
        "dyfrdwy",
        "gogledd cymru",
        "teifi",
        "river",
    )
