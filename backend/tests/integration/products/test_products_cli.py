"""``gwylio product``: the INTSUM on the seed, the strategic assessment on the legacy register."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from gwylio.dissemination.model import TACTICAL_MESSAGE
from gwylio.infrastructure.adapters import funnel_trend, run_dispositions
from gwylio.infrastructure.config.loaders import LoadedConfig
from gwylio.infrastructure.sqlite.db import Database
from gwylio.infrastructure.sqlite.repositories import SqliteProductRepository, dump_table
from gwylio.shared.vocabulary import DispositionOutcome
from tests.integration.products.conftest import TODAY, Cli

pytestmark = pytest.mark.integration

DASHES = (chr(0x2013), chr(0x2014))
OCTOBER = ("product", "--level", "operational", "--period", "2026-10", "--today", TODAY)
STRATEGIC = ("product", "--level", "strategic", "--period", "2026", "--today", TODAY)


def section(text: str, heading: str) -> list[str]:
    """The non-empty lines under one heading, up to the next heading of any depth."""
    lines = text.splitlines()
    start = lines.index(heading) + 1
    found: list[str] = []
    for line in lines[start:]:
        if line.startswith("#"):
            break
        if line:
            found.append(line)
    return found


def test_the_intsum_renders_on_the_seed(seeded: Cli, data: Path) -> None:
    result = seeded(*OCTOBER)
    assert result.exit_code == 0, result.output
    markdown = data / "products" / "operational_2026-10.md"
    record = data / "products" / "operational_2026-10.json"
    export = data / "exports" / "products.json"
    assert result.stdout.splitlines()[0] == str(markdown)
    assert f"wrote  {record}" in result.stdout and f"wrote  {export}" in result.stdout
    text = markdown.read_text(encoding="utf-8")
    assert text.startswith("# Operational intelligence summary (INTSUM), October 2026\n")
    for heading in (
        "## Summary",
        "## What moved",
        "## Quiet and blind spots",
        "## Verification due",
        "## Method note",
    ):
        assert heading in text.splitlines()
    assert not any(dash in text for dash in DASHES)
    products = json.loads(export.read_text(encoding="utf-8"))["products"]
    assert [p["id"] for p in products] == ["operational-2026-10"]
    assert products[0]["markdown_file"] == "operational_2026-10.md"


def test_threats_come_before_supports_within_each_list(seeded: Cli, data: Path) -> None:
    assert seeded(*OCTOBER).exit_code == 0
    text = (data / "products" / "operational_2026-10.md").read_text(encoding="utf-8")
    rank = {"threatens": 0, "two-way": 1, "informs the baseline": 2, "supports": 3}
    headings = [line for line in text.splitlines() if line.startswith("### ") and "(SI" in line]
    assert len(headings) == 3
    for heading in headings:
        lines = section(text, heading)
        assert lines, heading
        worst = []
        for line in lines:
            tags = re.search(r"\[(.*)\]", line)
            assert tags is not None, line
            worst.append(min(rank[t.split(" ", 1)[1]] for t in tags.group(1).split(", ")))
        assert worst == sorted(worst), heading
    nature = section(text, "### Nature is Recovering (SI1, SI2, SI3)")
    assert nature[0].endswith("[SI1 threatens] (tracking)")
    assert "[SI1 supports, SI2 supports]" in nature[-1]


def test_quiet_and_blind_spots_on_the_seed(seeded: Cli, data: Path) -> None:
    assert seeded(*OCTOBER).exit_code == 0
    text = (data / "products" / "operational_2026-10.md").read_text(encoding="utf-8")
    lines = section(text, "## Quiet and blind spots")
    assert lines[0].startswith("A blind spot is not quiet.")
    assert "- SI12 NRW colleague engagement: blind spot this period." in "\n".join(lines)
    assert "- SI3 Nature recovery in public services: quiet this period." in "\n".join(lines)


def test_rendering_twice_with_the_same_clock_is_byte_identical(seeded: Cli, data: Path) -> None:
    files = ("products/operational_2026-10.md", "products/operational_2026-10.json")
    assert seeded(*OCTOBER).exit_code == 0
    first = {name: (data / name).read_bytes() for name in (*files, "exports/products.json")}
    assert seeded(*OCTOBER).exit_code == 0
    second = {name: (data / name).read_bytes() for name in (*files, "exports/products.json")}
    assert first == second


def test_the_method_note_reconciles_with_the_runs(
    seeded: Cli, data: Path, shipped_config: LoadedConfig
) -> None:
    assert seeded(*OCTOBER).exit_code == 0
    record = json.loads((data / "products" / "operational_2026-10.json").read_text("utf-8"))
    method = next(s for s in record["sections"] if s["heading"] == "Method note")
    runs_table = method["tables"][0]
    with Database.open(data / "gwylio.sqlite") as db:
        trend = funnel_trend(db)
        outcomes = run_dispositions(db)
    october = [run for run in trend.runs if run.started_at.month == 10]
    assert [row[0] for row in runs_table["rows"]] == [run.run_id for run in october]
    assert [int(row[3]) for row in runs_table["rows"]] == [run.funnel.raw for run in october]
    summary = trend.disposition_summary(october[0].run_id, outcomes[october[0].run_id])
    counts = dict(summary.counts)
    assert (
        f"promoted {counts[DispositionOutcome.PROMOTED]}, "
        f"rejected {counts[DispositionOutcome.REJECTED]}"
    ) in method["body"][1]
    assert method["body"][3] == (
        f"Instrument version used by the period's runs: {shipped_config.instrument.version}."
    )


def test_a_product_survives_a_rebuild(seeded: Cli, data: Path) -> None:
    assert seeded(*OCTOBER).exit_code == 0
    export = (data / "exports" / "products.json").read_bytes()
    with Database.open(data / "gwylio.sqlite") as db:
        before = {t: dump_table(db, t) for t in ("product", "product_report")}
    rebuilt = seeded("rebuild")
    assert rebuilt.exit_code == 0, rebuilt.output
    assert "1 product and" in rebuilt.stdout
    with Database.open(data / "gwylio.sqlite") as db:
        after = {t: dump_table(db, t) for t in ("product", "product_report")}
        [stored] = SqliteProductRepository(db).all()
    assert before == after and before["product"]
    assert stored.markdown_file == "operational_2026-10.md"
    assert seeded("export").exit_code == 0
    assert (data / "exports" / "products.json").read_bytes() == export


def test_a_corrupt_product_file_stops_a_rebuild(seeded: Cli, data: Path) -> None:
    assert seeded(*OCTOBER).exit_code == 0
    path = data / "products" / "operational_2026-10.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["markdown_file"] = "elsewhere.md"
    path.write_text(json.dumps(document), encoding="utf-8")
    result = seeded("rebuild")
    assert result.exit_code == 1
    assert "names elsewhere.md, not operational_2026-10.md" in result.stderr


def test_tactical_exits_4_with_the_seam_message(seeded: Cli, data: Path) -> None:
    result = seeded("product", "--level", "tactical")
    assert result.exit_code == 4
    assert result.stderr.strip() == TACTICAL_MESSAGE
    assert not (data / "products").exists()


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("--level", "operational", "--period", "2026"), "an operational period is a month"),
        (("--level", "strategic", "--period", "2026-10"), "a strategic period is a year"),
        (("--level", "operational", "--set", "nope"), "no requirement set 'nope'"),
        (("--level", "operational", "--today", "6 October"), "not a YYYY-MM-DD date"),
    ],
)
def test_bad_arguments_exit_2(seeded: Cli, args: tuple[str, ...], message: str) -> None:
    result = seeded("product", *args)
    assert result.exit_code == 2
    assert message in result.stderr


def test_the_strategic_assessment_renders_on_the_legacy_register(legacy: Cli, data: Path) -> None:
    result = legacy(*STRATEGIC)
    assert result.exit_code == 0, result.output
    text = (data / "products" / "strategic_2026.md").read_text(encoding="utf-8")
    assert text.startswith(
        "# Strategic assessment, 2026: NRW corporate plan performance framework\n"
    )
    questions = [line for line in text.splitlines() if line.startswith("- What would change")]
    assert questions, "the legacy register holds threatening reports"
    template = re.compile(r"- What would change for (SI\d+)(, SI\d+)* if this holds: .+\?")
    assert all(template.fullmatch(q) for q in questions), questions
    for heading in (
        "## Questions for each well-being objective",
        "### Nature is Recovering (SI1, SI2, SI3)",
        "### Communities are Resilient to Climate Change (SI6, SI7, SI8, SI10)",
        "### Pollution is Minimised (SI4, SI5)",
        "## Coverage audit",
        "### Requirements by lane",
        "### Taxonomy: SoNaRR ecosystems and resources",
        "### Taxonomy: Hazard families",
    ):
        assert heading in text.splitlines(), heading
    assert "| Requirement | Welsh Government | Senedd |" in text
    assert "| SI12 NRW colleague engagement | 0 |" in text
    assert text.count("| Node | Requirements expecting it | Active reports | Status |") == 2
    assert not any(dash in text for dash in DASHES)
    note = section(text, "## Method note")
    assert note[0].startswith("No scan run started in the period")
    assert note[1].startswith("Reports created in the period: 35, of which")


def test_the_legacy_intsum_for_its_import_month_lists_every_objective(
    legacy: Cli, data: Path
) -> None:
    result = legacy("product", "--level", "operational", "--period", "2026-07", "--today", TODAY)
    assert result.exit_code == 0, result.output
    text = (data / "products" / "operational_2026-07.md").read_text(encoding="utf-8")
    assert "New reports created in the period: 35." in text
    assert "Nothing moved against this objective" not in text
