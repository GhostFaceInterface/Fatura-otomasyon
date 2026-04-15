from invoice_automation.app.automation.invoice_form_filler import InvoiceFormData, InvoiceFormFiller


class FakeLocator:
    def __init__(self, page: "FakePage", selector: str) -> None:
        self.page = page
        self.selector = selector

    def wait_for(self, state: str = "visible", timeout: int = 0) -> None:
        self.page.actions.append(("wait_for", self.selector, state, timeout))

    def fill(self, value: str) -> None:
        self.page.actions.append(("fill", self.selector, value))

    def select_option(self, value: str) -> None:
        self.page.actions.append(("select_option", self.selector, value))

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

    def locator(self, selector: str) -> FakeLocator:
        return FakeLocator(self, selector)

    def get_by_text(self, text: str) -> FakeTextLocator:
        return FakeTextLocator(self, text)

    def wait_for_timeout(self, timeout_ms: int) -> None:
        self.actions.append(("wait_for_timeout", timeout_ms))


def test_invoice_form_filler_maps_record_data_to_portal_fields() -> None:
    page = FakePage()
    form_data = InvoiceFormData(
        record_id=1,
        tc_kimlik_no="12345678901",
        tutar_usd=1000.0,
        mal_hizmet_adi="YURT DIŞI KONAKLAMA BEDELİ",
        il="**",
        ilce="**",
        para_birimi="USD",
        kdv_orani="0",
        istisna_option_value="string:302",
    )

    InvoiceFormFiller(timeout_ms=30_000).fill_form(page, form_data)

    assert ("select_option", "#DocumentCurrencyCode", "USD") in page.actions
    assert ("click_text", "Getir", 30_000) in page.actions
    assert ("fill", "#txtIdentificationID", "12345678901") in page.actions
    assert ("click_text", "Türmob Müsteri Sorgula", 30_000) in page.actions
    assert ("fill", "#txtIl", "**") in page.actions
    assert ("fill", "#txtIlce", "**") in page.actions
    assert ("fill", "#MalAdi", "YURT DIŞI KONAKLAMA BEDELİ") in page.actions
    assert ("fill", 'input[name="Price_Amount"]', "1000") in page.actions
    assert ("select_option", "#Tax_Perc0015", "0") in page.actions
    assert ("select_option", 'select[name="istisnaListname"]', "string:302") in page.actions
