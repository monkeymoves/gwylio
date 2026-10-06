"""``import-legacy``: seed the register from the previous tool's ``signals.json``.

The seed is itself a fact: the old register is translated into one
out-of-run submission, ``data/submissions/legacy__<received_on>.json``, which
is then ingested like any other. The mapping is written up in
``docs/adr/0003-legacy-import.md``; in short:

- ``sis[].si`` ``SI4`` becomes requirement ``si4``, direction verbatim;
- ``signal_type`` becomes ``report_type`` (the names are the same);
- ``scores.evidence_strength`` becomes ``scores.evidence``, and sets the
  credibility (high 2, medium 3, low 4);
- the source is the watched source whose domain the URL host equals or ends
  with (the longest match wins); otherwise there is none, ``source_name`` is
  the old ``source`` and ``reliability_if_unknown_source`` is B for the old
  government lens and C for the rest;
- ``scan_lane`` maps to a lane (``LEGACY_LANES``), used when no watched
  source gives the lane;
- lifecycle ``matured`` and ``parked`` become ``state_override``; every other
  state is left to the lifecycle, so those reports land as emerging with no
  sightings (the old appearance counts were mostly index echo and are not
  recreated);
- topics and hazards come from a small, conservative keyword table over the
  title (``KEYWORD_TAGS``); every report is placed in ``wales``;
- the old history is carried verbatim as ``imported`` entries, followed by a
  creation entry saying the report was imported and its grading defaulted;
- ``event_horizon``, ``last_verified``, ``bucket``, ``summary`` and ``owner``
  are carried verbatim (an empty owner becomes none).
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final
from urllib.parse import quote, urlsplit

from pydantic import ValidationError

from gwylio.collection.model import Source
from gwylio.infrastructure.config.loaders import LoadedConfig
from gwylio.infrastructure.handoff.submission_file import IngestOutcome, ingest_submission
from gwylio.infrastructure.sqlite.db import Database
from gwylio.processing.submission import (
    RUBRIC_VERSION,
    SUBMISSION_FORMAT,
    Submission,
    dumps_submission,
)

__all__ = [
    "CREDIBILITY_BY_EVIDENCE",
    "KEYWORD_TAGS",
    "LEGACY_ANALYST",
    "LEGACY_LANES",
    "LegacyImportError",
    "import_legacy",
    "legacy_stem",
    "legacy_submission",
    "match_source",
]

LEGACY_ANALYST: Final[str] = "import-legacy (NRW SI horizon register)"

LEGACY_LANES: Final[Mapping[str, str]] = {
    "welsh_gov_policy": "welsh-government",
    "senedd_scrutiny": "senedd",
    "uk_gov_and_regulators": "uk-government-and-regulators",
    "research_evidence": "research-evidence",
    "legal_civil_society": "partnership-and-civil-society",
    "ecological_early_warning": "ecological-surveillance",
    "governance_capacity": "governance-capacity",
    "international": "international",
}
"""The old tool's ``scan_lane`` values and the lanes they become."""

CREDIBILITY_BY_EVIDENCE: Final[Mapping[str, int]] = {"high": 2, "medium": 3, "low": 4}
"""Credibility from the old evidence strength: conservative, awaiting analyst review."""

