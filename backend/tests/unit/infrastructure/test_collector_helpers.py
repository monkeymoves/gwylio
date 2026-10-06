"""The helpers every real collector shares: URLs, plain text, dates, phrases and hits."""

from __future__ import annotations

from datetime import UTC, datetime

from gwylio.collection.model import Discipline
from gwylio.infrastructure.collectors.common import (
    SNIPPET_LIMIT,
    HitBuilder,
    as_dict,
    as_list,
    as_str,
    parse_date,
    plain_text,
    query_phrases,
    safe_url,
    warn,
)
from gwylio.shared.values import CleanText, IsoDate
from tests.support import query

EN, EM = chr(0x2013), chr(0x2014)


def test_safe_url_percent_encodes_dashes_only() -> None:
    assert safe_url(f" https://example.org/a{EN}b{EM}c?q=1 ") == (
        "https://example.org/a%E2%80%93b%E2%80%94c?q=1"
    )
    assert safe_url("https://example.org/a-b") == "https://example.org/a-b"


def test_plain_text_strips_markup_and_cuts_long_text() -> None:
    assert plain_text("<p>A <strong>bold</strong>&amp;  plain</p>\n") == "A bold & plain"
    assert plain_text("&lt;p&gt;escaped twice&lt;/p&gt;") == "escaped twice"
    long = "word " * 200
    cut = plain_text(long, SNIPPET_LIMIT)
    assert len(cut) <= SNIPPET_LIMIT + 3
    assert cut.endswith("word...")


def test_query_phrases_reads_quoted_or_joined_and_bare_text() -> None:
    assert query_phrases('"Nature Recovery" OR "rewilding" OR "nature recovery"') == (
        "nature recovery",
        "rewilding",
    )
    assert query_phrases("drought OR hosepipe ban") == ("drought", "hosepipe ban")
    assert query_phrases("habitat restoration Wales") == ("habitat restoration wales",)


def test_parse_date_reads_the_formats_publishers_use() -> None:
    assert parse_date("2026-09-15T09:00:00") == IsoDate("2026-09-15")
    assert parse_date("2026-09-15") == IsoDate("2026-09-15")
    assert parse_date("Thu, 24 Sep 2026 09:00:00 +0000") == IsoDate("2026-09-24")
    assert parse_date("September 20, 2026") == IsoDate("2026-09-20")
    assert parse_date("20 Sep 2026") == IsoDate("2026-09-20")
    for unknown in (None, "", "3 days ago", "2026-13-45", "soon"):
        assert parse_date(unknown) is None


def test_json_accessors_forgive_wrong_shapes() -> None:
    assert as_dict({"a": 1}) == {"a": 1}
    assert as_dict([1]) == {}
    assert as_list([1]) == [1]
    assert as_list({"a": 1}) == []
    assert as_str("x") == "x"
    assert as_str(None) == ""


def test_warn_scrubs_dashes() -> None:
    assert warn(f"feed x failed {EM} HTTP 500") == CleanText("feed x failed, HTTP 500")


def test_hit_builder_scrubs_text_and_refuses_unusable_urls() -> None:
    builder = HitBuilder(query("q1"), Discipline.OSINT_WEB, datetime(2026, 10, 6, tzinfo=UTC))
    hit = builder.build("https://gov.wales/x", f"2024{EN}25 <b>plan</b>", "snip")
    assert hit is not None
    assert hit.title == "2024 to 25 plan"
    assert hit.query_id == "q1"
    warnings: list[CleanText] = []
    assert builder.build("not a url", "t", warnings=warnings) is None
    assert builder.build("", "t", warnings=warnings) is None
    assert len(warnings) == 1
    assert "unusable URL" in warnings[0]
