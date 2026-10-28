import logging

import pytest

from invoice_automation.app.automation.invoice_form_filler import (
    InvoiceFormData,
    InvoiceFormFiller,
    normalize_person_name_tolerant,
)
from invoice_automation.app.utils.exceptions import NameMismatchError


class FakeLocator:
    def __init__(self, page: "FakePage", selector: str) -> None:
        self.page = page
        self.selector = selector
        self.selected_text = ""

    def wait_for(self, state: str = "visible", timeout: int = 0) -> None:
        self.page.actions.append(("wait_for", self.selector, state, timeout))

    def fill(self, value: str) -> None:
        self.page.actions.append(("fill", self.selector, value))

    def input_value(self, timeout: int = 0) -> str:
        self.page.actions.append(("input_value", self.selector, timeout))
        return self.page.values_by_selector.get(self.selector, "")

    def select_option(self, value: str | None = None, label: str | None = None) -> None:
        selected = label if label is not None else value
        self.selected_text = selected or ""
        self.page.selected_text_by_selector[self.selector] = self.selected_text
        self.page.actions.append(("select_option", self.selector, value, label))

    def evaluate(self, script: str) -> str:
        self.page.actions.append(("evaluate", self.selector))
        return self.page.selected_text_by_selector.get(self.selector, self.selected_text)

    def press(self, key: str) -> None:
        self.page.actions.append(("press", self.selector, key))


class FakeTextLocator:
    def __init__(self, page: "FakePage", text: str) -> None:
        self.page = page
        self.text = text

    def click(self, timeout: int = 0) -> None:
        self.page.actions.append(("click_text", self.text, timeout))


class FakePage:
    def __init__(self) -> None:
        self.actions: list[tuple] = []
        self.locators: dict[str, FakeLocator] = {}
        self.selected_text_by_selector: dict[str, str] = {}
        self.values_by_selector: dict[str, str] = {
            "#txtPerson_FirstName": "Ali",
            "#txtPerson_FamilyName": "Yilmaz",
        }

    def locator(self, selector: str) -> FakeLocator:
        if selector not in self.locators:
            self.locators[selector] = FakeLocator(self, selector)
        return self.locators[selector]

    def get_by_text(self, text: str) -> FakeTextLocator:
        return FakeTextLocator(self, text)

    def wait_for_timeout(self, timeout_ms: int) -> None:
        self.actions.append(("wait_for_timeout", timeout_ms))


def test_invoice_form_filler_maps_record_data_to_portal_fields() -> None:
    page = FakePage()
    form_data = InvoiceFormData(
        record_id=1,
        ad="Ali",
        soyad="Yilmaz",
        tc_kimlik_no="12345678901",
        tutar_usd=1000.0,
        mal_hizmet_adi="YURT DIŞI KONAKLAMA BEDELİ",
        il="**",
        ilce="**",
        para_birimi="USD",
        kdv_orani="0",
        istisna_target_text="302-11/1-a Hizmet ihracatı",
        istisna_option_value=None,
    )

    InvoiceFormFiller(timeout_ms=30_000).fill_form(page, form_data)

    assert ("select_option", "#DocumentCurrencyCode", "USD", None) in page.actions
    assert ("click_text", "Getir", 30_000) in page.actions
    assert ("fill", "#txtIdentificationID", "12345678901") in page.actions
    assert ("click_text", "Türmob Müsteri Sorgula", 30_000) in page.actions
    assert ("input_value", "#txtPerson_FirstName", 30_000) in page.actions
    assert ("input_value", "#txtPerson_FamilyName", 30_000) in page.actions
    assert ("fill", "#txtIl", "**") in page.actions
    assert ("fill", "#txtIlce", "**") in page.actions
    assert ("fill", "#MalAdi", "YURT DIŞI KONAKLAMA BEDELİ") in page.actions
    assert ("fill", 'input[name="Price_Amount"]', "1000") in page.actions
    assert ("select_option", "#Tax_Perc0015", "0", None) in page.actions
    assert (
        "select_option",
        'select[name="istisnaListname"]',
        None,
        "302-11/1-a Hizmet ihracatı",
    ) in page.actions
    assert ("evaluate", 'select[name="istisnaListname"]') in page.actions
    # No açıklama: the invoice's Açıklama/Notlar box is left alone.
    assert not [action for action in page.actions if action[:2] == ("fill", "#Note")]


