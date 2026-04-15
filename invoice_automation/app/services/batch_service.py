"""Batch preparation and execution service."""

from __future__ import annotations

import logging

from invoice_automation.app.automation.batch_runner import BatchRunner
from invoice_automation.app.db.repository import InvoiceRecordRepository
from invoice_automation.app.schemas.batch import BatchPreview, BatchRunReport
from invoice_automation.app.services.draft_service import SingleDraftService

logger = logging.getLogger(__name__)


class BatchService:
    """Prepare and run selected records through portal automation."""

    def __init__(
        self,
        repository: InvoiceRecordRepository | None = None,
        runner: BatchRunner | None = None,
    ) -> None:
        self.repository = repository or InvoiceRecordRepository()
        self.runner = runner

    def preview(self) -> BatchPreview:
        """Return a read-only preview of currently selected records."""

        selected_records = self.repository.list_selected()
        total_amount = sum(record.tutar_usd for record in selected_records)
        return BatchPreview(
            total_selected=len(selected_records),
            total_amount_usd=total_amount,
            status_counts=self.repository.count_by_status(),
            records=selected_records,
        )

    def prepare_selected_batch(self) -> BatchPreview:
        """Prepare the selected records for processing.

        Phase 2 does not run portal automation. This method is the stable entry
        point that later phases will extend with session and browser checks.
        """

        preview = self.preview()
        logger.info(
            "Batch prepared | total_selected=%s total_amount_usd=%.2f",
            preview.total_selected,
            preview.total_amount_usd,
        )
        return preview

    def run_selected_batch(self) -> BatchRunReport:
        """Run selected eligible records sequentially and return the final report."""

        selected_records = self.repository.list_selected_for_batch()
        logger.info("Batch run istegi alindi | eligible_selected=%s", len(selected_records))
        runner = self.runner or BatchRunner(
            draft_service=SingleDraftService(repository=self.repository),
        )
        report = runner.run(selected_records)
        logger.info(
            "Batch run raporu hazir | processed=%s success=%s skipped=%s failed=%s aborted=%s",
            report.total_processed,
            report.success_count,
            report.skipped_count,
            report.failed_count,
            report.aborted_count,
        )
        return report
