"""Background batch job management.

A batch run can take a long time, so it is started as a background job on the
Playwright worker thread instead of inside the HTTP request. Only one job may be
active at a time; progress is polled and the job can be cancelled between
records.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Callable
import logging
import threading
import uuid

from invoice_automation.app.automation.playwright_worker import PlaywrightWorker, playwright_worker
from invoice_automation.app.db.models import InvoiceRecord
from invoice_automation.app.db.repository import InvoiceRecordRepository
from invoice_automation.app.schemas.batch import BatchRecordResult, BatchRunReport
from invoice_automation.app.services.batch_service import BatchService
from invoice_automation.app.utils.exceptions import BatchJobAlreadyRunningError

logger = logging.getLogger(__name__)


class BatchJobStatus(StrEnum):
    """Lifecycle of a background batch job."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


ACTIVE_JOB_STATUSES = frozenset(
    {BatchJobStatus.QUEUED, BatchJobStatus.RUNNING, BatchJobStatus.CANCEL_REQUESTED}
)


@dataclass
class BatchJob:
    """Mutable progress state of one background batch run."""

    job_id: str
    batch_id: int | None
    status: BatchJobStatus
    created_at: str
    total: int = 0
    processed: int = 0
    success_count: int = 0
    failed_count: int = 0
    current_record_id: int | None = None
    current_record_name: str | None = None
    started_at: str | None = None
    ended_at: str | None = None
    error: str | None = None
    report: BatchRunReport | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)

    @property
    def is_active(self) -> bool:
        """Return True while the job is queued or running."""

        return self.status in ACTIVE_JOB_STATUSES

    @property
    def progress_percent(self) -> int:
        """Return processed percentage."""

        if self.total == 0:
            return 100 if not self.is_active else 0
        return int((self.processed / self.total) * 100)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable progress snapshot."""

        return {
            "job_id": self.job_id,
            "batch_id": self.batch_id,
            "status": self.status.value,
            "is_active": self.is_active,
            "total": self.total,
            "processed": self.processed,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "progress_percent": self.progress_percent,
            "current_record_id": self.current_record_id,
            "current_record_name": self.current_record_name,
            "cancel_requested": self.cancel_event.is_set(),
            "created_at": self.created_at,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "error": self.error,
            "report": self.report.to_dict() if self.report else None,
        }


class BatchJobManager:
    """Start, track and cancel the single active background batch job."""

    def __init__(
        self,
        worker: PlaywrightWorker = playwright_worker,
        service_factory: Callable[[], BatchService] | None = None,
        repository_factory: Callable[[], InvoiceRecordRepository] | None = None,
    ) -> None:
        self.worker = worker
        self.repository_factory = repository_factory or InvoiceRecordRepository
        self.service_factory = service_factory or (
            lambda: BatchService(repository=self.repository_factory())
        )
        self._lock = threading.Lock()
        self._current: BatchJob | None = None

    def start(self, batch_id: int | None) -> dict[str, Any]:
        """Start a background job; raises if one is already active."""

        with self._lock:
            if self._current is not None and self._current.is_active:
                raise BatchJobAlreadyRunningError(
                    "Zaten calisan bir toplu taslak islemi var. Bitmesini bekleyin veya durdurun."
                )
            job = BatchJob(
                job_id=uuid.uuid4().hex,
                batch_id=batch_id,
                status=BatchJobStatus.QUEUED,
                created_at=_utc_timestamp(),
            )
            self.worker.submit_background(self._run, job)
            self._current = job
            logger.info("Batch job kuyruga alindi | job_id=%s batch_id=%s", job.job_id, batch_id)
            return job.to_dict()

    def status(self) -> dict[str, Any] | None:
        """Return the active or most recent job snapshot."""

        with self._lock:
            return self._current.to_dict() if self._current else None

    def current_job(self) -> BatchJob | None:
        """Return the active or most recent job object."""

        with self._lock:
            return self._current

    def is_running(self) -> bool:
        """Return True while a job is queued or running."""

        with self._lock:
            return self._current is not None and self._current.is_active

    def cancel(self) -> bool:
        """Request cancellation; the record currently on the portal is finished first."""

        with self._lock:
            job = self._current
            if job is None or not job.is_active:
                return False
            job.cancel_event.set()
            job.status = BatchJobStatus.CANCEL_REQUESTED
            logger.warning("Batch job icin durdurma istendi | job_id=%s", job.job_id)
            return True

    def _run(self, job: BatchJob) -> None:
        with self._lock:
            if job.status == BatchJobStatus.QUEUED:
                job.status = BatchJobStatus.RUNNING
            job.started_at = _utc_timestamp()

        try:
            report = self.service_factory().run_selected_batch(
                batch_id=job.batch_id,
                progress_callback=lambda detail, record: self._on_progress(job, detail, record),
                should_cancel=job.cancel_event.is_set,
                on_records_loaded=lambda records: self._on_records_loaded(job, records),
            )
        except Exception as exc:
            logger.exception("Batch job beklenmeyen hatayla durdu | job_id=%s", job.job_id)
            recovered = self._recover_interrupted_records()
            with self._lock:
                job.status = BatchJobStatus.FAILED
                job.error = (
                    f"Beklenmeyen hata: {exc}. Yarida kalan {recovered} kayit NEEDS_REVIEW "
                    "durumuna alindi; portalda kontrol edin."
                )
                job.current_record_id = None
                job.current_record_name = None
                job.ended_at = _utc_timestamp()
            return

        with self._lock:
            job.report = report
            job.status = BatchJobStatus.CANCELLED if report.cancelled else BatchJobStatus.COMPLETED
            job.current_record_id = None
            job.current_record_name = None
            job.ended_at = _utc_timestamp()
        logger.info("Batch job bitti | job_id=%s status=%s", job.job_id, job.status.value)

    def _on_records_loaded(self, job: BatchJob, records: list[InvoiceRecord]) -> None:
        with self._lock:
            job.total = len(records)

    def _on_progress(
        self,
        job: BatchJob,
        detail: BatchRecordResult | None,
        next_record: InvoiceRecord | None,
    ) -> None:
        with self._lock:
            if next_record is not None:
                job.current_record_id = next_record.id
                job.current_record_name = f"{next_record.ad} {next_record.soyad}".strip()
            if detail is not None:
                job.processed += 1
                if detail.ok:
                    job.success_count += 1
                else:
                    job.failed_count += 1
                job.current_record_id = None
                job.current_record_name = None

    def _recover_interrupted_records(self) -> int:
        # The worker runs nothing else while this job is active, so anything
        # still IN_PROGRESS was interrupted by this job's crash.
        try:
            return self.repository_factory().recover_stale_in_progress()
        except Exception:
            logger.exception("Yarida kalan kayitlar NEEDS_REVIEW durumuna alinamadi")
            return 0


def _utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


batch_job_manager = BatchJobManager()
