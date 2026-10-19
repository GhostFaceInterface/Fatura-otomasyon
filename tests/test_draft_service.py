from pathlib import Path
import sqlite3

import pytest

from invoice_automation.app.automation.draft_creator import DraftCreationResult
from invoice_automation.app.automation.session_manager import PortalSessionState, PortalSessionStatus
from invoice_automation.app.constants import InvoiceStatus
from invoice_automation.app.db.models import InvoiceRecordCreate
from invoice_automation.app.db.repository import InvoiceRecordRepository
from invoice_automation.app.services.draft_service import SingleDraftService
from invoice_automation.app.utils.exceptions import (
    DraftSaveUnconfirmedError,
    InvalidTCKNError,
    NameMismatchError,
    RecordNotEligibleError,
    TurmobServiceError,
)


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


class CountingSuccessDraftCreator(SuccessDraftCreator):
    def __init__(self) -> None:
        self.calls = 0

    def create_draft(self, page: object, record) -> DraftCreationResult:
        self.calls += 1
        return super().create_draft(page, record)


class UnconfirmedSaveDraftCreator:
    def create_draft(self, page: object, record) -> DraftCreationResult:
        raise DraftSaveUnconfirmedError("redirect gelmedi", stage="draft_redirect_wait")


def test_single_draft_service_is_idempotent_on_double_submit(tmp_path: Path) -> None:
    repository, record_id = _repository_with_record(tmp_path)
    creator = CountingSuccessDraftCreator()
    service = SingleDraftService(
        repository=repository,
        session_manager=FakeSessionManager(PortalSessionStatus.READY),
        draft_creator=creator,
    )

    service.create_for_record(record_id)
    with pytest.raises(RecordNotEligibleError):
        service.create_for_record(record_id)

    assert creator.calls == 1
    assert repository.get(record_id).islem_durumu == InvoiceStatus.SUCCESS_DRAFT_CREATED.value


@pytest.mark.parametrize(
    "status",
    [
        InvoiceStatus.IN_PROGRESS,
        InvoiceStatus.SUCCESS_DRAFT_CREATED,
        InvoiceStatus.FAILED_INVALID_TCKN,
        InvoiceStatus.SKIPPED_EFATURA_MUKELLEFI,
        InvoiceStatus.NEEDS_REVIEW,
    ],
)
def test_single_draft_service_rejects_non_eligible_status_without_portal_call(
    tmp_path: Path,
    status: InvoiceStatus,
) -> None:
    repository, record_id = _repository_with_record(tmp_path)
    repository.update_processing_state(record_id, status)
    creator = CountingSuccessDraftCreator()
    service = SingleDraftService(
        repository=repository,
        session_manager=FakeSessionManager(PortalSessionStatus.READY),
        draft_creator=creator,
    )

    with pytest.raises(RecordNotEligibleError):
        service.create_for_record(record_id)

    assert creator.calls == 0
    assert repository.get(record_id).islem_durumu == status.value


def test_single_draft_service_marks_unconfirmed_save_as_needs_review(tmp_path: Path) -> None:
    repository, record_id = _repository_with_record(tmp_path)
    repository.update_selection([record_id])
    service = SingleDraftService(
        repository=repository,
        session_manager=FakeSessionManager(PortalSessionStatus.READY),
        draft_creator=UnconfirmedSaveDraftCreator(),
    )

    result = service.create_for_record(record_id)

    assert result.ok is False
    assert result.record.islem_durumu == InvoiceStatus.NEEDS_REVIEW.value
    assert result.record.hata_kodu == "DraftSaveUnconfirmedError"
    assert result.record.secili_mi is False
    # NEEDS_REVIEW is neither batch-eligible nor resettable via the retry action.
    assert repository.list_selected_for_batch() == []
    assert repository.reset_failed_to_pending([record_id]) == 0


def test_single_draft_service_success_db_failure_is_not_marked_failed(tmp_path: Path) -> None:
    repository, record_id = _repository_with_record(tmp_path)
    original_update = repository.update_processing_state

    def failing_success_update(record_id, status, **kwargs):
        if status == InvoiceStatus.SUCCESS_DRAFT_CREATED:
            raise sqlite3.OperationalError("database is locked")
        return original_update(record_id, status, **kwargs)

    repository.update_processing_state = failing_success_update
    service = SingleDraftService(
        repository=repository,
        session_manager=FakeSessionManager(PortalSessionStatus.READY),
        draft_creator=SuccessDraftCreator(),
    )

    with pytest.raises(sqlite3.OperationalError):
        service.create_for_record(record_id)

    # The draft exists on the portal: the record must not become FAILED (retryable).
    assert repository.get(record_id).islem_durumu == InvoiceStatus.IN_PROGRESS.value
    assert repository.recover_stale_in_progress() == 1
    assert repository.get(record_id).islem_durumu == InvoiceStatus.NEEDS_REVIEW.value
