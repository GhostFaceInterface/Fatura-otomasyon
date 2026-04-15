from invoice_automation.app.automation.draft_creator import DraftCreator
from invoice_automation.app.constants import EARCHIVE_DRAFTS_PATH, InvoiceStatus
from invoice_automation.app.db.models import InvoiceRecord


class FakeNavigation:
    def __init__(self) -> None:
        self.opened = False

    def open_create_invoice_page(self, page: "FakeDraftPage") -> None:
        self.opened = True
        page.actions.append(("open_create_invoice_page",))


class FakeFormFiller:
    def fill_form(self, page: "FakeDraftPage", form_data, after_turmob_lookup=None) -> None:
        page.actions.append(("fill_form", form_data.record_id))
        if after_turmob_lookup is not None:
            after_turmob_lookup()


class FakeDetector:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int | None]] = []

    def raise_if_portal_error(self, page: "FakeDraftPage", stage: str, record_id: int | None = None) -> None:
        self.calls.append((stage, record_id))
        page.actions.append(("detect", stage, record_id))


class FakeVisibleText:
    def __init__(self, page: "FakeDraftPage", text: str) -> None:
        self.page = page
        self.text = text

    def wait_for(self, state: str = "visible", timeout: int = 0) -> None:
        if self.text not in self.page.visible_texts:
            raise RuntimeError(f"text not visible: {self.text}")
        self.page.actions.append(("wait_for_text", self.text, state, timeout))


class FakeButton:
    def __init__(self, page: "FakeDraftPage") -> None:
        self.page = page

    def wait_for(self, state: str = "visible", timeout: int = 0) -> None:
        self.page.actions.append(("wait_for_button", state, timeout))

    def click(self, timeout: int = 0) -> None:
        self.page.actions.append(("click_save", timeout))


class FakeDraftPage:
    def __init__(self) -> None:
        self.actions: list[tuple] = []
        self.fail_wait_for_url = False
        self.visible_texts: set[str] = set()

    def get_by_role(self, role: str, name: str) -> FakeButton:
        if role == "heading":
            return FakeVisibleText(self, name)
        self.actions.append(("get_by_role", role, name))
        return FakeButton(self)

    def wait_for_url(self, pattern: str, timeout: int) -> None:
        self.actions.append(("wait_for_url", pattern, timeout))
        if self.fail_wait_for_url:
            raise RuntimeError("redirect timeout")

    def get_by_text(self, text: str) -> FakeVisibleText:
        return FakeVisibleText(self, text)


def _record() -> InvoiceRecord:
    return InvoiceRecord(
        id=11,
        batch_id=1,
        ad="Ali",
        soyad="Yilmaz",
        tc_kimlik_no="12345678901",
        tutar_usd=1000.0,
        aciklama="YURT DIŞI KONAKLAMA BEDELİ",
        fatura_tipi_hedef="earshiv",
        kaynak_dosya=None,
        kaynak_satir_no=None,
        secili_mi=True,
        islem_durumu=InvoiceStatus.SELECTED.value,
        portal_ref_no=None,
        hata_kodu=None,
        hata_mesaji=None,
        olusturma_zamani="2026-04-15T00:00:00Z",
        guncelleme_zamani="2026-04-15T00:00:00Z",
    )


def test_draft_creator_waits_for_drafts_redirect_after_save() -> None:
    page = FakeDraftPage()
    detector = FakeDetector()
    creator = DraftCreator(
        navigation=FakeNavigation(),
        form_filler=FakeFormFiller(),
        error_detector=detector,
        timeout_ms=30_000,
    )

    result = creator.create_draft(page, _record())

    assert result.status == InvoiceStatus.SUCCESS_DRAFT_CREATED
    assert ("wait_for_url", f"**{EARCHIVE_DRAFTS_PATH}*", 30_000) in page.actions
    assert ("turmob_lookup", 11) in detector.calls
    assert ("save_draft", 11) in detector.calls


def test_draft_creator_accepts_visible_drafts_page_signal_when_redirect_wait_times_out() -> None:
    page = FakeDraftPage()
    page.fail_wait_for_url = True
    page.visible_texts.add("Taslaklar")
    detector = FakeDetector()
    creator = DraftCreator(
        navigation=FakeNavigation(),
        form_filler=FakeFormFiller(),
        error_detector=detector,
        timeout_ms=30_000,
    )

    result = creator.create_draft(page, _record())

    assert result.status == InvoiceStatus.SUCCESS_DRAFT_CREATED
    assert ("draft_redirect_wait", 11) in detector.calls
    assert ("wait_for_text", "Taslaklar", "visible", 2_000) in page.actions
