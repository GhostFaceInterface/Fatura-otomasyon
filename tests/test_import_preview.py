from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from invoice_automation.app.db.repository import InvoiceRecordRepository
from invoice_automation.app.schemas.invoice_record import PreviewRow
from invoice_automation.app.services.import_service import (
    ImportService,
    check_preview_rows,
    parse_amount,
    summarize_preview,
)
from invoice_automation.app.utils.exceptions import ImportValidationError


def _write_csv(tmp_path: Path, body: str) -> Path:
    csv_path = tmp_path / "people.csv"
    csv_path.write_text("ad,soyad,tc_kimlik_no,tutar_usd,aciklama\n" + body, encoding="utf-8")
    return csv_path


def _row(ad="Ali", soyad="Yilmaz", tc="12345678901", tutar="100", aciklama="", **kwargs) -> PreviewRow:
    values = {"ad": ad, "soyad": soyad, "tc_kimlik_no": tc, "tutar_usd": tutar, "aciklama": aciklama}
    return PreviewRow(values=values, **kwargs)


def _service(tmp_path: Path) -> tuple[ImportService, InvoiceRecordRepository]:
    repository = InvoiceRecordRepository(tmp_path / "test.sqlite3")
    return ImportService(repository), repository


def test_read_preview_rows_cleans_values_and_writes_nothing(tmp_path: Path) -> None:
    csv_path = _write_csv(
        tmp_path,
        '  Ali ,Yilmaz,12345678901.0,"$1.450",Konaklama\n'
        ",,,,\n"
        "Ayse,Demir,123,abc,\n",
    )
    service, repository = _service(tmp_path)

    rows = service.read_preview_rows(csv_path)

    assert [row.source_row for row in rows] == [2, 4]  # empty line 3 is left out
    assert rows[0].values == {
        "ad": "Ali",
        "soyad": "Yilmaz",
        "tc_kimlik_no": "12345678901",
        "tutar_usd": "1450.00",
        "aciklama": "Konaklama",
    }
    assert rows[0].original == rows[0].values
    assert rows[0].errors == {}
    assert set(rows[1].errors) == {"tc_kimlik_no", "tutar_usd"}
    assert repository.count() == 0
    assert repository.list_import_batches() == []


def test_import_preview_rows_saves_edits_removals_and_additions(tmp_path: Path) -> None:
    csv_path = _write_csv(
        tmp_path,
        "Ali,Yilmaz,12345678901,1500,\n"
        "Ayse,Demir,10987654321,2200,\n"
        "Veli,Kaya,11111111111,900,\n",
    )
    service, repository = _service(tmp_path)
    ali, ayse, veli = service.read_preview_rows(csv_path)

    edited = [
        replace(ali, values={**ali.values, "tutar_usd": "1.750,50"}),  # amount changed
        replace(ayse, removed=True),  # deleted
        veli,
        _row(ad="Zeynep", soyad="Ak", tc="22222222222", tutar="300"),  # added by hand
        _row(ad="", soyad="", tc="", tutar=""),  # empty added row is ignored
    ]
    result = service.import_preview_rows(
        edited, batch_name="  Ekim   2026 ", source_file_name="people.csv", sheet_name="CSV"
    )

    records = repository.list_all(batch_id=result.batch.id, sort_by="id", sort_dir="asc")
    assert result.imported_count == 3
    assert result.batch.name == "Ekim 2026"
    assert [(r.ad, r.tc_kimlik_no, r.tutar_usd, r.kaynak_satir_no) for r in records] == [
        ("Ali", "12345678901", 1750.5, 2),
        ("Veli", "11111111111", 900.0, 4),
        ("Zeynep", "22222222222", 300.0, None),
    ]
    assert all(record.islem_durumu == "PENDING" and record.kaynak_dosya == "people.csv" for record in records)
    assert repository.count() == 3


def test_import_preview_rows_writes_nothing_when_a_row_is_invalid(tmp_path: Path) -> None:
    service, repository = _service(tmp_path)
    rows = [_row(), _row(ad="Ayse", tc="10987654321", tutar="0")]

    with pytest.raises(ImportValidationError, match="1 satırda hata"):
        service.import_preview_rows(rows, batch_name="Ekim", source_file_name="x.csv", sheet_name=None)

    assert repository.count() == 0
    assert repository.list_import_batches() == []


def test_removed_invalid_row_does_not_block_import(tmp_path: Path) -> None:
    service, repository = _service(tmp_path)
    rows = [_row(), _row(ad="", tc="bad", tutar="x", removed=True, source_row=3)]

    result = service.import_preview_rows(rows, batch_name="Ekim", source_file_name="x.csv", sheet_name=None)

    assert result.imported_count == 1
    assert repository.count() == 1


