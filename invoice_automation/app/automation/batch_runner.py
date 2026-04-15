"""Sequential batch runner for selected e-Arsiv draft records."""

from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Any, Protocol
import logging

from invoice_automation.app.automation.portal_navigation import EArchiveNavigation
from invoice_automation.app.automation.session_manager import (
    PortalSessionManager,
    PortalSessionStatus,
    portal_session_manager,
)
from invoice_automation.app.config import settings
from invoice_automation.app.constants import BATCH_ABORT_STATUSES
from invoice_automation.app.db.models import InvoiceRecord
from invoice_automation.app.schemas.batch import BatchRecordResult, BatchRunReport
from invoice_automation.app.schemas.draft import SingleDraftServiceResult
from invoice_automation.app.services.draft_service import SingleDraftService
from invoice_automation.app.services.report_service import BatchReportService
from invoice_automation.app.utils.exceptions import SessionLostError

logger = logging.getLogger(__name__)


class DraftServiceProtocol(Protocol):
    """Contract used by the batch runner for one-record processing."""

    def create_for_record(self, record_id: int) -> SingleDraftServiceResult:
        """Create a draft for one record and persist the result."""


class BatchRunner:
    """Run selected records sequentially through the single-record draft flow."""

    def __init__(
        self,
        *,
        draft_service: DraftServiceProtocol | None = None,
        session_manager: PortalSessionManager = portal_session_manager,
        navigation: EArchiveNavigation | None = None,
        report_service: BatchReportService | None = None,
        navigation_retry_count: int | None = None,
    ) -> None:
        self.session_manager = session_manager
        self.draft_service = draft_service or SingleDraftService(session_manager=session_manager)
        self.navigation = navigation or EArchiveNavigation()
        self.report_service = report_service or BatchReportService()
        self.navigation_retry_count = navigation_retry_count or settings.navigation_retry_count

    def run(self, records: list[InvoiceRecord]) -> BatchRunReport:
        """Process selected records in deterministic order and return a report."""

        started_at = self._utc_timestamp()
        started_timer = perf_counter()
        details: list[BatchRecordResult] = []
        aborted_due_to_session_loss = False
        abort_reason: str | None = None

        logger.info("Batch basladi | selected_count=%s", len(records))

        try:
            self._ensure_session_ready()
        except SessionLostError as exc:
            aborted_due_to_session_loss = True
            abort_reason = str(exc)
            logger.error("Batch baslamadan durduruldu | reason=%s", abort_reason)
            return self._build_report(
                total_selected=len(records),
                details=details,
                started_at=started_at,
                started_timer=started_timer,
                aborted_due_to_session_loss=aborted_due_to_session_loss,
                abort_reason=abort_reason,
            )

        for index, record in enumerate(records, start=1):
            record_started_at = self._utc_timestamp()
            logger.info(
                "Batch kayit isleme basladi | index=%s total=%s record_id=%s tc=%s",
                index,
                len(records),
                record.id,
                record.tc_kimlik_no,
            )

            result = self.draft_service.create_for_record(record.id)
            record_ended_at = self._utc_timestamp()
            detail = self._detail_from_result(result, record_started_at, record_ended_at)
            details.append(detail)

            logger.info(
                "Batch kayit sonucu | index=%s total=%s record_id=%s status=%s error_code=%s screenshot=%s",
                index,
                len(records),
                detail.record_id,
                detail.final_status,
                detail.error_code,
                detail.screenshot_path,
            )

            if self._is_abort_status(detail.final_status):
                aborted_due_to_session_loss = True
                abort_reason = detail.error_message or "Session kaybi nedeniyle batch durduruldu."
                logger.error(
                    "Batch kritik hata nedeniyle durduruldu | record_id=%s status=%s reason=%s",
                    detail.record_id,
                    detail.final_status,
                    abort_reason,
                )
                break

            if index < len(records):
                try:
                    self._prepare_clean_create_page_for_next_record()
                except SessionLostError as exc:
                    aborted_due_to_session_loss = True
                    abort_reason = str(exc)
                    logger.exception(
                        "Batch yeni kayit ekranina donemedi; islem durduruldu | last_record_id=%s",
                        record.id,
                    )
                    break

        return self._build_report(
            total_selected=len(records),
            details=details,
            started_at=started_at,
            started_timer=started_timer,
            aborted_due_to_session_loss=aborted_due_to_session_loss,
            abort_reason=abort_reason,
        )

    def _ensure_session_ready(self) -> Any:
        page = self.session_manager.browser_manager.page
        if page is None:
            raise SessionLostError("Aktif browser session bulunamadi.")
        if self._page_is_closed(page):
            raise SessionLostError("Browser page kapali gorunuyor.")
        if self.session_manager.state.status != PortalSessionStatus.READY:
            raise SessionLostError("Portal session READY degil. Once /session ekraninda 2FA onayi yapin.")
        return page

    def _prepare_clean_create_page_for_next_record(self) -> None:
        last_error: Exception | None = None
        for attempt in range(1, self.navigation_retry_count + 1):
            try:
                page = self._ensure_session_ready()
                logger.info(
                    "Sonraki kayit icin e-Arsiv olustur sayfasi hazirlaniyor | attempt=%s",
                    attempt,
                )
                self._open_fresh_create_page(page)
                logger.info("Sonraki kayit icin temiz e-Arsiv formu hazir")
                return
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Yeni e-Arsiv olustur sayfasina donus basarisiz | attempt=%s retry_count=%s error=%s",
                    attempt,
                    self.navigation_retry_count,
                    exc,
                )
                self._short_wait_after_navigation_error()

        raise SessionLostError(
            f"Yeni e-Arsiv olustur sayfasina guvenli donulemedi: {last_error}"
        ) from last_error

    def _open_fresh_create_page(self, page: Any) -> None:
        try:
            self.navigation.open_next_create_invoice_page(page)
        except Exception:
            logger.info("Direkt e-Arsiv olustur linki basarisiz; menu uzerinden tekrar deneniyor")
            self.navigation.open_create_invoice_page(page)

    def _short_wait_after_navigation_error(self) -> None:
        page = self.session_manager.browser_manager.page
        if page is None or self._page_is_closed(page):
            return
        try:
            page.wait_for_timeout(settings.retry_backoff_base_ms)
        except Exception:
            return

    def _detail_from_result(
        self,
        result: SingleDraftServiceResult,
        started_at: str,
        ended_at: str,
    ) -> BatchRecordResult:
        record = result.record
        return BatchRecordResult(
            record_id=record.id,
            tc_kimlik_no=record.tc_kimlik_no,
            full_name=f"{record.ad} {record.soyad}".strip(),
            final_status=record.islem_durumu,
            ok=result.ok,
            error_code=result.error_code,
            error_message=None if result.ok else result.message,
            screenshot_path=result.screenshot_path,
            started_at=started_at,
            ended_at=ended_at,
        )

    def _is_abort_status(self, status: str) -> bool:
        return status in {abort_status.value for abort_status in BATCH_ABORT_STATUSES}

    def _build_report(
        self,
        *,
        total_selected: int,
        details: list[BatchRecordResult],
        started_at: str,
        started_timer: float,
        aborted_due_to_session_loss: bool,
        abort_reason: str | None,
    ) -> BatchRunReport:
        ended_at = self._utc_timestamp()
        report = self.report_service.build_report(
            total_selected=total_selected,
            details=details,
            started_at=started_at,
            ended_at=ended_at,
            duration_seconds=perf_counter() - started_timer,
            aborted_due_to_session_loss=aborted_due_to_session_loss,
            abort_reason=abort_reason,
        )
        logger.info(
            "Batch bitti | selected=%s processed=%s success=%s skipped=%s failed=%s aborted=%s abort_reason=%s",
            report.total_selected,
            report.total_processed,
            report.success_count,
            report.skipped_count,
            report.failed_count,
            report.aborted_count,
            report.abort_reason,
        )
        return report

    def _page_is_closed(self, page: Any) -> bool:
        is_closed = getattr(page, "is_closed", None)
        if not callable(is_closed):
            return False
        try:
            return bool(is_closed())
        except Exception:
            return True

    def _utc_timestamp(self) -> str:
        return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