KEYWORD_TAGS: Final[tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...]] = (
    ("drought", ("water-resources",), ("drought-and-low-flows",)),
    ("flood", ("flood-risk",), ()),
    ("flooding", ("flood-risk",), ("river-and-surface-water-flooding",)),
    ("coastal erosion", ("flood-risk", "marine-and-coastal"), ("coastal-flooding-and-erosion",)),
    ("wildfire", (), ("upland-wildfire",)),
    ("avian flu", ("biosecurity",), ("avian-influenza",)),
    ("avian influenza", ("biosecurity",), ("avian-influenza",)),
    ("asian hornet", ("biosecurity",), ()),
    ("air quality", ("air-quality",), ()),
    ("carbon budget", ("climate-emissions",), ()),
    ("net zero", ("climate-emissions",), ()),
    ("emissions", ("climate-emissions",), ()),
    ("adaptation", ("people-place-and-resilience",), ()),
    ("agricultural pollution", ("pollution-water-and-land",), ("agricultural-pollution",)),
    ("poultry", ("pollution-water-and-land",), ("agricultural-pollution",)),
    ("metal mines", ("pollution-water-and-land",), ("metal-mine-pollution",)),
    ("pollution", ("pollution-water-and-land",), ()),
    ("judicial review", (), ("legal-challenge",)),
    ("sue", (), ("legal-challenge",)),
    ("tree planting", ("woodland-and-forestry",), ()),
    ("soil", ("soil-and-land",), ()),
    ("peatland", ("peatland",), ()),
    ("marine", ("marine-and-coastal",), ()),
    ("seabird", ("marine-and-coastal",), ()),
    ("fisheries", ("marine-and-coastal",), ()),
    ("biodiversity", ("nature-and-ecosystems",), ()),
    ("nature recovery", ("nature-and-ecosystems",), ()),
    ("nature crisis", ("nature-and-ecosystems",), ()),
    ("sssis", ("nature-and-ecosystems",), ()),
    ("green spaces", ("people-place-and-resilience",), ()),
    ("petition", ("partnership-and-society",), ()),
    ("savings programme", ("governance-and-funding",), ("public-funding-pressure",)),
    ("budget reductions", ("governance-and-funding",), ("public-funding-pressure",)),
)
"""``(phrase, topics, hazards)``: a whole-word phrase in the title adds these tags."""

_URL_SAFE: Final[str] = ":/?#[]@!$&'()*+,;=%~"


class LegacyImportError(ValueError):
    """The legacy file could not be read or translated."""


def match_source(url: str, sources: Sequence[Source]) -> Source | None:
    """The watched source whose domain the URL host equals or ends with; the longest wins."""
    host = (urlsplit(url).hostname or "").lower()
    while host.startswith("www."):
        host = host[4:]
    best: Source | None = None
    for source in sources:
        if (host == source.domain or host.endswith("." + source.domain)) and (
            best is None or len(source.domain) > len(best.domain)
        ):
            best = source
    return best


def _tags(title: str) -> tuple[list[str], list[str]]:
    lowered = title.casefold()
    topics: list[str] = []
    hazards: list[str] = []
    for phrase, topic_ids, hazard_ids in KEYWORD_TAGS:
        if re.search(rf"\b{re.escape(phrase)}\b", lowered):
            topics.extend(t for t in topic_ids if t not in topics)
            hazards.extend(h for h in hazard_ids if h not in hazards)
    return topics, hazards


def _field(signal: Mapping[str, Any], name: str, index: int) -> Any:
    if name not in signal:
        raise LegacyImportError(f"signals[{index}] has no {name}")
    return signal[name]


def _promotion(
    signal: Mapping[str, Any], index: int, sources: Sequence[Source], creation_note: str
) -> dict[str, Any]:
    url = quote(str(_field(signal, "url", index)), safe=_URL_SAFE)
    source = match_source(url, sources)
    scores = _field(signal, "scores", index)
    evidence = scores.get("evidence_strength")
    if evidence not in CREDIBILITY_BY_EVIDENCE:
        raise LegacyImportError(f"signals[{index}] has evidence_strength {evidence!r}")
    old_lane = _field(signal, "scan_lane", index)
    if old_lane not in LEGACY_LANES:
        raise LegacyImportError(f"signals[{index}] has an unmapped scan_lane {old_lane!r}")
    lifecycle = _field(signal, "lifecycle", index)
    topics, hazards = _tags(str(_field(signal, "title", index)))
    owner = str(signal.get("owner") or "").strip()
    return {
        "id": _field(signal, "id", index),
        "from_candidate": None,
        "title": _field(signal, "title", index),
        "url": url,
        "source_id": None if source is None else str(source.id),
        "source_name": str(_field(signal, "source", index)) if source is None else source.name,
        "actor_id": None if source is None else str(source.actor),
        "lane": LEGACY_LANES[old_lane],
        "report_type": _field(signal, "signal_type", index),
        "credibility": CREDIBILITY_BY_EVIDENCE[evidence],
        "reliability_if_unknown_source": None
        if source is not None
        else ("B" if signal.get("lens") == "government" else "C"),
        "assessments": [
            {"requirement_id": str(item["si"]).lower(), "direction": item["direction"]}
            for item in _field(signal, "sis", index)
        ],
        "topics": topics,
        "hazards": hazards,
        "places": ["wales"],
        "scores": {
            "evidence": evidence,
            "novelty": scores.get("novelty"),
            "confidence": scores.get("confidence"),
            "potential_impact": scores.get("potential_impact"),
            "time_horizon": scores.get("time_horizon"),
        },
        "bucket": _field(signal, "bucket", index),
        "event_horizon": signal.get("event_horizon"),
        "last_verified": signal.get("last_verified"),
        "summary": _field(signal, "summary", index),
        "notes": str(signal.get("notes") or "").strip(),
        "owner": owner or None,
        "state_override": lifecycle if lifecycle in ("matured", "parked") else None,
        "prior_history": [
            {"on": entry["date"], "change": entry["change"]} for entry in signal.get("history", [])
        ],
        "creation_note": creation_note,
    }


