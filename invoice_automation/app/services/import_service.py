"""CSV and Excel import service."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from decimal import Decimal, InvalidOperation
import logging
from pathlib import Path
from typing import Any
import unicodedata

import pandas as pd

from invoice_automation.app.constants import OPTIONAL_IMPORT_COLUMNS, REQUIRED_IMPORT_COLUMNS, SUPPORTED_IMPORT_EXTENSIONS
from invoice_automation.app.db.models import ImportBatchCreate, InvoiceRecordCreate
from invoice_automation.app.db.repository import InvoiceRecordRepository
from invoice_automation.app.schemas.invoice_record import (
    PREVIEW_FIELDS,
    ImportResult,
    ImportSheetInspection,
    PreviewRow,
    RowValidationError,
)
from invoice_automation.app.services.validation_service import validate_required_columns
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


def parse_currency(value: Any) -> float:
    """Normalize USD amount strings from import files into a positive float."""

    if value is None or pd.isna(value):
        raise ValueError("tutar_usd bos olamaz.")

    if isinstance(value, int | float | Decimal) and not isinstance(value, bool):
        try:
            return _positive_decimal_to_float(Decimal(str(value)))
        except InvalidOperation as exc:
            raise ValueError(f"tutar_usd parse edilemedi: {value}") from exc

    raw_value = str(value).strip()
    if not raw_value:
        raise ValueError("tutar_usd bos olamaz.")
    return _positive_decimal_to_float(_currency_to_decimal(raw_value))


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

    def read_preview_rows(
        self,
        file_path: Path,
        *,
        sheet_name: str | None = None,
        column_mapping: dict[str, str] | None = None,
    ) -> list[PreviewRow]:
        """Read the people of a file as checked, editable preview rows.

        Fully empty rows are left out. Nothing is written to the database.
        """

        self._ensure_supported_file(file_path)
        effective_sheet_name = self._effective_sheet_name(file_path, sheet_name)
        dataframe = self._read_dataframe(file_path, effective_sheet_name)
        dataframe = self._apply_mapping_or_normalize(dataframe, column_mapping)
        validate_required_columns(dataframe.columns)

        rows: list[PreviewRow] = []
        for index, row in dataframe.iterrows():
            raw_data = self._row_to_clean_dict(row.to_dict())
            preview = PreviewRow(
                values={name: _clean_text(raw_data.get(name, "")) for name in PREVIEW_FIELDS},
                source_row=int(index) + 2,
            )
            if not preview.is_blank:
                rows.append(preview)

        # The cleaned file values are the baseline that marks a cell as edited.
        return [replace(row, original=dict(row.values)) for row in check_preview_rows(rows)]

    def import_preview_rows(
        self,
        rows: list[PreviewRow],
        *,
        batch_name: str,
        source_file_name: str,
        sheet_name: str | None,
    ) -> ImportResult:
        """Create a period from the rows confirmed on the preview screen.

        Rows are checked again here; if any row that would be imported has an
        error, nothing is written. Otherwise the period and all of its people are
        written in one transaction.
        """

        name = " ".join(batch_name.split())
        if not name:
            raise ImportValidationError("Dönem adı boş olamaz.")

        checked = check_preview_rows(rows)
        active = [row for row in checked if row.is_active]
        invalid = [row for row in active if row.errors]
        if invalid:
            raise ImportValidationError(
                f"{len(invalid)} satırda hata var. Düzelt ya da sil, sonra tekrar dene."
            )
        if not active:
            raise ImportValidationError("İçe aktarılacak kişi yok.")

        import_batch, records = self.repository.create_import(
            ImportBatchCreate(name=name, source_file_name=source_file_name, sheet_name=sheet_name),
            [_record_create(row, source_file_name) for row in active],
        )
        logger.info(
            "Preview import completed | file=%s batch_id=%s sheet=%s imported=%s removed=%s added=%s edited=%s",
            source_file_name,
            import_batch.id,
            sheet_name,
            len(records),
            sum(1 for row in checked if row.removed and not row.is_blank),
            sum(1 for row in active if row.original is None),
            sum(1 for row in active if row.original is not None and row.values != row.original),
        )
        return ImportResult(
            source_file=source_file_name,
            batch=import_batch,
            imported_count=len(records),
            failed_count=0,
            records=records,
        )

    def import_file(
        self,
        file_path: Path,
        *,
        batch_name: str | None = None,
        sheet_name: str | None = None,
        column_mapping: dict[str, str] | None = None,
    ) -> ImportResult:
        """Import every valid row of a file without a preview; report invalid rows."""

        rows = self.read_preview_rows(file_path, sheet_name=sheet_name, column_mapping=column_mapping)
        effective_sheet_name = self._effective_sheet_name(file_path, sheet_name)
        valid_rows = [row for row in rows if not row.errors]
        row_errors = [
            RowValidationError(
                row_number=row.source_row or 0,
                errors=list(row.errors.values()),
                raw_data=dict(row.values),
            )
            for row in rows
            if row.errors
        ]
        for row_error in row_errors:
            logger.info(
                "Import row skipped | file=%s row=%s errors=%s",
                file_path.name,
                row_error.row_number,
                row_error.errors,
            )

        # Rows are validated first and persisted together with the batch in one
        # transaction, so a failure never leaves a half-imported fatura donemi.
        import_batch, records = self.repository.create_import(
            ImportBatchCreate(
                name=self._batch_name(batch_name, file_path, effective_sheet_name),
                source_file_name=file_path.name,
                sheet_name=effective_sheet_name,
            ),
            [_record_create(row, file_path.name) for row in valid_rows],
        )

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


def check_preview_rows(rows: list[PreviewRow]) -> list[PreviewRow]:
    """Clean every row and attach field errors and warnings.

    This is the single rule set for the preview: the live check, the final
    import and the plain file import all go through it. Removed and empty rows
    get no errors because they are not imported.
    """

    cleaned: list[PreviewRow] = []
    for row in rows:
        values, errors = check_row_values(row.values)
        is_used = not row.removed and any(values.values())
        cleaned.append(replace(row, values=values, errors=errors if is_used else {}, warnings={}))

    tckn_counts = Counter(
        row.values["tc_kimlik_no"]
        for row in cleaned
        if row.is_active and "tc_kimlik_no" not in row.errors
    )
    return [
        replace(
            row,
            warnings={"tc_kimlik_no": f"Listede {tckn_counts[row.values['tc_kimlik_no']]} kez var."},
        )
        if row.is_active and tckn_counts.get(row.values["tc_kimlik_no"], 0) > 1
        else row
        for row in cleaned
    ]


def check_row_values(values: dict[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    """Return the cleaned values of one row and its errors keyed by field."""

    cleaned = {name: _clean_text(values.get(name, "")) for name in PREVIEW_FIELDS}
    errors: dict[str, str] = {}

    if not cleaned["ad"]:
        errors["ad"] = "Ad boş olamaz."
    if not cleaned["soyad"]:
        errors["soyad"] = "Soyad boş olamaz."

    tckn = cleaned["tc_kimlik_no"].replace(" ", "")
    if tckn.endswith(".0"):  # Excel number cells come back as "12345678901.0"
        tckn = tckn[:-2]
    cleaned["tc_kimlik_no"] = tckn
    if not tckn:
        errors["tc_kimlik_no"] = "TCKN boş olamaz."
    elif not tckn.isdigit() or len(tckn) != 11:
        errors["tc_kimlik_no"] = "TCKN 11 haneli rakam olmalı."

    try:
        cleaned["tutar_usd"] = format_amount(parse_amount(cleaned["tutar_usd"]))
    except ValueError as exc:
        errors["tutar_usd"] = str(exc)

    return cleaned, errors


def parse_amount(value: Any) -> Decimal:
    """Parse a USD amount into a positive Decimal with at most two decimals.

    Uses the same separator rules as `parse_currency` ("1.450" and "1,450" are
    1450; "1450,50" and "1.450,50" are 1450.50).
    """

    text = _clean_text(value)
    if not text:
        raise ValueError("Tutar boş olamaz.")
    try:
        amount = _currency_to_decimal(text)
    except ValueError as exc:
        raise ValueError("Tutar sayı olmalı (örn. 1450,50).") from exc
    if amount <= 0:
        raise ValueError("Tutar 0'dan büyük olmalı.")
    cents = amount.quantize(Decimal("0.01"))
    # Excel float noise such as 1450.1000000000001 is rounded; real extra digits are not.
    if abs(amount - cents) > Decimal("0.000001"):
        raise ValueError("En fazla 2 ondalık basamak olabilir.")
    return cents


def format_amount(amount: Decimal) -> str:
    """Format an amount the way the preview shows it (dot decimal, two places)."""

    return f"{amount:.2f}"


def summarize_preview(rows: list[PreviewRow]) -> dict[str, Any]:
    """Return the counts and total shown under the preview table."""

    active = [row for row in rows if row.is_active]
    total = sum(
        (Decimal(row.values["tutar_usd"]) for row in active if "tutar_usd" not in row.errors),
        Decimal("0"),
    )
    return {
        "count": len(active),
        "total_usd": format_amount(total),
        "error_count": sum(1 for row in active if row.errors),
        "removed_count": sum(1 for row in rows if row.removed and not row.is_blank),
    }


def _record_create(row: PreviewRow, source_file_name: str) -> InvoiceRecordCreate:
    return InvoiceRecordCreate(
        ad=row.values["ad"],
        soyad=row.values["soyad"],
        tc_kimlik_no=row.values["tc_kimlik_no"],
        tutar_usd=float(Decimal(row.values["tutar_usd"])),
        aciklama=row.values["aciklama"],
        kaynak_dosya=source_file_name,
        kaynak_satir_no=row.source_row,
    )


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return " ".join(str(value).split())


def _currency_to_decimal(value: str) -> Decimal:
    """Turn an amount string into a finite Decimal, sign not checked."""

    cleaned = value.replace("$", "").replace("\u00a0", "").replace(" ", "").strip()
    if not cleaned:
        raise ValueError("tutar_usd bos olamaz.")
    try:
        amount = Decimal(_normalize_currency_separators(cleaned))
    except InvalidOperation as exc:
        raise ValueError(f"tutar_usd parse edilemedi: {value}") from exc
    if not amount.is_finite():
        raise ValueError(f"tutar_usd sonlu bir sayi olmalidir: {amount}")
    return amount


def _normalize_currency_separators(value: str) -> str:
    """Normalize thousands and decimal separators for deterministic parsing."""

    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            return value.replace(".", "").replace(",", ".")
        return value.replace(",", "")

    if "," in value:
        parts = value.split(",")
        if _has_grouped_thousands(parts):
            return "".join(parts)
        if len(parts) == 2:
            return ".".join(parts)
        raise ValueError(f"tutar_usd parse edilemedi: {value}")

    if "." in value:
        parts = value.split(".")
        if _has_grouped_thousands(parts):
            return "".join(parts)
        if len(parts) == 2:
            return value
        raise ValueError(f"tutar_usd parse edilemedi: {value}")

    return value


def _has_grouped_thousands(parts: list[str]) -> bool:
    if len(parts) < 2:
        return False
    first_part = parts[0]
    if first_part.startswith(("+", "-")):
        first_part = first_part[1:]
    if not first_part or not first_part.isdigit():
        return False
    return all(len(part) == 3 and part.isdigit() for part in parts[1:])


def _positive_decimal_to_float(amount: Decimal) -> float:
    # NaN/Infinity are valid Decimals; NaN even raises InvalidOperation on "<=".
    if not amount.is_finite():
        raise ValueError(f"tutar_usd sonlu bir sayi olmalidir: {amount}")
    if amount <= 0:
        raise ValueError("tutar_usd pozitif olmalidir.")
    return float(amount)
