"""Service layer for Phase 4 single-record draft creation."""

from __future__ import annotations

import logging

from invoice_automation.app.automation.draft_creator import DraftCreator
from invoice_automation.app.automation.session_manager import (
    PortalSessionManager,
    PortalSessionStatus,
    portal_session_manager,
)
from invoice_automation.app.constants import InvoiceStatus
from invoice_automation.app.db.repository import InvoiceRecordRepository
from invoice_automation.app.schemas.draft import SingleDraftServiceResult
from invoice_automation.app.utils.exceptions import (
    DraftAutomationError,
    DraftCreationError,
    EFaturaMukellefiError,
    ElementNotFoundError,
    InvalidTCKNError,
    NameMismatchError,
    PortalTimeoutError,
    SessionLostError,
    TurmobServiceError,
    UnknownPortalError,
)
from invoice_automation.app.utils.screenshots import capture_error_screenshot

logger = logging.getLogger(__name__)


class SingleDraftService:
    """Create one draft invoice using the existing authenticated session."""

    def __init__(
        self,
        repository: InvoiceRecordRepository | None = None,
        session_manager: PortalSessionManager = portal_session_manager,
        draft_creator: DraftCreator | None = None,
    ) -> None:
        self.repository = repository or InvoiceRecordRepository()
        self.session_manager = session_manager
        self.draft_creator = draft_creator or DraftCreator()

    def create_for_record(self, record_id: int) -> SingleDraftServiceResult:
        """Create a draft for one invoice record and persist the outcome."""

        record = self.repository.get(record_id)
        if record is None:
            raise ValueError(f"Kayit bulunamadi: {record_id}")

        logger.info("Tek kayit draft servisi basladi | record_id=%s", record_id)
        self.repository.update_processing_state(record_id, InvoiceStatus.IN_PROGRESS)

        try:
            page = self._ready_page()
            draft_result = self.draft_creator.create_draft(page, record)
            updated_record = self.repository.update_processing_state(
                record_id,
                draft_result.status,
                portal_ref_no=draft_result.portal_ref_no,
                hata_kodu=None,
                hata_mesaji=None,
                secili_mi=False,
            )
            logger.info("Tek kayit draft basarili | record_id=%s", record_id)
            return SingleDraftServiceResult(
                ok=True,
                record=updated_record,
                message=draft_result.message,
            )
        except Exception as exc:
            status = self._status_for_exception(exc)
            error_code = exc.__class__.__name__
            screenshot_path = getattr(exc, "screenshot_path", None)
            stage = getattr(exc, "stage", None) or "draft_service_error"
            if screenshot_path is None:
                page = self.session_manager.browser_manager.page
                if page is not None:
                    screenshot_path = capture_error_screenshot(page, record_id, stage)
            updated_record = self.repository.update_processing_state(
                record_id,
                status,
                hata_kodu=error_code,
                hata_mesaji=str(exc),
                secili_mi=True,
            )
            logger.exception(
                "Tek kayit draft basarisiz | record_id=%s tc=%s status=%s error_code=%s stage=%s screenshot=%s",
                record_id,
                record.tc_kimlik_no,
                status.value,
                error_code,
                stage,
                screenshot_path,
            )
            return SingleDraftServiceResult(
                ok=False,
                record=updated_record,
                message=str(exc),
                error_code=error_code,
                screenshot_path=screenshot_path,
            )

    def _ready_page(self):
        page = self.session_manager.browser_manager.page
        if page is None:
            raise SessionLostError("Aktif browser session bulunamadi.")
        if self.session_manager.state.status != PortalSessionStatus.READY:
            raise SessionLostError("Portal session READY degil. Once /session ekraninda 2FA onayi yapin.")
        return page

    def _status_for_exception(self, exc: Exception) -> InvoiceStatus:
        if isinstance(exc, InvalidTCKNError):
            return InvoiceStatus.FAILED_INVALID_TCKN
        if isinstance(exc, NameMismatchError):
            return InvoiceStatus.FAILED_NAME_MISMATCH
        if isinstance(exc, TurmobServiceError):
            return InvoiceStatus.FAILED_TURMOB_SERVICE_ERROR
        if isinstance(exc, EFaturaMukellefiError):
            return InvoiceStatus.SKIPPED_EFATURA_MUKELLEFI
        if isinstance(exc, (PortalTimeoutError, ElementNotFoundError)):
            return InvoiceStatus.FAILED_PORTAL_TIMEOUT
        if isinstance(exc, SessionLostError):
            return InvoiceStatus.ABORTED_SESSION_LOST
        if isinstance(exc, (UnknownPortalError, DraftCreationError, DraftAutomationError)):
            return InvoiceStatus.FAILED_UNKNOWN
        return InvoiceStatus.FAILED_UNKNOWN