def legacy_submission(
    data: Mapping[str, Any], config: LoadedConfig, received_on: str | None = None
) -> Submission:
    """The out-of-run submission that imports every signal in the old register."""
    signals = data.get("signals")
    if not isinstance(signals, list) or not signals:
        raise LegacyImportError("the legacy file has no signals list")
    scan_date = str(data.get("scan_date") or "")
    received = received_on or scan_date
    if not received:
        raise LegacyImportError("the legacy file has no scan_date; pass --received-on")
    creation_note = (
        f"Imported from the NRW SI horizon register (signals.json, scan date {scan_date}). "
        "Grading defaulted on import and awaits analyst review."
    )
    sources = [source for source in config.sources]
    promotions = [
        _promotion(signal, index, sources, creation_note) for index, signal in enumerate(signals)
    ]
    document = {
        "schema": SUBMISSION_FORMAT,
        "run_id": None,
        "analyst": LEGACY_ANALYST,
        "rubric_version": RUBRIC_VERSION,
        "received_on": received,
        "promotions": promotions,
        "method_note": (
            f"One-off import of the {len(promotions)} signals in the NRW SI horizon register "
            f"(signals.json, scan date {scan_date}), written by gwylio import-legacy. Mapping in "
            "docs/adr/0003-legacy-import.md: grades defaulted from the source's reliability "
            "(B for government, C otherwise, when the source is not watched) and the old "
            "evidence strength; old appearance counts not recreated as sightings, because "
            "most were index echo; topics and hazards from a conservative title keyword table; "
            "every report placed in Wales."
        ),
    }
    try:
        return Submission.model_validate(document)
    except ValidationError as error:
        details = "; ".join(
            f"{'.'.join(str(part) for part in detail['loc'])}: {detail['msg']}"
            for detail in error.errors(include_url=False)
        )
        raise LegacyImportError(f"the legacy file does not translate: {details}") from error


def legacy_stem(received_on: str) -> str:
    """The legacy submission's file stem, ``legacy__<received_on>``."""
    return f"legacy__{received_on}"


def import_legacy(
    db: Database,
    config: LoadedConfig,
    signals_path: Path,
    submissions_dir: Path,
    *,
    received_on: str | None = None,
) -> IngestOutcome:
    """Write ``legacy__<received_on>.json`` under ``submissions_dir`` and ingest it.

    The file is written inside the ingest transaction, so it exists only if
    the ingest succeeds. An identical file already there is reused; a
    different one is refused (facts are never overwritten).
    """
    try:
        data = json.loads(signals_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise LegacyImportError(f"{signals_path}: cannot read: {error}") from error
    if not isinstance(data, dict):
        raise LegacyImportError(f"{signals_path}: not a legacy register")
    submission = legacy_submission(data, config, received_on)
    stem = legacy_stem(submission.received_on)
    target = submissions_dir / f"{stem}.json"
    text = dumps_submission(submission)
    if target.exists() and target.read_text(encoding="utf-8") != text:
        raise LegacyImportError(
            f"{target} already exists with different content; submissions are never replaced"
        )

    def write() -> None:
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")

    outcome = ingest_submission(db, config, submission, stem, before_commit=write)
    return IngestOutcome(outcome.submission_id, outcome.problems, outcome.result, target)
