"""Server-rendered UI routes.

The panel is organised around fatura dönemleri (import batches): the home page
lists them, a period page lists its people and runs every action on them. All
POST actions redirect back with a one-line flash message.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
import logging
from pathlib import Path
import shutil
from typing import Any
from urllib.parse import parse_qsl, urlencode

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from invoice_automation.app.automation.session_manager import portal_session_manager
from invoice_automation.app.config import ROOT_DIR, ensure_runtime_directories, settings
from invoice_automation.app.constants import (
    AMOUNT_EDITABLE_STATUSES,
    BATCH_ELIGIBLE_STATUSES,
    RETRYABLE_STATUSES,
    InvoiceStatus,
    status_label,
    status_tone,
)
from invoice_automation.app.db.models import InvoiceRecord
from invoice_automation.app.db.repository import InvoiceRecordRepository
from invoice_automation.app.services.batch_job_service import batch_job_manager
from invoice_automation.app.services.cleanup_service import RecordCleanupService
from invoice_automation.app.schemas.invoice_record import PREVIEW_FIELDS, PreviewRow
from invoice_automation.app.services.import_service import (
    ImportService,
    check_preview_rows,
    normalize_column_name,
    summarize_preview,
)
from invoice_automation.app.services.record_edit_service import RecordEditService
from invoice_automation.app.services.selection_service import SelectionService
from invoice_automation.app.utils.exceptions import (
    BatchJobAlreadyRunningError,
    DeletionBlockedError,
    ImportValidationError,
    PortalSessionError,
    RecordEditBlockedError,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ui"])
templates = Jinja2Templates(directory=str(ROOT_DIR / "invoice_automation" / "app" / "templates"))

ELIGIBLE_STATUS_VALUES = frozenset(status.value for status in BATCH_ELIGIBLE_STATUSES)
RETRYABLE_STATUS_VALUES = frozenset(status.value for status in RETRYABLE_STATUSES)
AMOUNT_EDITABLE_STATUS_VALUES = frozenset(status.value for status in AMOUNT_EDITABLE_STATUSES)
STATUS_GROUPS = (
    ("waiting", "Bekliyor"),
    ("success", "Taslak oluştu"),
    ("failed", "Hatalı / atlandı"),
    ("review", "Kontrol gerekli"),
    ("progress", "İşleniyor"),
)


def status_group(status: str) -> str:
    """Bucket a status into the filter groups shown in the UI."""

    if status in ELIGIBLE_STATUS_VALUES:
        return "waiting"
    if status == InvoiceStatus.SUCCESS_DRAFT_CREATED:
        return "success"
    if status == InvoiceStatus.NEEDS_REVIEW:
        return "review"
    if status == InvoiceStatus.IN_PROGRESS:
        return "progress"
    return "failed"


templates.env.filters["status_label"] = status_label
templates.env.filters["status_tone"] = status_tone
templates.env.filters["status_group"] = status_group
templates.env.globals["RETRYABLE_STATUS_VALUES"] = RETRYABLE_STATUS_VALUES
templates.env.globals["STATUS_GROUPS"] = STATUS_GROUPS
templates.env.globals["AMOUNT_EDITABLE_STATUS_VALUES"] = AMOUNT_EDITABLE_STATUS_VALUES
# Changes with the stylesheet so browsers never keep a stale cached copy.
templates.env.globals["CSS_VERSION"] = int(
    (ROOT_DIR / "invoice_automation" / "app" / "static" / "css" / "app.css").stat().st_mtime
)


# --- Dönemler -----------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
def periods(request: Request) -> HTMLResponse:
    """List every fatura period with its record counts."""

    repository = InvoiceRecordRepository()
    return _render(
        request,
        "periods.html",
        summaries=repository.list_import_batch_summaries(),
        unassigned_count=repository.count_unassigned_records(),
        running_batch_id=_running_batch_id(),
    )


@router.get("/periods/{batch_id}", response_class=HTMLResponse, response_model=None)
def period(request: Request, batch_id: int) -> HTMLResponse | RedirectResponse:
    """Show the people of one period and every action on them."""

    repository = InvoiceRecordRepository()
    batch = repository.get_import_batch(batch_id)
    if batch is None:
        return _redirect("/", "Dönem bulunamadı.", error=True)

    records = repository.list_all(batch_id=batch_id, sort_by="id", sort_dir="asc")
    job = batch_job_manager.current_job()
    period_job = job if job is not None and job.batch_id == batch_id else None
    return _render(
        request,
        "period.html",
        batch=batch,
        records=records,
        counts=_group_counts(records),
        total_usd=sum(record.tutar_usd for record in records),
        job=period_job.to_dict() if period_job is not None else None,
        report=period_job.report if period_job is not None and not period_job.is_active else None,
        other_job_running=job is not None and job.is_active and period_job is None,
        session_ready=portal_session_manager.state.status == "READY",
    )


@router.post("/periods/{batch_id}/delete")
def delete_period(batch_id: int) -> RedirectResponse:
    """Delete a period and all of its records."""

    try:
        deleted = RecordCleanupService().delete_batch(batch_id)
    except DeletionBlockedError as exc:
        return _redirect(f"/periods/{batch_id}", str(exc), error=True)
    if deleted is None:
        return _redirect("/", "Dönem bulunamadı.", error=True)
    return _redirect("/", f"Dönem silindi ({deleted} kişi).")


@router.post("/periods/{batch_id}/records/delete")
def delete_period_records(
    batch_id: int,
    record_ids: list[int] | None = Form(default=None),
) -> RedirectResponse:
    """Delete the checked people of a period."""

    try:
        deleted = RecordCleanupService().delete_records(record_ids or [], batch_id=batch_id)
    except DeletionBlockedError as exc:
        return _redirect(f"/periods/{batch_id}", str(exc), error=True)
    return _redirect(f"/periods/{batch_id}", f"{deleted} kişi silindi.")


@router.post("/periods/{batch_id}/records/amount")
def update_period_amounts(
    batch_id: int,
    record_ids: list[int] | None = Form(default=None),
    amount: str = Form(default=""),
) -> RedirectResponse:
    """Give the checked people of a period one new amount."""

    target = f"/periods/{batch_id}"
    wanted = set(record_ids or [])
    if not wanted:
        return _redirect(target, "Kişi seçilmedi.", error=True)
    try:
        updated, shown = RecordEditService().update_amount(sorted(wanted), amount, batch_id=batch_id)
    except (ValueError, RecordEditBlockedError) as exc:
        return _redirect(target, str(exc), error=True)
    message = f"{updated} kişinin tutarı {shown} USD yapıldı."
    if updated < len(wanted):
        message += f" {len(wanted) - updated} kişi değişmedi (taslağı oluşmuş, işleniyor veya kontrol bekliyor)."
    return _redirect(target, message, error=updated == 0)


@router.post("/periods/{batch_id}/draft")
def start_drafts(
    batch_id: int,
    record_ids: list[int] | None = Form(default=None),
) -> RedirectResponse:
    """Select the checked people and start the background draft job."""

    target = f"/periods/{batch_id}"
    if portal_session_manager.state.status != "READY":
        return _redirect(target, "Portal oturumu hazır değil. Önce Portal sayfasından giriş yap.", error=True)
    if batch_job_manager.is_running():
        return _redirect(target, "Başka bir taslak işlemi çalışıyor.", error=True)

    repository = InvoiceRecordRepository()
    SelectionService(repository=repository).save_selection(record_ids or [], batch_id=batch_id)
    if not repository.list_selected_for_batch(batch_id=batch_id):
        return _redirect(target, "Seçilenler arasında taslak oluşturulabilecek kişi yok.", error=True)
    try:
        batch_job_manager.start(batch_id)
    except (BatchJobAlreadyRunningError, PortalSessionError) as exc:
        logger.warning("Batch job baslatilamadi | batch_id=%s error=%s", batch_id, exc)
        return _redirect(target, str(exc), error=True)
    return _redirect(target)


@router.post("/periods/{batch_id}/cancel")
def cancel_drafts(batch_id: int) -> RedirectResponse:
    """Stop the running job after the current person."""

    batch_job_manager.cancel()
    return _redirect(f"/periods/{batch_id}", "Durdurma istendi; işlenen kişi bitince duracak.")


@router.post("/unassigned/delete")
def delete_unassigned_records() -> RedirectResponse:
    """Delete records that belong to no period."""

    try:
        deleted = RecordCleanupService().delete_unassigned_records()
    except DeletionBlockedError as exc:
        return _redirect("/", str(exc), error=True)
    return _redirect("/", f"Döneme bağlı olmayan {deleted} kayıt silindi.")


# --- Tüm kayıtlar ---------------------------------------------------------------


@router.get("/records", response_class=HTMLResponse)
def all_records(
    request: Request,
    q: str = Query(default=""),
    group: str = Query(default=""),
    period: str = Query(default=""),
) -> HTMLResponse:
    """Search people across every period."""

    repository = InvoiceRecordRepository()
    batches = repository.list_import_batches(include_archived=True)
    period_id = int(period) if period.isdigit() else None
    records = repository.list_all(batch_id=period_id, search=q or None, sort_by="id", sort_dir="desc")
    if group:
        records = [record for record in records if status_group(record.islem_durumu) == group]
    return _render(
        request,
        "records.html",
        records=records,
        batches=batches,
        batch_names={batch.id: batch.name for batch in batches},
        q=q,
        group=group,
        period_id=period_id,
    )


@router.post("/records/{record_id}/retry")
def retry_record(record_id: int, next: str = Form(default="/")) -> RedirectResponse:
    """Return a failed record to Bekliyor so it can be processed again."""

    reset = InvoiceRecordRepository().reset_failed_to_pending([record_id])
    if not reset:
        return _redirect(next, "Bu kayıt tekrar denenemez.", error=True)
    return _redirect(next, "Kayıt tekrar Bekliyor durumuna alındı.")


@router.post("/records/{record_id}/review")
def review_record(
    record_id: int,
    draft_exists: str = Form(...),
    next: str = Form(default="/"),
) -> RedirectResponse:
    """Close a 'Kontrol gerekli' record after checking the portal by hand."""

    exists = draft_exists == "1"
    resolved = InvoiceRecordRepository().resolve_needs_review(record_id, draft_exists=exists)
    logger.info(
        "NEEDS_REVIEW kaydi manuel sonuclandirildi | record_id=%s draft_exists=%s resolved=%s",
        record_id,
        exists,
        resolved is not None,
    )
    if resolved is None:
        return _redirect(next, "Kayıt artık kontrol bekleyen durumda değil.", error=True)
    message = "Taslak oluştu olarak işaretlendi." if exists else "Kayıt tekrar Bekliyor durumuna alındı."
    return _redirect(next, message)


@router.post("/records/{record_id}/delete")
def delete_record(record_id: int, next: str = Form(default="/")) -> RedirectResponse:
    """Delete one record."""

    repository = InvoiceRecordRepository()
    record = repository.get(record_id)
    if record is None:
        return _redirect(next, "Kayıt bulunamadı.", error=True)
    try:
        deleted = RecordCleanupService(repository=repository).delete_records(
            [record_id], batch_id=record.batch_id
        )
    except DeletionBlockedError as exc:
        return _redirect(next, str(exc), error=True)
    if not deleted:
        return _redirect(next, "İşlenmekte olan kayıt silinemez.", error=True)
    return _redirect(next, f"{record.ad} {record.soyad} silindi.")


@router.post("/records/{record_id}/amount")
def update_record_amount(record_id: int, amount: str = Form(default="")) -> JSONResponse:
    """Change one person's amount from the period table (answers JSON)."""

    repository = InvoiceRecordRepository()
    record = repository.get(record_id)
    if record is None or record.batch_id is None:
        return JSONResponse({"error": "Kayıt bulunamadı."}, status_code=404)
    try:
        updated, shown = RecordEditService(repository=repository).update_amount(
            [record_id], amount, batch_id=record.batch_id
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except RecordEditBlockedError as exc:
        return JSONResponse({"error": str(exc)}, status_code=409)
    if not updated:
        return JSONResponse(
            {"error": "Bu kişinin tutarı artık değiştirilemez; sayfayı yenile."}, status_code=409
        )
    total = sum(item.tutar_usd for item in repository.list_all(batch_id=record.batch_id))
    return JSONResponse({"amount": shown, "total_usd": f"{total:.2f}"})


# --- Dosya yükleme --------------------------------------------------------------


@router.get("/upload", response_class=HTMLResponse)
def upload(request: Request) -> HTMLResponse:
    """Render the file upload form."""

    return _render(request, "upload.html", error=None)


@router.post("/import", response_class=HTMLResponse)
def import_records(request: Request, file: UploadFile = File(...)) -> HTMLResponse:
    """Receive a CSV/Excel file and show the sheet/column mapping form."""

    ensure_runtime_directories()
    saved_path = _save_upload(file)
    try:
        inspection = ImportService().inspect_file(saved_path)
        return _render_import_mapping(request, saved_path, inspection)
    except ImportValidationError as exc:
        error = str(exc)
        logger.info("Import rejected | file=%s error=%s", file.filename, error)
    except Exception:
        logger.exception("Unexpected import error | file=%s", file.filename)
        error = "Dosya okunamadı. Ayrıntı log dosyasında."
    return _render(request, "upload.html", error=error)


@router.post("/import/inspect", response_class=HTMLResponse)
def inspect_import_sheet(
    request: Request,
    saved_path: str = Form(...),
    sheet_name: str = Form(...),
    map_ad: str = Form(default=""),
    map_soyad: str = Form(default=""),
    map_tc_kimlik_no: str = Form(default=""),
    map_tutar_usd: str = Form(default=""),
    map_aciklama: str = Form(default=""),
) -> HTMLResponse:
    """Reload the mapping form for another sheet, or come back from the preview."""

    chosen = {
        "ad": map_ad,
        "soyad": map_soyad,
        "tc_kimlik_no": map_tc_kimlik_no,
        "tutar_usd": map_tutar_usd,
        "aciklama": map_aciklama,
    }
    try:
        file_path = _resolve_import_path(saved_path)
        inspection = ImportService().inspect_file(file_path, sheet_name=sheet_name)
        return _render_import_mapping(request, file_path, inspection, chosen)
    except ImportValidationError as exc:
        return _render(request, "upload.html", error=str(exc))


@router.post("/import/preview", response_class=HTMLResponse)
def preview_import(
    request: Request,
    saved_path: str = Form(...),
    sheet_name: str = Form(...),
    map_ad: str = Form(...),
    map_soyad: str = Form(...),
    map_tc_kimlik_no: str = Form(...),
    map_tutar_usd: str = Form(...),
    map_aciklama: str = Form(default=""),
) -> HTMLResponse:
    """Show the people of the sheet in an editable table. Nothing is saved yet."""

    mapping = {
        "ad": map_ad,
        "soyad": map_soyad,
        "tc_kimlik_no": map_tc_kimlik_no,
        "tutar_usd": map_tutar_usd,
        "aciklama": map_aciklama,
    }
    try:
        file_path = _resolve_import_path(saved_path)
        rows = ImportService().read_preview_rows(file_path, sheet_name=sheet_name, column_mapping=mapping)
    except ImportValidationError as exc:
        logger.info("Import preview rejected | file=%s error=%s", saved_path, exc)
        return _render(request, "upload.html", error=str(exc))
    except Exception:
        logger.exception("Unexpected import preview error | file=%s", saved_path)
        return _render(request, "upload.html", error="Dosya okunamadı. Ayrıntı log dosyasında.")
    return _render_import_preview(
        request,
        saved_path=file_path,
        sheet_name=sheet_name,
        mapping=mapping,
        batch_name="",
        rows=rows,
    )


class PreviewRowIn(BaseModel):
    """A preview row as the browser sends it."""

    values: dict[str, str] = {}
    source_row: int | None = None
    original: dict[str, str] | None = None
    removed: bool = False

    def to_row(self) -> PreviewRow:
        return PreviewRow(
            values={name: self.values.get(name, "") for name in PREVIEW_FIELDS},
            source_row=self.source_row,
            original={name: self.original.get(name, "") for name in PREVIEW_FIELDS}
            if self.original is not None
            else None,
            removed=self.removed,
        )


@router.post("/import/check")
def check_import_rows(rows: list[PreviewRowIn]) -> JSONResponse:
    """Check the preview table as it is being edited (same rules as the import)."""

    checked = check_preview_rows([row.to_row() for row in rows])
    return JSONResponse(
        {"rows": [row.to_dict() for row in checked], "summary": summarize_preview(checked)}
    )


@router.post("/import/confirm", response_class=HTMLResponse, response_model=None)
def confirm_import(
    request: Request,
    saved_path: str = Form(...),
    sheet_name: str = Form(...),
    batch_name: str = Form(default=""),
    rows_json: str = Form(...),
    map_ad: str = Form(default=""),
    map_soyad: str = Form(default=""),
    map_tc_kimlik_no: str = Form(default=""),
    map_tutar_usd: str = Form(default=""),
    map_aciklama: str = Form(default=""),
) -> HTMLResponse | RedirectResponse:
    """Create the period from the preview table exactly as the user left it."""

    mapping = {
        "ad": map_ad,
        "soyad": map_soyad,
        "tc_kimlik_no": map_tc_kimlik_no,
        "tutar_usd": map_tutar_usd,
        "aciklama": map_aciklama,
    }
    try:
        file_path = _resolve_import_path(saved_path)
        rows = [PreviewRowIn.model_validate(item).to_row() for item in json.loads(rows_json)]
    except (ImportValidationError, ValueError, TypeError) as exc:
        logger.warning("Import confirm rejected: bad form data | file=%s error=%s", saved_path, exc)
        return _render(request, "upload.html", error="Önizleme verisi okunamadı. Dosyayı tekrar yükle.")

    try:
        result = ImportService().import_preview_rows(
            rows,
            batch_name=batch_name,
            source_file_name=file_path.name,
            sheet_name=sheet_name,
        )
    except ImportValidationError as exc:
        error = str(exc)
    except Exception:
        logger.exception("Unexpected import confirm error | file=%s", saved_path)
        error = "İçe aktarılamadı, hiçbir kayıt yazılmadı. Ayrıntı log dosyasında."
    else:
        assert result.batch is not None
        return _redirect(f"/periods/{result.batch.id}", f"{result.imported_count} kişi içe aktarıldı.")

    # Nothing was written; show the same table again with the problem on top.
    return _render_import_preview(
        request,
        saved_path=file_path,
        sheet_name=sheet_name,
        mapping=mapping,
        batch_name=batch_name,
        rows=check_preview_rows(rows),
        error=error,
    )


# --- Portal oturumu ---------------------------------------------------------------


@router.get("/portal", response_class=HTMLResponse)
def portal(request: Request) -> HTMLResponse:
    """Render the portal session page."""

    return _render(request, "portal.html")


@router.post("/session/start")
def start_session() -> RedirectResponse:
    """Open the browser and fill in the login form."""

    return _session_action(portal_session_manager.start_login, "Portal girişi başlatılamadı")


@router.post("/session/verify")
def verify_session() -> RedirectResponse:
    """Check that manual 2FA is complete and the session is ready."""

    return _session_action(portal_session_manager.confirm_manual_2fa_completed, "Oturum doğrulanamadı")


@router.post("/session/close")
def close_session() -> RedirectResponse:
    """Close the browser."""

    return _session_action(portal_session_manager.close, "Tarayıcı kapatılamadı")


# --- Yardımcılar ------------------------------------------------------------------


def _render(request: Request, template: str, **context: Any) -> HTMLResponse:
    """Render a page with the shared header state and flash message."""

    return templates.TemplateResponse(
        request,
        template,
        {
            "portal_state": portal_session_manager.state,
            "flash": request.query_params.get("msg"),
            "flash_error": request.query_params.get("err") == "1",
            **context,
        },
    )


def _redirect(target: str, message: str | None = None, *, error: bool = False) -> RedirectResponse:
    """Redirect to a local path, keeping its query and adding an optional flash message."""

    # Only same-site paths; "//host" would leave the panel.
    if not target.startswith("/") or target.startswith("//"):
        target = "/"
    path, _, raw_query = target.partition("?")
    query = {key: value for key, value in parse_qsl(raw_query) if key not in {"msg", "err"}}
    if message:
        query["msg"] = message
        if error:
            query["err"] = "1"
    return RedirectResponse(url=f"{path}?{urlencode(query)}" if query else path, status_code=303)


def _session_action(action, failure_message: str) -> RedirectResponse:
    try:
        action()
    except PortalSessionError as exc:
        logger.exception(failure_message)
        return _redirect("/portal", f"{failure_message}: {exc}", error=True)
    return _redirect("/portal")


def _running_batch_id() -> int | None:
    job = batch_job_manager.current_job()
    return job.batch_id if job is not None and job.is_active else None


def _group_counts(records: list[InvoiceRecord]) -> dict[str, int]:
    counts = {key: 0 for key, _label in STATUS_GROUPS}
    for record in records:
        counts[status_group(record.islem_durumu)] += 1
    return counts


def _save_upload(file: UploadFile) -> Path:
    """Persist an uploaded file under data/imports with a timestamped name."""

    original_name = Path(file.filename or "import").name
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    saved_path = settings.import_dir / f"{timestamp}_{original_name}"

    with saved_path.open("wb") as output_file:
        shutil.copyfileobj(file.file, output_file)

    return saved_path


def _render_import_mapping(
    request: Request,
    saved_path: Path,
    inspection,
    chosen: dict[str, str] | None = None,
) -> HTMLResponse:
    """Render the mapping form for an uploaded import file."""

    if chosen and any(chosen.values()):
        # Coming back from the preview keeps the columns picked before.
        mapping = {field: column for field, column in chosen.items() if column in inspection.columns}
    else:
        mapping = _default_mapping(inspection.columns)
    return _render(
        request,
        "import_mapping.html",
        saved_path=str(saved_path),
        inspection=inspection,
        default_mapping=mapping,
    )


def _render_import_preview(
    request: Request,
    *,
    saved_path: Path,
    sheet_name: str,
    mapping: dict[str, str],
    batch_name: str,
    rows: list[PreviewRow],
    error: str | None = None,
) -> HTMLResponse:
    """Render the editable preview table."""

    return _render(
        request,
        "import_preview.html",
        saved_path=str(saved_path),
        display_name=saved_path.name.split("_", 1)[-1],
        sheet_name=sheet_name,
        mapping=mapping,
        batch_name=batch_name,
        show_aciklama=bool(mapping.get("aciklama")),
        rows=[row.to_dict() for row in rows],
        summary=summarize_preview(rows),
        error=error,
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
