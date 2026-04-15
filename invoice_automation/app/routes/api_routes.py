"""JSON API routes for health checks and records."""

from __future__ import annotations

from fastapi import APIRouter, Query

from invoice_automation.app.db.repository import InvoiceRecordRepository
from invoice_automation.app.services.batch_service import BatchService

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/health")
def health() -> dict[str, str]:
    """Return a basic health response."""

    return {"status": "ok"}


@router.get("/records")
def list_records(status: str | None = Query(default=None)) -> dict[str, object]:
    """Return invoice records as JSON."""

    repository = InvoiceRecordRepository()
    records = repository.list_all(status=status)
    return {
        "count": len(records),
        "records": [record.to_dict() for record in records],
    }


@router.get("/batch/preview")
def batch_preview() -> dict[str, object]:
    """Return the current batch preparation preview."""

    return BatchService().preview().to_dict()
