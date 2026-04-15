"""Run the local FastAPI application."""

from invoice_automation.app.config import settings


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "invoice_automation.app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
