"""Frozen value objects shared by every context.

These are small, I/O-free types that make invalid states unrepresentable at the
edges of the domain:

- ``CleanText``: text that is guaranteed free of en and em dashes, with
  normalised line endings. It is the only place the dash rule is implemented.
- ``CanonicalUrl``: the identity of a web resource used for deduplication.
- ``IsoDate``: a calendar date parsed strictly from ``YYYY-MM-DD``.
- ``KebabId``: a lowercase kebab-case identifier of at most 80 characters.
- ``RunId``: a scan run identifier, the UTC minute the run started plus four
  hex characters.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from typing import Any, ClassVar, Final, NoReturn
from urllib.parse import urlsplit

__all__ = [
    "KEBAB_MAX_LENGTH",
    "KEBAB_PATTERN",
    "RUN_ID_PATTERN",
    "CanonicalUrl",
    "CleanText",
    "IsoDate",
    "KebabId",
    "RunId",
]

_FORBIDDEN_DASHES: Final[dict[int, str]] = {
    0x2013: "EN DASH",
    0x2014: "EM DASH",
}


class CleanText(str):
    """A ``str`` that never contains an en dash (U+2013) or an em dash (U+2014).

    On construction the text is normalised: CRLF line endings become LF and
    trailing whitespace is stripped from every line. Construction raises
    ``ValueError`` naming the offending code point and its position if either
    dash is present. Normalisation is idempotent, so wrapping a ``CleanText``
    again returns an equal value.

    This class is the single implementation of the project's dash rule.
    Persistence and the snapshot exporter accept only ``CleanText``.
    """

    __slots__ = ()

    def __new__(cls, text: str = "") -> CleanText:
        if not isinstance(text, str):
            raise TypeError(f"CleanText needs a str, got {type(text).__name__}")
        for index, char in enumerate(text):
            name = _FORBIDDEN_DASHES.get(ord(char))
            if name is not None:
                raise ValueError(
                    f"text contains U+{ord(char):04X} {name} at index {index}; "
                    "use a comma, a colon or 'to' instead"
                )
        normalised = "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").split("\n"))
        return super().__new__(cls, normalised)

    @classmethod
    def scrub(cls, text: str) -> CleanText:
        """Clean external text (a web page title, a feed snippet) that may carry dashes.

        Collectors call this on text they did not write, so a dash in a
        publisher's headline never aborts a scan. A dash between two digits
        becomes ``" to "`` (``2024`` dash ``25`` reads ``2024 to 25``), a dash
        with space on both sides becomes ``", "``, and any other dash becomes a
        hyphen. Whitespace around the result is trimmed. Text written by Gwylio
        itself goes through the constructor, which refuses dashes outright.
        """
        if not isinstance(text, str):
            raise TypeError(f"CleanText needs a str, got {type(text).__name__}")
        text = _DASH_RANGE_RE.sub(" to ", text)
        text = _DASH_SPACED_RE.sub(", ", text)
        text = _DASH_ANY_RE.sub("-", text)
        return cls(text.strip())

    def __repr__(self) -> str:
        return f"CleanText({str.__repr__(self)})"


_DASH_CLASS: Final[str] = "[" + "".join(chr(code) for code in _FORBIDDEN_DASHES) + "]"
_DASH_RANGE_RE: Final[re.Pattern[str]] = re.compile(rf"(?<=\d)\s*{_DASH_CLASS}\s*(?=\d)")
_DASH_SPACED_RE: Final[re.Pattern[str]] = re.compile(rf"\s+{_DASH_CLASS}+\s+")
_DASH_ANY_RE: Final[re.Pattern[str]] = re.compile(_DASH_CLASS)


_TRACKING_EXACT: Final[frozenset[str]] = frozenset({"fbclid", "gclid", "mc_cid", "mc_eid"})
_TRACKING_PREFIXES: Final[tuple[str, ...]] = ("utm_",)
_DEFAULT_PORTS: Final[dict[str, int]] = {"http": 80, "https": 443}
_SCHEME_RE: Final[re.Pattern[str]] = re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*://")
_PERCENT_ESCAPE_RE: Final[re.Pattern[str]] = re.compile(r"%[0-9a-fA-F]{2}")


def _is_unsafe(char: str) -> bool:
    return char.isspace() or unicodedata.category(char) == "Cc"


def _encode_unsafe(text: str) -> str:
    """Percent-encode whitespace and control characters, which are never legal in a URL."""
    if not any(_is_unsafe(char) for char in text):
        return text
    return "".join(
        "".join(f"%{byte:02X}" for byte in char.encode("utf-8")) if _is_unsafe(char) else char
        for char in text
    )


def _is_tracking_param(key: str) -> bool:
    lowered = key.lower()
    return lowered in _TRACKING_EXACT or lowered.startswith(_TRACKING_PREFIXES)


class _Frozen:
    """Mixin that blocks attribute assignment after ``__init__`` completes."""

    __slots__ = ()
    _frozen_attrs: ClassVar[tuple[str, ...]] = ()

    def _freeze(self, **values: Any) -> None:
        for name, value in values.items():
            object.__setattr__(self, name, value)

    def __setattr__(self, name: str, value: object) -> NoReturn:
        raise AttributeError(f"{type(self).__name__} is immutable")

    def __delattr__(self, name: str) -> NoReturn:
        raise AttributeError(f"{type(self).__name__} is immutable")


class CanonicalUrl(_Frozen):
    """The canonical identity of a URL, used to deduplicate hits and match reports.

    Built from any URL string, with or without a scheme. The canonical form:

    - lower-cases the scheme and host, then drops the scheme;
    - drops every leading ``www.`` label from the host and any user information;
    - keeps the port only when it is not the default for the scheme
      (80 for http, 443 for https; with no scheme every explicit port is kept);
    - drops the fragment and any trailing slashes on the path;
    - removes tracking query parameters (``utm_*``, ``fbclid``, ``gclid``,
      ``mc_cid``, ``mc_eid``) and empty query segments, keeping every other
      parameter verbatim and in its original order;
    - percent-encodes any whitespace or control character left in the path or
      query (surrounding whitespace is trimmed first; tabs and newlines inside
      the URL are dropped, as the standard library parser does).

    The transformation is idempotent: ``CanonicalUrl(c.value).value == c.value``.
    Raises ``ValueError`` when the input has no host, a host containing
    whitespace or control characters, or an invalid port.
    """

    __slots__ = ("_host", "_value")
    _host: str
    _value: str

    def __init__(self, url: str) -> None:
        if not isinstance(url, str):
            raise TypeError(f"CanonicalUrl needs a str, got {type(url).__name__}")
        raw = url.strip()
        if _SCHEME_RE.match(raw):
            to_parse = raw
        elif raw.startswith("//"):
            to_parse = "http:" + raw
        else:
            to_parse = "//" + raw
        parts = urlsplit(to_parse)
        scheme = parts.scheme.lower()
        hostname = parts.hostname
        if not hostname:
            raise ValueError(f"URL has no host: {url!r}")
        host = hostname.lower()
        while host.startswith("www."):
            host = host[4:]
        if not host:
            raise ValueError(f"URL has no host after removing 'www.': {url!r}")
        if any(_is_unsafe(char) for char in host):
            raise ValueError(f"URL host contains whitespace or a control character: {url!r}")
        port = parts.port  # raises ValueError on an invalid port
        netloc = f"[{host}]" if ":" in host else host
        if port is not None and port != _DEFAULT_PORTS.get(scheme):
            netloc = f"{netloc}:{port}"
        path = _encode_unsafe(parts.path).rstrip("/")
        kept = [
            segment
            for segment in _encode_unsafe(parts.query).split("&")
            if segment and not _is_tracking_param(segment.split("=", 1)[0])
        ]
        query = "&".join(kept)
        value = netloc + path + (f"?{query}" if query else "")
        self._freeze(_host=host, _value=value)

    @property
    def value(self) -> str:
        """The canonical string, for example ``gov.wales/consultations?id=12``."""
        return self._value

    @property
    def host(self) -> str:
        """The lower-cased host without ``www.`` and without the port."""
        return self._host

    @property
    def match_key(self) -> str:
        """The canonical string with its percent escapes in upper case, for matching reports.

        A publisher's dash in a URL reaches Gwylio percent-encoded
        (``%E2%80%93``, sometimes in lower case). Two contexts compare URLs
        built from different spellings of one address (a candidate and a
        report), so both use this key and an escape's case never decides a match.
        """
        return _PERCENT_ESCAPE_RE.sub(lambda match: match.group(0).upper(), self._value)

    def __str__(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return f"CanonicalUrl({self._value!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CanonicalUrl):
            return NotImplemented
        return self._value == other._value

    def __hash__(self) -> int:
        return hash(("CanonicalUrl", self._value))


_ISO_DATE_RE: Final[re.Pattern[str]] = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


class IsoDate(_Frozen):
    """A calendar date parsed strictly from ``YYYY-MM-DD``.

    Accepts a string in exactly that form (ASCII digits, zero padded, no time
    part, no surrounding whitespace) or a ``datetime.date`` that is not a
    ``datetime``. Raises ``ValueError`` on anything else. Supports the
    comparison operators against other ``IsoDate`` values and renders back to
    ``YYYY-MM-DD`` with ``str()``.
    """

    __slots__ = ("_value",)
    _value: date

    def __init__(self, value: str | date) -> None:
        if isinstance(value, datetime):
            raise ValueError("IsoDate needs a date, not a datetime")
        if isinstance(value, date):
            parsed = value
        elif isinstance(value, str):
            if not _ISO_DATE_RE.fullmatch(value):
                raise ValueError(f"not a YYYY-MM-DD date: {value!r}")
            parsed = date.fromisoformat(value)
        else:
            raise TypeError(f"IsoDate needs a str or date, got {type(value).__name__}")
        self._freeze(_value=parsed)

    @property
    def value(self) -> date:
        """The wrapped ``datetime.date``."""
        return self._value

    def __str__(self) -> str:
        return self._value.isoformat()

    def __repr__(self) -> str:
        return f"IsoDate({self._value.isoformat()!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, IsoDate):
            return NotImplemented
        return self._value == other._value

    def __hash__(self) -> int:
        return hash(("IsoDate", self._value))

    def __lt__(self, other: IsoDate) -> bool:
        if not isinstance(other, IsoDate):
            return NotImplemented
        return self._value < other._value

    def __le__(self, other: IsoDate) -> bool:
        if not isinstance(other, IsoDate):
            return NotImplemented
        return self._value <= other._value

    def __gt__(self, other: IsoDate) -> bool:
        if not isinstance(other, IsoDate):
            return NotImplemented
        return self._value > other._value

    def __ge__(self, other: IsoDate) -> bool:
        if not isinstance(other, IsoDate):
            return NotImplemented
        return self._value >= other._value


KEBAB_PATTERN: Final[str] = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
"""The kebab-case rule as an anchored regular expression, for JSON Schema ``pattern``."""
_KEBAB_RE: Final[re.Pattern[str]] = re.compile(KEBAB_PATTERN[1:-1])
KEBAB_MAX_LENGTH: Final[int] = 80


class KebabId(str):
    """A lowercase kebab-case identifier such as ``nrw-corporate-plan``.

    Must match ``[a-z0-9]+(-[a-z0-9]+)*`` in full (ASCII only, no leading,
    trailing or doubled hyphens) and be at most 80 characters long. Raises
    ``ValueError`` on anything else. Being a ``str`` it can be used directly
    as a dictionary key or database value.
    """

    __slots__ = ()

    def __new__(cls, value: str) -> KebabId:
        if not isinstance(value, str):
            raise TypeError(f"KebabId needs a str, got {type(value).__name__}")
        if len(value) > KEBAB_MAX_LENGTH:
            raise ValueError(f"id is {len(value)} characters, the maximum is {KEBAB_MAX_LENGTH}")
        if not _KEBAB_RE.fullmatch(value):
            raise ValueError(f"not a lowercase kebab-case id: {value!r}")
        return super().__new__(cls, value)

    def __repr__(self) -> str:
        return f"KebabId({str.__repr__(self)})"


RUN_ID_PATTERN: Final[str] = r"^[0-9]{8}T[0-9]{4}Z-[0-9a-f]{4}$"
"""A scan run id as an anchored regular expression, for JSON Schema ``pattern``."""
_RUN_ID_RE: Final[re.Pattern[str]] = re.compile(RUN_ID_PATTERN[1:-1])


class RunId(str):
    """A scan run identifier such as ``20261006T0215Z-3f9a``.

    The UTC minute the run started (``YYYYMMDDTHHMMZ``), a hyphen and four
    lower-case hex characters. Run ids sort by start time. Raises
    ``ValueError`` on anything else.
    """

    __slots__ = ()

    def __new__(cls, value: str) -> RunId:
        if not isinstance(value, str):
            raise TypeError(f"RunId needs a str, got {type(value).__name__}")
        if not _RUN_ID_RE.fullmatch(value):
            raise ValueError(
                f"not a run id: {value!r}; expected the UTC minute and four hex characters, "
                "such as '20261006T0215Z-3f9a'"
            )
        return super().__new__(cls, value)

    def __repr__(self) -> str:
        return f"RunId({str.__repr__(self)})"
