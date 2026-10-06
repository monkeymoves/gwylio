"""Table and property tests for the shared value objects.

The two forbidden dash characters are built with ``chr()`` so that this file
itself passes the repository-wide dash check.
"""

from __future__ import annotations

import re
from datetime import date, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st

from gwylio.shared.values import CanonicalUrl, CleanText, IsoDate, KebabId

EN_DASH = chr(0x2013)
EM_DASH = chr(0x2014)
DASHES = (EN_DASH, EM_DASH)
# 2026-08-15 written in Arabic-Indic digits, which IsoDate must refuse.
ARABIC_INDIC_DATE = "".join(chr(0x0660 + int(c)) if c.isdigit() else c for c in "2026-08-15")


# CleanText


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("plain text", "plain text"),
        ("", ""),
        ("line one\r\nline two", "line one\nline two"),
        ("trailing   \nspaces\t\n", "trailing\nspaces\n"),
        ("keeps  inner  spacing", "keeps  inner  spacing"),
        ("hyphen-minus is fine", "hyphen-minus is fine"),
        ("Cymraeg: Cyfoeth Naturiol Cymru, ŵ ŷ", "Cymraeg: Cyfoeth Naturiol Cymru, ŵ ŷ"),
    ],
)
def test_clean_text_normalises(raw: str, expected: str) -> None:
    text = CleanText(raw)
    assert text == expected
    assert isinstance(text, str)


@pytest.mark.parametrize(
    ("raw", "code_point"),
    [
        (f"2025{EN_DASH}2026", "U+2013"),
        (f"a pause{EM_DASH}then more", "U+2014"),
        (f"{EM_DASH}", "U+2014"),
    ],
)
def test_clean_text_refuses_dashes_naming_the_code_point(raw: str, code_point: str) -> None:
    with pytest.raises(ValueError, match=re.escape(code_point)):
        CleanText(raw)


def test_clean_text_refuses_non_strings() -> None:
    with pytest.raises(TypeError):
        CleanText(42)  # type: ignore[arg-type]


def test_clean_text_has_no_instance_dict() -> None:
    assert not hasattr(CleanText("x"), "__dict__")


@given(st.text().filter(lambda s: not any(d in s for d in DASHES)))
def test_clean_text_accepts_any_text_without_the_two_dashes(raw: str) -> None:
    text = CleanText(raw)
    assert CleanText(text) == text
    assert "\r\n" not in text
    assert all(line == line.rstrip() for line in text.split("\n"))


@given(st.text(), st.sampled_from(DASHES), st.text())
def test_clean_text_refuses_any_text_with_a_dash(before: str, dash: str, after: str) -> None:
    with pytest.raises(ValueError, match=f"U\\+{ord(dash):04X}"):
        CleanText(before + dash + after)


# CanonicalUrl


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://www.gov.wales/", "gov.wales"),
        ("HTTPS://WWW.Gov.Wales/Path/", "gov.wales/Path"),
        ("http://example.org/a/b/#section", "example.org/a/b"),
        ("https://example.org:443/x", "example.org/x"),
        ("http://example.org:80/x", "example.org/x"),
        ("https://example.org:8443/x", "example.org:8443/x"),
        ("http://example.org:443/x", "example.org:443/x"),
        (
            "https://senedd.wales/committee?id=123&utm_source=x&utm_Medium=y&fbclid=z",
            "senedd.wales/committee?id=123",
        ),
        ("https://example.org/?b=2&gclid=1&a=1&mc_cid=3&mc_eid=4", "example.org?b=2&a=1"),
        ("https://example.org/p?utm_source=only", "example.org/p"),
        ("https://example.org/p?a=1&&b=2&", "example.org/p?a=1&b=2"),
        ("https://example.org/p?flag", "example.org/p?flag"),
        ("example.org/path/", "example.org/path"),
        ("//example.org/path", "example.org/path"),
        ("https://user:secret@example.org/x", "example.org/x"),
        ("https://www.www.example.org", "example.org"),
        ("https://www.example.org.uk/www.page", "example.org.uk/www.page"),
        ("  https://example.org/padded  ", "example.org/padded"),
        ("https://[2001:db8::1]:8080/x", "[2001:db8::1]:8080/x"),
        ("https://example.org/a b/?q=x y", "example.org/a%20b?q=x%20y"),
        ("https://example.org/a /", "example.org/a%20"),
    ],
)
def test_canonical_url_table(raw: str, expected: str) -> None:
    url = CanonicalUrl(raw)
    assert url.value == expected
    assert str(url) == expected
    assert CanonicalUrl(url.value).value == expected


def test_canonical_url_host_excludes_www_and_port() -> None:
    url = CanonicalUrl("https://WWW.Example.ORG:8443/x?y=1")
    assert url.host == "example.org"


def test_canonical_url_equality_and_hash() -> None:
    a = CanonicalUrl("https://www.gov.wales/news/?utm_source=feed")
    b = CanonicalUrl("http://gov.wales/news#top")
    assert a == b
    assert hash(a) == hash(b)
    assert len({a, b}) == 1
    assert a != "gov.wales/news"


def test_canonical_url_is_immutable() -> None:
    url = CanonicalUrl("https://example.org")
    with pytest.raises(AttributeError):
        url.foo = "bar"  # type: ignore[attr-defined]
    with pytest.raises(AttributeError):
        del url._value


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "https://",
        "https://www.",
        "/just/a/path",
        "http://example.org:notaport/",
        "https://exa mple.org/",
    ],
)
def test_canonical_url_rejects_inputs_without_a_valid_host(raw: str) -> None:
    with pytest.raises(ValueError):
        CanonicalUrl(raw)


