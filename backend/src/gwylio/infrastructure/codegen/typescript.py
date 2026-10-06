"""A small TypeScript generator over JSON Schema.

Handles what the configuration contracts use: objects (as interfaces),
arrays, tuples (``prefixItems``), string enums (as unions of literals),
constants, optional and nullable properties, ``anyOf`` and ``oneOf`` unions,
strings, numbers, booleans and ``$ref`` links to ``$defs``. Anything else
renders as ``unknown`` rather than guessing.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from typing import Any, Final

__all__ = ["typescript_module"]

_IDENTIFIER: Final[re.Pattern[str]] = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
_SIMPLE: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9_$.\"']+")
_ROOT_ONLY_KEYS: Final[frozenset[str]] = frozenset({"$defs", "$schema", "$id", "$comment"})

Schema = Mapping[str, Any]


def _ref_name(ref: str) -> str:
    return ref.rsplit("/", 1)[-1]


def _literal(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _union(parts: Iterable[str]) -> str:
    unique: list[str] = []
    for part in parts:
        if part not in unique:
            unique.append(part)
    return " | ".join(unique)


def _type(schema: Schema, indent: str) -> str:
    if "$ref" in schema:
        return _ref_name(str(schema["$ref"]))
    if "const" in schema:
        return _literal(schema["const"])
    if "enum" in schema:
        return _union(_literal(value) for value in schema["enum"])
    for key in ("anyOf", "oneOf"):
        if key in schema:
            return _union(_type(option, indent) for option in schema[key])
    if "allOf" in schema and len(schema["allOf"]) == 1:
        return _type(schema["allOf"][0], indent)
    kind = schema.get("type")
    if isinstance(kind, list):
        return _union(_type({**schema, "type": one}, indent) for one in kind)
    if kind == "string":
        return "string"
    if kind in ("integer", "number"):
        return "number"
    if kind == "boolean":
        return "boolean"
    if kind == "null":
        return "null"
    if kind == "array":
        if "prefixItems" in schema:
            return "[" + ", ".join(_type(item, indent) for item in schema["prefixItems"]) + "]"
        item = _type(schema.get("items", {}), indent)
        return f"{item}[]" if _SIMPLE.fullmatch(item) else f"Array<{item}>"
    if kind == "object" or "properties" in schema:
        if "properties" in schema:
            return _object_body(schema, indent)
        extra = schema.get("additionalProperties")
        if isinstance(extra, Mapping):
            return f"Record<string, {_type(extra, indent)}>"
        return "Record<string, unknown>"
    return "unknown"


def _doc(text: str | None, indent: str) -> list[str]:
    if not text:
        return []
    lines = [line.rstrip() for line in text.replace("*/", "*\\/").strip().splitlines()]
    if len(lines) == 1:
        return [f"{indent}/** {lines[0]} */"]
    return [f"{indent}/**", *(f"{indent} * {line}".rstrip() for line in lines), f"{indent} */"]


def _object_body(schema: Schema, indent: str) -> str:
    inner = indent + "\t"
    required = set(schema.get("required", ()))
    lines = ["{"]
    for name, prop in schema["properties"].items():
        key = name if _IDENTIFIER.fullmatch(name) else _literal(name)
        optional = "" if name in required else "?"
        lines.extend(_doc(prop.get("description"), inner))
        lines.append(f"{inner}{key}{optional}: {_type(prop, inner)};")
    lines.append(f"{indent}}}")
    return "\n".join(lines)


def _named(name: str, schema: Schema) -> str:
    lines = _doc(schema.get("description"), "")
    is_object = schema.get("type") == "object" and "properties" in schema
    if is_object:
        lines.append(f"export interface {name} {_object_body(schema, '')}")
    else:
        lines.append(f"export type {name} = {_type(schema, '')};")
    return "\n".join(lines)


def _collect(definitions: dict[str, Schema], name: str, schema: Schema) -> None:
    body = {key: value for key, value in schema.items() if key not in _ROOT_ONLY_KEYS}
    existing = definitions.get(name)
    if existing is not None and existing != body:
        raise ValueError(f"two schemas define {name!r} differently")
    definitions[name] = body


def typescript_module(schemas: Iterable[Schema], header: str) -> str:
    """One TypeScript module declaring every root schema and every ``$defs`` entry.

    Each root schema must carry a ``title``, which names its type. Types are
    emitted in name order so the output is stable.
    """
    definitions: dict[str, Schema] = {}
    for schema in schemas:
        for name, sub in schema.get("$defs", {}).items():
            _collect(definitions, name, sub)
        title = schema.get("title")
        if not isinstance(title, str) or not _IDENTIFIER.fullmatch(title):
            raise ValueError(f"root schema needs an identifier title, got {title!r}")
        _collect(definitions, title, schema)
    blocks = [_named(name, definitions[name]) for name in sorted(definitions)]
    return header.rstrip("\n") + "\n\n" + "\n\n".join(blocks) + "\n"
