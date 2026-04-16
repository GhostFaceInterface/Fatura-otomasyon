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
from invoice_automation.app.constants import EARCHIVE_DRAFTS_PATH, EARCHIVE_DRAFTS_SUCCESS_TEXTS, InvoiceStatus
from invoice_automation.app.db.models import InvoiceRecord
from invoice_automation.app.utils.exceptions import DraftCreationError, ElementNotFoundError, PortalTimeoutError
from invoice_automation.app.utils.screenshots import capture_error_screenshot

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
        self.redirect_timeout_ms = settings.redirect_wait_timeout_ms

    def create_draft(self, page: Any, record: InvoiceRecord) -> DraftCreationResult:
        """Create a draft invoice for exactly one record."""

        logger.info(
            "Tek kayit taslak olusturma basladi | record_id=%s tc=%s",
            record.id,
            record.tc_kimlik_no,
        )
        self.navigation.open_create_invoice_page(page)
        self.error_detector.raise_if_portal_error(page, stage="navigation", record_id=record.id)

        form_data = InvoiceFormData.from_record(record)
        self.form_filler.fill_form(
            page,
            form_data,
            after_turmob_lookup=lambda: self.error_detector.raise_if_portal_error(
                page,
                stage="turmob_lookup",
                record_id=record.id,
            ),
        )
        self.error_detector.raise_if_portal_error(page, stage="form_fill", record_id=record.id)

        self._click_save_draft(page)
        self._wait_after_save(page)
        self.error_detector.raise_if_portal_error(page, stage="save_draft", record_id=record.id)
        self._wait_for_success_redirect(page, record.id)

        logger.info("Taslak kaydetme tamamlandi | record_id=%s", record.id)
        return DraftCreationResult(
            record_id=record.id,
            status=InvoiceStatus.SUCCESS_DRAFT_CREATED,
            message="Taslak fatura olusturuldu.",
        )

    def _click_save_draft(self, page: Any) -> None:
        try:
            button = page.get_by_role("button", name=self.selectors.save_draft_button_name)
            button.wait_for(state="visible", timeout=self.timeout_ms)
            button.click(timeout=self.timeout_ms)
        except ElementNotFoundError:
            raise
        except Exception as exc:
            raise PortalTimeoutError(f"Taslak kaydet butonuna basilamadi: {exc}") from exc

    def _wait_after_save(self, page: Any) -> None:
        try:
            page.wait_for_timeout(settings.draft_save_wait_ms)
            logger.info("Taslak kaydet sonrasi bekleme tamamlandi | wait_ms=%s", settings.draft_save_wait_ms)
        except Exception:
            logger.debug("Taslak kaydet sonrasi bekleme basarisiz", exc_info=True)

    def _wait_for_success_redirect(self, page: Any, record_id: int) -> None:
        try:
            page.wait_for_url(f"**{EARCHIVE_DRAFTS_PATH}*", timeout=self.redirect_timeout_ms)
            logger.info("Taslak redirect dogrulandi | record_id=%s path=%s", record_id, EARCHIVE_DRAFTS_PATH)
        except Exception as exc:
            self.error_detector.raise_if_portal_error(
                page,
                stage="draft_redirect_wait",
                record_id=record_id,
            )
            if self._has_drafts_page_success_signal(page):
                logger.info(
                    "Taslak sayfasi ikincil basari sinyaliyle dogrulandi | record_id=%s",
                    record_id,
                )
                return
            screenshot_path = capture_error_screenshot(page, record_id, "draft_redirect_timeout")
            raise PortalTimeoutError(
                f"Taslak kayit sonrasi {EARCHIVE_DRAFTS_PATH} redirect'i gelmedi.",
                stage="draft_redirect_wait",
                screenshot_path=screenshot_path,
            ) from exc

    def _has_drafts_page_success_signal(self, page: Any) -> bool:
        for text in EARCHIVE_DRAFTS_SUCCESS_TEXTS:
            if self._is_text_visible(page, text):
                return True
            if self._is_heading_visible(page, text):
                return True
        return False

    def _is_text_visible(self, page: Any, text: str) -> bool:
        try:
            page.get_by_text(text).wait_for(state="visible", timeout=2_000)
            return True
        except Exception:
            return False

    def _is_heading_visible(self, page: Any, text: str) -> bool:
        try:
            page.get_by_role("heading", name=text).wait_for(state="visible", timeout=2_000)
            return True
        except Exception:
            return False
