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
from invoice_automation.app.schemas.batch import BatchPreview
from invoice_automation.app.services.batch_service import BatchService
from invoice_automation.app.services.draft_service import SingleDraftService
from invoice_automation.app.services.import_service import ImportService, normalize_column_name
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
            "batches": InvoiceRecordRepository().list_import_batches(),
        },
    )


@router.post("/import", response_class=HTMLResponse)
def import_records(request: Request, file: UploadFile = File(...)) -> HTMLResponse:
    """Receive a CSV/Excel file and show sheet/mapping options."""

    ensure_runtime_directories()
    saved_path = _save_upload(file)
    error = None

    try:
        inspection = ImportService().inspect_file(saved_path)
        return _render_import_mapping(request, saved_path, inspection)
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
            "result": None,
            "error": error,
            "batches": InvoiceRecordRepository().list_import_batches(),
        },
    )


@router.post("/import/inspect", response_class=HTMLResponse)
def inspect_import_sheet(
    request: Request,
    saved_path: str = Form(...),
    sheet_name: str = Form(...),
) -> HTMLResponse:
    """Reload mapping form for the selected sheet."""

    error = None
    try:
        file_path = _resolve_import_path(saved_path)
        inspection = ImportService().inspect_file(file_path, sheet_name=sheet_name)
        return _render_import_mapping(request, file_path, inspection)
    except ImportValidationError as exc:
        error = str(exc)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "result": None,
            "error": error,
            "batches": InvoiceRecordRepository().list_import_batches(),
        },
    )


@router.post("/import/confirm", response_class=HTMLResponse)
def confirm_import(
    request: Request,
    saved_path: str = Form(...),
    sheet_name: str = Form(...),
    batch_name: str = Form(...),
    map_ad: str = Form(...),
    map_soyad: str = Form(...),
    map_tc_kimlik_no: str = Form(...),
    map_tutar_usd: str = Form(...),
    map_aciklama: str = Form(default=""),
) -> HTMLResponse:
    """Import the selected sheet using explicit column mapping and batch name."""

    result = None
    error = None
    try:
        file_path = _resolve_import_path(saved_path)
        result = ImportService().import_file(
            file_path,
            batch_name=batch_name,
            sheet_name=sheet_name,
            column_mapping={
                "ad": map_ad,
                "soyad": map_soyad,
                "tc_kimlik_no": map_tc_kimlik_no,
                "tutar_usd": map_tutar_usd,
                "aciklama": map_aciklama,
            },
        )
    except ImportValidationError as exc:
        error = str(exc)
        logger.info("Mapped import rejected | file=%s error=%s", saved_path, error)
    except Exception:
        logger.exception("Unexpected mapped import error | file=%s", saved_path)
        error = "Dosya islenirken beklenmeyen bir hata olustu. Detaylar log dosyasina yazildi."

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "result": result,
            "error": error,
            "batches": InvoiceRecordRepository().list_import_batches(),
        },
    )


@router.get("/records", response_class=HTMLResponse)
def records(request: Request, status: str | None = Query(default=None)) -> HTMLResponse:
    """Render invoice records as a table."""

    repository = InvoiceRecordRepository()
    active_batch = _active_batch(repository, request.query_params.get("batch_id"))
    active_batch_id = active_batch.id if active_batch else None
    invoice_records = (
        repository.list_all(status=status, batch_id=active_batch_id)
        if active_batch_id is not None
        else []
    )
    statuses = [status_value.value for status_value in InvoiceStatus]
    selected_count = len(repository.list_selected(batch_id=active_batch_id))
    return templates.TemplateResponse(
        "records.html",
        {
            "request": request,
            "records": invoice_records,
            "batches": repository.list_import_batches(),
            "active_batch": active_batch,
            "selected_status": status,
            "statuses": statuses,
            "selected_count": selected_count,
            "selection_saved": request.query_params.get("selection_saved") == "1",
        },
    )


@router.post("/records/selection")
def save_selection(
    batch_id: int = Form(...),
    selected_record_ids: list[int] | None = Form(default=None),
) -> RedirectResponse:
    """Persist selected records from the records screen."""

    selected_records = SelectionService().save_selection(selected_record_ids or [], batch_id=batch_id)
    return RedirectResponse(
        url=f"/records?batch_id={batch_id}&selection_saved=1&selected_count={len(selected_records)}",
        status_code=303,
    )


