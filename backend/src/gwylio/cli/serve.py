"""``gwylio serve``: run the read API locally with uvicorn.

The API is a development and analyst tool (ADR 0001); production is the
static site reading the published snapshot. The API reads the settings
database on every request, so ``gwylio rebuild``, ``ingest`` or ``product``
show up on the next request without a restart. Ctrl+C stops it.
"""

from __future__ import annotations

import typer
import uvicorn

from gwylio.api.app import create_app
from gwylio.cli.common import load
from gwylio.infrastructure.config.settings import Settings
from gwylio.infrastructure.snapshot import API_PREFIX

__all__ = ["DEFAULT_HOST", "DEFAULT_PORT", "run_serve"]

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def run_serve(settings: Settings, *, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> int:
    """Serve the read API until interrupted; return the exit code."""
    if load(settings.config_root, "serve") is None:
        return 1
    if not settings.db_path.is_file():
        typer.echo(
            f"serve: no database at {settings.db_path} yet; requests answer 503 until "
            "`gwylio rebuild` creates it",
            err=True,
        )
    typer.echo(f"serve: http://{host}:{port}{API_PREFIX}/meta (docs at {API_PREFIX}/docs)")
    uvicorn.run(create_app(settings), host=host, port=port, log_level="info")
    return 0
