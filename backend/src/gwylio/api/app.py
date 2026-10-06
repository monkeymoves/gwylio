"""The read API: GET-only routes under ``/api/v1`` serving the snapshot's documents.

A local development and analyst tool (ADR 0001): production is the static
site reading the published snapshot. Every route returns a read model built
by ``ReadModels`` and serialised by ``to_jsonable``, exactly as ``gwylio
publish`` writes it, so the front end can switch between the snapshot and
this API without noticing.

One dependency provides the database for each request: the settings
database, opened for the request and closed after it, or a database handed
to ``create_app`` (the tests hand in the seed, rebuilt in memory). The
configuration is loaded once. Unknown ids answer 404 with a JSON body
(``{"detail": "no report 'x'"}``); a missing or unmigrated database answers
503. CORS allows the Vite dev and preview origins. The OpenAPI document is at
``/api/v1/openapi.json`` and ``gwylio schema`` writes it to
``docs/schema/openapi.json``.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from typing import Annotated, Final

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from gwylio.api.schemas import (
    Coverage,
    DateCheck,
    Enums,
    Meta,
    Picture,
    ProductDetail,
    ProductSummary,
    ReportDetail,
    ReportSummary,
    RequirementSetDetail,
    RequirementSetSummary,
    RunDetail,
    RunSummary,
    SourcesHealth,
    SourceSummary,
)
from gwylio.infrastructure.config.loaders import ConfigInvalidError, LoadedConfig, load_config
from gwylio.infrastructure.config.settings import Settings
from gwylio.infrastructure.readmodels import NotFound, ReadModels, ReportFilter, app_version
from gwylio.infrastructure.snapshot import API_PREFIX, Document, database_ready, to_jsonable
from gwylio.infrastructure.sqlite.db import Database
from gwylio.shared.clock import Clock, SystemClock
from gwylio.shared.vocabulary import Bucket, Credibility, Direction, IndicatorState, Reliability

__all__ = ["DEV_ORIGINS", "create_app"]

DEV_ORIGINS: Final[tuple[str, ...]] = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
)
"""The Vite dev server and preview origins the API answers cross-origin requests from."""


@dataclass
class _AppState:
    """What every request shares: settings, the clock, an optional database and the config."""

    settings: Settings | None
    clock: Clock
    database: Database | None
    _config: LoadedConfig | None = field(default=None, init=False)

    def resolved_settings(self) -> Settings:
        if self.settings is None:
            self.settings = Settings.load()
        return self.settings

    def config(self) -> LoadedConfig:
        if self._config is None:
            try:
                self._config = load_config(self.resolved_settings().config_root)
            except ConfigInvalidError as error:
                raise HTTPException(
                    status_code=503,
                    detail=f"configuration is invalid, run `gwylio check`: {error}",
                ) from error
        return self._config


def _models(request: Request) -> Iterator[ReadModels]:
    state: _AppState = request.app.state.gwylio
    config = state.config()
    settings = state.resolved_settings()
    if state.database is not None:
        yield ReadModels(state.database, config, clock=state.clock, data_dir=settings.data_dir)
        return
    path = settings.db_path
    if not path.is_file():
        raise HTTPException(status_code=503, detail=f"no database at {path}; run gwylio rebuild")
    db = Database.open(path, check_same_thread=False)
    try:
        if not database_ready(db):
            raise HTTPException(
                status_code=503, detail=f"the database at {path} needs gwylio migrate"
            )
        yield ReadModels(db, config, clock=state.clock, data_dir=settings.data_dir)
    finally:
        db.close()


Models = Annotated[ReadModels, Depends(_models)]


def _json(document: Document) -> JSONResponse:
    return JSONResponse(content=to_jsonable(document))


router = APIRouter(prefix=API_PREFIX)


@router.get("/meta", response_model=Meta, summary="When and from what the data was built")
def get_meta(models: Models) -> JSONResponse:
    """meta.json: when and from what the data was built, and how much it holds."""
    return _json(models.meta())


@router.get("/meta/enums", response_model=Enums, summary="Every closed vocabulary")
def get_enums(models: Models) -> JSONResponse:
    """enums.json: every closed vocabulary with labels and meanings."""
    return _json(models.enums())


@router.get(
    "/requirement-sets",
    response_model=list[RequirementSetSummary],
    summary="Every requirement set",
)
def get_requirement_sets(models: Models) -> JSONResponse:
    """requirement_sets.json: every configured requirement set, the default first."""
    return _json(models.requirement_sets())


@router.get(
    "/requirement-sets/{set_id}",
    response_model=RequirementSetDetail,
    summary="One requirement set",
)
def get_requirement_set(set_id: str, models: Models) -> JSONResponse:
    """requirement_set_<id>.json: one requirement set with requirements and groups."""
    return _json(models.requirement_set(set_id))


@router.get(
    "/requirement-sets/{set_id}/picture",
    response_model=Picture,
    summary="One requirement set's picture",
)
def get_picture(set_id: str, models: Models) -> JSONResponse:
    """picture_<set>.json: tiles per group and requirement, and the date check counts."""
    return _json(models.picture(set_id))


@router.get("/reports", response_model=list[ReportSummary], summary="The register, filtered")
def get_reports(
    models: Models,
    set_id: Annotated[
        str | None, Query(alias="set", description="Assessed against this requirement set.")
    ] = None,
    requirement: Annotated[
        str | None, Query(description="Assessed against this requirement id.")
    ] = None,
    direction: Annotated[
        Direction | None,
        Query(description="An assessment in this direction (on the requirement or set if given)."),
    ] = None,
    state: IndicatorState | None = None,
    bucket: Bucket | None = None,
    lane: str | None = None,
    hazard: str | None = None,
    place: str | None = None,
    topic: str | None = None,
    since: Annotated[
        date | None, Query(description="Latest history entry on or after this date.")
    ] = None,
    q: Annotated[str | None, Query(description="Text in the title or summary.")] = None,
    reliability: Reliability | None = None,
    credibility: Credibility | None = None,
) -> JSONResponse:
    """reports.json: every report, by id; with filters, only those that pass every one."""
    report_filter = ReportFilter(
        set_id=set_id,
        requirement=requirement,
        direction=direction,
        state=state,
        bucket=bucket,
        lane=lane,
        hazard=hazard,
        place=place,
        topic=topic,
        since=since,
        q=q,
        reliability=reliability,
        credibility=credibility,
    )
    return _json(models.reports(report_filter))


@router.get("/reports/{report_id}", response_model=ReportDetail, summary="One report")
def get_report(report_id: str, models: Models) -> JSONResponse:
    """reports/<id>.json: one report with assessments, tags, sightings and history."""
    return _json(models.report(report_id))


@router.get("/sources", response_model=list[SourceSummary], summary="The watchlist and yield")
def get_sources(models: Models) -> JSONResponse:
    """sources.json: every watched source with its yield, in watchlist order."""
    return _json(models.sources())


@router.get("/sources/health", response_model=SourcesHealth, summary="Funnel trend and silence")
def get_sources_health(models: Models) -> JSONResponse:
    """sources_health.json: the funnel trend over recent runs and the silent sources."""
    return _json(models.sources_health())


@router.get(
    "/sources/{source_id}/yield", response_model=SourceSummary, summary="One source's yield"
)
def get_source_yield(source_id: str, models: Models) -> JSONResponse:
    """One watched source with its yield (the matching entry of sources.json)."""
    return _json(models.source(source_id))


@router.get("/scan-runs", response_model=list[RunSummary], summary="Every scan run")
def get_runs(models: Models) -> JSONResponse:
    """runs.json: every stored scan run, oldest first."""
    return _json(models.runs())


@router.get("/scan-runs/{run_id}", response_model=RunDetail, summary="One scan run")
def get_run(run_id: str, models: Models) -> JSONResponse:
    """runs/<id>.json: one run's funnel, shares, dispositions and credibility spread."""
    return _json(models.run(run_id))


