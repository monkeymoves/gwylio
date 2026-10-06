"""Firebase Hosting configuration and the deploy target (ADR 0001, docs/DEPLOY.md).

``firebase.json`` serves the static build with clean URLs, never caches the
snapshot, caches hashed assets for a year and serves product Markdown as
text/markdown. The project id is the owner's, so no ``.firebaserc`` is
committed. ``make deploy`` refuses with a clear line before publishing when
the Firebase command line tool is missing.
"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest

from tests.support import PROJECT_ROOT

pytestmark = pytest.mark.integration


def hosting() -> dict[str, Any]:
    config: dict[str, Any] = json.loads(
        (PROJECT_ROOT / "firebase.json").read_text(encoding="utf-8")
    )
    hosting_config: dict[str, Any] = config["hosting"]
    return hosting_config


def headers_for(source: str) -> dict[str, str]:
    rules = [rule for rule in hosting()["headers"] if rule["source"] == source]
    assert len(rules) == 1, source
    return {header["key"]: header["value"] for header in rules[0]["headers"]}


def test_hosting_serves_the_static_build_with_clean_urls() -> None:
    config = hosting()
    assert config["public"] == "frontend/build"
    assert config["cleanUrls"] is True
    assert config["trailingSlash"] is False
    assert "firebase.json" in config["ignore"]
    assert "rewrites" not in config  # every page is prerendered; no single-page fallback


def test_the_snapshot_is_never_cached_and_hashed_assets_are_cached_for_a_year() -> None:
    assert headers_for("/data/**") == {"Cache-Control": "no-cache"}
    assert headers_for("/_app/immutable/**") == {
        "Cache-Control": "public, max-age=31536000, immutable"
    }


def test_product_markdown_is_served_as_markdown() -> None:
    assert headers_for("/products/*.md")["Content-Type"] == "text/markdown; charset=utf-8"


def test_no_project_id_is_committed() -> None:
    assert not (PROJECT_ROOT / ".firebaserc").exists()


def test_make_deploy_checks_for_firebase_before_publishing() -> None:
    makefile = (PROJECT_ROOT / "Makefile").read_text(encoding="utf-8")
    match = re.search(r"^deploy:.*\n((?:\t.*\n?)+)", makefile, re.MULTILINE)
    assert match is not None
    lines = [line.strip() for line in match.group(1).splitlines()]
    assert lines[0].startswith("@command -v firebase")
    assert "the firebase command is missing" in lines[0]
    assert lines[1:] == [
        "$(UV) gwylio publish",
        "$(PNPM) build",
        "firebase deploy --only hosting",
    ]
