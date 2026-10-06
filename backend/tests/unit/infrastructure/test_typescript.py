"""The JSON Schema to TypeScript generator, one schema feature at a time."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

import pytest
from pydantic import BaseModel, Field, TypeAdapter

from gwylio.infrastructure.codegen.typescript import typescript_module

HEADER = "// header"


class Colour(StrEnum):
    """A colour."""

    RED = "red"
    BLUE = "blue"


class Inner(BaseModel):
    """An inner object."""

    flag: bool


class Outer(BaseModel):
    """An outer object.

    Second paragraph with a */ in it.
    """

    name: str = Field(description="The name.")
    count: int
    ratio: float | None = None
    tags: list[str] = Field(default_factory=list)
    colour: Colour
    colours: list[Colour | None]
    inner: Inner
    inners: list[Inner]
    pair: tuple[float, float] | None = None
    extras: dict[str, int]


def render(*schemas: dict[str, Any]) -> str:
    return typescript_module(list(schemas), HEADER)


def test_models_render_as_interfaces_with_optional_and_nullable_properties() -> None:
    out = render(Outer.model_json_schema())
    assert out.startswith("// header\n\n")
    assert out.endswith("}\n")
    assert "export interface Outer {" in out
    assert "\t/** The name. */\n\tname: string;" in out
    assert "\tcount: number;" in out
    assert "\tratio?: number | null;" in out
    assert "\ttags?: string[];" in out
    assert "\tcolour: Colour;" in out
    assert "\tcolours: Array<Colour | null>;" in out
    assert "\tinner: Inner;" in out
    assert "\tinners: Inner[];" in out
    assert "\tpair?: [number, number] | null;" in out
    assert "\textras: Record<string, number>;" in out


def test_enums_render_as_literal_unions() -> None:
    out = render(Outer.model_json_schema())
    assert '/** A colour. */\nexport type Colour = "red" | "blue";' in out


def test_nested_definitions_are_emitted_once_in_name_order() -> None:
    out = render(Outer.model_json_schema(), Inner.model_json_schema())
    names = [line.split()[2] for line in out.splitlines() if line.startswith("export ")]
    assert names == ["Colour", "Inner", "Outer"]
    assert out.count("export interface Inner") == 1


def test_multi_line_descriptions_become_block_comments_and_close_safely() -> None:
    out = render(Outer.model_json_schema())
    assert "/**\n * An outer object.\n *\n * Second paragraph with a *\\/ in it.\n */" in out


def test_standalone_enum_schema() -> None:
    out = render(TypeAdapter(Colour).json_schema())
    assert 'export type Colour = "red" | "blue";' in out


def test_non_identifier_property_names_are_quoted() -> None:
    schema = {
        "title": "Odd",
        "type": "object",
        "properties": {"x-y": {"type": "string"}, "$ok": {"const": 1}},
        "required": ["$ok"],
    }
    out = render(schema)
    assert '\t"x-y"?: string;' in out
    assert "\t$ok: 1;" in out


@pytest.mark.parametrize(
    ("schema", "expected"),
    [
        ({"type": ["string", "null"]}, "string | null"),
        ({"oneOf": [{"type": "integer"}, {"type": "boolean"}]}, "number | boolean"),
        ({"allOf": [{"$ref": "#/$defs/Thing"}]}, "Thing"),
        ({"type": "object"}, "Record<string, unknown>"),
        ({"type": "array"}, "unknown[]"),
        ({}, "unknown"),
        ({"type": "object", "properties": {"a": {"type": "string"}}}, "{\n\ta?: string;\n}"),
    ],
)
def test_type_expressions(schema: dict[str, Any], expected: str) -> None:
    root = {"title": "Root", "type": "object", "properties": {"x": schema}, "required": ["x"]}
    out = render(root)
    assert f"\tx: {expected.replace(chr(10), chr(10) + chr(9))};" in out


def test_conflicting_definitions_are_refused() -> None:
    first = {"title": "A", "type": "object", "properties": {}, "$defs": {"X": {"type": "string"}}}
    second = {"title": "B", "type": "object", "properties": {}, "$defs": {"X": {"type": "number"}}}
    with pytest.raises(ValueError, match="define 'X' differently"):
        render(first, second)


def test_root_needs_an_identifier_title() -> None:
    with pytest.raises(ValueError, match="identifier title"):
        render({"type": "object", "properties": {}})
