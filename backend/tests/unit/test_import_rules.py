"""The dependency rule, enforced over the source tree with the ``ast`` module.

- ``gwylio.shared`` imports no other gwylio package.
- A context package imports only ``gwylio.shared`` and itself.
- ``infrastructure``, ``cli`` and ``api`` may import contexts.
- No context imports ``infrastructure``, ``cli`` or ``api``.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"
PACKAGE = "gwylio"
SHARED = "shared"
CONTEXTS = frozenset(
    {
        "reference",
        "direction",
        "collection",
        "processing",
        "intelligence",
        "dissemination",
        "evaluation",
    }
)
OUTER = frozenset({"infrastructure", "cli", "api"})


@dataclass(frozen=True)
class Violation:
    file: str
    line: int
    importer: str
    imported: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line}: {self.importer} must not import gwylio.{self.imported}"


def _module_name(path: Path, src: Path) -> str:
    parts = list(path.relative_to(src).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _resolve_relative(module: str, is_package: bool, level: int, target: str | None) -> str:
    base = module.split(".")
    if not is_package:
        base = base[:-1]
    if level > 1:
        base = base[: len(base) - (level - 1)]
    return ".".join([*base, target] if target else base)


def _imported_modules(tree: ast.AST, module: str, is_package: bool) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = (
                _resolve_relative(module, is_package, node.level, node.module)
                if node.level
                else node.module or ""
            )
            if base == PACKAGE:
                # ``from gwylio import shared`` names subpackages directly.
                found.extend((node.lineno, f"{PACKAGE}.{alias.name}") for alias in node.names)
            else:
                found.append((node.lineno, base))
    return found


def _allowed(importer_top: str, imported_top: str) -> bool:
    if importer_top == imported_top:
        return True
    if importer_top == SHARED:
        return False
    if importer_top in CONTEXTS:
        return imported_top == SHARED
    return True  # infrastructure, cli, api and the package root may import contexts


def find_violations(src: Path) -> list[Violation]:
    """Every import in ``src/gwylio`` that breaks the dependency rule."""
    violations: list[Violation] = []
    for path in sorted((src / PACKAGE).rglob("*.py")):
        module = _module_name(path, src)
        parts = module.split(".")
        if len(parts) < 2:
            continue  # the package root carries no rule
        importer_top = parts[1]
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        is_package = path.name == "__init__.py"
        for line, imported in _imported_modules(tree, module, is_package):
            imported_parts = imported.split(".")
            if imported_parts[0] != PACKAGE or len(imported_parts) < 2:
                continue
            imported_top = imported_parts[1]
            if not _allowed(importer_top, imported_top):
                violations.append(
                    Violation(
                        str(path.relative_to(src)), line, f"gwylio.{importer_top}", imported_top
                    )
                )
    return violations


def test_every_planned_package_exists() -> None:
    for name in sorted({SHARED} | CONTEXTS | OUTER):
        assert (SRC / PACKAGE / name / "__init__.py").is_file(), f"missing package gwylio.{name}"


def test_source_tree_obeys_the_dependency_rule() -> None:
    violations = find_violations(SRC)
    assert not violations, "dependency rule broken:\n" + "\n".join(map(str, violations))


def _write(root: Path, relative: str, body: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


@pytest.mark.parametrize(
    ("relative", "body", "expected"),
    [
        ("gwylio/shared/x.py", "import gwylio.collection\n", "collection"),
        ("gwylio/shared/x.py", "from gwylio import direction\n", "direction"),
        ("gwylio/collection/x.py", "from gwylio.intelligence.model import R\n", "intelligence"),
        (
            "gwylio/collection/x.py",
            "from gwylio.infrastructure.http import client\n",
            "infrastructure",
        ),
        ("gwylio/collection/x.py", "from ..infrastructure import sqlite\n", "infrastructure"),
        ("gwylio/collection/sub/x.py", "from ...cli import main\n", "cli"),
        ("gwylio/evaluation/__init__.py", "from ..api import app\n", "api"),
        ("gwylio/reference/x.py", "def f():\n    import gwylio.api\n", "api"),
    ],
)
def test_checker_catches_violations(
    tmp_path: Path, relative: str, body: str, expected: str
) -> None:
    _write(tmp_path, relative, body)
    violations = find_violations(tmp_path)
    assert [v.imported for v in violations] == [expected]


@pytest.mark.parametrize(
    ("relative", "body"),
    [
        ("gwylio/shared/x.py", "from gwylio.shared.values import CleanText\nimport json\n"),
        ("gwylio/collection/x.py", "from gwylio.shared import values\nfrom . import ports\n"),
        ("gwylio/collection/sub/x.py", "from ..ports import Collector\n"),
        ("gwylio/infrastructure/x.py", "from gwylio.collection.ports import Collector\n"),
        ("gwylio/cli/x.py", "from gwylio.infrastructure.sqlite import db\nimport gwylio.api\n"),
        ("gwylio/api/x.py", "from gwylio.intelligence import model\n"),
    ],
)
def test_checker_allows_legal_imports(tmp_path: Path, relative: str, body: str) -> None:
    _write(tmp_path, relative, body)
    assert find_violations(tmp_path) == []
