"""Selection service for invoice records."""

from __future__ import annotations

import logging

from invoice_automation.app.db.models import InvoiceRecord
from invoice_automation.app.db.repository import InvoiceRecordRepository

logger = logging.getLogger(__name__)


class SelectionService:
    """Handle persistent record selection rules."""

    def __init__(self, repository: InvoiceRecordRepository | None = None) -> None:
        self.repository = repository or InvoiceRecordRepository()

    def save_selection(self, selected_ids: list[int], batch_id: int | None = None) -> list[InvoiceRecord]:
        """Persist selected records and return the selected records."""

        selected_count = self.repository.update_selection(selected_ids, batch_id=batch_id)
        logger.info(
            "Selection saved | batch_id=%s selected_count=%s ids=%s",
            batch_id,
            selected_count,
            selected_ids,
        )
        return self.repository.list_selected(batch_id=batch_id)

    def selected_records(self, batch_id: int | None = None) -> list[InvoiceRecord]:
        """Return records currently selected for batch preparation."""

        return self.repository.list_selected(batch_id=batch_id)
