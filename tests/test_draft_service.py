from pathlib import Path

from invoice_automation.app.automation.draft_creator import DraftCreationResult
from invoice_automation.app.automation.session_manager import PortalSessionState, PortalSessionStatus
from invoice_automation.app.constants import InvoiceStatus
from invoice_automation.app.db.models import InvoiceRecordCreate
from invoice_automation.app.db.repository import InvoiceRecordRepository
from invoice_automation.app.services.draft_service import SingleDraftService
from invoice_automation.app.utils.exceptions import InvalidTCKNError, NameMismatchError, TurmobServiceError


class FakeBrowserManager:
    def __init__(self, page: object | None) -> None:
        self.page = page


class FakeSessionManager:
    def __init__(self, status: PortalSessionStatus, page: object | None = object()) -> None:
        self.browser_manager = FakeBrowserManager(page)
        self._state = PortalSessionState(
            status=status,
            message="test",
            current_url="https://portal.test",
            updated_at="2026-04-15T00:00:00Z",
        )

    @property
    def state(self) -> PortalSessionState:
        return self._state


class SuccessDraftCreator:
    def create_draft(self, page: object, record) -> DraftCreationResult:
        return DraftCreationResult(
            record_id=record.id,
            status=InvoiceStatus.SUCCESS_DRAFT_CREATED,
            message="Taslak fatura olusturuldu.",
        )


class InvalidTcknDraftCreator:
    def create_draft(self, page: object, record) -> DraftCreationResult:
        raise InvalidTCKNError("Musteri bulunamadi.")


class TurmobServiceDraftCreator:
    def create_draft(self, page: object, record) -> DraftCreationResult:
        raise TurmobServiceError("Servis hatası oluştu !", stage="turmob_lookup")


class NameMismatchDraftCreator:
    def create_draft(self, page: object, record) -> DraftCreationResult:
        raise NameMismatchError("Turmob ad/soyad eslesmedi.", stage="name_verification")


def _repository_with_record(tmp_path: Path) -> tuple[InvoiceRecordRepository, int]:
    repository = InvoiceRecordRepository(tmp_path / "test.sqlite3")
    record = repository.create(
        InvoiceRecordCreate(
            ad="Ali",
            soyad="Yilmaz",
            tc_kimlik_no="12345678901",
            tutar_usd=1000.0,
            aciklama="YURT DIŞI KONAKLAMA BEDELİ",
        )
    )
    return repository, record.id


def test_single_draft_service_marks_success(tmp_path: Path) -> None:
    repository, record_id = _repository_with_record(tmp_path)
    service = SingleDraftService(
        repository=repository,
        session_manager=FakeSessionManager(PortalSessionStatus.READY),
        draft_creator=SuccessDraftCreator(),
    )

    result = service.create_for_record(record_id)

    assert result.ok is True
    assert result.record.islem_durumu == InvoiceStatus.SUCCESS_DRAFT_CREATED.value
    assert result.record.secili_mi is False
    assert result.record.hata_kodu is None


def test_single_draft_service_maps_invalid_tckn_to_failed_status(tmp_path: Path) -> None:
    repository, record_id = _repository_with_record(tmp_path)
    service = SingleDraftService(
        repository=repository,
        session_manager=FakeSessionManager(PortalSessionStatus.READY),
        draft_creator=InvalidTcknDraftCreator(),
    )

    result = service.create_for_record(record_id)

    assert result.ok is False
    assert result.record.islem_durumu == InvoiceStatus.FAILED_INVALID_TCKN.value
    assert result.record.hata_kodu == "InvalidTCKNError"
    assert result.record.secili_mi is True


def test_single_draft_service_maps_turmob_service_error_to_failed_status(tmp_path: Path) -> None:
    repository, record_id = _repository_with_record(tmp_path)
    service = SingleDraftService(
        repository=repository,
        session_manager=FakeSessionManager(PortalSessionStatus.READY),
        draft_creator=TurmobServiceDraftCreator(),
    )

    result = service.create_for_record(record_id)

    assert result.ok is False
    assert result.record.islem_durumu == InvoiceStatus.FAILED_TURMOB_SERVICE_ERROR.value
    assert result.record.hata_kodu == "TurmobServiceError"


def test_single_draft_service_maps_name_mismatch_to_failed_status(tmp_path: Path) -> None:
    repository, record_id = _repository_with_record(tmp_path)
    service = SingleDraftService(
        repository=repository,
        session_manager=FakeSessionManager(PortalSessionStatus.READY),
        draft_creator=NameMismatchDraftCreator(),
    )

    result = service.create_for_record(record_id)

    assert result.ok is False
    assert result.record.islem_durumu == InvoiceStatus.FAILED_NAME_MISMATCH.value
    assert result.record.hata_kodu == "NameMismatchError"
    assert result.record.secili_mi is True
    assert result.record.secili_mi is True


def test_single_draft_service_requires_ready_session(tmp_path: Path) -> None:
    repository, record_id = _repository_with_record(tmp_path)
    service = SingleDraftService(
        repository=repository,
        session_manager=FakeSessionManager(PortalSessionStatus.IDLE, page=None),
        draft_creator=SuccessDraftCreator(),
    )

    result = service.create_for_record(record_id)

    assert result.ok is False
    assert result.record.islem_durumu == InvoiceStatus.ABORTED_SESSION_LOST.value
    assert result.record.hata_kodu == "SessionLostError"
