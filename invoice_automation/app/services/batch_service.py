"""Batch preparation service skeleton for later automation phases."""

from __future__ import annotations

import logging

from invoice_automation.app.db.repository import InvoiceRecordRepository
from invoice_automation.app.schemas.batch import BatchPreview

logger = logging.getLogger(__name__)


class BatchService:
    """Prepare selected records for a future browser automation batch."""

    def __init__(self, repository: InvoiceRecordRepository | None = None) -> None:
        self.repository = repository or InvoiceRecordRepository()

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