@router.get("/coverage/{set_id}", response_model=Coverage, summary="The coverage audit")
def get_coverage(set_id: str, models: Models) -> JSONResponse:
    """coverage_<set>.json: requirements by lane and taxonomy nodes by count, with the legend."""
    return _json(models.coverage(set_id))


@router.get("/datecheck", response_model=DateCheck, summary="The verification queue")
def get_datecheck(models: Models) -> JSONResponse:
    """datecheck.json: every date check finding, grouped by kind."""
    return _json(models.datecheck())


@router.get("/products", response_model=list[ProductSummary], summary="Every product")
def get_products(models: Models) -> JSONResponse:
    """products.json: every recorded product, by id."""
    return _json(models.products())


@router.get("/products/{product_id}", response_model=ProductDetail, summary="One product")
def get_product(product_id: str, models: Models) -> JSONResponse:
    """products/<id>.json: one product's sections and its Markdown."""
    return _json(models.product(product_id))


def _not_found(request: Request, error: Exception) -> JSONResponse:
    message = error.message if isinstance(error, NotFound) else str(error)
    return JSONResponse(status_code=404, content={"detail": message})


def create_app(
    settings: Settings | None = None,
    *,
    clock: Clock | None = None,
    database: Database | None = None,
) -> FastAPI:
    """The read API over ``settings`` (default: loaded from the environment on first use).

    ``clock`` stamps ``generated_at`` and dates the date check (default: the
    system clock). ``database`` serves every request from one open database
    instead of opening the settings database per request; it must allow use
    from any thread.
    """
    app = FastAPI(
        title="Gwylio read API",
        version=app_version(),
        description=(
            "Read-only development and analyst API serving the same JSON documents as the "
            "published snapshot."
        ),
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
    )
    app.state.gwylio = _AppState(settings, clock or SystemClock(), database)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(DEV_ORIGINS),
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    app.add_exception_handler(NotFound, _not_found)
    app.include_router(router)
    return app
