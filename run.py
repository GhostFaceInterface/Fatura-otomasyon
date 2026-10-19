"""Run the local FastAPI application."""

from invoice_automation.app.config import settings


if __name__ == "__main__":
    import uvicorn

    # Port 8000 is reserved on this machine; fall back to 8010 like scripts/start.sh.
    port = 8010 if settings.port == 8000 else settings.port
    uvicorn.run(
        "invoice_automation.app.main:app",
        host=settings.host,
        port=port,
        reload=settings.debug,
    )
