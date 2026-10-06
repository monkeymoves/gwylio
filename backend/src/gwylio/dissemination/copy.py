"""The standing copy: every heading and standing sentence a product uses, as data.

``config/copy.json`` holds the words; the renderers hold only structure. A
renderer never contains a literal heading or standing sentence: it asks the
``Copy`` for one and fills in the numbers and titles with ``fill``. Change a
word in ``config/copy.json`` and every product says it the new way.

Templates name their blanks in braces, such as ``{count}``. Each field
declares the blanks it may use (shown in the JSON Schema as
``placeholders``); loading refuses a template that names any other blank or
has unbalanced braces, so a typo fails at ``gwylio check`` rather than in
the middle of a render. Every string is ``CleanText``: no en or em dash.

This module parses the copy from its text; reading the file is
infrastructure's job.
"""

from __future__ import annotations

import string
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.fields import FieldInfo

from gwylio.shared.values import CleanText

__all__ = [
    "CommonCopy",
    "Copy",
    "CoverageCopy",
    "CredibilityCopy",
    "DirectionCopy",
    "FindingCopy",
    "IntsumCopy",
    "MethodCopy",
    "ScanabilityCopy",
    "StateCopy",
    "StrategicCopy",
    "fill",
    "parse_copy",
    "placeholders_of",
]


def _text(description: str, *placeholders: str) -> Any:
    """A copy field: a description and the blanks its template may name."""
    extra: dict[str, Any] = {"placeholders": list(placeholders)}
    return Field(min_length=1, description=description, json_schema_extra=extra)


def placeholders_of(template: str) -> tuple[str, ...]:
    """The blanks a template names, in order; raises ``ValueError`` on bad braces or formats."""
    names: list[str] = []
    for _, name, spec, conversion in string.Formatter().parse(template):
        if name is None:
            continue
        if not name.isidentifier() or spec or conversion:
            raise ValueError(f"blank {{{name}}} must be a plain name with no format or conversion")
        names.append(name)
    return tuple(names)


def _allowed(info: FieldInfo) -> frozenset[str]:
    extra = info.json_schema_extra
    if isinstance(extra, dict):
        listed = extra.get("placeholders", [])
        if isinstance(listed, list):
            return frozenset(str(name) for name in listed)
    return frozenset()


class _CopyModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def _templates_are_clean(self) -> _CopyModel:
        for name, info in type(self).model_fields.items():
            if name == "notes":
                continue
            value = getattr(self, name)
            texts = value if isinstance(value, list) else [value]
            for text in texts:
                if not isinstance(text, str):
                    continue
                CleanText(text)
                allowed = _allowed(info)
                unknown = sorted(set(placeholders_of(text)) - allowed)
                if unknown:
                    known = ", ".join(sorted(allowed)) or "none"
                    raise ValueError(
                        f"{name}: unknown blank {', '.join('{' + u + '}' for u in unknown)}; "
                        f"this text may use: {known}"
                    )
        return self


def fill(template: str, **values: object) -> CleanText:
    """The template with its blanks filled; every value is turned into text first."""
    return CleanText(template.format_map({key: str(value) for key, value in values.items()}))


class DirectionCopy(_CopyModel):
    """How each direction reads in a product."""

    threatens: str = _text("Label for the threatens direction.")
    neutral: str = _text("Label for the neutral (two-way) direction.")
    informs_baseline: str = _text("Label for the informs_baseline direction.")
    supports: str = _text("Label for the supports direction.")


class StateCopy(_CopyModel):
    """How each indicator state reads in a product."""

    emerging: str = _text("Label for emerging.")
    tracking: str = _text("Label for tracking.")
    reinforced: str = _text("Label for reinforced.")
    matured: str = _text("Label for matured.")
    faded: str = _text("Label for faded.")
    parked: str = _text("Label for parked.")


class CoverageCopy(_CopyModel):
    """How each coverage status reads in a product."""

    covered: str = _text("Label for covered.")
    thin: str = _text("Label for thin.")
    quiet: str = _text("Label for quiet.")
    blind_spot: str = _text("Label for blind spot.")


class ScanabilityCopy(_CopyModel):
    """How each scanability value reads in a product."""

    high: str = _text("Label for high scanability.")
    medium: str = _text("Label for medium scanability.")
    low: str = _text("Label for low scanability.")
    none: str = _text("Label for no scanability.")


