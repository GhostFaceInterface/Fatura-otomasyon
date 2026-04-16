from pathlib import Path

import pandas as pd
import pytest

from invoice_automation.app.db.repository import InvoiceRecordRepository
from invoice_automation.app.services.import_service import ImportService, parse_currency
from invoice_automation.app.utils.exceptions import ImportValidationError


def test_import_service_imports_valid_csv_rows(tmp_path: Path) -> None:
    csv_path = tmp_path / "valid.csv"
    csv_path.write_text(
        "ad,soyad,tc_kimlik_no,tutar_usd,aciklama\n"
        "Ali,Yilmaz,12345678901,1500,Yurt disi konaklama\n",
        encoding="utf-8",
    )
    repository = InvoiceRecordRepository(tmp_path / "test.sqlite3")

    result = ImportService(repository).import_file(csv_path)

    assert result.imported_count == 1
    assert result.failed_count == 0
    assert repository.count() == 1
    assert repository.list_all()[0].kaynak_dosya == "valid.csv"
    assert result.batch is not None
    assert repository.list_all()[0].batch_id == result.batch.id


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("$1.450", 1450.0),
        ("$850", 850.0),
        ("1.350", 1350.0),
        ("1350", 1350.0),
        ("$1,450", 1450.0),
        ("$1450.75", 1450.75),
    ],
)
def test_parse_currency_normalizes_import_amounts(raw_value: str, expected: float) -> None:
    assert parse_currency(raw_value) == expected


@pytest.mark.parametrize("raw_value", ["", "   ", None, "abc"])
def test_parse_currency_rejects_empty_or_unparseable_values(raw_value) -> None:
    with pytest.raises(ValueError):
        parse_currency(raw_value)


def test_import_service_normalizes_currency_amounts_before_persisting(tmp_path: Path) -> None:
    csv_path = tmp_path / "amounts.csv"
    csv_path.write_text(
        "ad,soyad,tc_kimlik_no,tutar_usd,aciklama\n"
        'Ali,Yilmaz,12345678901,"$1.450",Gecerli\n'
        'Ayse,Demir,10987654321,"$1,450",Gecerli\n',
        encoding="utf-8",
    )
    repository = InvoiceRecordRepository(tmp_path / "test.sqlite3")

    result = ImportService(repository).import_file(csv_path)
    records = repository.list_all(batch_id=result.batch.id)

    assert result.imported_count == 2
    assert result.failed_count == 0
    assert sorted(record.tutar_usd for record in records) == [1450.0, 1450.0]


def test_import_service_rejects_missing_columns(tmp_path: Path) -> None:
    csv_path = tmp_path / "missing.csv"
    csv_path.write_text("ad,soyad\nAli,Yilmaz\n", encoding="utf-8")
    repository = InvoiceRecordRepository(tmp_path / "test.sqlite3")

    with pytest.raises(ImportValidationError):
        ImportService(repository).import_file(csv_path)


def test_import_service_skips_invalid_rows_without_crashing(tmp_path: Path) -> None:
    csv_path = tmp_path / "mixed.csv"
    csv_path.write_text(
        "ad,soyad,tc_kimlik_no,tutar_usd,aciklama\n"
        "Ali,Yilmaz,12345678901,1500,Gecerli\n"
        "Ayse,Demir,invalid,2200,Hatali tckn\n"
        "Mehmet,Kaya,10987654321,-10,Hatali tutar\n",
        encoding="utf-8",
    )
    repository = InvoiceRecordRepository(tmp_path / "test.sqlite3")

    result = ImportService(repository).import_file(csv_path)

    assert result.imported_count == 1
    assert result.failed_count == 2
    assert repository.count() == 1
    assert [error.row_number for error in result.row_errors] == [3, 4]


def test_import_service_imports_selected_excel_sheet_with_column_mapping(tmp_path: Path) -> None:
    excel_path = tmp_path / "payments.xlsx"
    with pd.ExcelWriter(excel_path) as writer:
        pd.DataFrame({"ignored": ["x"]}).to_excel(writer, sheet_name="Bos", index=False)
        pd.DataFrame(
            {
                "Adi": ["Ali"],
                "Soyadi": ["Yilmaz"],
                "Kimlik": ["12345678901"],
                "Odenen": ["1500"],
            }
        ).to_excel(writer, sheet_name="Nisan", index=False)
    repository = InvoiceRecordRepository(tmp_path / "test.sqlite3")

    inspection = ImportService(repository).inspect_file(excel_path, sheet_name="Nisan")
    result = ImportService(repository).import_file(
        excel_path,
        batch_name="2026-04 Nisan",
        sheet_name="Nisan",
        column_mapping={
            "ad": "Adi",
            "soyad": "Soyadi",
            "tc_kimlik_no": "Kimlik",
            "tutar_usd": "Odenen",
            "aciklama": "",
        },
    )

    records = repository.list_all(batch_id=result.batch.id)
    assert inspection.sheet_names == ["Bos", "Nisan"]
    assert inspection.columns == ["Adi", "Soyadi", "Kimlik", "Odenen"]
    assert result.batch.name == "2026-04 Nisan"
    assert result.batch.sheet_name == "Nisan"
    assert len(records) == 1
    assert records[0].ad == "Ali"
