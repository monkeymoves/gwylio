"""Entry point for the ``gwylio`` command line tool.

Only the ``version`` command exists in WP0; later work packages add one module
per verb and register it here.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

import typer

app = typer.Typer(
    name="gwylio",
    help="Gwylio: a Welsh environmental open-source intelligence (OSINT) system.",
    no_args_is_help=True,
    add_completion=False,
)


def package_version() -> str:
    """The installed version of the ``gwylio`` distribution."""
    try:
        return version("gwylio")
    except PackageNotFoundError:  # pragma: no cover, only when run from a bare checkout
        return "0.0.0+unknown"


@app.callback()
def main() -> None:
    """Gwylio: a Welsh environmental open-source intelligence (OSINT) system."""


@app.command("version")
def version_command() -> None:
    """Print the package version."""
    typer.echo(package_version())


if __name__ == "__main__":  # pragma: no cover
    app()