@router.get("/batch", response_class=HTMLResponse)
def batch(request: Request) -> HTMLResponse:
    """Render selected records prepared for batch processing."""

    repository = InvoiceRecordRepository()
    active_batch = _active_batch(repository, request.query_params.get("batch_id"))
    active_batch_id = active_batch.id if active_batch else None
    preview = (
        BatchService(repository=repository).preview(batch_id=active_batch_id)
        if active_batch_id is not None
        else _empty_batch_preview()
    )
    return templates.TemplateResponse(
        "batch.html",
        {
            "request": request,
            "preview": preview,
            "batches": repository.list_import_batches(),
            "active_batch": active_batch,
            "prepared": False,
            "report": None,
        },
    )


@router.post("/batch/prepare", response_class=HTMLResponse)
def prepare_batch(request: Request, batch_id: int = Form(...)) -> HTMLResponse:
    """Prepare selected records for the future automation batch."""

    repository = InvoiceRecordRepository()
    active_batch = repository.get_import_batch(batch_id)
    preview = BatchService(repository=repository).prepare_selected_batch(batch_id=batch_id)
    return templates.TemplateResponse(
        "batch.html",
        {
            "request": request,
            "preview": preview,
            "batches": repository.list_import_batches(),
            "active_batch": active_batch,
            "prepared": True,
            "report": None,
        },
    )


@router.post("/batch/run", response_class=HTMLResponse)
def run_batch(request: Request, batch_id: int = Form(...)) -> HTMLResponse:
    """Run selected eligible records through the Phase 6 batch flow."""

    repository = InvoiceRecordRepository()
    active_batch = repository.get_import_batch(batch_id)
    batch_service = BatchService(repository=repository)
    report = batch_service.run_selected_batch(batch_id=batch_id)
    preview = batch_service.preview(batch_id=batch_id)
    return templates.TemplateResponse(
        "batch.html",
        {
            "request": request,
            "preview": preview,
            "batches": repository.list_import_batches(),
            "active_batch": active_batch,
            "prepared": False,
            "report": report,
        },
    )


@router.get("/draft", response_class=HTMLResponse)
def draft(request: Request) -> HTMLResponse:
    """Render single-record draft creation POC screen."""

    repository = InvoiceRecordRepository()
    selected_records = repository.list_selected()
    records = selected_records or repository.list_all()
    return templates.TemplateResponse(
        "draft.html",
        {
            "request": request,
            "records": records,
            "using_selected_records": bool(selected_records),
            "result": None,
            "error": None,
        },
    )


@router.post("/draft/create", response_class=HTMLResponse)
def create_single_draft(request: Request, record_id: int = Form(...)) -> HTMLResponse:
    """Run Phase 4 POC for one selected record."""

    repository = InvoiceRecordRepository()
    result = None
    error = None
    try:
        result = SingleDraftService(repository=repository).create_for_record(record_id)
    except ValueError as exc:
        error = str(exc)
        logger.info("Draft POC rejected | record_id=%s error=%s", record_id, error)

    selected_records = repository.list_selected()
    records = selected_records or repository.list_all()
    return templates.TemplateResponse(
        "draft.html",
        {
            "request": request,
            "records": records,
            "using_selected_records": bool(selected_records),
            "result": result,
            "error": error,
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


def _render_import_mapping(request: Request, saved_path: Path, inspection) -> HTMLResponse:
    """Render the mapping form for an uploaded import file."""

    return templates.TemplateResponse(
        "import_mapping.html",
        {
            "request": request,
            "saved_path": str(saved_path),
            "inspection": inspection,
            "default_mapping": _default_mapping(inspection.columns),
            "required_fields": ("ad", "soyad", "tc_kimlik_no", "tutar_usd"),
            "optional_fields": ("aciklama",),
        },
    )


def _default_mapping(columns: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for column in columns:
        normalized = normalize_column_name(column)
        if normalized in {"ad", "soyad", "tc_kimlik_no", "tutar_usd", "aciklama"}:
            mapping.setdefault(normalized, column)
    return mapping


def _resolve_import_path(saved_path: str) -> Path:
    """Resolve a hidden import path and ensure it stays under the import directory."""

    candidate = Path(saved_path)
    if not candidate.is_absolute():
        candidate = settings.import_dir / candidate.name
    resolved = candidate.resolve()
    import_root = settings.import_dir.resolve()
    if resolved != import_root and import_root not in resolved.parents:
        raise ImportValidationError("Gecersiz import dosya yolu.")
    return resolved


def _active_batch(repository: InvoiceRecordRepository, raw_batch_id: str | None):
    if raw_batch_id:
        try:
            return repository.get_import_batch(int(raw_batch_id))
        except ValueError:
            return None
    return repository.latest_import_batch()


def _empty_batch_preview() -> BatchPreview:
    return BatchPreview(total_selected=0, total_amount_usd=0.0, status_counts={}, records=[])
