from pathlib import Path
from types import SimpleNamespace

import pytest

from invoice_automation.app.constants import InvoiceStatus
from invoice_automation.app.db.models import ImportBatchCreate, InvoiceRecordCreate
from invoice_automation.app.db.repository import InvoiceRecordRepository
from invoice_automation.app.services.cleanup_service import RecordCleanupService
from invoice_automation.app.utils.exceptions import DeletionBlockedError


class FakeJobManager:
    def __init__(self, job=None) -> None:
        self.job = job

    def current_job(self):
        return self.job


def _record(batch_id: int | None, ad: str, tckn: str, tutar: float = 100.0) -> InvoiceRecordCreate:
    return InvoiceRecordCreate(
        batch_id=batch_id,
        ad=ad,
        soyad="Test",
        tc_kimlik_no=tckn,
        tutar_usd=tutar,
    )


def _seed(repository: InvoiceRecordRepository):
    wrong, _ = repository.create_import(
        ImportBatchCreate(name="Yanlis", source_file_name="yanlis.xlsx"),
        [_record(None, "Ali", "10000000001"), _record(None, "Veli", "10000000002")],
    )
    kept, _ = repository.create_import(
        ImportBatchCreate(name="Dogru", source_file_name="dogru.xlsx"),
        [_record(None, "Ayse", "10000000003", 250.0)],
    )
    return wrong, kept


def test_delete_batch_removes_period_and_only_its_records(tmp_path: Path) -> None:
    repository = InvoiceRecordRepository(tmp_path / "test.sqlite3")
    wrong, kept = _seed(repository)

    deleted = RecordCleanupService(repository, FakeJobManager()).delete_batch(wrong.id)

    assert deleted == 2
    assert repository.get_import_batch(wrong.id) is None
    assert [batch.id for batch in repository.list_import_batches()] == [kept.id]
    assert [record.ad for record in repository.list_all()] == ["Ayse"]


def test_delete_batch_returns_none_for_missing_period(tmp_path: Path) -> None:
    repository = InvoiceRecordRepository(tmp_path / "test.sqlite3")

    assert RecordCleanupService(repository, FakeJobManager()).delete_batch(999) is None


def test_delete_batch_refused_while_record_in_progress(tmp_path: Path) -> None:
    repository = InvoiceRecordRepository(tmp_path / "test.sqlite3")
    wrong, _ = _seed(repository)
    record = repository.list_all(batch_id=wrong.id)[0]
    repository.claim_for_processing(record.id)

    with pytest.raises(DeletionBlockedError):
        RecordCleanupService(repository, FakeJobManager()).delete_batch(wrong.id)

    assert repository.get_import_batch(wrong.id) is not None
    assert len(repository.list_all(batch_id=wrong.id)) == 2


def test_delete_refused_while_batch_job_runs_for_that_period(tmp_path: Path) -> None:
    repository = InvoiceRecordRepository(tmp_path / "test.sqlite3")
    wrong, kept = _seed(repository)
    service = RecordCleanupService(
        repository,
        FakeJobManager(SimpleNamespace(is_active=True, batch_id=wrong.id)),
    )

    with pytest.raises(DeletionBlockedError):
        service.delete_batch(wrong.id)
    with pytest.raises(DeletionBlockedError):
        service.delete_records([1], batch_id=wrong.id)
    with pytest.raises(DeletionBlockedError):
        service.delete_unassigned_records()

    # Another period is not touched by the running job.
    assert service.delete_batch(kept.id) == 1


def test_finished_job_does_not_block_delete(tmp_path: Path) -> None:
    repository = InvoiceRecordRepository(tmp_path / "test.sqlite3")
    wrong, _ = _seed(repository)
    service = RecordCleanupService(
        repository,
        FakeJobManager(SimpleNamespace(is_active=False, batch_id=wrong.id)),
    )

    assert service.delete_batch(wrong.id) == 2


def test_delete_records_keeps_in_progress_and_other_periods(tmp_path: Path) -> None:
    repository = InvoiceRecordRepository(tmp_path / "test.sqlite3")
    wrong, kept = _seed(repository)
    first, second = repository.list_all(batch_id=wrong.id, sort_by="id", sort_dir="asc")
    other = repository.list_all(batch_id=kept.id)[0]
    repository.claim_for_processing(second.id)

    deleted = RecordCleanupService(repository, FakeJobManager()).delete_records(
        [first.id, second.id, other.id],
        batch_id=wrong.id,
    )

    assert deleted == 1
    assert repository.get(first.id) is None
    assert repository.get(second.id).islem_durumu == InvoiceStatus.IN_PROGRESS.value
    assert repository.get(other.id) is not None


def test_unassigned_records_are_counted_and_deleted(tmp_path: Path) -> None:
    repository = InvoiceRecordRepository(tmp_path / "test.sqlite3")
    _, kept = _seed(repository)
    repository.create(_record(None, "Eski", "10000000009"))
    repository.create(_record(4242, "Kayip", "10000000010"))

    assert repository.count_unassigned_records() == 2

    deleted = RecordCleanupService(repository, FakeJobManager()).delete_unassigned_records()

    assert deleted == 2
    assert repository.count_unassigned_records() == 0
    assert len(repository.list_all(batch_id=kept.id)) == 1


def test_batch_summaries_aggregate_status_groups(tmp_path: Path) -> None:
    repository = InvoiceRecordRepository(tmp_path / "test.sqlite3")
    batch, records = repository.create_import(
        ImportBatchCreate(name="Ekim", source_file_name="ekim.xlsx"),
        [
            _record(None, "A", "10000000001", 100.0),
            _record(None, "B", "10000000002", 200.0),
            _record(None, "C", "10000000003", 300.0),
            _record(None, "D", "10000000004", 400.0),
            _record(None, "E", "10000000005", 500.0),
        ],
    )
    empty = repository.create_import_batch(ImportBatchCreate(name="Bos", source_file_name="bos.csv"))
    repository.update_processing_state(records[1].id, InvoiceStatus.SUCCESS_DRAFT_CREATED)
    repository.update_processing_state(records[2].id, InvoiceStatus.FAILED_INVALID_TCKN)
    repository.update_processing_state(records[3].id, InvoiceStatus.SKIPPED_EFATURA_MUKELLEFI)
    repository.update_processing_state(records[4].id, InvoiceStatus.NEEDS_REVIEW)

    summaries = {summary.batch.id: summary for summary in repository.list_import_batch_summaries()}

    ekim = summaries[batch.id]
    assert ekim.record_count == 5
    assert ekim.total_usd == 1500.0
    assert ekim.waiting_count == 1
    assert ekim.success_count == 1
    assert ekim.failed_count == 2
    assert ekim.review_count == 1
    assert ekim.in_progress_count == 0
    assert summaries[empty.id].record_count == 0
    assert summaries[empty.id].total_usd == 0.0
