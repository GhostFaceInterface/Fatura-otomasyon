"""Fill the e-Arsiv invoice form for a single local record."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import logging

from invoice_automation.app.automation.portal_selectors import PortalSelectors, portal_selectors
from invoice_automation.app.config import settings
from invoice_automation.app.db.models import InvoiceRecord
from invoice_automation.app.utils.exceptions import ElementNotFoundError, PortalTimeoutError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InvoiceFormData:
    """Data mapped from SQLite record/config into portal form fields."""

    record_id: int
    tc_kimlik_no: str
    tutar_usd: float
    mal_hizmet_adi: str
    il: str
    ilce: str
    para_birimi: str
    kdv_orani: str
    istisna_option_value: str

    @classmethod
    def from_record(cls, record: InvoiceRecord) -> "InvoiceFormData":
        """Create form data from a persisted invoice record."""

        description = (record.aciklama or "").strip()
        service_name = description or settings.mal_hizmet_adi
        return cls(
            record_id=record.id,
            tc_kimlik_no=record.tc_kimlik_no,
            tutar_usd=record.tutar_usd,
            mal_hizmet_adi=service_name,
            il=settings.default_il,
            ilce=settings.default_ilce,
            para_birimi=settings.para_birimi,
            kdv_orani=settings.kdv_orani,
            istisna_option_value=settings.istisna_option_value,
        )


class InvoiceFormFiller:
    """Fill all fields required for Phase 4 single-record draft creation."""

    def __init__(
        self,
        selectors: PortalSelectors = portal_selectors,
        timeout_ms: int | None = None,
    ) -> None:
        self.selectors = selectors
        self.timeout_ms = timeout_ms or settings.playwright_timeout_ms

    def fill_form(self, page: Any, form_data: InvoiceFormData) -> None:
        """Fill currency, customer and line item fields."""

        logger.info("Fatura formu dolduruluyor | record_id=%s", form_data.record_id)
        self._select_option(
            page,
            self.selectors.document_currency_selector,
            form_data.para_birimi,
            "Para birimi secilemedi.",
        )
        self._click_text(page, self.selectors.getir_text, "Kur getir aksiyonu tetiklenemedi.")
        self._wait_after_action(page, 750)

        self._fill_locator(
            page,
            self.selectors.identification_selector,
            form_data.tc_kimlik_no,
            "TCKN alani doldurulamadi.",
        )
        self._click_text(
            page,
            self.selectors.turmob_search_text,
            "Turmob musteri sorgulama tetiklenemedi.",
        )
        self._wait_after_action(page, 1_000)

        self._fill_locator(page, self.selectors.city_selector, form_data.il, "Il alani doldurulamadi.")
        self._press_locator(page, self.selectors.city_selector, "Tab")
        self._fill_locator(
            page,
            self.selectors.district_selector,
            form_data.ilce,
            "Ilce alani doldurulamadi.",
        )
        self._fill_locator(
            page,
            self.selectors.service_name_selector,
            form_data.mal_hizmet_adi,
            "Mal/hizmet adi doldurulamadi.",
        )
        self._fill_locator(
            page,
            self.selectors.price_amount_selector,
            self._format_amount(form_data.tutar_usd),
            "Fiyat alani doldurulamadi.",
        )
        self._select_option(
            page,
            self.selectors.tax_selector,
            form_data.kdv_orani,
            "KDV orani secilemedi.",
        )
        self._select_option(
            page,
            self.selectors.exemption_selector,
            form_data.istisna_option_value,
            "Istisna kodu secilemedi.",
        )
        logger.info("Fatura formu dolduruldu | record_id=%s", form_data.record_id)

    def _fill_locator(self, page: Any, selector: str, value: str, error_message: str) -> None:
        try:
            locator = page.locator(selector)
            locator.wait_for(state="visible", timeout=self.timeout_ms)
            locator.fill(value)
        except Exception as exc:
            raise ElementNotFoundError(error_message) from exc

    def _press_locator(self, page: Any, selector: str, key: str) -> None:
        try:
            page.locator(selector).press(key)
        except Exception:
            logger.debug("Optional key press failed | selector=%s key=%s", selector, key, exc_info=True)

    def _select_option(self, page: Any, selector: str, value: str, error_message: str) -> None:
        try:
            locator = page.locator(selector)
            locator.wait_for(state="visible", timeout=self.timeout_ms)
            locator.select_option(value)
        except Exception as exc:
            raise ElementNotFoundError(error_message) from exc

    def _click_text(self, page: Any, text: str, error_message: str) -> None:
        try:
            page.get_by_text(text).click(timeout=self.timeout_ms)
        except Exception as exc:
            raise PortalTimeoutError(error_message) from exc

    def _wait_after_action(self, page: Any, timeout_ms: int) -> None:
        try:
            page.wait_for_timeout(timeout_ms)
        except Exception:
            logger.debug("Optional wait failed | timeout_ms=%s", timeout_ms, exc_info=True)

    def _format_amount(self, amount: float) -> str:
        text = f"{amount:.2f}".rstrip("0").rstrip(".")
        return text or "0"