class CredibilityCopy(_CopyModel):
    """The Admiralty wording for each credibility digit."""

    one: str = _text("Credibility 1.")
    two: str = _text("Credibility 2.")
    three: str = _text("Credibility 3.")
    four: str = _text("Credibility 4.")
    five: str = _text("Credibility 5.")
    six: str = _text("Credibility 6.")

    def label(self, digit: int) -> str:
        """The wording for one digit, 1 to 6."""
        return (self.one, self.two, self.three, self.four, self.five, self.six)[digit - 1]


class FindingCopy(_CopyModel):
    """A date check finding kind: a heading and the sentence that explains it."""

    heading: str = _text("Heading for this kind of finding.")
    meaning: str = _text("One sentence on what this kind of finding means.")


class CommonCopy(_CopyModel):
    """Words both products share."""

    months: list[str] = Field(
        min_length=12, max_length=12, description="Month names, January first."
    )
    set_line: str = _text("Lead line naming the requirement set.", "name", "version")
    period_line: str = _text(
        "Lead line naming the period and the render date.", "start", "end", "generated_on"
    )
    none: str = _text("What a list with nothing in it says.")
    list_separator: str = _text("Joins items in a running list, such as ', '.")
    count_pair: str = _text("One item of a running count, such as 'supports 3'.", "label", "count")
    direction_tag: str = _text("One assessment on a report line.", "code", "direction")
    share: str = _text("A share written as a percentage.", "percent")
    yes: str = _text("A table cell for true.")
    no: str = _text("A table cell for false.")
    unattributed: str = _text("Column heading for reports with no resolvable lane.")
    header_measure: str = _text("Table heading: the measure counted.")
    header_count: str = _text("Table heading: the count.")
    header_requirement: str = _text("Table heading: the requirement.")
    header_total: str = _text("Table heading: the row total.")
    header_status: str = _text("Table heading: the coverage status.")
    header_node: str = _text("Table heading: the taxonomy node.")
    header_expected: str = _text("Table heading: requirements expecting the node.")
    header_reports: str = _text("Table heading: active reports.")
    header_direction: str = _text("Table heading: the direction.")
    header_credibility: str = _text("Table heading: the credibility digit.")
    header_label: str = _text("Table heading: the wording of a value.")
    blind_spot_rule: str = _text("The standing sentence that a blind spot is not quiet.")
    undercount: str = _text(
        "The standing sentence that counts of reports are not counts of impact."
    )
    directions: DirectionCopy
    states: StateCopy
    statuses: CoverageCopy
    scanability: ScanabilityCopy
    credibility: CredibilityCopy


class MethodCopy(_CopyModel):
    """The method note both products end with."""

    heading: str = _text("Heading of the method note.")
    runs: str = _text("How many scan runs started in the period.", "count")
    no_runs: str = _text("What the note says when no run started in the period.")
    header_run: str = _text("Runs table heading: run id.")
    header_started: str = _text("Runs table heading: start date.")
    header_instrument: str = _text("Runs table heading: instrument version.")
    header_raw: str = _text("Runs table heading: raw hits.")
    header_unique: str = _text("Runs table heading: unique candidates.")
    header_new: str = _text("Runs table heading: new candidates.")
    header_reinforcements: str = _text("Runs table heading: reinforcements.")
    header_requests: str = _text("Runs table heading: requests made.")
    header_budget: str = _text("Runs table heading: budget exhausted.")
    header_reports: str = _text("Credibility table heading: reports created in the period.")
    dispositions: str = _text(
        "Dispositions of the period's candidates.",
        "promoted",
        "rejected",
        "duplicate",
        "deferred",
        "reinforcement",
        "undisposed",
    )
    promotions: str = _text(
        "Reports created in the period and the non-government share.",
        "count",
        "non_government",
        "share",
    )
    no_promotions: str = _text("What the note says when no report was created in the period.")
    credibility: str = _text("Introduces the credibility table for the period's reports.", "count")
    instrument: str = _text("The instrument versions the period's runs used.", "versions")
    instrument_current: str = _text(
        "The current instrument version, when no run used one in the period.", "version"
    )
    blind_spots: str = _text("The requirements this tool cannot see.", "codes")
    no_blind_spots: str = _text("What the note says when no requirement is a blind spot.")
    streetlight: str = _text("The standing sentence on what the queries would never find.")


