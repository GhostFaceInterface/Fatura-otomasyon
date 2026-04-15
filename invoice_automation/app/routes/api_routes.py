"""JSON API routes for health checks and records."""

from __future__ import annotations

from fastapi import APIRouter, Query

from invoice_automation.app.automation.session_manager import portal_session_manager
from invoice_automation.app.db.repository import InvoiceRecordRepository
from invoice_automation.app.services.batch_service import BatchService
from invoice_automation.app.services.draft_service import SingleDraftService
from invoice_automation.app.utils.exceptions import PortalSessionError

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


@router.post("/batch/run")
def run_batch() -> dict[str, object]:
    """Run selected eligible records and return the batch report."""

    return BatchService().run_selected_batch().to_dict()


@router.get("/session/status")
def session_status() -> dict[str, str | None]:
    """Return current browser session status."""

    return portal_session_manager.state.to_dict()


@router.post("/session/start")
def start_session() -> dict[str, object]:
    """Start browser login flow and wait until manual 2FA is required."""

    try:
        state = portal_session_manager.start_login()
        return {"ok": True, "state": state.to_dict()}
    except PortalSessionError as exc:
        return {"ok": False, "error": str(exc), "state": portal_session_manager.state.to_dict()}


@router.post("/session/verify")
def verify_session() -> dict[str, object]:
    """Verify that manual 2FA completed and session is ready."""

    try:
        state = portal_session_manager.confirm_manual_2fa_completed()
        return {"ok": True, "state": state.to_dict()}
    except PortalSessionError as exc:
        return {"ok": False, "error": str(exc), "state": portal_session_manager.state.to_dict()}


@router.post("/session/close")
def close_session() -> dict[str, object]:
    """Close active browser session."""

    return {"ok": True, "state": portal_session_manager.close().to_dict()}


@router.post("/draft/create")
def create_single_draft(record_id: int = Query(...)) -> dict[str, object]:
    """Create one draft invoice using the ready portal session."""

    try:
        result = SingleDraftService().create_for_record(record_id)
        return result.to_dict()
    except ValueError as exc:
        return {"ok": False, "error_code": exc.__class__.__name__, "message": str(exc)}
