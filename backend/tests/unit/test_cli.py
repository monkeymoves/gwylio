"""Smoke tests for the Typer command line application."""

from __future__ import annotations

from typer.testing import CliRunner

from gwylio.cli.main import app, package_version

runner = CliRunner()


def test_version_prints_the_package_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == package_version()
    assert package_version() == "0.1.0"


def test_help_lists_the_version_command() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "version" in result.stdout
