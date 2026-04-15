from pathlib import Path

from invoice_automation.app.constants import InvoiceStatus
from invoice_automation.app.db.models import InvoiceRecordCreate
from invoice_automation.app.db.repository import InvoiceRecordRepository


def test_repository_creates_and_lists_records(tmp_path: Path) -> None:
    repository = InvoiceRecordRepository(tmp_path / "test.sqlite3")

    created = repository.create(
        InvoiceRecordCreate(
            ad="Ali",
            soyad="Yilmaz",
            tc_kimlik_no="12345678901",
            tutar_usd=1500.0,
            aciklama="Test kaydi",
        )
    )

    records = repository.list_all()

    assert created.id > 0
    assert repository.count() == 1
    assert len(records) == 1
    assert records[0].ad == "Ali"
    assert records[0].islem_durumu == InvoiceStatus.PENDING.value


def test_repository_filters_by_status(tmp_path: Path) -> None:
    repository = InvoiceRecordRepository(tmp_path / "test.sqlite3")
    repository.create(
        InvoiceRecordCreate(
            ad="Ayse",
            soyad="Demir",
            tc_kimlik_no="12345678901",
            tutar_usd=2200.0,
            aciklama="Test kaydi",
        )
    )

    assert len(repository.list_all(status=InvoiceStatus.PENDING)) == 1
    assert len(repository.list_all(status=InvoiceStatus.FAILED_UNKNOWN)) == 0


def test_repository_updates_selection_statuses(tmp_path: Path) -> None:
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
    second = repository.create(
        InvoiceRecordCreate(
            ad="Ayse",
            soyad="Demir",
            tc_kimlik_no="10987654321",
            tutar_usd=2200.0,
            aciklama="Test kaydi",
        )
    )

    selected_count = repository.update_selection([first.id])

    assert selected_count == 1
    assert repository.get(first.id).secili_mi is True
    assert repository.get(first.id).islem_durumu == InvoiceStatus.SELECTED.value
    assert repository.get(second.id).secili_mi is False
    assert repository.get(second.id).islem_durumu == InvoiceStatus.PENDING.value


def test_repository_deselects_selected_records(tmp_path: Path) -> None:
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
    repository.update_selection([])

    reloaded = repository.get(record.id)
    assert reloaded.secili_mi is False
    assert reloaded.islem_durumu == InvoiceStatus.PENDING.value


def test_repository_does_not_select_finished_records(tmp_path: Path) -> None:
    repository = InvoiceRecordRepository(tmp_path / "test.sqlite3")
    record = repository.create(
        InvoiceRecordCreate(
            ad="Ali",
            soyad="Yilmaz",
            tc_kimlik_no="12345678901",
            tutar_usd=1500.0,
            aciklama="Test kaydi",
            islem_durumu=InvoiceStatus.SUCCESS_DRAFT_CREATED,
        )
    )

    selected_count = repository.update_selection([record.id])

    reloaded = repository.get(record.id)
    assert selected_count == 0
    assert reloaded.secili_mi is False
    assert reloaded.islem_durumu == InvoiceStatus.SUCCESS_DRAFT_CREATED.value


def test_repository_updates_processing_state(tmp_path: Path) -> None:
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

    updated = repository.update_processing_state(
        record.id,
        InvoiceStatus.FAILED_PORTAL_TIMEOUT,
        hata_kodu="PortalTimeoutError",
        hata_mesaji="Timeout",
        secili_mi=True,
    )

    assert updated.islem_durumu == InvoiceStatus.FAILED_PORTAL_TIMEOUT.value
    assert updated.hata_kodu == "PortalTimeoutError"
    assert updated.hata_mesaji == "Timeout"
    assert updated.secili_mi is True


def test_repository_lists_only_selected_eligible_records_for_batch(tmp_path: Path) -> None:
    repository = InvoiceRecordRepository(tmp_path / "test.sqlite3")
    pending = repository.create(
        InvoiceRecordCreate(
            ad="Ali",
            soyad="Yilmaz",
            tc_kimlik_no="12345678901",
            tutar_usd=1500.0,
            secili_mi=True,
            islem_durumu=InvoiceStatus.PENDING,
        )
    )
    selected = repository.create(
        InvoiceRecordCreate(
            ad="Ayse",
            soyad="Demir",
            tc_kimlik_no="10987654321",
            tutar_usd=2200.0,
            secili_mi=True,
            islem_durumu=InvoiceStatus.SELECTED,
        )
    )
    repository.create(
        InvoiceRecordCreate(
            ad="Veli",
            soyad="Kaya",
            tc_kimlik_no="11111111111",
            tutar_usd=900.0,
            secili_mi=True,
            islem_durumu=InvoiceStatus.FAILED_INVALID_TCKN,
        )
    )

    eligible_records = repository.list_selected_for_batch()

    assert [record.id for record in eligible_records] == [pending.id, selected.id]
