from pathlib import Path

from invoice_automation.app.constants import InvoiceStatus
from invoice_automation.app.db.models import ImportBatchCreate, InvoiceRecordCreate
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


def test_repository_creates_import_batch_and_filters_records_by_batch(tmp_path: Path) -> None:
    repository = InvoiceRecordRepository(tmp_path / "test.sqlite3")
    april = repository.create_import_batch(
        ImportBatchCreate(name="Nisan", source_file_name="nisan.xlsx", sheet_name="Sayfa1")
    )
    may = repository.create_import_batch(
        ImportBatchCreate(name="Mayis", source_file_name="mayis.xlsx", sheet_name="Sayfa1")
    )
    repository.create(
        InvoiceRecordCreate(
            batch_id=april.id,
            ad="Ali",
            soyad="Yilmaz",
            tc_kimlik_no="12345678901",
            tutar_usd=1500.0,
        )
    )
    repository.create(
        InvoiceRecordCreate(
            batch_id=may.id,
            ad="Ayse",
            soyad="Demir",
            tc_kimlik_no="10987654321",
            tutar_usd=2200.0,
        )
    )

    april_records = repository.list_all(batch_id=april.id)

    assert [batch.name for batch in repository.list_import_batches()] == ["Mayis", "Nisan"]
    assert len(april_records) == 1
    assert april_records[0].ad == "Ali"


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


def test_repository_searches_records_inside_batch(tmp_path: Path) -> None:
    repository = InvoiceRecordRepository(tmp_path / "test.sqlite3")
    batch = repository.create_import_batch(
        ImportBatchCreate(name="Nisan", source_file_name="nisan.xlsx", sheet_name="Sayfa1")
    )
    repository.create(
        InvoiceRecordCreate(
            batch_id=batch.id,
            ad="Ali",
            soyad="Yilmaz",
            tc_kimlik_no="12345678901",
            tutar_usd=1500.0,
        )
    )
    repository.create(
        InvoiceRecordCreate(
            batch_id=batch.id,
            ad="Ayse",
            soyad="Demir",
            tc_kimlik_no="10987654321",
            tutar_usd=2200.0,
        )
    )

    records = repository.list_all(batch_id=batch.id, search="109876")

    assert len(records) == 1
    assert records[0].ad == "Ayse"


def test_repository_search_handles_turkish_case(tmp_path: Path) -> None:
    repository = InvoiceRecordRepository(tmp_path / "test.sqlite3")
    batch = repository.create_import_batch(
        ImportBatchCreate(name="Nisan", source_file_name="nisan.xlsx", sheet_name="Sayfa1")
    )
    repository.create(
        InvoiceRecordCreate(
            batch_id=batch.id,
            ad="ŞÜKRAN",
            soyad="ARSLAN",
            tc_kimlik_no="12345678901",
            tutar_usd=1500.0,
        )
    )

    records = repository.list_all(batch_id=batch.id, search="şü")

    assert len(records) == 1
    assert records[0].ad == "ŞÜKRAN"


def test_repository_sorts_records_by_allowed_fields(tmp_path: Path) -> None:
    repository = InvoiceRecordRepository(tmp_path / "test.sqlite3")
    repository.create(
        InvoiceRecordCreate(
            ad="Zeynep",
            soyad="Arslan",
            tc_kimlik_no="30000000000",
            tutar_usd=900.0,
        )
    )
    repository.create(
        InvoiceRecordCreate(
            ad="Ali",
            soyad="Yilmaz",
            tc_kimlik_no="10000000000",
            tutar_usd=1500.0,
        )
    )
    repository.create(
        InvoiceRecordCreate(
            ad="Mehmet",
            soyad="Demir",
            tc_kimlik_no="20000000000",
            tutar_usd=1200.0,
        )
    )

    by_name = repository.list_all(sort_by="ad", sort_dir="asc")
    by_amount = repository.list_all(sort_by="tutar_usd", sort_dir="desc")
    by_tckn = repository.list_all(sort_by="tc_kimlik_no", sort_dir="asc")

    assert [record.ad for record in by_name] == ["Ali", "Mehmet", "Zeynep"]
    assert [record.tutar_usd for record in by_amount] == [1500.0, 1200.0, 900.0]
    assert [record.tc_kimlik_no for record in by_tckn] == [
        "10000000000",
        "20000000000",
        "30000000000",
    ]


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


def _new_record(repository: InvoiceRecordRepository, tc: str = "12345678901"):
    return repository.create(
        InvoiceRecordCreate(ad="Ali", soyad="Yilmaz", tc_kimlik_no=tc, tutar_usd=100.0)
    )


def test_claim_for_processing_is_atomic_and_only_once(tmp_path: Path) -> None:
    repository = InvoiceRecordRepository(tmp_path / "test.sqlite3")
    record = _new_record(repository)

    first = repository.claim_for_processing(record.id)
    second = repository.claim_for_processing(record.id)

    assert first is not None
    assert first.islem_durumu == InvoiceStatus.IN_PROGRESS.value
    assert second is None


