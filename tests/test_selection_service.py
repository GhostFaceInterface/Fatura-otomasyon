from pathlib import Path

from invoice_automation.app.constants import InvoiceStatus
from invoice_automation.app.db.models import InvoiceRecordCreate
from invoice_automation.app.db.repository import InvoiceRecordRepository
from invoice_automation.app.services.selection_service import SelectionService


def test_selection_service_persists_selected_records(tmp_path: Path) -> None:
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

    selected_records = SelectionService(repository).save_selection([first.id])

    assert len(selected_records) == 1
    assert selected_records[0].id == first.id
    assert selected_records[0].islem_durumu == InvoiceStatus.SELECTED.value
