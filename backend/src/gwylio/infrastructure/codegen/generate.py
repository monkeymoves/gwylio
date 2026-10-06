"""Render every generated file and write them under a root directory."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from pydantic import TypeAdapter

from gwylio.infrastructure.codegen.jsonschema import (
    GENERATED_NOTE,
    json_schema_documents,
    render_json,
)
from gwylio.infrastructure.codegen.markdown import CliVerb, glossary_markdown, reference_markdown
from gwylio.infrastructure.codegen.typescript import typescript_module
from gwylio.infrastructure.config.loaders import LoadedConfig
from gwylio.infrastructure.config.schemas import SCHEMA_ENUMS, SCHEMA_MODELS
from gwylio.shared.glossary import GLOSSARY

__all__ = [
    "GLOSSARY_PATH",
    "REFERENCE_PATH",
    "SCHEMA_DIR",
    "TYPESCRIPT_PATH",
    "WriteResult",
    "render_generated",
    "stale_files",
    "write_generated",
]

SCHEMA_DIR: Final[str] = "docs/schema"
GLOSSARY_PATH: Final[str] = "docs/GLOSSARY.md"
REFERENCE_PATH: Final[str] = "skill/REFERENCE.md"
TYPESCRIPT_PATH: Final[str] = "frontend/src/lib/data/types.generated.ts"


@dataclass(frozen=True, slots=True)
class WriteResult:
    """One generated file and whether writing it changed what was on disk."""

    path: str
    changed: bool


def render_generated(config: LoadedConfig, verbs: Sequence[CliVerb]) -> dict[str, str]:
    """Every generated file's text, keyed by its path relative to the project root."""
    documents = json_schema_documents(SCHEMA_MODELS)
    files = {
        f"{SCHEMA_DIR}/{name}.schema.json": render_json(document)
        for name, document in documents.items()
    }
    enum_schemas = [TypeAdapter(enum).json_schema() for enum in SCHEMA_ENUMS]
    model_schemas = [SCHEMA_MODELS[name].model_json_schema() for name in sorted(SCHEMA_MODELS)]
    header = "\n".join(f"// {line}" for line in _wrap(GENERATED_NOTE))
    files[TYPESCRIPT_PATH] = typescript_module([*model_schemas, *enum_schemas], header)
    files[GLOSSARY_PATH] = glossary_markdown(GLOSSARY)
    files[REFERENCE_PATH] = reference_markdown(config, verbs)
    return dict(sorted(files.items()))


def write_generated(
    root: Path, files: Mapping[str, str], *, dry_run: bool = False
) -> list[WriteResult]:
    """Write each file under ``root`` (unless ``dry_run``) and report which ones changed."""
    results: list[WriteResult] = []
    for relative, text in files.items():
        path = root / relative
        data = text.encode("utf-8")
        changed = not path.is_file() or path.read_bytes() != data
        if changed and not dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        results.append(WriteResult(relative, changed))
    return results


def _wrap(text: str, width: int = 90) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        if current and len(current) + 1 + len(word) > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}" if current else word
    if current:
        lines.append(current)
    return lines


def stale_files(root: Path, files: Mapping[str, str]) -> list[str]:
    """Generated schema files on disk that the generators no longer produce."""
    directory = root / SCHEMA_DIR
    if not directory.is_dir():
        return []
    on_disk = (path.relative_to(root).as_posix() for path in directory.glob("*.schema.json"))
    return sorted(path for path in on_disk if path not in files)
