"""Renderers hold structure only: no literal heading or standing sentence in their source.

Every string constant in a renderer module that is not a docstring must be
shorter than three words, so the words a reader sees can only come from
``config/copy.json``.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[3] / "src" / "gwylio" / "dissemination"
RENDERERS = ("render_intsum.py", "render_strategic.py", "render_common.py")
_WORDS = re.compile(r"[A-Za-z]{2,}(?:\s+[A-Za-z]{2,}){2,}")


def _docstrings(tree: ast.Module) -> set[int]:
    found: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.FunctionDef | ast.ClassDef | ast.AsyncFunctionDef):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                found.add(id(body[0].value))
    # A bare string expression after an assignment documents a constant.
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            found.add(id(node.value))
    return found


def prose_in(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    skip = _docstrings(tree)
    return [
        f"{path.name}:{node.lineno}: {node.value!r}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in skip
        and _WORDS.search(node.value)
    ]


@pytest.mark.parametrize("name", RENDERERS)
def test_renderers_contain_no_literal_sentences(name: str) -> None:
    assert prose_in(SRC / name) == []


def test_the_checker_catches_a_literal_sentence(tmp_path: Path) -> None:
    path = tmp_path / "render_bad.py"
    path.write_text('"""Doc string is fine here."""\nHEADING = "What moved this month"\n')
    assert prose_in(path) == ["render_bad.py:2: 'What moved this month'"]