@pytest.mark.parametrize(
    ("batch_name", "rows", "message"),
    [
        ("   ", [_row()], "Dönem adı"),
        ("Ekim", [_row(removed=True)], "kişi yok"),
        ("Ekim", [], "kişi yok"),
    ],
)
def test_import_preview_rows_rejects_empty_input(tmp_path: Path, batch_name, rows, message) -> None:
    service, repository = _service(tmp_path)

    with pytest.raises(ImportValidationError, match=message):
        service.import_preview_rows(rows, batch_name=batch_name, source_file_name="x.csv", sheet_name=None)

    assert repository.list_import_batches() == []


def test_import_preview_rows_rolls_back_on_database_failure(tmp_path: Path, monkeypatch) -> None:
    service, repository = _service(tmp_path)
    from invoice_automation.app.db import repository as repository_module

    original_insert = repository_module._insert_record
    calls = {"count": 0}

    def failing_insert(connection, record, now):
        calls["count"] += 1
        if calls["count"] == 2:
            raise RuntimeError("disk full")
        return original_insert(connection, record, now)

    monkeypatch.setattr(repository_module, "_insert_record", failing_insert)
    rows = [_row(), _row(ad="Ayse", tc="10987654321")]

    with pytest.raises(RuntimeError):
        service.import_preview_rows(rows, batch_name="Ekim", source_file_name="x.csv", sheet_name=None)

    assert repository.count() == 0
    assert repository.list_import_batches() == []


def test_check_preview_rows_marks_errors_per_field_and_duplicate_tckn() -> None:
    rows = check_preview_rows(
        [
            _row(),
            _row(ad="Ayse", soyad=""),  # same TCKN as the first row
            _row(ad="Veli", tc="12345678901", removed=True),  # removed: not counted
            _row(ad="", soyad="", tc="", tutar=""),  # empty added row: no errors
        ]
    )

    assert rows[0].errors == {}
    assert rows[0].warnings == {"tc_kimlik_no": "Aynı TCKN: yeni eklenen satır Ayse"}
    assert rows[1].errors == {"soyad": "Soyad boş olamaz."}
    assert rows[2].errors == {} and rows[2].warnings == {}
    assert rows[3].errors == {}

    summary = summarize_preview(rows)
    assert summary == {"count": 2, "total_usd": "100.00", "error_count": 1, "removed_count": 1}


def test_duplicate_tckn_warning_names_the_other_rows() -> None:
    rows = check_preview_rows(
        [
            _row(ad="FATIM", soyad="KAYA", tc="60763196402", source_row=13),
            _row(ad="HEDİYE", soyad="ÇEBER", tc="60763196402", source_row=56),
            _row(ad="Ali", soyad="Veli", tc="60763196402"),  # added by hand, no row number
            _row(ad="Tek", soyad="Kişi", tc="11111111111", source_row=14),
        ]
    )

    assert [row.warnings.get("tc_kimlik_no") for row in rows] == [
        "Aynı TCKN: 56. satır HEDİYE ÇEBER, yeni eklenen satır Ali Veli",
        "Aynı TCKN: 13. satır FATIM KAYA, yeni eklenen satır Ali Veli",
        "Aynı TCKN: 13. satır FATIM KAYA, 56. satır HEDİYE ÇEBER",
        None,
    ]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1450", "1450.00"),
        ("$1.450", "1450.00"),
        ("1,450", "1450.00"),
        ("1450,5", "1450.50"),
        ("1.450,75", "1450.75"),
        ("1450.10000000000001", "1450.10"),  # Excel float noise
    ],
)
def test_parse_amount_accepts_common_formats(raw: str, expected: str) -> None:
    assert parse_amount(raw) == Decimal(expected)


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ("", "boş"),
        ("abc", "sayı olmalı"),
        ("NaN", "sayı olmalı"),
        ("0", "0'dan büyük"),
        ("-5", "0'dan büyük"),
        ("10,505", None),  # read as 10505 (thousands), which is valid
        ("10.5051", "2 ondalık"),
    ],
)
def test_parse_amount_rejects_bad_values(raw: str, message: str | None) -> None:
    if message is None:
        assert parse_amount(raw) == Decimal("10505")
        return
    with pytest.raises(ValueError, match=message):
        parse_amount(raw)


def test_cleaned_amount_reads_back_to_the_same_value() -> None:
    # The preview writes the cleaned value back into the cell; reading it again
    # must not change it (e.g. "1450.50" must never become 145050).
    for raw in ["1.450", "1450,5", "0.99", "1.234.567,89"]:
        once = check_preview_rows([_row(tutar=raw)])[0].values["tutar_usd"]
        twice = check_preview_rows([_row(tutar=once)])[0].values["tutar_usd"]
        assert once == twice
