from dataclasses import replace

from invoice_automation.app.automation.batch_runner import BatchRunner
from invoice_automation.app.automation.session_manager import PortalSessionState, PortalSessionStatus
from invoice_automation.app.constants import InvoiceStatus
from invoice_automation.app.db.models import InvoiceRecord
from invoice_automation.app.schemas.draft import SingleDraftServiceResult


class FakePage:
    def __init__(self, closed: bool = False) -> None:
        self.closed = closed
        self.wait_calls = 0

    def is_closed(self) -> bool:
        return self.closed

    def wait_for_timeout(self, timeout_ms: int) -> None:
        self.wait_calls += 1


class FakeBrowserManager:
    def __init__(self, page: FakePage | None = None) -> None:
        self.page = page or FakePage()


class FakeSessionManager:
    def __init__(self, status: PortalSessionStatus = PortalSessionStatus.READY) -> None:
        self.browser_manager = FakeBrowserManager()
        self._state = PortalSessionState(
            status=status,
            message="test",
            current_url="https://portal.test",
            updated_at="2026-04-16T00:00:00Z",
        )

    @property
    def state(self) -> PortalSessionState:
        return self._state


class FakeNavigation:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.next_calls = 0
        self.menu_calls = 0

    def open_next_create_invoice_page(self, page: FakePage) -> None:
        self.next_calls += 1
        if self.fail:
            raise RuntimeError("next failed")

    def open_create_invoice_page(self, page: FakePage) -> None:
        self.menu_calls += 1
        if self.fail:
            raise RuntimeError("menu failed")


class FakeDraftService:
    def __init__(self, records: list[InvoiceRecord], statuses: list[InvoiceStatus]) -> None:
        self.records = {record.id: record for record in records}
        self.statuses = list(statuses)
        self.calls: list[int] = []

    def create_for_record(self, record_id: int) -> SingleDraftServiceResult:
        self.calls.append(record_id)
        status = self.statuses.pop(0)
        updated_record = replace(self.records[record_id], islem_durumu=status.value)
        ok = status == InvoiceStatus.SUCCESS_DRAFT_CREATED
        return SingleDraftServiceResult(
            ok=ok,
            record=updated_record,
            message="ok" if ok else "portal error",
            error_code=None if ok else f"{status.value}Error",
            screenshot_path=None if ok else "/tmp/screenshot.png",
        )


def test_batch_runner_continues_after_record_level_errors() -> None:
    records = [_record(1), _record(2), _record(3)]
    draft_service = FakeDraftService(
        records,
        [
            InvoiceStatus.SUCCESS_DRAFT_CREATED,
            InvoiceStatus.FAILED_INVALID_TCKN,
            InvoiceStatus.SKIPPED_EFATURA_MUKELLEFI,
        ],
    )
    navigation = FakeNavigation()
    runner = BatchRunner(
        draft_service=draft_service,
        session_manager=FakeSessionManager(),
        navigation=navigation,
        navigation_retry_count=2,
    )

    report = runner.run(records)

    assert draft_service.calls == [1, 2, 3]
    assert report.total_processed == 3
    assert report.success_count == 1
    assert report.failed_count == 1
    assert report.skipped_count == 1
    assert report.aborted_due_to_session_loss is False
    assert navigation.next_calls == 2


def test_batch_runner_stops_on_session_abort_status() -> None:
    records = [_record(1), _record(2), _record(3)]
    draft_service = FakeDraftService(
        records,
        [
            InvoiceStatus.SUCCESS_DRAFT_CREATED,
            InvoiceStatus.ABORTED_SESSION_LOST,
            InvoiceStatus.SUCCESS_DRAFT_CREATED,
        ],
    )
    runner = BatchRunner(
        draft_service=draft_service,
        session_manager=FakeSessionManager(),
        navigation=FakeNavigation(),
        navigation_retry_count=2,
    )

    report = runner.run(records)

    assert draft_service.calls == [1, 2]
    assert report.total_processed == 2
    assert report.aborted_count == 1
    assert report.aborted_due_to_session_loss is True
    assert report.abort_reason == "portal error"


def test_batch_runner_stops_when_clean_page_reset_fails() -> None:
    records = [_record(1), _record(2)]
    draft_service = FakeDraftService(
        records,
        [
            InvoiceStatus.SUCCESS_DRAFT_CREATED,
            InvoiceStatus.SUCCESS_DRAFT_CREATED,
        ],
    )
    navigation = FakeNavigation(fail=True)
    runner = BatchRunner(
        draft_service=draft_service,
        session_manager=FakeSessionManager(),
        navigation=navigation,
        navigation_retry_count=2,
    )

    report = runner.run(records)

    assert draft_service.calls == [1]
    assert report.total_processed == 1
    assert report.aborted_due_to_session_loss is True
    assert "Yeni e-Arsiv olustur sayfasina guvenli donulemedi" in report.abort_reason
    assert navigation.next_calls == 2
    assert navigation.menu_calls == 2


def test_batch_runner_does_not_start_without_ready_session() -> None:
    records = [_record(1)]
    draft_service = FakeDraftService(records, [InvoiceStatus.SUCCESS_DRAFT_CREATED])
    runner = BatchRunner(
        draft_service=draft_service,
        session_manager=FakeSessionManager(status=PortalSessionStatus.IDLE),
        navigation=FakeNavigation(),
        navigation_retry_count=2,
    )

    report = runner.run(records)

    assert draft_service.calls == []
    assert report.total_processed == 0
    assert report.aborted_due_to_session_loss is True
    assert "READY degil" in report.abort_reason


def _record(record_id: int) -> InvoiceRecord:
    return InvoiceRecord(
        id=record_id,
        batch_id=1,
        ad=f"Ad{record_id}",
        soyad=f"Soyad{record_id}",
        tc_kimlik_no=f"1234567890{record_id}",
        tutar_usd=1000.0,
        aciklama="YURT DIŞI KONAKLAMA BEDELİ",
        fatura_tipi_hedef="earshiv",
        kaynak_dosya="test.csv",
        kaynak_satir_no=record_id,
        secili_mi=True,
        islem_durumu=InvoiceStatus.SELECTED.value,
        portal_ref_no=None,
        hata_kodu=None,
        hata_mesaji=None,
        olusturma_zamani="2026-04-16T00:00:00Z",
        guncelleme_zamani="2026-04-16T00:00:00Z",
    )
