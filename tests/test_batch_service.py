from pathlib import Path

from invoice_automation.app.db.models import InvoiceRecordCreate
from invoice_automation.app.db.repository import InvoiceRecordRepository
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
