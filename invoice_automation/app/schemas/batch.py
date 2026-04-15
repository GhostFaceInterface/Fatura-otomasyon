"""DTOs for batch preparation and progress previews."""

from __future__ import annotations

from dataclasses import dataclass

from invoice_automation.app.db.models import InvoiceRecord


@dataclass(frozen=True)
class BatchPreview:
    """Summary of the records currently prepared for a batch run."""

    total_selected: int
    total_amount_usd: float
    status_counts: dict[str, int]
    records: list[InvoiceRecord]

    @property
    def completed_count(self) -> int:
        """Return completed count for the Phase 2 progress skeleton."""

        return 0

    @property
    def progress_percent(self) -> int:
        """Return progress percent for Phase 2 before real processing exists."""

        return 0

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable batch preview."""

        return {
            "total_selected": self.total_selected,
            "total_amount_usd": self.total_amount_usd,
            "status_counts": self.status_counts,
            "completed_count": self.completed_count,
            "progress_percent": self.progress_percent,
            "records": [record.to_dict() for record in self.records],
        }
