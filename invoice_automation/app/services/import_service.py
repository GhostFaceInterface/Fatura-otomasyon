"""CSV and Excel import service."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
import unicodedata

import pandas as pd

from invoice_automation.app.constants import OPTIONAL_IMPORT_COLUMNS, REQUIRED_IMPORT_COLUMNS, SUPPORTED_IMPORT_EXTENSIONS
from invoice_automation.app.db.models import ImportBatchCreate, InvoiceRecordCreate
from invoice_automation.app.db.repository import InvoiceRecordRepository
from invoice_automation.app.schemas.invoice_record import (
    ImportResult,
    ImportSheetInspection,
    RowValidationError,
)
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

    def inspect_file(self, file_path: Path, sheet_name: str | None = None) -> ImportSheetInspection:
        """Return available sheets and columns for the uploaded import file."""

        self._ensure_supported_file(file_path)
        sheet_names = self.get_sheet_names(file_path)
        selected_sheet = sheet_name or sheet_names[0]
        if selected_sheet not in sheet_names:
            raise ImportValidationError(f"Sheet bulunamadi: {selected_sheet}")
        columns = self.get_columns(file_path, selected_sheet)
        return ImportSheetInspection(
            source_file=file_path.name,
            sheet_names=sheet_names,
            selected_sheet=selected_sheet,
            columns=columns,
        )

    def get_sheet_names(self, file_path: Path) -> list[str]:
        """Return sheet names for Excel files or a single CSV pseudo-sheet."""

        self._ensure_supported_file(file_path)
        if file_path.suffix.lower() == ".csv":
            return ["CSV"]
        try:
            return list(pd.ExcelFile(file_path).sheet_names)
        except Exception as exc:
            raise ImportValidationError(f"Excel sheet bilgisi okunamadi: {exc}") from exc

    def get_columns(self, file_path: Path, sheet_name: str | None = None) -> list[str]:
        """Return source column names for a CSV or selected Excel sheet."""

        self._ensure_supported_file(file_path)
        try:
            if file_path.suffix.lower() == ".csv":
                dataframe = pd.read_csv(file_path, dtype=str, keep_default_na=False, nrows=0)
            else:
                dataframe = pd.read_excel(
                    file_path,
                    sheet_name=sheet_name,
                    dtype=str,
                    keep_default_na=False,
                    nrows=0,
                )
        except Exception as exc:
            raise ImportValidationError(f"Kolonlar okunamadi: {exc}") from exc
        return [str(column) for column in dataframe.columns]

    def import_file(
        self,
        file_path: Path,
        *,
        batch_name: str | None = None,
        sheet_name: str | None = None,
        column_mapping: dict[str, str] | None = None,
    ) -> ImportResult:
        """Read an import file, persist valid rows, and report invalid rows."""

        self._ensure_supported_file(file_path)

        effective_sheet_name = self._effective_sheet_name(file_path, sheet_name)
        dataframe = self._read_dataframe(file_path, effective_sheet_name)
        dataframe = self._apply_mapping_or_normalize(dataframe, column_mapping)
        validate_required_columns(dataframe.columns)
        import_batch = self.repository.create_import_batch(
            ImportBatchCreate(
                name=self._batch_name(batch_name, file_path, effective_sheet_name),
                source_file_name=file_path.name,
                sheet_name=effective_sheet_name,
            )
        )

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
                    batch_id=import_batch.id,
                    kaynak_dosya=file_path.name,
                    kaynak_satir_no=source_row_number,
                )
            )
            records.append(created_record)

        logger.info(
            "Import completed | file=%s batch_id=%s sheet=%s imported=%s failed=%s",
            file_path.name,
            import_batch.id,
            effective_sheet_name,
            len(records),
            len(row_errors),
        )

        return ImportResult(
            source_file=file_path.name,
            batch=import_batch,
            imported_count=len(records),
            failed_count=len(row_errors),
            records=records,
            row_errors=row_errors,
        )

    def _ensure_supported_file(self, file_path: Path) -> None:
        if not file_path.exists():
            raise ImportValidationError(f"Dosya bulunamadi: {file_path}")

        extension = file_path.suffix.lower()
        if extension not in SUPPORTED_IMPORT_EXTENSIONS:
            supported = ", ".join(SUPPORTED_IMPORT_EXTENSIONS)
            raise UnsupportedFileTypeError(f"Desteklenmeyen dosya tipi. Desteklenen: {supported}.")

    def _effective_sheet_name(self, file_path: Path, sheet_name: str | None) -> str | None:
        if file_path.suffix.lower() == ".csv":
            return "CSV"
        sheet_names = self.get_sheet_names(file_path)
        selected_sheet = sheet_name or sheet_names[0]
        if selected_sheet not in sheet_names:
            raise ImportValidationError(f"Sheet bulunamadi: {selected_sheet}")
        return selected_sheet

    def _read_dataframe(self, file_path: Path, sheet_name: str | None = None) -> pd.DataFrame:
        extension = file_path.suffix.lower()
        if extension == ".csv":
            return pd.read_csv(file_path, dtype=str, keep_default_na=False)
        return pd.read_excel(file_path, sheet_name=sheet_name, dtype=str, keep_default_na=False)

    def _apply_mapping_or_normalize(
        self,
        dataframe: pd.DataFrame,
        column_mapping: dict[str, str] | None,
    ) -> pd.DataFrame:
        if not column_mapping:
            return self._normalize_dataframe(dataframe)

        cleaned_mapping = {
            target: source
            for target, source in column_mapping.items()
            if target in (*REQUIRED_IMPORT_COLUMNS, *OPTIONAL_IMPORT_COLUMNS) and source
        }
        missing_targets = [target for target in REQUIRED_IMPORT_COLUMNS if target not in cleaned_mapping]
        if missing_targets:
            raise ImportValidationError(
                "Eksik kolon mapping alanlari: " + ", ".join(missing_targets)
            )

        missing_sources = [
            source for source in cleaned_mapping.values() if source not in dataframe.columns
        ]
        if missing_sources:
            raise ImportValidationError("Dosyada bulunamayan kolonlar: " + ", ".join(missing_sources))

        mapped_data: dict[str, Any] = {}
        for target, source in cleaned_mapping.items():
            mapped_data[target] = dataframe[source]
        if "aciklama" not in mapped_data:
            mapped_data["aciklama"] = ""
        return pd.DataFrame(mapped_data)

    def _normalize_dataframe(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        normalized_columns = [normalize_column_name(column) for column in dataframe.columns]
        dataframe = dataframe.copy()
        dataframe.columns = normalized_columns
        return dataframe

    def _batch_name(self, batch_name: str | None, file_path: Path, sheet_name: str | None) -> str:
        normalized = (batch_name or "").strip()
        if normalized:
            return normalized
        if sheet_name and sheet_name != "CSV":
            return f"{file_path.stem} - {sheet_name}"
        return file_path.stem

    def _row_to_clean_dict(self, row: dict[str, Any]) -> dict[str, Any]:
        clean_row: dict[str, Any] = {}
        for key, value in row.items():
            if pd.isna(value):
                clean_row[key] = ""
            else:
                clean_row[key] = value
        return clean_row