_label = st.from_regex(r"[A-Za-z0-9]{1,10}", fullmatch=True)
_segment = st.from_regex(r"[A-Za-z0-9._~%-]{0,8}", fullmatch=True)
_param_key = st.one_of(
    st.from_regex(r"[a-z]{1,6}", fullmatch=True),
    st.sampled_from(["utm_source", "UTM_campaign", "fbclid", "gclid", "mc_cid", "mc_eid", "id"]),
)
_param = st.builds(
    lambda k, v: f"{k}={v}" if v is not None else k,
    _param_key,
    st.one_of(st.none(), st.from_regex(r"[A-Za-z0-9%+]{0,6}", fullmatch=True)),
)


@st.composite
def realistic_urls(draw: st.DrawFn) -> str:
    scheme = draw(st.sampled_from(["http://", "https://", "HTTPS://", "//", ""]))
    www = draw(st.sampled_from(["", "www.", "WWW."]))
    labels = draw(st.lists(_label, min_size=1, max_size=4))
    port = draw(st.one_of(st.none(), st.sampled_from([80, 443, 8080, 8443])))
    segments = draw(st.lists(_segment, max_size=4))
    trailing = draw(st.sampled_from(["", "/", "//"]))
    params = draw(st.lists(_param, max_size=5))
    fragment = draw(st.one_of(st.none(), _segment))
    url = scheme + www + ".".join(labels)
    if port is not None:
        url += f":{port}"
    if segments:
        url += "/" + "/".join(segments)
    url += trailing
    if params:
        url += "?" + "&".join(params)
    if fragment is not None:
        url += "#" + fragment
    return url


@given(realistic_urls())
def test_canonical_url_is_idempotent_on_realistic_urls(raw: str) -> None:
    once = CanonicalUrl(raw)
    assert CanonicalUrl(once.value).value == once.value
    assert "#" not in once.value
    assert not once.value.endswith("/")
    lowered = once.value.lower()
    assert "utm_" not in lowered
    assert "fbclid" not in lowered
    assert "gclid" not in lowered


@given(st.text(max_size=60))
def test_canonical_url_is_idempotent_or_refuses_on_arbitrary_text(raw: str) -> None:
    try:
        once = CanonicalUrl(raw)
    except ValueError:
        return
    assert CanonicalUrl(once.value).value == once.value


@given(
    st.lists(st.from_regex(r"[a-z]{1,5}=[0-9]{1,3}", fullmatch=True), min_size=1, max_size=6),
    st.lists(st.sampled_from(["utm_source=a", "fbclid=b", "gclid=c"]), max_size=4),
)
def test_canonical_url_keeps_other_params_in_order(kept: list[str], tracking: list[str]) -> None:
    mixed: list[str] = []
    for index, param in enumerate(kept):
        mixed.append(param)
        if index < len(tracking):
            mixed.append(tracking[index])
    url = CanonicalUrl("https://example.org/p?" + "&".join(mixed))
    assert url.value == "example.org/p?" + "&".join(kept)


# IsoDate


def test_iso_date_parses_and_renders() -> None:
    d = IsoDate("2026-08-15")
    assert d.value == date(2026, 8, 15)
    assert str(d) == "2026-08-15"
    assert IsoDate(date(2026, 8, 15)) == d
    assert hash(IsoDate("2026-08-15")) == hash(d)


@pytest.mark.parametrize(
    "raw",
    [
        "2026-8-15",
        "26-08-15",
        "2026/08/15",
        "2026-08-15T00:00:00",
        " 2026-08-15",
        "2026-08-15\n",
        "2026-02-30",
        "2026-13-01",
        "",
        ARABIC_INDIC_DATE,
    ],
)
def test_iso_date_is_strict(raw: str) -> None:
    with pytest.raises(ValueError):
        IsoDate(raw)


def test_iso_date_refuses_datetime_and_other_types() -> None:
    with pytest.raises(ValueError):
        IsoDate(datetime(2026, 8, 15))
    with pytest.raises(TypeError):
        IsoDate(20260815)  # type: ignore[arg-type]


def test_iso_date_ordering() -> None:
    early, late = IsoDate("2026-01-01"), IsoDate("2026-12-31")
    assert early < late
    assert early <= late
    assert late > early
    assert late >= early
    assert early <= IsoDate("2026-01-01")
    assert sorted([late, early]) == [early, late]
    assert early != "2026-01-01"


def test_iso_date_is_immutable() -> None:
    d = IsoDate("2026-01-01")
    with pytest.raises(AttributeError):
        d._value = date(2027, 1, 1)  # type: ignore[misc]


@given(st.dates())
def test_iso_date_round_trips(value: date) -> None:
    assert IsoDate(str(IsoDate(value))).value == value


# KebabId


@pytest.mark.parametrize("raw", ["nrw-corporate-plan", "si1", "a", "2026-q3", "a" * 80])
def test_kebab_id_accepts(raw: str) -> None:
    assert KebabId(raw) == raw


@pytest.mark.parametrize(
    "raw",
    ["", "-a", "a-", "a--b", "A", "has space", "under_score", "café", "a" * 81, "a\n", "a.b"],
)
def test_kebab_id_rejects(raw: str) -> None:
    with pytest.raises(ValueError):
        KebabId(raw)


@given(st.from_regex(r"[a-z0-9]{1,8}(-[a-z0-9]{1,8}){0,6}", fullmatch=True))
def test_kebab_id_round_trips(raw: str) -> None:
    kebab = KebabId(raw)
    assert KebabId(str(kebab)) == kebab
    assert str(kebab) == raw