class IntsumCopy(_CopyModel):
    """The operational intelligence summary (INTSUM)."""

    title: str = _text("Title of the INTSUM.", "period", "set_name")
    purpose: str = _text("Lead sentence on what the INTSUM is for.")
    summary_heading: str = _text("Heading of the summary.")
    summary_new: str = _text("Sentence: new reports in the period.", "count")
    summary_state_changes: str = _text("Sentence: lifecycle state changes in the period.", "count")
    summary_faded: str = _text("Sentence: reports faded in the period.", "count")
    summary_verified: str = _text("Sentence: reports verified in the period.", "count")
    summary_directions: str = _text(
        "Sentence: assessments on the reports that moved, by direction.",
        "threatens",
        "neutral",
        "informs_baseline",
        "supports",
    )
    measure_new: str = _text("Summary table row: new reports.")
    measure_state_changes: str = _text("Summary table row: state changes.")
    measure_faded: str = _text("Summary table row: faded.")
    measure_verified: str = _text("Summary table row: verified.")
    measure_direction: str = _text("Summary table row: assessments in one direction.", "direction")
    moved_heading: str = _text("Heading of the reports that moved.")
    moved_intro: str = _text("Sentence introducing the per objective lists.")
    group_heading: str = _text("Subheading for one well-being objective.", "name", "codes")
    outside_heading: str = _text("Subheading for reports outside every well-being objective.")
    group_empty: str = _text("What an objective with nothing moving says.")
    report_line: str = _text(
        "One report in a list.", "grading", "title", "directions", "state", "report_id"
    )
    quiet_heading: str = _text("Heading of the quiet requirements and blind spots.")
    quiet_intro: str = _text("Sentence introducing the requirements with no movement.")
    quiet_line: str = _text(
        "One requirement with no movement.",
        "code",
        "short",
        "status",
        "active",
        "scanability",
    )
    quiet_none: str = _text("What the section says when every requirement moved.")
    verification_heading: str = _text("Heading of the date check findings.")
    verification_intro: str = _text(
        "Sentence counting the date check findings.", "count", "reports", "today"
    )
    verification_none: str = _text("What the section says when the date check found nothing.")
    finding_line: str = _text("One finding.", "title", "report_id", "detail")
    passed_horizon: FindingCopy
    future_language: FindingCopy
    stale_verification: FindingCopy
    never_verified: FindingCopy


class StrategicCopy(_CopyModel):
    """The strategic assessment: the annual picture per requirement set."""

    title: str = _text("Title of the strategic assessment.", "period", "set_name")
    purpose_heading: str = _text("Heading of the purpose.")
    purpose: list[str] = Field(
        min_length=1, description="Paragraphs on what the assessment is for."
    )
    picture_heading: str = _text("Heading of the standing picture.")
    picture_intro: str = _text("Sentence introducing the standing picture.")
    requirement_heading: str = _text("Subheading for one requirement.", "code", "name")
    status_line: str = _text("Coverage status of a requirement.", "status", "active")
    directions_line: str = _text("Active reports by direction.", "directions")
    states_line: str = _text("Active reports by state.", "states")
    grading_line: str = _text("Grading spread of the active reports.", "gradings")
    matured_line: str = _text("Matured reports kept as settled context.", "count")
    scanability_line: str = _text(
        "Scanability, with the requirement's note verbatim.", "scanability", "note"
    )
    top_intro: str = _text("Sentence introducing the highest potential impact reports.")
    top_line: str = _text(
        "One report among the highest potential impact.",
        "grading",
        "title",
        "directions",
        "state",
        "impact",
        "report_id",
    )
    impact_high: str = _text("Potential impact: high.")
    impact_medium: str = _text("Potential impact: medium.")
    impact_low: str = _text("Potential impact: low.")
    questions_heading: str = _text("Heading of the questions per well-being objective.")
    questions_intro: str = _text("Sentence on what the questions are and are not.")
    group_heading: str = _text("Subheading for one well-being objective.", "name", "codes")
    question: str = _text(
        "One question drawn from a threatening or two-way report.", "title", "codes", "report_id"
    )
    questions_none: str = _text("What an objective with no threat or two-way report says.")
    coverage_heading: str = _text("Heading of the coverage audit.")
    coverage_intro: str = _text("Sentence introducing the coverage audit.")
    lane_matrix_heading: str = _text("Subheading of the requirement by lane matrix.")
    lane_matrix_note: str = _text("Sentence explaining the requirement by lane matrix.")
    taxonomy_heading: str = _text("Subheading of one taxonomy axis.", "axis")
    taxonomy_note: str = _text("Sentence explaining the taxonomy counts.")


class Copy(_CopyModel):
    """config/copy.json: every heading and standing sentence the products use."""

    notes: str | None = Field(default=None, description="Free notes for whoever edits the copy.")
    common: CommonCopy
    method: MethodCopy
    intsum: IntsumCopy
    strategic: StrategicCopy


def parse_copy(text: str) -> Copy:
    """Parse ``config/copy.json`` text; raises ``pydantic.ValidationError``."""
    return Copy.model_validate_json(text)