def test_invoice_form_filler_writes_aciklama_into_the_invoice_note() -> None:
    page = FakePage()
    form_data = InvoiceFormData(
        record_id=1,
        ad="Ali",
        soyad="Yilmaz",
        tc_kimlik_no="12345678901",
        tutar_usd=1000.0,
        mal_hizmet_adi="YURT DIŞI KONAKLAMA BEDELİ",
        il="**",
        ilce="**",
        para_birimi="USD",
        kdv_orani="0",
        istisna_target_text="302-11/1-a Hizmet ihracatı",
        istisna_option_value=None,
        aciklama="100$ İSKONTO",
    )

    InvoiceFormFiller(timeout_ms=30_000).fill_form(page, form_data)

    assert ("fill", "#Note", "100$ İSKONTO") in page.actions
    assert ("fill", "#MalAdi", "YURT DIŞI KONAKLAMA BEDELİ") in page.actions


def test_invoice_form_filler_raises_when_turmob_name_does_not_match() -> None:
    page = FakePage()
    page.values_by_selector["#txtPerson_FirstName"] = "Mehmet"
    page.values_by_selector["#txtPerson_FamilyName"] = "Kaya"
    form_data = InvoiceFormData(
        record_id=1,
        ad="Ali",
        soyad="Yilmaz",
        tc_kimlik_no="12345678901",
        tutar_usd=1000.0,
        mal_hizmet_adi="YURT DIŞI KONAKLAMA BEDELİ",
        il="**",
        ilce="**",
        para_birimi="USD",
        kdv_orani="0",
        istisna_target_text="302-11/1-a Hizmet ihracatı",
        istisna_option_value=None,
    )

    with pytest.raises(NameMismatchError):
        InvoiceFormFiller(timeout_ms=30_000).fill_form(page, form_data)


def test_invoice_form_filler_skips_turmob_when_tax_scheme_is_prefilled() -> None:
    page = FakePage()
    page.values_by_selector["#txtTaxSchemeName"] = "ŞİRİNYER VERGİ DAİRESİ MÜD."
    form_data = InvoiceFormData(
        record_id=2,
        ad="Ali",
        soyad="Yilmaz",
        tc_kimlik_no="12345678901",
        tutar_usd=1000.0,
        mal_hizmet_adi="YURT DIŞI KONAKLAMA BEDELİ",
        il="**",
        ilce="**",
        para_birimi="USD",
        kdv_orani="0",
        istisna_target_text="302-11/1-a Hizmet ihracatı",
        istisna_option_value=None,
    )

    InvoiceFormFiller(timeout_ms=30_000).fill_form(page, form_data)

    assert ("input_value", "#txtTaxSchemeName", 30_000) in page.actions
    assert ("click_text", "Türmob Müsteri Sorgula", 30_000) not in page.actions
    assert ("fill", "#MalAdi", "YURT DIŞI KONAKLAMA BEDELİ") in page.actions


def _name_form_data(ad: str, soyad: str) -> InvoiceFormData:
    return InvoiceFormData(
        record_id=1,
        ad=ad,
        soyad=soyad,
        tc_kimlik_no="12345678901",
        tutar_usd=1000.0,
        mal_hizmet_adi="YURT DIŞI KONAKLAMA BEDELİ",
        il="**",
        ilce="**",
        para_birimi="USD",
        kdv_orani="0",
        istisna_target_text="302-11/1-a Hizmet ihracatı",
        istisna_option_value=None,
    )


@pytest.mark.parametrize(
    ("source", "portal"),
    [
        ("Işık", "Işik"),
        ("IŞIK", "Işık"),
        ("Gül", "Gul"),
        ("Öztürk", "Ozturk"),
        ("ILKAY", "İlkay"),
        ("İLKAY", "ılkay"),
        ("ÜMIT", "Ümit"),
        ("ÖMÜR ÜNAL", "omur unal"),
        ("  Gül   Öztürk ", "gul ozturk"),
        ("I\u0307lkay", "İlkay"),
        ("Gu\u0308l", "Gül"),
    ],
)
def test_normalize_person_name_tolerant_accepts_i_u_o_variants(source: str, portal: str) -> None:
    assert normalize_person_name_tolerant(source) == normalize_person_name_tolerant(portal)


