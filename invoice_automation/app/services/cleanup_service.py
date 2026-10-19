"""Deleting wrongly imported fatura periods and records from the local database.

Only local SQLite rows are removed. Drafts that were already created on the
portal stay there; the operator must handle them on the portal if needed.
"""

from __future__ import annotations

import logging

from invoice_automation.app.db.repository import InvoiceRecordRepository
from invoice_automation.app.services.batch_job_service import BatchJobManager, batch_job_manager
from invoice_automation.app.utils.exceptions import DeletionBlockedError

logger = logging.getLogger(__name__)

JOB_RUNNING_MESSAGE = (
    "Bu donem icin toplu taslak islemi calisiyor. Islem bitince veya durdurulunca tekrar dene."
)


class RecordCleanupService:
    """Delete local data, refusing while a batch job may still touch it."""

    def __init__(
        self,
        repository: InvoiceRecordRepository | None = None,
        job_manager: BatchJobManager | None = None,
    ) -> None:
        self.repository = repository or InvoiceRecordRepository()
        self.job_manager = job_manager or batch_job_manager

    def delete_batch(self, batch_id: int) -> int | None:
        """Delete a fatura period with all of its records.

        Returns the deleted record count, or None when the period does not exist.
        """

        self._ensure_no_active_job(batch_id)
        deleted = self.repository.delete_import_batch(batch_id)
        logger.info("Fatura donemi silindi | batch_id=%s deleted_records=%s", batch_id, deleted)
        return deleted

    def delete_records(self, record_ids: list[int], batch_id: int | None) -> int:
        """Delete records of one fatura period; IN_PROGRESS records are kept.

        ``batch_id=None`` targets records without a period and is refused while any
        batch job is active.
        """

        self._ensure_no_active_job(batch_id)
        deleted = self.repository.delete_records(record_ids, batch_id=batch_id)
        logger.info(
            "Kayitlar silindi | batch_id=%s requested=%s deleted=%s",
            batch_id,
            len(record_ids),
            deleted,
        )
        return deleted

    def delete_unassigned_records(self) -> int:
        """Delete records that belong to no fatura period."""

        self._ensure_no_active_job(None)
        deleted = self.repository.delete_unassigned_records()
        logger.info("Doneme bagli olmayan kayitlar silindi | deleted=%s", deleted)
        return deleted

    def _ensure_no_active_job(self, batch_id: int | None) -> None:
        job = self.job_manager.current_job()
        if job is None or not job.is_active:
            return
        # A job without batch_id, or a cleanup without batch_id, may overlap anything.
        if batch_id is None or job.batch_id is None or job.batch_id == batch_id:
            raise DeletionBlockedError(JOB_RUNNING_MESSAGE)
