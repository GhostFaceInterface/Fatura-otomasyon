"""Server-rendered UI routes."""

from __future__ import annotations

from datetime import UTC, datetime
import logging
from pathlib import Path
import shutil

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from invoice_automation.app.automation.session_manager import portal_session_manager
from invoice_automation.app.config import ROOT_DIR, ensure_runtime_directories, settings
from invoice_automation.app.constants import InvoiceStatus
from invoice_automation.app.db.repository import InvoiceRecordRepository
from invoice_automation.app.services.batch_service import BatchService
from invoice_automation.app.services.import_service import ImportService
from invoice_automation.app.services.selection_service import SelectionService
from invoice_automation.app.utils.exceptions import ImportValidationError, PortalSessionError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ui"])
templates = Jinja2Templates(directory=str(ROOT_DIR / "invoice_automation" / "app" / "templates"))


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    """Render the file upload page."""

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "result": None,
            "error": None,
        },
    )


@router.post("/import", response_class=HTMLResponse)
def import_records(request: Request, file: UploadFile = File(...)) -> HTMLResponse:
    """Receive a CSV/Excel file and import valid rows."""

    ensure_runtime_directories()
    saved_path = _save_upload(file)
    result = None
    error = None

    try:
        result = ImportService().import_file(saved_path)
    except ImportValidationError as exc:
        error = str(exc)
        logger.info("Import rejected | file=%s error=%s", file.filename, error)
    except Exception:
        logger.exception("Unexpected import error | file=%s", file.filename)
        error = "Dosya islenirken beklenmeyen bir hata olustu. Detaylar log dosyasina yazildi."

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "result": result,
            "error": error,
        },
    )


@router.get("/records", response_class=HTMLResponse)
def records(request: Request, status: str | None = Query(default=None)) -> HTMLResponse:
    """Render invoice records as a table."""

    repository = InvoiceRecordRepository()
    invoice_records = repository.list_all(status=status)
    statuses = [status_value.value for status_value in InvoiceStatus]
    selected_count = len(repository.list_selected())
    return templates.TemplateResponse(
        "records.html",
        {
            "request": request,
            "records": invoice_records,
            "selected_status": status,
            "statuses": statuses,
            "selected_count": selected_count,
            "selection_saved": request.query_params.get("selection_saved") == "1",
        },
    )


@router.post("/records/selection")
def save_selection(
    selected_record_ids: list[int] | None = Form(default=None),
) -> RedirectResponse:
    """Persist selected records from the records screen."""

    selected_records = SelectionService().save_selection(selected_record_ids or [])
    return RedirectResponse(
        url=f"/records?selection_saved=1&selected_count={len(selected_records)}",
        status_code=303,
    )


@router.get("/batch", response_class=HTMLResponse)
def batch(request: Request) -> HTMLResponse:
    """Render selected records prepared for batch processing."""

    preview = BatchService().preview()
    return templates.TemplateResponse(
        "batch.html",
        {
            "request": request,
            "preview": preview,
            "prepared": False,
        },
    )


@router.post("/batch/prepare", response_class=HTMLResponse)
def prepare_batch(request: Request) -> HTMLResponse:
    """Prepare selected records for the future automation batch."""

    preview = BatchService().prepare_selected_batch()
    return templates.TemplateResponse(
        "batch.html",
        {
            "request": request,
            "preview": preview,
            "prepared": True,
        },
    )


@router.get("/session", response_class=HTMLResponse)
def session(request: Request) -> HTMLResponse:
    """Render browser session management screen."""

    return templates.TemplateResponse(
        "session.html",
        {
            "request": request,
            "state": portal_session_manager.state,
            "error": None,
        },
    )


@router.post("/session/start", response_class=HTMLResponse)
def start_session(request: Request) -> HTMLResponse:
    """Start browser and advance login flow to the manual 2FA screen."""

    error = None
    try:
        state = portal_session_manager.start_login()
    except PortalSessionError as exc:
        logger.exception("Portal session start failed")
        state = portal_session_manager.state
        error = str(exc)

    return templates.TemplateResponse(
        "session.html",
        {
            "request": request,
            "state": state,
            "error": error,
        },
    )


@router.post("/session/verify", response_class=HTMLResponse)
def verify_session(request: Request) -> HTMLResponse:
    """Confirm that manual 2FA is complete and the session is ready."""

    error = None
    try:
        state = portal_session_manager.confirm_manual_2fa_completed()
    except PortalSessionError as exc:
        logger.exception("Portal session verification failed")
        state = portal_session_manager.state
        error = str(exc)

    return templates.TemplateResponse(
        "session.html",
        {
            "request": request,
            "state": state,
            "error": error,
        },
    )


@router.post("/session/close", response_class=HTMLResponse)
def close_session(request: Request) -> HTMLResponse:
    """Close the active browser session."""

    state = portal_session_manager.close()
    return templates.TemplateResponse(
        "session.html",
        {
            "request": request,
            "state": state,
            "error": None,
        },
    )


def _save_upload(file: UploadFile) -> Path:
    """Persist an uploaded file under data/imports with a timestamped name."""

    original_name = Path(file.filename or "import").name
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    saved_path = settings.import_dir / f"{timestamp}_{original_name}"

    with saved_path.open("wb") as output_file:
        shutil.copyfileobj(file.file, output_file)

    return saved_path
