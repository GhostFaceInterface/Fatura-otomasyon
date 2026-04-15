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

    def preview(self, batch_id: int | None = None) -> BatchPreview:
        """Return a read-only preview of currently selected records."""

        effective_batch_id = self._effective_batch_id(batch_id)
        selected_records = self.repository.list_selected_for_batch(batch_id=effective_batch_id)
        total_amount = sum(record.tutar_usd for record in selected_records)
        return BatchPreview(
            total_selected=len(selected_records),
            total_amount_usd=total_amount,
            status_counts=self.repository.count_by_status(batch_id=effective_batch_id),
            records=selected_records,
        )

    def prepare_selected_batch(self, batch_id: int | None = None) -> BatchPreview:
        """Prepare the selected records for processing.

        Phase 2 does not run portal automation. This method is the stable entry
        point that later phases will extend with session and browser checks.
        """

        preview = self.preview(batch_id=batch_id)
        logger.info(
            "Batch prepared | total_selected=%s total_amount_usd=%.2f",
            preview.total_selected,
            preview.total_amount_usd,
        )
        return preview

    def run_selected_batch(self, batch_id: int | None = None) -> BatchRunReport:
        """Run selected eligible records sequentially and return the final report."""

        effective_batch_id = self._effective_batch_id(batch_id)
        selected_records = self.repository.list_selected_for_batch(batch_id=effective_batch_id)
        logger.info(
            "Batch run istegi alindi | batch_id=%s eligible_selected=%s",
            effective_batch_id,
            len(selected_records),
        )
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

    def _effective_batch_id(self, batch_id: int | None) -> int | None:
        if batch_id is not None:
            return batch_id
        latest_batch = self.repository.latest_import_batch()
        return latest_batch.id if latest_batch else None
