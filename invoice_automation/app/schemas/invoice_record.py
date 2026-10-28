"""DTOs for import and invoice record presentation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from invoice_automation.app.db.models import ImportBatch, InvoiceRecord


@dataclass(frozen=True)
class RowValidationError:
    """Validation error for one source row."""

    row_number: int
    errors: list[str]
    raw_data: dict[str, Any]


@dataclass(frozen=True)
class ImportSheetInspection:
    """Sheet and column metadata for an uploaded import file."""

    source_file: str
    sheet_names: list[str]
    selected_sheet: str
    columns: list[str]


PREVIEW_FIELDS = ("ad", "soyad", "tc_kimlik_no", "tutar_usd", "aciklama")


@dataclass(frozen=True)
class PreviewRow:
    """One editable row of the import preview.

    `values` are the strings shown in the table. `original` holds the values read
    from the file (None for a person added by hand) so edits can be marked.
    """

    values: dict[str, str]
    source_row: int | None = None
    original: dict[str, str] | None = None
    removed: bool = False
    errors: dict[str, str] = field(default_factory=dict)
    warnings: dict[str, str] = field(default_factory=dict)

    @property
    def is_blank(self) -> bool:
        """Return whether every field is empty (an unused added row)."""

        return not any(str(self.values.get(name, "")).strip() for name in PREVIEW_FIELDS)

    @property
    def is_active(self) -> bool:
        """Return whether this row will be imported."""

        return not self.removed and not self.is_blank

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary."""

        return {
            "values": self.values,
            "source_row": self.source_row,
            "original": self.original,
            "removed": self.removed,
            "errors": self.errors,
            "warnings": self.warnings,
        }


@dataclass(frozen=True)
class ImportResult:
    """Summary returned after importing an Excel or CSV file."""

    source_file: str
    batch: ImportBatch | None
    imported_count: int
    failed_count: int
    records: list[InvoiceRecord] = field(default_factory=list)
    row_errors: list[RowValidationError] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Return whether any rows failed validation."""

        return bool(self.row_errors)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable import summary."""

        return {
            "source_file": self.source_file,
            "batch": self.batch.to_dict() if self.batch else None,
            "imported_count": self.imported_count,
            "failed_count": self.failed_count,
            "row_errors": [
                {
                    "row_number": row_error.row_number,
                    "errors": row_error.errors,
                    "raw_data": row_error.raw_data,
                }
                for row_error in self.row_errors
            ],
            "records": [record.to_dict() for record in self.records],
        }
