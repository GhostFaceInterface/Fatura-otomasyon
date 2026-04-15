from pathlib import Path

import pytest

from invoice_automation.app.db.repository import InvoiceRecordRepository
from invoice_automation.app.services.import_service import ImportService
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
