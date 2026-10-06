"""``data/instruments/<version>.json``: every instrument version a run used, archived once."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gwylio.infrastructure.config.loaders import LoadedConfig
from gwylio.infrastructure.handoff.instrument_file import (
    InstrumentFileError,
    archive_instrument,
    dumps_instrument,
    read_instrument_archives,
    read_instrument_file,
)
from tests.support import PROJECT_ROOT, instrument, query

pytestmark = pytest.mark.integration


def test_an_archive_round_trips_in_the_config_format(
    shipped_config: LoadedConfig, tmp_path: Path
) -> None:
    path = archive_instrument(shipped_config.instrument, tmp_path)
    assert path == tmp_path / f"{shipped_config.instrument.version}.json"
    assert read_instrument_file(path) == shipped_config.instrument
    archived = json.loads(path.read_text(encoding="utf-8"))
    shipped = json.loads((PROJECT_ROOT / "config/instrument.json").read_text(encoding="utf-8"))
    for key in ("version", "content_hash", "global_negative_terms", "max_requests_per_run"):
        assert archived[key] == shipped[key]
    assert [q["id"] for q in archived["queries"]] == [q["id"] for q in shipped["queries"]]
    assert path.read_text(encoding="utf-8") == dumps_instrument(shipped_config.instrument)


def test_a_version_is_archived_once_and_never_replaced(tmp_path: Path) -> None:
    first = instrument(query("q1"), version="2026.10.0")
    path = archive_instrument(first, tmp_path)
    stamp = path.stat().st_mtime_ns
    assert archive_instrument(first, tmp_path) == path
    assert path.stat().st_mtime_ns == stamp
    with pytest.raises(InstrumentFileError, match="needs a new version"):
        archive_instrument(instrument(query("q2"), version="2026.10.0"), tmp_path)
    second = instrument(query("q2"), version="2026.11.0")
    archive_instrument(second, tmp_path)
    assert read_instrument_archives(tmp_path) == (first, second)
    assert read_instrument_archives(tmp_path / "missing") == ()


def test_a_tampered_or_misnamed_archive_is_refused(tmp_path: Path) -> None:
    path = archive_instrument(instrument(query("q1")), tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["queries"][0]["text"] = "something else"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(InstrumentFileError, match="does not match the queries"):
        read_instrument_file(path)
    renamed = tmp_path / "2026.12.0.json"
    archive_instrument(instrument(query("q1"), version="2026.11.0"), tmp_path).rename(renamed)
    with pytest.raises(InstrumentFileError, match=r"holds version 2026\.11\.0"):
        read_instrument_file(renamed)
    (tmp_path / "broken.json").write_text("{", encoding="utf-8")
    with pytest.raises(InstrumentFileError, match="not a valid instrument file"):
        read_instrument_file(tmp_path / "broken.json")
