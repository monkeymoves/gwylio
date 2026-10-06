"""The standing copy: parsed, checked for blanks and dashes, and filled."""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

from gwylio.dissemination.copy import Copy, fill, parse_copy, placeholders_of
from tests.support import PROJECT_ROOT

COPY_FILE = PROJECT_ROOT / "config" / "copy.json"


def shipped() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(COPY_FILE.read_text(encoding="utf-8"))
    return data


def test_the_shipped_copy_parses() -> None:
    copy = parse_copy(COPY_FILE.read_text(encoding="utf-8"))
    assert copy.intsum.summary_heading == "Summary"
    assert len(copy.common.months) == 12
    assert copy.common.credibility.label(2) == "probably true"
    assert "blind spot is not quiet" in copy.common.blind_spot_rule.lower()


def test_a_template_naming_an_unknown_blank_is_refused() -> None:
    data = shipped()
    data["intsum"]["summary_new"] = "New reports: {total}."
    with pytest.raises(ValidationError, match=r"unknown blank \{total\}; this text may use: count"):
        Copy.model_validate(data)


def test_a_text_with_no_blanks_allowed_refuses_any() -> None:
    data = shipped()
    data["intsum"]["summary_heading"] = "Summary {count}"
    with pytest.raises(ValidationError, match="may use: none"):
        Copy.model_validate(data)


def test_bad_braces_and_format_specs_are_refused() -> None:
    data = shipped()
    data["intsum"]["summary_new"] = "New reports: {count."
    with pytest.raises(ValidationError):
        Copy.model_validate(data)
    with pytest.raises(ValueError, match="plain name"):
        placeholders_of("{count:>5}")


def test_a_dash_in_the_copy_is_refused() -> None:
    data = shipped()
    data["method"]["heading"] = "Method " + chr(0x2014) + " note"
    with pytest.raises(ValidationError, match="EM DASH"):
        Copy.model_validate(data)


def test_missing_and_extra_keys_are_refused() -> None:
    data = shipped()
    del data["strategic"]["question"]
    with pytest.raises(ValidationError, match="question"):
        Copy.model_validate(data)
    data = shipped()
    data["intsum"]["surprise"] = "x"
    with pytest.raises(ValidationError, match="surprise"):
        Copy.model_validate(data)


def test_fill_turns_values_into_text() -> None:
    assert fill("{count} of {total}", count=3, total=4) == "3 of 4"
    assert placeholders_of("What would change for {codes} if this holds: {title}?") == (
        "codes",
        "title",
    )
