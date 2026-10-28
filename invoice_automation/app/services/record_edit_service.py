"""Changing the invoice amount of people already imported into a period."""

from __future__ import annotations

import logging

from invoice_automation.app.db.repository import InvoiceRecordRepository
from invoice_automation.app.services.batch_job_service import BatchJobManager, batch_job_manager
from invoice_automation.app.services.import_service import format_amount, parse_amount
from invoice_automation.app.utils.exceptions import RecordEditBlockedError

logger = logging.getLogger(__name__)

JOB_RUNNING_MESSAGE = "Bu dönemde taslak işlemi çalışıyor. Bitince veya durdurulunca tutarı değiştirebilirsin."


class RecordEditService:
    """Update amounts with the same rules as the import, never under a running job."""

    def __init__(
        self,
        repository: InvoiceRecordRepository | None = None,
        job_manager: BatchJobManager | None = None,
    ) -> None:
        self.repository = repository or InvoiceRecordRepository()
        self.job_manager = job_manager or batch_job_manager

    def update_amount(self, record_ids: list[int], raw_amount: str, *, batch_id: int) -> tuple[int, str]:
        """Set one amount on the given records of a period.

        Returns the number of records changed and the amount as shown in the UI.
        Records with a draft, in progress or awaiting review are skipped. Raises
        ValueError for an invalid amount and RecordEditBlockedError while a draft
        job runs on this period.
        """

        amount = parse_amount(raw_amount)
        job = self.job_manager.current_job()
        if job is not None and job.is_active and job.batch_id in (None, batch_id):
            raise RecordEditBlockedError(JOB_RUNNING_MESSAGE)

        wanted = set(record_ids)
        previous = {
            record.id: record.tutar_usd
            for record in self.repository.list_all(batch_id=batch_id)
            if record.id in wanted
        }
        updated = self.repository.update_amounts(sorted(wanted), float(amount), batch_id=batch_id)
        logger.info(
            "Tutar guncellendi | batch_id=%s requested=%s updated=%s new_amount=%s previous=%s",
            batch_id,
            len(wanted),
            updated,
            format_amount(amount),
            previous,
        )
        return updated, format_amount(amount)
