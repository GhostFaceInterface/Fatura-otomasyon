"""CSV and Excel import service."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
import unicodedata

import pandas as pd

from invoice_automation.app.constants import SUPPORTED_IMPORT_EXTENSIONS
from invoice_automation.app.db.models import InvoiceRecordCreate
from invoice_automation.app.db.repository import InvoiceRecordRepository
from invoice_automation.app.schemas.invoice_record import ImportResult, RowValidationError
from invoice_automation.app.services.validation_service import (
    validate_import_row,
    validate_required_columns,
)
from invoice_automation.app.utils.exceptions import ImportValidationError, UnsupportedFileTypeError

logger = logging.getLogger(__name__)


COLUMN_ALIASES = {
    "ad": "ad",
    "adi": "ad",
    "isim": "ad",
    "soyad": "soyad",
    "soyadi": "soyad",
    "soyisim": "soyad",
    "tc": "tc_kimlik_no",
    "tckn": "tc_kimlik_no",
    "tc_no": "tc_kimlik_no",
    "tc_kimlik": "tc_kimlik_no",
    "tc_kimlik_no": "tc_kimlik_no",
    "tutar": "tutar_usd",
    "usd_tutar": "tutar_usd",
    "tutar_usd": "tutar_usd",
    "aciklama": "aciklama",
}


def normalize_column_name(column_name: str) -> str:
    """Normalize source column names for predictable import handling."""

    text = str(column_name).strip().lower()
    text = text.translate(str.maketrans({"ı": "i", "İ": "i"}))
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.replace("/", " ").replace("-", " ").replace(".", " ")
    text = "_".join(part for part in text.split() if part)
    return COLUMN_ALIASES.get(text, text)


class ImportService:
    """Import records from CSV or Excel files into SQLite."""

    def __init__(self, repository: InvoiceRecordRepository | None = None) -> None:
        self.repository = repository or InvoiceRecordRepository()

    def import_file(self, file_path: Path) -> ImportResult:
        """Read an import file, persist valid rows, and report invalid rows."""

        if not file_path.exists():
            raise ImportValidationError(f"Dosya bulunamadi: {file_path}")

        extension = file_path.suffix.lower()
        if extension not in SUPPORTED_IMPORT_EXTENSIONS:
            supported = ", ".join(SUPPORTED_IMPORT_EXTENSIONS)
            raise UnsupportedFileTypeError(f"Desteklenmeyen dosya tipi. Desteklenen: {supported}.")

        dataframe = self._read_dataframe(file_path)
        dataframe = self._normalize_dataframe(dataframe)
        validate_required_columns(dataframe.columns)

        records = []
        row_errors: list[RowValidationError] = []

        for index, row in dataframe.iterrows():
            source_row_number = int(index) + 2
            raw_data = self._row_to_clean_dict(row.to_dict())
            validated_data, errors = validate_import_row(raw_data)
            if errors:
                row_errors.append(
                    RowValidationError(
                        row_number=source_row_number,
                        errors=errors,
                        raw_data=raw_data,
                    )
                )
                logger.info(
                    "Import row skipped | file=%s row=%s errors=%s",
                    file_path.name,
                    source_row_number,
                    errors,
                )
                continue

            assert validated_data is not None
            created_record = self.repository.create(
                InvoiceRecordCreate(
                    **validated_data,
                    kaynak_dosya=file_path.name,
                    kaynak_satir_no=source_row_number,
                )
            )
            records.append(created_record)

        logger.info(
            "Import completed | file=%s imported=%s failed=%s",
            file_path.name,
            len(records),
            len(row_errors),
        )

        return ImportResult(
            source_file=file_path.name,
            imported_count=len(records),
            failed_count=len(row_errors),
            records=records,
            row_errors=row_errors,
        )

    def _read_dataframe(self, file_path: Path) -> pd.DataFrame:
        extension = file_path.suffix.lower()
        if extension == ".csv":
            return pd.read_csv(file_path, dtype=str, keep_default_na=False)
        return pd.read_excel(file_path, dtype=str, keep_default_na=False)

    def _normalize_dataframe(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        normalized_columns = [normalize_column_name(column) for column in dataframe.columns]
        dataframe = dataframe.copy()
        dataframe.columns = normalized_columns
        return dataframe

    def _row_to_clean_dict(self, row: dict[str, Any]) -> dict[str, Any]:
        clean_row: dict[str, Any] = {}
        for key, value in row.items():
            if pd.isna(value):
                clean_row[key] = ""
            else:
                clean_row[key] = value
        return clean_row