def test_claim_for_processing_is_exclusive_across_threads(tmp_path: Path) -> None:
    import threading

    repository = InvoiceRecordRepository(tmp_path / "test.sqlite3")
    record = _new_record(repository)
    barrier = threading.Barrier(8)
    results: list[bool] = []

    def claim() -> None:
        barrier.wait()
        results.append(repository.claim_for_processing(record.id) is not None)

    threads = [threading.Thread(target=claim) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert results.count(True) == 1


def test_recover_stale_in_progress_moves_records_to_needs_review(tmp_path: Path) -> None:
    repository = InvoiceRecordRepository(tmp_path / "test.sqlite3")
    stuck = _new_record(repository, "12345678901")
    untouched = _new_record(repository, "12345678902")
    repository.claim_for_processing(stuck.id)

    assert repository.recover_stale_in_progress() == 1

    recovered = repository.get(stuck.id)
    assert recovered.islem_durumu == InvoiceStatus.NEEDS_REVIEW.value
    assert recovered.hata_kodu == "StaleInProgressRecovered"
    assert recovered.secili_mi is False
    assert repository.get(untouched.id).islem_durumu == InvoiceStatus.PENDING.value
    assert repository.recover_stale_in_progress() == 0


def test_reset_failed_to_pending_only_touches_retryable_statuses(tmp_path: Path) -> None:
    repository = InvoiceRecordRepository(tmp_path / "test.sqlite3")
    failed = _new_record(repository, "12345678901")
    aborted = _new_record(repository, "12345678902")
    success = _new_record(repository, "12345678903")
    review = _new_record(repository, "12345678904")
    skipped = _new_record(repository, "12345678905")
    repository.update_processing_state(
        failed.id, InvoiceStatus.FAILED_PORTAL_TIMEOUT, hata_kodu="X", hata_mesaji="x", secili_mi=True
    )
    repository.update_processing_state(aborted.id, InvoiceStatus.ABORTED_SESSION_LOST)
    repository.update_processing_state(success.id, InvoiceStatus.SUCCESS_DRAFT_CREATED)
    repository.update_processing_state(review.id, InvoiceStatus.NEEDS_REVIEW)
    repository.update_processing_state(skipped.id, InvoiceStatus.SKIPPED_EFATURA_MUKELLEFI)

    reset = repository.reset_failed_to_pending(
        [failed.id, aborted.id, success.id, review.id, skipped.id]
    )

    assert reset == 2
    reset_record = repository.get(failed.id)
    assert reset_record.islem_durumu == InvoiceStatus.PENDING.value
    assert reset_record.hata_kodu is None
    assert reset_record.secili_mi is False
    assert repository.get(aborted.id).islem_durumu == InvoiceStatus.PENDING.value
    assert repository.get(success.id).islem_durumu == InvoiceStatus.SUCCESS_DRAFT_CREATED.value
    assert repository.get(review.id).islem_durumu == InvoiceStatus.NEEDS_REVIEW.value
    assert repository.get(skipped.id).islem_durumu == InvoiceStatus.SKIPPED_EFATURA_MUKELLEFI.value


def test_resolve_needs_review_requires_review_status(tmp_path: Path) -> None:
    repository = InvoiceRecordRepository(tmp_path / "test.sqlite3")
    exists = _new_record(repository, "12345678901")
    missing = _new_record(repository, "12345678902")
    pending = _new_record(repository, "12345678903")
    repository.update_processing_state(exists.id, InvoiceStatus.NEEDS_REVIEW)
    repository.update_processing_state(missing.id, InvoiceStatus.NEEDS_REVIEW)

    resolved_exists = repository.resolve_needs_review(exists.id, draft_exists=True)
    resolved_missing = repository.resolve_needs_review(missing.id, draft_exists=False)

    assert resolved_exists.islem_durumu == InvoiceStatus.SUCCESS_DRAFT_CREATED.value
    assert resolved_missing.islem_durumu == InvoiceStatus.PENDING.value
    assert repository.resolve_needs_review(pending.id, draft_exists=True) is None
    assert repository.get(pending.id).islem_durumu == InvoiceStatus.PENDING.value


def test_initialize_database_migrates_pre_batch_schema(tmp_path: Path) -> None:
    import sqlite3

    from invoice_automation.app.db.database import initialize_database

    db_path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(db_path)
    connection.executescript(
        """
        CREATE TABLE invoice_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ad TEXT NOT NULL,
            soyad TEXT NOT NULL,
            tc_kimlik_no TEXT NOT NULL,
            tutar_usd REAL NOT NULL,
            aciklama TEXT,
            fatura_tipi_hedef TEXT NOT NULL DEFAULT 'earshiv',
            kaynak_dosya TEXT,
            kaynak_satir_no INTEGER,
            secili_mi INTEGER NOT NULL DEFAULT 0,
            islem_durumu TEXT NOT NULL DEFAULT 'PENDING',
            portal_ref_no TEXT,
            hata_kodu TEXT,
            hata_mesaji TEXT,
            olusturma_zamani TEXT NOT NULL,
            guncelleme_zamani TEXT NOT NULL
        );
        INSERT INTO invoice_records (ad, soyad, tc_kimlik_no, tutar_usd, olusturma_zamani, guncelleme_zamani)
        VALUES ('Ali', 'Yilmaz', '12345678901', 100.0, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z');
        """
    )
    connection.commit()
    connection.close()

    initialize_database(db_path)
    initialize_database(db_path)

    connection = sqlite3.connect(db_path)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(invoice_records)")}
    indexes = {row[1] for row in connection.execute("PRAGMA index_list(invoice_records)")}
    connection.close()
    assert "batch_id" in columns
    assert "idx_invoice_records_batch_id" in indexes
    assert InvoiceRecordRepository(db_path).count() == 1
