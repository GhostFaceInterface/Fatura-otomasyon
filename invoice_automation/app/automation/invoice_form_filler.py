"""Fill the e-Arsiv invoice form for a single local record."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
import logging
import re
import unicodedata

from invoice_automation.app.automation.portal_selectors import PortalSelectors, portal_selectors
from invoice_automation.app.config import settings
from invoice_automation.app.db.models import InvoiceRecord
from invoice_automation.app.utils.exceptions import ElementNotFoundError, NameMismatchError, PortalTimeoutError
from invoice_automation.app.utils.retry import retry_with_backoff
from invoice_automation.app.utils.screenshots import capture_error_screenshot

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InvoiceFormData:
    """Data mapped from SQLite record/config into portal form fields."""

    record_id: int
    ad: str
    soyad: str
    tc_kimlik_no: str
    tutar_usd: float
    mal_hizmet_adi: str
    il: str
    ilce: str
    para_birimi: str
    kdv_orani: str
    istisna_target_text: str
    istisna_option_value: str | None
    aciklama: str = ""

    @classmethod
    def from_record(cls, record: InvoiceRecord) -> "InvoiceFormData":
        """Create form data from a persisted invoice record.

        The service name is always the fixed MAL_HIZMET_ADI setting. The
        record's açıklama goes to the invoice's Açıklama/Notlar box only.
        """

        return cls(
            record_id=record.id,
            ad=record.ad,
            soyad=record.soyad,
            tc_kimlik_no=record.tc_kimlik_no,
            tutar_usd=record.tutar_usd,
            mal_hizmet_adi=settings.mal_hizmet_adi,
            il=settings.default_il,
            ilce=settings.default_ilce,
            para_birimi=settings.para_birimi,
            kdv_orani=settings.kdv_orani,
            istisna_target_text=settings.istisna_target_text,
            istisna_option_value=settings.istisna_option_value,
            aciklama=(record.aciklama or "").strip(),
        )


class InvoiceFormFiller:
    """Fill all fields required for Phase 4 single-record draft creation."""

    def __init__(
        self,
        selectors: PortalSelectors = portal_selectors,
        timeout_ms: int | None = None,
    ) -> None:
        self.selectors = selectors
        self.timeout_ms = timeout_ms or settings.field_wait_timeout_ms

    def fill_form(
        self,
        page: Any,
        form_data: InvoiceFormData,
        after_turmob_lookup: Callable[[], None] | None = None,
    ) -> None:
        """Fill currency, customer and line item fields."""

        logger.info("Fatura formu dolduruluyor | record_id=%s", form_data.record_id)
        self._select_option(
            page,
            self.selectors.document_currency_selector,
            form_data.para_birimi,
            "Para birimi secilemedi.",
        )
        self._click_text(page, self.selectors.getir_text, "Kur getir aksiyonu tetiklenemedi.")
        self._wait_after_action(page, settings.retry_backoff_base_ms)

        self._fill_locator(
            page,
            self.selectors.identification_selector,
            form_data.tc_kimlik_no,
            "TCKN alani doldurulamadi.",
        )
        should_lookup_turmob = self._should_lookup_turmob(page, form_data)
        if should_lookup_turmob:
            self._click_text(
                page,
                self.selectors.turmob_search_text,
                "Turmob musteri sorgulama tetiklenemedi.",
            )
            self._wait_after_action(page, 1_000)
            if after_turmob_lookup is not None:
                after_turmob_lookup()
        else:
            logger.info(
                "Vergi dairesi dolu geldigi icin Turmob sorgusu atlandi | record_id=%s tc=%s",
                form_data.record_id,
                form_data.tc_kimlik_no,
            )
        self._verify_turmob_customer_name(page, form_data)

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
        self._select_exemption(
            page,
            self.selectors.exemption_selector,
            form_data.istisna_target_text,
            form_data.istisna_option_value,
        )
        if form_data.aciklama:
            self._fill_locator(
                page,
                self.selectors.note_selector,
                form_data.aciklama,
                "Aciklama/Notlar alani doldurulamadi.",
            )
        logger.info("Fatura formu dolduruldu | record_id=%s", form_data.record_id)

    def _fill_locator(self, page: Any, selector: str, value: str, error_message: str) -> None:
        try:
            locator = page.locator(selector)
            locator.wait_for(state="visible", timeout=self.timeout_ms)
            locator.fill(value)
        except Exception as exc:
            raise ElementNotFoundError(error_message) from exc

    def _read_locator_value(self, page: Any, selector: str, error_message: str) -> str:
        try:
            locator = page.locator(selector)
            locator.wait_for(state="visible", timeout=self.timeout_ms)
            return str(locator.input_value(timeout=self.timeout_ms)).strip()
        except Exception as exc:
            raise ElementNotFoundError(error_message) from exc

    def _try_read_locator_value(self, page: Any, selector: str) -> str:
        try:
            return self._read_locator_value(page, selector, f"{selector} okunamadi.")
        except Exception:
            logger.debug("Optional locator value okunamadi | selector=%s", selector, exc_info=True)
            return ""

    def _should_lookup_turmob(self, page: Any, form_data: InvoiceFormData) -> bool:
        self._wait_after_action(page, settings.tax_scheme_prefill_wait_ms)
        tax_scheme_name = self._try_read_locator_value(page, self.selectors.tax_scheme_name_selector)
        has_prefilled_tax_scheme = bool(tax_scheme_name.strip())
        logger.info(
            "TCKN sonrasi vergi dairesi kontrolu | record_id=%s tc=%s tax_scheme_filled=%s tax_scheme=%s wait_ms=%s",
            form_data.record_id,
            form_data.tc_kimlik_no,
            has_prefilled_tax_scheme,
            tax_scheme_name or "-",
            settings.tax_scheme_prefill_wait_ms,
        )
        return not has_prefilled_tax_scheme

    def _verify_turmob_customer_name(self, page: Any, form_data: InvoiceFormData) -> None:
        first_name = self._read_non_empty_locator_value(
            page,
            self.selectors.person_first_name_selector,
            "Turmob ad alani okunamadi veya bos geldi.",
        )
        family_name = self._read_non_empty_locator_value(
            page,
            self.selectors.person_family_name_selector,
            "Turmob soyad alani okunamadi veya bos geldi.",
        )
        source_full_name = f"{form_data.ad} {form_data.soyad}"
        turmob_full_name = f"{first_name} {family_name}"
        normalized_source = normalize_person_name(source_full_name)
        normalized_turmob = normalize_person_name(turmob_full_name)
        matched = normalized_source == normalized_turmob
        tolerant_matched = matched or (
            normalize_person_name_tolerant(source_full_name) == normalize_person_name_tolerant(turmob_full_name)
        )
        logger.info(
            "Turmob ad soyad kontrolu | record_id=%s tc=%s source=%s turmob=%s normalized_source=%s normalized_turmob=%s matched=%s tolerant_matched=%s",
            form_data.record_id,
            form_data.tc_kimlik_no,
            source_full_name,
            turmob_full_name,
            normalized_source,
            normalized_turmob,
            matched,
            tolerant_matched,
        )
        if matched:
            return
        if tolerant_matched:
            # Excel yazim hatasi toleransi: sadece i/ı, u/ü, o/ö farki kabul edilir.
            logger.warning(
                "Ad/soyad i/u/o harf toleransiyla eslesti, fatura devam ediyor | record_id=%s tc=%s source=%s turmob=%s",
                form_data.record_id,
                form_data.tc_kimlik_no,
                source_full_name,
                turmob_full_name,
            )
            return

        screenshot_path = capture_error_screenshot(page, form_data.record_id, "name_mismatch")
        raise NameMismatchError(
            f"Turmob ad/soyad eslesmedi. Kaynak: {source_full_name}, Turmob: {turmob_full_name}",
            stage="name_verification",
            screenshot_path=screenshot_path,
        )

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

    def _select_exemption(
        self,
        page: Any,
        selector: str,
        target_text: str,
        option_value: str | None,
    ) -> None:
        logger.info("Istisna dropdown bulundu mu kontrol ediliyor | selector=%s", selector)
        try:
            locator = page.locator(selector)
            locator.wait_for(state="visible", timeout=self.timeout_ms)
        except Exception as exc:
            raise ElementNotFoundError("Istisna dropdown bulunamadi.") from exc

        logger.info(
            "Hedef istisna secimi deneniyor | target_text=%s option_value=%s",
            target_text,
            option_value or "-",
        )

        errors: list[str] = []
        if option_value:
            try:
                locator.select_option(option_value)
                self._verify_selected_option_text(locator, target_text)
                logger.info("Istisna option value ile secildi | target_text=%s", target_text)
                return
            except Exception as exc:
                errors.append(f"value={option_value}: {exc}")
                logger.warning(
                    "Istisna value ile secilemedi, metin ile denenecek | target_text=%s option_value=%s",
                    target_text,
                    option_value,
                    exc_info=True,
                )

        try:
            locator.select_option(label=target_text)
            self._verify_selected_option_text(locator, target_text)
            logger.info("Istisna basariyla secildi | target_text=%s", target_text)
        except Exception as exc:
            errors.append(f"label={target_text}: {exc}")
            detail = " | ".join(errors)
            logger.error(
                "Istisna secimi basarisiz | target_text=%s detail=%s",
                target_text,
                detail,
            )
            raise ElementNotFoundError(
                f"Istisna secilemedi: {target_text}. Detay: {detail}"
            ) from exc

    def _verify_selected_option_text(self, locator: Any, expected_text: str) -> None:
        selected_text = locator.evaluate(
            """
            (select) => {
                const option = select.options[select.selectedIndex];
                return option ? option.textContent.trim() : "";
            }
            """
        )
        if str(selected_text).strip() != expected_text:
            raise ElementNotFoundError(
                f"Istisna secimi dogrulanamadi. Beklenen: {expected_text}, secilen: {selected_text}"
            )

    def _click_text(self, page: Any, text: str, error_message: str) -> None:
        try:
            retry_with_backoff(
                lambda: page.get_by_text(text).click(timeout=self.timeout_ms),
                attempts=settings.retry_count,
                base_delay_ms=settings.retry_backoff_base_ms,
                description=f"click_text:{text}",
                page=page,
            )
        except Exception as exc:
            raise PortalTimeoutError(error_message) from exc

    def _read_non_empty_locator_value(self, page: Any, selector: str, error_message: str) -> str:
        def read_value() -> str:
            value = self._read_locator_value(page, selector, error_message)
            if value:
                return value
            raise ElementNotFoundError(error_message)

        try:
            return retry_with_backoff(
                read_value,
                attempts=settings.turmob_lookup_retry_count,
                base_delay_ms=settings.retry_backoff_base_ms,
                description=f"read_non_empty:{selector}",
                page=page,
                retry_exceptions=(ElementNotFoundError,),
            )
        except ElementNotFoundError:
            raise

    def _wait_after_action(self, page: Any, timeout_ms: int) -> None:
        try:
            page.wait_for_timeout(timeout_ms)
        except Exception:
            logger.debug("Optional wait failed | timeout_ms=%s", timeout_ms, exc_info=True)

    def _format_amount(self, amount: float) -> str:
        text = f"{amount:.2f}".rstrip("0").rstrip(".")
        return text or "0"


def normalize_person_name(value: str) -> str:
    """Normalize person names for source-vs-Turmob comparison."""

    return re.sub(r"\s+", " ", str(value).strip().casefold())


# Excel'e yazarken sik yapilan Turkce/Ingilizce karakter hatalari icin esdeger harf gruplari.
# Sadece i/ı/I/İ, u/ü/U/Ü ve o/ö/O/Ö birbirine esit sayilir; ş/s, ç/c, ğ/g farki uyusmazlik kalir.
_PERSON_NAME_VOWEL_FOLD = str.maketrans(
    {
        "İ": "i",
        "I": "i",
        "ı": "i",
        "Ü": "u",
        "ü": "u",
        "Ö": "o",
        "ö": "o",
    }
)


def normalize_person_name_tolerant(value: str) -> str:
    """Normalize person names treating i/ı, u/ü and o/ö variants as equal."""

    # NFC: ayrik yazilmis "I + U+0307" veya "u + U+0308" gibi formlar tek harfe birlestirilir.
    composed = unicodedata.normalize("NFC", str(value))
    return normalize_person_name(composed.translate(_PERSON_NAME_VOWEL_FOLD))
