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

    def get_by_role(self, role: str, name: str) -> FakeButton:
        self.actions.append(("get_by_role", role, name))
        return FakeButton(self)

    def wait_for_url(self, pattern: str, timeout: int) -> None:
        self.actions.append(("wait_for_url", pattern, timeout))


def _record() -> InvoiceRecord:
    return InvoiceRecord(
        id=11,
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
