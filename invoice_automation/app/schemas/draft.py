"""DTOs for single-record draft creation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from invoice_automation.app.db.models import InvoiceRecord


@dataclass(frozen=True)
class SingleDraftServiceResult:
    """Service-level result for one draft creation attempt."""

    ok: bool
    record: InvoiceRecord
    message: str
    error_code: str | None = None
    screenshot_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable result."""

        return {
            "ok": self.ok,
            "message": self.message,
            "error_code": self.error_code,
            "screenshot_path": self.screenshot_path,
            "record": self.record.to_dict(),
        }
