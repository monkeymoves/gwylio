"""Archive every instrument version a run used: ``data/instruments/<version>.json``.

A candidates file names its instrument by version and hash only.
``config/instrument.json`` holds the current version, so once the instrument
moves on the version an older run used would exist nowhere on disk and a
rebuild could not restore it. ``gwylio collect`` therefore writes each version
it uses here, once, in the same format as ``config/instrument.json``. The
archive is append-only like the candidates files: a version is never
rewritten, and a different instrument under a stored version is refused.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Final

from pydantic import ValidationError

from gwylio.collection.model import QueryInstrument
from gwylio.infrastructure.config.loaders import build_instrument
from gwylio.infrastructure.config.schemas import InstrumentFile, QueryConfig

__all__ = [
    "ARCHIVE_NOTE",
    "InstrumentFileError",
    "archive_instrument",
    "dumps_instrument",
    "instrument_document",
    "read_instrument_archives",
    "read_instrument_file",
]

ARCHIVE_NOTE: Final[str] = (
    "The query instrument exactly as a scan run used it, archived by gwylio collect so the "
    "run can be rebuilt after config/instrument.json moves on. Never edit this file."
)


class InstrumentFileError(ValueError):
    """An archived instrument could not be read, or would overwrite a different one."""


def instrument_document(instrument: QueryInstrument) -> InstrumentFile:
    """The instrument in the ``config/instrument.json`` format."""
    return InstrumentFile(
        notes=ARCHIVE_NOTE,
        version=str(instrument.version),
        content_hash=instrument.content_hash,
        global_negative_terms=[str(term) for term in instrument.global_negative_terms],
        max_requests_per_run=instrument.max_requests_per_run,
        queries=[QueryConfig.model_validate(query.as_canonical()) for query in instrument.queries],
    )


def dumps_instrument(instrument: QueryInstrument) -> str:
    """The archive file's text: two-space indent, UTF-8 characters, trailing newline."""
    data = instrument_document(instrument).model_dump(mode="json")
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def read_instrument_file(path: Path) -> QueryInstrument:
    """The instrument an archive file holds; its content hash must verify."""
    try:
        parsed = InstrumentFile.model_validate_json(path.read_text(encoding="utf-8"))
        instrument = build_instrument(parsed)
    except (OSError, UnicodeDecodeError, ValidationError, ValueError) as error:
        raise InstrumentFileError(f"{path}: not a valid instrument file: {error}") from error
    if not instrument.verify_hash():
        raise InstrumentFileError(
            f"{path}: content hash {instrument.content_hash} does not match the queries "
            f"({instrument.expected_hash()})"
        )
    if path.stem != instrument.version:
        raise InstrumentFileError(f"{path}: holds version {instrument.version}, not {path.stem}")
    return instrument


def archive_instrument(instrument: QueryInstrument, directory: Path) -> Path:
    """Write ``<directory>/<version>.json`` unless that version is already archived.

    An archived version with the same hash is left untouched; one with a
    different hash raises ``InstrumentFileError``.
    """
    path = directory / f"{instrument.version}.json"
    if path.exists():
        stored = read_instrument_file(path)
        if stored.content_hash != instrument.content_hash:
            raise InstrumentFileError(
                f"{path} already archives version {instrument.version} with hash "
                f"{stored.content_hash}; a changed instrument needs a new version"
            )
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps_instrument(instrument), encoding="utf-8")
    return path


def read_instrument_archives(directory: Path) -> tuple[QueryInstrument, ...]:
    """Every archived instrument under ``directory``, in file name order."""
    if not directory.is_dir():
        return ()
    return tuple(read_instrument_file(path) for path in sorted(directory.glob("*.json")))
