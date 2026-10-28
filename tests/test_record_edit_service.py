from pathlib import Path
from types import SimpleNamespace

import pytest

from invoice_automation.app.constants import InvoiceStatus
from invoice_automation.app.db.models import ImportBatchCreate, InvoiceRecordCreate
from invoice_automation.app.db.repository import InvoiceRecordRepository
from invoice_automation.app.services.record_edit_service import RecordEditService
from invoice_automation.app.utils.exceptions import RecordEditBlockedError


class FakeJobManager:
    def __init__(self, job=None) -> None:
        self.job = job

    def current_job(self):
        return self.job


def _person(index: int, status: InvoiceStatus) -> InvoiceRecordCreate:
    return InvoiceRecordCreate(
        ad=f"Ad{index}",
        soyad="Soy",
        tc_kimlik_no=f"{10000000000 + index}",
        tutar_usd=2100.0,
        islem_durumu=status,
    )


def _setup(tmp_path: Path):
    repository = InvoiceRecordRepository(tmp_path / "test.sqlite3")
    statuses = [
        InvoiceStatus.PENDING,
        InvoiceStatus.SELECTED,
        InvoiceStatus.FAILED_NAME_MISMATCH,
        InvoiceStatus.SUCCESS_DRAFT_CREATED,
        InvoiceStatus.IN_PROGRESS,
        InvoiceStatus.NEEDS_REVIEW,
    ]
    batch, records = repository.create_import(
        ImportBatchCreate(name="Ekim", source_file_name="x.xlsx"),
        [_person(index, status) for index, status in enumerate(statuses)],
    )
    other_batch, other_records = repository.create_import(
        ImportBatchCreate(name="Kasim", source_file_name="y.xlsx"),
        [_person(99, InvoiceStatus.PENDING)],
    )
    return repository, batch, records, other_batch, other_records


def _amounts(repository: InvoiceRecordRepository, batch_id: int) -> dict[str, float]:
    return {
        record.islem_durumu: record.tutar_usd
        for record in repository.list_all(batch_id=batch_id)
    }


def test_update_amount_changes_only_records_without_a_draft(tmp_path: Path) -> None:
    repository, batch, records, other_batch, other_records = _setup(tmp_path)
    service = RecordEditService(repository=repository, job_manager=FakeJobManager())

    updated, shown = service.update_amount(
        [record.id for record in records] + [other_records[0].id],  # one id from another period
        "2.250,50",
        batch_id=batch.id,
    )

    assert (updated, shown) == (3, "2250.50")
    assert _amounts(repository, batch.id) == {
        "PENDING": 2250.5,
        "SELECTED": 2250.5,
        "FAILED_NAME_MISMATCH": 2250.5,
        "SUCCESS_DRAFT_CREATED": 2100.0,  # draft exists on the portal
        "IN_PROGRESS": 2100.0,  # being drafted right now
        "NEEDS_REVIEW": 2100.0,  # a draft may exist
    }
    assert repository.get(other_records[0].id).tutar_usd == 2100.0


@pytest.mark.parametrize(("raw", "message"), [("", "boş"), ("abc", "sayı"), ("0", "0'dan büyük")])
def test_update_amount_rejects_invalid_amount_and_writes_nothing(tmp_path: Path, raw, message) -> None:
    repository, batch, records, _other_batch, _other_records = _setup(tmp_path)
    service = RecordEditService(repository=repository, job_manager=FakeJobManager())

    with pytest.raises(ValueError, match=message):
        service.update_amount([records[0].id], raw, batch_id=batch.id)

    assert repository.get(records[0].id).tutar_usd == 2100.0


def test_update_amount_is_blocked_while_a_job_runs_on_the_period(tmp_path: Path) -> None:
    repository, batch, records, other_batch, other_records = _setup(tmp_path)
    running = SimpleNamespace(is_active=True, batch_id=batch.id)
    service = RecordEditService(repository=repository, job_manager=FakeJobManager(running))

    with pytest.raises(RecordEditBlockedError):
        service.update_amount([records[0].id], "2500", batch_id=batch.id)
    assert repository.get(records[0].id).tutar_usd == 2100.0

    # A job on another period does not block this one.
    updated, _shown = service.update_amount([other_records[0].id], "2500", batch_id=other_batch.id)
    assert updated == 1
    assert repository.get(other_records[0].id).tutar_usd == 2500.0