@pytest.mark.parametrize(
    ("source", "portal"),
    [
        ("Şahin", "Sahin"),
        ("Işık", "Isik"),
        ("Çelik", "Celik"),
        ("Doğan", "Dogan"),
        ("Ali", "Alı\u0307m"),
        ("Ali", "Alı\u0307"),
        ("Ali", "Alii"),
        ("Gül", "Gülü"),
        ("Ali Yilmaz", "Mehmet Kaya"),
        ("Ozan", "Ezan"),
    ],
)
def test_normalize_person_name_tolerant_rejects_other_differences(source: str, portal: str) -> None:
    assert normalize_person_name_tolerant(source) != normalize_person_name_tolerant(portal)


@pytest.mark.parametrize(
    ("ad", "soyad", "portal_ad", "portal_soyad"),
    [
        ("Isik", "Ozturk", "ISIK", "ÖZTÜRK"),
        ("Gul", "Yilmaz", "Gül", "Yılmaz"),
        ("ILKAY", "Uslu", "İlkay", "Üslü"),
    ],
)
def test_invoice_form_filler_accepts_turmob_name_with_vowel_tolerance(
    caplog: pytest.LogCaptureFixture,
    ad: str,
    soyad: str,
    portal_ad: str,
    portal_soyad: str,
) -> None:
    page = FakePage()
    page.values_by_selector["#txtPerson_FirstName"] = portal_ad
    page.values_by_selector["#txtPerson_FamilyName"] = portal_soyad

    with caplog.at_level(logging.INFO, logger="invoice_automation.app.automation.invoice_form_filler"):
        InvoiceFormFiller(timeout_ms=30_000).fill_form(page, _name_form_data(ad, soyad))

    assert ("fill", 'input[name="Price_Amount"]', "1000") in page.actions
    tolerance_logs = [record for record in caplog.records if "harf toleransiyla eslesti" in record.getMessage()]
    assert len(tolerance_logs) == 1
    assert tolerance_logs[0].levelno == logging.WARNING
    message = tolerance_logs[0].getMessage()
    assert f"source={ad} {soyad}" in message
    assert f"turmob={portal_ad} {portal_soyad}" in message


def test_invoice_form_filler_exact_name_match_does_not_log_tolerance(caplog: pytest.LogCaptureFixture) -> None:
    page = FakePage()

    with caplog.at_level(logging.INFO, logger="invoice_automation.app.automation.invoice_form_filler"):
        InvoiceFormFiller(timeout_ms=30_000).fill_form(page, _name_form_data("ali", "YILMAZ"))

    assert not [record for record in caplog.records if "harf toleransiyla eslesti" in record.getMessage()]


@pytest.mark.parametrize(
    ("ad", "soyad", "portal_ad", "portal_soyad"),
    [
        ("Ali", "Sahin", "Ali", "Şahin"),
        ("Ali", "Celik", "Ali", "Çelik"),
        ("Ali", "Yilmaz", "Ali", "Yilmazz"),
    ],
)
def test_invoice_form_filler_still_rejects_non_vowel_name_differences(
    ad: str,
    soyad: str,
    portal_ad: str,
    portal_soyad: str,
) -> None:
    page = FakePage()
    page.values_by_selector["#txtPerson_FirstName"] = portal_ad
    page.values_by_selector["#txtPerson_FamilyName"] = portal_soyad

    with pytest.raises(NameMismatchError):
        InvoiceFormFiller(timeout_ms=30_000).fill_form(page, _name_form_data(ad, soyad))



@pytest.mark.parametrize(("aciklama", "note"), [(" 50$ İSKONTO ", "50$ İSKONTO"), ("", ""), (None, "")])
def test_service_name_is_always_the_fixed_setting(aciklama, note) -> None:
    from invoice_automation.app.config import settings
    from invoice_automation.app.db.models import InvoiceRecord

    record = InvoiceRecord(
        id=1, batch_id=1, ad="Ali", soyad="Yilmaz", tc_kimlik_no="12345678901", tutar_usd=1450.0,
        aciklama=aciklama, fatura_tipi_hedef="E_ARSIV", kaynak_dosya=None, kaynak_satir_no=None,
        secili_mi=False, islem_durumu="PENDING", portal_ref_no=None, hata_kodu=None, hata_mesaji=None,
        olusturma_zamani="", guncelleme_zamani="",
    )

    # The açıklama goes to the invoice note; it must never replace the service name.
    form_data = InvoiceFormData.from_record(record)
    assert form_data.mal_hizmet_adi == settings.mal_hizmet_adi
    assert form_data.aciklama == note
