"""DTOs for batch preparation, execution, and reports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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


@dataclass(frozen=True)
class BatchRecordResult:
    """Outcome of one record inside a batch run."""

    record_id: int
    tc_kimlik_no: str
    full_name: str
    final_status: str
    ok: bool
    error_code: str | None = None
    error_message: str | None = None
    screenshot_path: str | None = None
    started_at: str | None = None
    ended_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable record result."""

        return {
            "record_id": self.record_id,
            "tc_kimlik_no": self.tc_kimlik_no,
            "full_name": self.full_name,
            "final_status": self.final_status,
            "ok": self.ok,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "screenshot_path": self.screenshot_path,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
        }


@dataclass(frozen=True)
class BatchRunReport:
    """Summary report returned after a batch run."""

    total_selected: int
    total_processed: int
    success_count: int
    skipped_count: int
    failed_count: int
    aborted_count: int
    results_by_status: dict[str, int]
    processed_record_ids: list[int]
    failed_record_ids: list[int]
    skipped_record_ids: list[int]
    aborted_due_to_session_loss: bool
    started_at: str
    ended_at: str
    duration_seconds: float
    details: list[BatchRecordResult]
    abort_reason: str | None = None

    @property
    def progress_percent(self) -> int:
        """Return completed percentage for a finished batch."""

        if self.total_selected == 0:
            return 0
        return int((self.total_processed / self.total_selected) * 100)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable batch report."""

        return {
            "total_selected": self.total_selected,
            "total_processed": self.total_processed,
            "success_count": self.success_count,
            "skipped_count": self.skipped_count,
            "failed_count": self.failed_count,
            "aborted_count": self.aborted_count,
            "results_by_status": self.results_by_status,
            "processed_record_ids": self.processed_record_ids,
            "failed_record_ids": self.failed_record_ids,
            "skipped_record_ids": self.skipped_record_ids,
            "aborted_due_to_session_loss": self.aborted_due_to_session_loss,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_seconds": self.duration_seconds,
            "progress_percent": self.progress_percent,
            "abort_reason": self.abort_reason,
            "details": [detail.to_dict() for detail in self.details],
        }
