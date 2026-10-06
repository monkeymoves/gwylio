"""Repository-wide check: no en dash (U+2013) or em dash (U+2014) in any text file.

Walks the project from the ``gwylio/`` root, skipping version control, virtual
environments, dependency folders, build output, caches, lock files and binary
files. The characters are built with ``chr()`` so this file stays clean.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
FORBIDDEN = {chr(0x2013): "U+2013 EN DASH", chr(0x2014): "U+2014 EM DASH"}
SKIP_DIRS = frozenset(
    {
        ".git",
        "node_modules",
        ".venv",
        "build",
        ".svelte-kit",
        "__pycache__",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        ".hypothesis",
        "test-results",
        "playwright-report",
    }
)
SKIP_FILES = frozenset({"uv.lock", "pnpm-lock.yaml"})
SNIFF_BYTES = 8192


def _text_files(root: Path) -> Iterator[Path]:
    for path in sorted(root.iterdir()):
        if path.is_symlink():
            continue
        if path.is_dir():
            if path.name not in SKIP_DIRS:
                yield from _text_files(path)
        elif path.is_file() and path.name not in SKIP_FILES:
            yield path


def _decode(path: Path) -> str | None:
    data = path.read_bytes()
    if b"\x00" in data[:SNIFF_BYTES]:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def find_dashes(root: Path) -> list[str]:
    """``file:line: NAME`` for every forbidden dash under ``root``."""
    problems: list[str] = []
    for path in _text_files(root):
        text = _decode(path)
        if text is None:
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            for char, name in FORBIDDEN.items():
                if char in line:
                    problems.append(f"{path.relative_to(root)}:{number}: {name}")
    return problems


def test_project_root_is_the_gwylio_directory() -> None:
    assert (PROJECT_ROOT / "backend" / "pyproject.toml").is_file()
    assert (PROJECT_ROOT / "docs" / "PLAN.md").is_file()


def test_no_en_or_em_dashes_anywhere_in_the_project() -> None:
    problems = find_dashes(PROJECT_ROOT)
    assert not problems, "forbidden dashes found:\n" + "\n".join(problems)


def test_checker_finds_dashes_and_skips_what_it_should(tmp_path: Path) -> None:
    (tmp_path / "bad.md").write_text("fine\nnot " + chr(0x2014) + " fine\n", encoding="utf-8")
    (tmp_path / "ok.txt").write_text("plain - hyphen\n", encoding="utf-8")
    (tmp_path / "uv.lock").write_text(chr(0x2013), encoding="utf-8")
    (tmp_path / "image.png").write_bytes(b"\x89PNG\x00\x00" + chr(0x2013).encode())
    hidden = tmp_path / "node_modules" / "pkg"
    hidden.mkdir(parents=True)
    (hidden / "readme.md").write_text(chr(0x2013), encoding="utf-8")
    assert find_dashes(tmp_path) == ["bad.md:2: U+2014 EM DASH"]
