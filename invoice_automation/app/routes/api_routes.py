"""JSON API routes for health checks and records."""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from invoice_automation.app.automation.session_manager import portal_session_manager
from invoice_automation.app.db.repository import InvoiceRecordRepository
from invoice_automation.app.services.batch_job_service import batch_job_manager
from invoice_automation.app.services.batch_service import BatchService
from invoice_automation.app.services.draft_service import SingleDraftService
from invoice_automation.app.utils.exceptions import BatchJobAlreadyRunningError, PortalSessionError

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/health")
def health() -> dict[str, str]:
    """Return a basic health response."""

    return {"status": "ok"}


@router.get("/records")
def list_records(
    status: str | None = Query(default=None),
    batch_id: int | None = Query(default=None),
    q: str | None = Query(default=None),
    sort_by: str = Query(default="id"),
    sort_dir: str = Query(default="desc"),
) -> dict[str, object]:
    """Return invoice records as JSON."""

    repository = InvoiceRecordRepository()
    records = repository.list_all(
        status=status,
        batch_id=batch_id,
        search=q,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return {
        "count": len(records),
        "records": [record.to_dict() for record in records],
    }


@router.get("/batch/preview")
def batch_preview(batch_id: int | None = Query(default=None)) -> dict[str, object]:
    """Return the current batch preparation preview."""

    return BatchService().preview(batch_id=batch_id).to_dict()


@router.post("/batch/run", response_model=None)
def run_batch(batch_id: int | None = Query(default=None)) -> dict[str, object] | JSONResponse:
    """Start the batch as a background job; poll ``/api/batch/job`` for progress."""

    try:
        job = batch_job_manager.start(batch_id)
    except (BatchJobAlreadyRunningError, PortalSessionError) as exc:
        return JSONResponse(
            status_code=409,
            content={"ok": False, "error": str(exc), "job": batch_job_manager.status()},
        )
    return {"ok": True, "job": job}


@router.get("/batch/job")
def batch_job_status() -> dict[str, object]:
    """Return progress of the active or most recent batch job."""

    return {"job": batch_job_manager.status()}


@router.post("/batch/cancel")
def cancel_batch() -> dict[str, object]:
    """Request cancellation of the running batch job between records."""

    return {"ok": batch_job_manager.cancel(), "job": batch_job_manager.status()}


@router.post("/records/{record_id}/retry")
def retry_failed_record(record_id: int) -> dict[str, object]:
    """Consciously return a retryable failed record to PENDING."""

    repository = InvoiceRecordRepository()
    reset = repository.reset_failed_to_pending([record_id]) == 1
    record = repository.get(record_id)
    return {"ok": reset, "record": record.to_dict() if record else None}


@router.post("/records/{record_id}/review")
def resolve_review_record(record_id: int, draft_exists: bool = Query(...)) -> dict[str, object]:
    """Close a NEEDS_REVIEW record after checking the portal manually."""

    repository = InvoiceRecordRepository()
    resolved = repository.resolve_needs_review(record_id, draft_exists=draft_exists)
    record = resolved or repository.get(record_id)
    return {"ok": resolved is not None, "record": record.to_dict() if record else None}


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

    try:
        return {"ok": True, "state": portal_session_manager.close().to_dict()}
    except PortalSessionError as exc:
        return {"ok": False, "error": str(exc), "state": portal_session_manager.state.to_dict()}


@router.post("/draft/create")
def create_single_draft(record_id: int = Query(...)) -> dict[str, object]:
    """Create one draft invoice using the ready portal session."""

    try:
        result = SingleDraftService().create_for_record(record_id)
        return result.to_dict()
    except (ValueError, PortalSessionError) as exc:
        return {"ok": False, "error_code": exc.__class__.__name__, "message": str(exc)}
