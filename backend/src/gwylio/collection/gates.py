"""The gates every raw hit passes through before deduplication.

Three gates, always in this order, and the first that drops a hit decides
its outcome:

1. **Own domain.** A hit on one of the organisation's own domains is dropped:
   the register tracks external signals only.
2. **Negative term.** A hit whose title, snippet or URL contains a global
   negative term, then one of the query's own, is dropped. Matching is
   case-insensitive substring matching, so ``new south wales`` catches the
   Australian state wherever it appears.
3. **Relevance.** A hit from a trusted source passes on its domain alone. Any
   other hit (an untrusted source, or no known source at all) must carry a
   relevance token, matched as a whole word or phrase, in its title, snippet
   or URL.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Final

from gwylio.collection.model import GateOutcome, Query, QueryInstrument, RawHit, Source
from gwylio.shared.values import CanonicalUrl

__all__ = ["GatingRules", "gate", "relevance_tokens"]

_SEPARATOR: Final[str] = r"[\s_\-]+"
_RIVER_PREFIXES: Final[tuple[str, ...]] = ("river ", "afon ")


def _token_pattern(token: str) -> str:
    return _SEPARATOR.join(re.escape(word) for word in token.split())


@dataclass(frozen=True, slots=True)
class GatingRules:
    """The organisation's own domains and the tokens that make a hit relevant.

    Own domains match the host exactly or as a parent domain
    (``cyfoethnaturiol.cymru`` covers ``www.`` and any subdomain). Relevance
    tokens are lower-case words or phrases; a phrase matches across spaces,
    hyphens or underscores, so ``north wales`` also matches ``north-wales`` in
    a URL. Tokens match whole words only: ``dee`` does not match ``deep``.
    """

    own_domains: frozenset[str]
    relevance_tokens: tuple[str, ...]
    _relevance: re.Pattern[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        for domain in self.own_domains:
            canonical = CanonicalUrl(domain)
            if canonical.value != domain or canonical.host != domain:
                raise ValueError(f"own domain '{domain}' must be a bare lower-case host")
        for token in self.relevance_tokens:
            if not token.strip() or token != " ".join(token.split()):
                raise ValueError(f"relevance token {token!r} must be words separated by one space")
            if token != token.casefold():
                raise ValueError(f"relevance token '{token}' must be lower case")
        if len(set(self.relevance_tokens)) != len(self.relevance_tokens):
            raise ValueError("relevance tokens repeat a value")
        ordered = sorted(self.relevance_tokens, key=lambda token: (-len(token), token))
        body = "|".join(_token_pattern(token) for token in ordered) or r"(?!)"
        object.__setattr__(self, "_relevance", re.compile(rf"(?<!\w)(?:{body})(?!\w)"))

    def is_own_domain(self, host: str) -> bool:
        """True when ``host`` is one of the own domains or a subdomain of one."""
        return any(host == domain or host.endswith("." + domain) for domain in self.own_domains)

    def is_relevant(self, texts: Iterable[str]) -> bool:
        """True when any of ``texts`` carries a relevance token as a whole word or phrase."""
        return any(self._relevance.search(text.casefold()) for text in texts)

    def relevance_tokens_in(self, text: str) -> tuple[str, ...]:
        """The tokens found in ``text``, in the order they appear, for explaining a decision."""
        return tuple(match.group(0) for match in self._relevance.finditer(text.casefold()))


def gate(
    hit: RawHit,
    source: Source | None,
    query: Query,
    instrument: QueryInstrument,
    rules: GatingRules,
) -> GateOutcome:
    """The outcome of the three gates for one hit, applied in order."""
    if rules.is_own_domain(hit.canonical_url.host):
        return GateOutcome.DROPPED_OWN
    blob = f"{hit.title}\n{hit.snippet}\n{hit.url}".casefold()
    if any(term.casefold() in blob for term in instrument.negative_terms_for(query)):
        return GateOutcome.DROPPED_NEGATIVE
    if source is not None and source.trusted:
        return GateOutcome.PASSED
    if rules.is_relevant((hit.title, hit.snippet, hit.url)):
        return GateOutcome.PASSED
    return GateOutcome.DROPPED_UNRELATED


def relevance_tokens(base: Iterable[str], place_names: Iterable[str]) -> tuple[str, ...]:
    """The base tokens plus a token for each place name, lower-cased and de-duplicated.

    A river's name drops its ``River`` or Welsh ``Afon`` prefix, so ``River
    Dee`` gives ``dee`` and ``Afon Teifi`` gives ``teifi``; other names are kept
    whole, so ``Gogledd Cymru`` gives ``gogledd cymru``. Base tokens come
    first, in their order, then place tokens in order of first appearance.
    """
    tokens: dict[str, None] = {}
    for token in base:
        tokens.setdefault(" ".join(token.casefold().split()), None)
    for name in place_names:
        token = " ".join(name.casefold().split())
        for prefix in _RIVER_PREFIXES:
            if token.startswith(prefix) and len(token) > len(prefix):
                token = token[len(prefix) :]
                break
        tokens.setdefault(token, None)
    return tuple(token for token in tokens if token)
