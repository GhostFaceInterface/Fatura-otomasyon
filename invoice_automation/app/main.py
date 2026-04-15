"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from invoice_automation.app.config import ROOT_DIR, settings
from invoice_automation.app.db.database import initialize_database
from invoice_automation.app.logging_config import configure_logging
from invoice_automation.app.routes import api_routes, ui_routes


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    configure_logging()
    initialize_database()

    app = FastAPI(title=settings.app_name, debug=settings.debug)
    app.mount(
        "/static",
        StaticFiles(directory=str(ROOT_DIR / "invoice_automation" / "app" / "static")),
        name="static",
    )
    app.include_router(ui_routes.router)
    app.include_router(api_routes.router)
    return app


app = create_app()
