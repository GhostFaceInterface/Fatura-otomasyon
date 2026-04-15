from pathlib import Path

from invoice_automation.app.db.models import InvoiceRecordCreate
from invoice_automation.app.db.repository import InvoiceRecordRepository
from invoice_automation.app.schemas.batch import BatchRunReport
from invoice_automation.app.services.batch_service import BatchService


def test_batch_service_returns_selected_record_preview(tmp_path: Path) -> None:
    repository = InvoiceRecordRepository(tmp_path / "test.sqlite3")
    first = repository.create(
        InvoiceRecordCreate(
            ad="Ali",
            soyad="Yilmaz",
            tc_kimlik_no="12345678901",
            tutar_usd=1500.0,
            aciklama="Test kaydi",
        )
    )
    repository.create(
        InvoiceRecordCreate(
            ad="Ayse",
            soyad="Demir",
            tc_kimlik_no="10987654321",
            tutar_usd=2200.0,
            aciklama="Test kaydi",
        )
    )
    repository.update_selection([first.id])

    preview = BatchService(repository).preview()

    assert preview.total_selected == 1
    assert preview.total_amount_usd == 1500.0
    assert preview.completed_count == 0
    assert preview.progress_percent == 0
    assert preview.records[0].id == first.id


def test_batch_service_prepare_uses_preview_contract(tmp_path: Path) -> None:
    repository = InvoiceRecordRepository(tmp_path / "test.sqlite3")
    record = repository.create(
        InvoiceRecordCreate(
            ad="Ali",
            soyad="Yilmaz",
            tc_kimlik_no="12345678901",
            tutar_usd=1500.0,
            aciklama="Test kaydi",
        )
    )
    repository.update_selection([record.id])

    preview = BatchService(repository).prepare_selected_batch()

    assert preview.to_dict()["total_selected"] == 1
    assert len(preview.to_dict()["records"]) == 1


def test_batch_service_runs_only_selected_eligible_records(tmp_path: Path) -> None:
    repository = InvoiceRecordRepository(tmp_path / "test.sqlite3")
    first = repository.create(
        InvoiceRecordCreate(
            ad="Ali",
            soyad="Yilmaz",
            tc_kimlik_no="12345678901",
            tutar_usd=1500.0,
        )
    )
    second = repository.create(
        InvoiceRecordCreate(
            ad="Ayse",
            soyad="Demir",
            tc_kimlik_no="10987654321",
            tutar_usd=2200.0,
        )
    )
    repository.update_selection([first.id, second.id])
    repository.update_processing_state(second.id, status=_status("FAILED_INVALID_TCKN"), secili_mi=True)
    runner = FakeBatchRunner()

    report = BatchService(repository, runner=runner).run_selected_batch()

    assert runner.record_ids == [first.id]
    assert report.total_selected == 1


class FakeBatchRunner:
    def __init__(self) -> None:
        self.record_ids: list[int] = []

    def run(self, records) -> BatchRunReport:
        self.record_ids = [record.id for record in records]
        return BatchRunReport(
            total_selected=len(records),
            total_processed=0,
            success_count=0,
            skipped_count=0,
            failed_count=0,
            aborted_count=0,
            results_by_status={},
            processed_record_ids=[],
            failed_record_ids=[],
            skipped_record_ids=[],
            aborted_due_to_session_loss=False,
            started_at="2026-04-16T00:00:00Z",
            ended_at="2026-04-16T00:00:00Z",
            duration_seconds=0.0,
            details=[],
        )


def _status(value: str):
    from invoice_automation.app.constants import InvoiceStatus

    return InvoiceStatus(value)
