"""The glossary: complete against the plan, free of duplicates and dashes."""

from __future__ import annotations

import re

from gwylio.shared.glossary import GLOSSARY
from gwylio.shared.values import CleanText
from tests.support import PROJECT_ROOT


def _plan_vocabulary_terms() -> set[str]:
    """Every bold term in the vocabulary section of docs/PLAN.md, lower-cased."""
    text = (PROJECT_ROOT / "docs" / "PLAN.md").read_text(encoding="utf-8")
    section = text.split("## Vocabulary", 1)[1].split("\n## ", 1)[0]
    terms: set[str] = set()
    for bold in re.findall(r"\*\*(.+?)\*\*", section):
        terms.update(part.strip().lower() for part in bold.split(","))
    return terms


def test_the_plan_section_parses_into_a_sensible_number_of_terms() -> None:
    assert len(_plan_vocabulary_terms()) >= 40


def test_every_plan_vocabulary_term_is_in_the_glossary() -> None:
    glossary_terms = {term.lower() for term, _ in GLOSSARY}
    missing = sorted(_plan_vocabulary_terms() - glossary_terms)
    assert not missing, f"terms in docs/PLAN.md missing from the glossary: {missing}"


def test_terms_are_unique_ignoring_case() -> None:
    lowered = [term.casefold() for term, _ in GLOSSARY]
    duplicates = sorted({term for term in lowered if lowered.count(term) > 1})
    assert not duplicates


def test_terms_and_definitions_are_clean_non_empty_sentences() -> None:
    for term, definition in GLOSSARY:
        assert term.strip() == term and term, term
        assert CleanText(term) == term
        assert CleanText(definition) == definition
        assert definition.endswith("."), term
        assert "  " not in definition, term


def test_glossary_has_no_en_or_em_dash() -> None:
    forbidden = (chr(0x2013), chr(0x2014))
    for term, definition in GLOSSARY:
        assert not any(dash in term + definition for dash in forbidden), term
