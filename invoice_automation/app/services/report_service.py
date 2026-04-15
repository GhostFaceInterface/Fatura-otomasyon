"""Report builders for automation batch runs."""

from __future__ import annotations

from collections import Counter

from invoice_automation.app.constants import InvoiceStatus
from invoice_automation.app.schemas.batch import BatchRecordResult, BatchRunReport


class BatchReportService:
    """Build user-facing summary data from per-record batch results."""

    def build_report(
        self,
        *,
        total_selected: int,
        details: list[BatchRecordResult],
        started_at: str,
        ended_at: str,
        duration_seconds: float,
        aborted_due_to_session_loss: bool,
        abort_reason: str | None = None,
    ) -> BatchRunReport:
        """Return a completed batch report."""

        status_counts = Counter(detail.final_status for detail in details)
        failed_statuses = {
            InvoiceStatus.FAILED_INVALID_TCKN.value,
            InvoiceStatus.FAILED_NAME_MISMATCH.value,
            InvoiceStatus.FAILED_TURMOB_SERVICE_ERROR.value,
            InvoiceStatus.FAILED_PORTAL_TIMEOUT.value,
            InvoiceStatus.FAILED_UNKNOWN.value,
        }

        return BatchRunReport(
            total_selected=total_selected,
            total_processed=len(details),
            success_count=status_counts[InvoiceStatus.SUCCESS_DRAFT_CREATED.value],
            skipped_count=status_counts[InvoiceStatus.SKIPPED_EFATURA_MUKELLEFI.value],
            failed_count=sum(status_counts[status] for status in failed_statuses),
            aborted_count=status_counts[InvoiceStatus.ABORTED_SESSION_LOST.value],
            results_by_status=dict(status_counts),
            processed_record_ids=[detail.record_id for detail in details],
            failed_record_ids=[
                detail.record_id for detail in details if detail.final_status in failed_statuses
            ],
            skipped_record_ids=[
                detail.record_id
                for detail in details
                if detail.final_status == InvoiceStatus.SKIPPED_EFATURA_MUKELLEFI.value
            ],
            aborted_due_to_session_loss=aborted_due_to_session_loss,
            started_at=started_at,
            ended_at=ended_at,
            duration_seconds=round(duration_seconds, 3),
            details=details,
            abort_reason=abort_reason,
        )
