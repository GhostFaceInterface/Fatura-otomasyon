"""DTOs for import and invoice record presentation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from invoice_automation.app.db.models import InvoiceRecord


@dataclass(frozen=True)
class RowValidationError:
    """Validation error for one source row."""

    row_number: int
    errors: list[str]
    raw_data: dict[str, Any]


@dataclass(frozen=True)
class ImportResult:
    """Summary returned after importing an Excel or CSV file."""

    source_file: str
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
