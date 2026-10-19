"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from invoice_automation.app.automation.playwright_worker import playwright_worker
from invoice_automation.app.automation.session_manager import portal_session_manager
from invoice_automation.app.config import ROOT_DIR, settings
from invoice_automation.app.db.database import initialize_database
from invoice_automation.app.db.repository import InvoiceRecordRepository
from invoice_automation.app.logging_config import configure_logging
from invoice_automation.app.routes import api_routes, ui_routes
from invoice_automation.app.services.batch_job_service import batch_job_manager

logger = logging.getLogger(__name__)


def recover_interrupted_records() -> int:
    """Move records stuck IN_PROGRESS from a previous run to NEEDS_REVIEW."""

    recovered = InvoiceRecordRepository().recover_stale_in_progress()
    if recovered:
        logger.warning(
            "Yarida kalmis %s kayit NEEDS_REVIEW durumuna alindi; portalda manuel kontrol gerekli.",
            recovered,
        )
    return recovered


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Recover interrupted records on startup; release the browser on shutdown."""

    recover_interrupted_records()
    yield
    if batch_job_manager.is_running():
        batch_job_manager.cancel()
        logger.warning("Uygulama kapanirken calisan batch job icin durdurma istendi")
    else:
        try:
            portal_session_manager.close()
        except Exception:
            logger.exception("Uygulama kapanirken browser session kapatilamadi")
    playwright_worker.shutdown()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    configure_logging()
    initialize_database()

    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
    app.mount(
        "/static",
        StaticFiles(directory=str(ROOT_DIR / "invoice_automation" / "app" / "static")),
        name="static",
    )
    app.include_router(ui_routes.router)
    app.include_router(api_routes.router)
    return app


app = create_app()
