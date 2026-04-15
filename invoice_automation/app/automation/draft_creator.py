"""Single-record e-Arsiv draft creation orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import logging

from invoice_automation.app.automation.error_detector import PortalErrorDetector
from invoice_automation.app.automation.invoice_form_filler import InvoiceFormData, InvoiceFormFiller
from invoice_automation.app.automation.portal_navigation import EArchiveNavigation
from invoice_automation.app.automation.portal_selectors import PortalSelectors, portal_selectors
from invoice_automation.app.config import settings
from invoice_automation.app.constants import InvoiceStatus
from invoice_automation.app.db.models import InvoiceRecord
from invoice_automation.app.utils.exceptions import DraftCreationError, ElementNotFoundError, PortalTimeoutError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DraftCreationResult:
    """Result of a single-record draft creation attempt."""

    record_id: int
    status: InvoiceStatus
    message: str
    portal_ref_no: str | None = None


class DraftCreator:
    """Create one e-Arsiv draft using an already authenticated page."""

    def __init__(
        self,
        navigation: EArchiveNavigation | None = None,
        form_filler: InvoiceFormFiller | None = None,
        error_detector: PortalErrorDetector | None = None,
        selectors: PortalSelectors = portal_selectors,
        timeout_ms: int | None = None,
    ) -> None:
        self.navigation = navigation or EArchiveNavigation(selectors=selectors, timeout_ms=timeout_ms)
        self.form_filler = form_filler or InvoiceFormFiller(selectors=selectors, timeout_ms=timeout_ms)
        self.error_detector = error_detector or PortalErrorDetector()
        self.selectors = selectors
        self.timeout_ms = timeout_ms or settings.playwright_timeout_ms

    def create_draft(self, page: Any, record: InvoiceRecord) -> DraftCreationResult:
        """Create a draft invoice for exactly one record."""

        logger.info(
            "Tek kayit taslak olusturma basladi | record_id=%s tc=%s",
            record.id,
            record.tc_kimlik_no,
        )
        self.navigation.open_create_invoice_page(page)
        self.error_detector.raise_if_portal_error(page, stage="navigation")

        form_data = InvoiceFormData.from_record(record)
        self.form_filler.fill_form(page, form_data)
        self.error_detector.raise_if_portal_error(page, stage="form_fill")

        self._save_draft(page)
        self.error_detector.raise_if_portal_error(page, stage="save_draft")

        logger.info("Taslak kaydetme tamamlandi | record_id=%s", record.id)
        return DraftCreationResult(
            record_id=record.id,
            status=InvoiceStatus.SUCCESS_DRAFT_CREATED,
            message="Taslak fatura olusturuldu.",
        )

    def _save_draft(self, page: Any) -> None:
        try:
            button = page.get_by_role("button", name=self.selectors.save_draft_button_name)
            button.wait_for(state="visible", timeout=self.timeout_ms)
            button.click(timeout=self.timeout_ms)
            self._wait_after_save(page)
        except ElementNotFoundError:
            raise
        except Exception as exc:
            raise PortalTimeoutError(f"Taslak kaydet butonuna basilamadi: {exc}") from exc

    def _wait_after_save(self, page: Any) -> None:
        try:
            page.wait_for_load_state("networkidle", timeout=5_000)
        except Exception:
            try:
                page.wait_for_timeout(1_000)
            except Exception as exc:
                raise DraftCreationError(f"Taslak kayit sonrasi bekleme basarisiz: {exc}") from exc
