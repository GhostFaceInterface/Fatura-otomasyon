from pathlib import Path
import threading

import pytest

from invoice_automation.app.automation.playwright_worker import PlaywrightWorker
from invoice_automation.app.constants import InvoiceStatus
from invoice_automation.app.db.models import InvoiceRecordCreate
from invoice_automation.app.db.repository import InvoiceRecordRepository
from invoice_automation.app.schemas.batch import BatchRecordResult
from invoice_automation.app.services.batch_job_service import BatchJobManager, BatchJobStatus
from invoice_automation.app.services.report_service import BatchReportService
from invoice_automation.app.utils.exceptions import BatchJobAlreadyRunningError


class ControlledBatchService:
    """Fake BatchService that processes records only when the test allows it."""

    def __init__(self, records, *, fail: bool = False) -> None:
        self.records = records
        self.fail = fail
        self.started = threading.Event()
        self.first_record_started = threading.Event()
        self.step = threading.Semaphore(0)
        self.thread_ident: int | None = None

    def run_selected_batch(self, batch_id=None, *, progress_callback, should_cancel, on_records_loaded):
        self.thread_ident = threading.get_ident()
        on_records_loaded(self.records)
        self.started.set()
        details = []
        cancelled = False
        for record in self.records:
            if should_cancel():
                cancelled = True
                break
            progress_callback(None, record)
            self.first_record_started.set()
            assert self.step.acquire(timeout=5)
            if self.fail:
                raise RuntimeError("boom")
            detail = BatchRecordResult(
                record_id=record.id,
                tc_kimlik_no=record.tc_kimlik_no,
                full_name=f"{record.ad} {record.soyad}",
                final_status=InvoiceStatus.SUCCESS_DRAFT_CREATED.value,
                ok=True,
            )
            details.append(detail)
            progress_callback(detail, None)
        return BatchReportService().build_report(
            total_selected=len(self.records),
            details=details,
            started_at="2026-10-17T00:00:00Z",
            ended_at="2026-10-17T00:00:01Z",
            duration_seconds=1.0,
            aborted_due_to_session_loss=False,
            cancelled=cancelled,
        )


def _records(repository: InvoiceRecordRepository, count: int):
    return [
        repository.create(
            InvoiceRecordCreate(
                ad=f"Ad{index}",
                soyad="Soyad",
                tc_kimlik_no=f"1234567890{index}",
                tutar_usd=100.0,
            )
        )
        for index in range(count)
    ]


def _wait_until_inactive(manager: BatchJobManager) -> dict:
    for _ in range(500):
        status = manager.status()
        if status is not None and not status["is_active"]:
            return status
        threading.Event().wait(0.01)
    raise AssertionError("job did not finish")


def test_batch_job_runs_in_background_and_reports_progress(tmp_path: Path) -> None:
    repository = InvoiceRecordRepository(tmp_path / "test.sqlite3")
    worker = PlaywrightWorker()
    service = ControlledBatchService(_records(repository, 2))
    manager = BatchJobManager(worker=worker, service_factory=lambda: service)

    job = manager.start(batch_id=1)

    assert job["status"] in {"QUEUED", "RUNNING"}
    assert service.first_record_started.wait(timeout=5)
    assert manager.is_running() is True
    assert manager.status()["total"] == 2
    assert manager.status()["current_record_name"] == "Ad0 Soyad"

    service.step.release()
    service.step.release()
    status = _wait_until_inactive(manager)

    assert status["status"] == BatchJobStatus.COMPLETED.value
    assert status["processed"] == 2
    assert status["success_count"] == 2
    assert status["progress_percent"] == 100
    assert status["report"]["success_count"] == 2
    assert service.thread_ident == worker.thread_ident
    worker.shutdown()


def test_batch_job_allows_only_one_active_job(tmp_path: Path) -> None:
    repository = InvoiceRecordRepository(tmp_path / "test.sqlite3")
    worker = PlaywrightWorker()
    service = ControlledBatchService(_records(repository, 1))
    manager = BatchJobManager(worker=worker, service_factory=lambda: service)

    manager.start(batch_id=1)
    assert service.started.wait(timeout=5)

    with pytest.raises(BatchJobAlreadyRunningError):
        manager.start(batch_id=1)

    service.step.release()
    _wait_until_inactive(manager)
    # A finished job no longer blocks a new one.
    second_service = ControlledBatchService([])
    manager.service_factory = lambda: second_service
    manager.start(batch_id=1)
    assert _wait_until_inactive(manager)["status"] == BatchJobStatus.COMPLETED.value
    worker.shutdown()


def test_batch_job_cancel_stops_between_records(tmp_path: Path) -> None:
    repository = InvoiceRecordRepository(tmp_path / "test.sqlite3")
    worker = PlaywrightWorker()
    service = ControlledBatchService(_records(repository, 3))
    manager = BatchJobManager(worker=worker, service_factory=lambda: service)

    manager.start(batch_id=1)
    assert service.started.wait(timeout=5)
    assert manager.cancel() is True
    assert manager.status()["status"] == BatchJobStatus.CANCEL_REQUESTED.value

    # The record already on the portal is finished before the job stops.
    service.step.release()
    status = _wait_until_inactive(manager)

    assert status["status"] == BatchJobStatus.CANCELLED.value
    assert status["processed"] == 1
    assert status["report"]["cancelled"] is True
    assert manager.cancel() is False
    worker.shutdown()


def test_batch_job_crash_moves_in_progress_records_to_needs_review(tmp_path: Path) -> None:
    repository = InvoiceRecordRepository(tmp_path / "test.sqlite3")
    records = _records(repository, 1)
    repository.claim_for_processing(records[0].id)
    worker = PlaywrightWorker()
    service = ControlledBatchService(records, fail=True)
    manager = BatchJobManager(
        worker=worker,
        service_factory=lambda: service,
        repository_factory=lambda: repository,
    )

    manager.start(batch_id=1)
    assert service.started.wait(timeout=5)
    service.step.release()
    status = _wait_until_inactive(manager)

    assert status["status"] == BatchJobStatus.FAILED.value
    assert "boom" in status["error"]
    assert repository.get(records[0].id).islem_durumu == InvoiceStatus.NEEDS_REVIEW.value
    assert worker.background_active is False
    worker.shutdown()
