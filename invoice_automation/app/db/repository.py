"""Repository layer for invoice records."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sqlite3

from invoice_automation.app.constants import (
    BATCH_ELIGIBLE_STATUSES,
    RETRYABLE_STATUSES,
    STALE_IN_PROGRESS_ERROR_CODE,
    InvoiceStatus,
)
from invoice_automation.app.db.database import get_connection, initialize_database
from invoice_automation.app.db.models import (
    ImportBatch,
    ImportBatchCreate,
    ImportBatchSummary,
    InvoiceRecord,
    InvoiceRecordCreate,
    utc_timestamp,
)
from invoice_automation.app.utils.exceptions import DeletionBlockedError


SELECTABLE_STATUSES = (InvoiceStatus.PENDING.value, InvoiceStatus.SELECTED.value)
RECORD_SORT_COLUMNS = {
    "id": "id",
    "ad": "LOWER(ad)",
    "soyad": "LOWER(soyad)",
    "tc_kimlik_no": "tc_kimlik_no",
    "tutar_usd": "tutar_usd",
}


_UNASSIGNED_RECORD_FILTER = (
    "(batch_id IS NULL OR batch_id NOT IN (SELECT id FROM import_batches))"
)


class InvoiceRecordRepository:
    """SQLite-backed repository for invoice records."""

    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path
        initialize_database(database_path)

    def _connect(self) -> sqlite3.Connection:
        return get_connection(self.database_path)

    def create(self, record: InvoiceRecordCreate) -> InvoiceRecord:
        """Insert a record and return the persisted row."""

        with self._connect() as connection:
            record_id = _insert_record(connection, record, utc_timestamp())

        persisted = self.get(record_id)
        if persisted is None:
            raise RuntimeError("Inserted invoice record could not be loaded.")
        return persisted

    def create_import(
        self,
        batch: ImportBatchCreate,
        records: list[InvoiceRecordCreate],
    ) -> tuple[ImportBatch, list[InvoiceRecord]]:
        """Persist an import batch and all of its records in one transaction.

        Either the whole import lands or nothing does; a failure mid-way leaves no
        half-imported fatura donemi behind.
        """

        now = utc_timestamp()
        with self._connect() as connection:
            batch_id = _insert_import_batch(connection, batch, now)
            record_ids = [
                _insert_record(connection, replace(record, batch_id=batch_id), now)
                for record in records
            ]

        persisted_batch = self.get_import_batch(batch_id)
        if persisted_batch is None:
            raise RuntimeError("Inserted import batch could not be loaded.")
        persisted_records = [self.get(record_id) for record_id in record_ids]
        if any(record is None for record in persisted_records):
            raise RuntimeError("Inserted invoice records could not be loaded.")
        return persisted_batch, persisted_records  # type: ignore[return-value]

    def create_import_batch(self, batch: ImportBatchCreate) -> ImportBatch:
        """Create an import/fatura period and return it."""

        with self._connect() as connection:
            batch_id = _insert_import_batch(connection, batch, utc_timestamp())

        persisted = self.get_import_batch(batch_id)
        if persisted is None:
            raise RuntimeError("Inserted import batch could not be loaded.")
        return persisted

    def list_import_batches(self, include_archived: bool = False) -> list[ImportBatch]:
        """List import/fatura periods, newest first."""

        with self._connect() as connection:
            if include_archived:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM import_batches
                    ORDER BY id DESC
                    """
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM import_batches
                    WHERE is_archived = 0
                    ORDER BY id DESC
                    """
                ).fetchall()
        return [ImportBatch.from_row(row) for row in rows]

    def get_import_batch(self, batch_id: int) -> ImportBatch | None:
        """Return one import/fatura period by id."""

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM import_batches
                WHERE id = ?
                """,
                (batch_id,),
            ).fetchone()
        return ImportBatch.from_row(row) if row else None

    def latest_import_batch(self) -> ImportBatch | None:
        """Return the latest non-archived import/fatura period."""

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM import_batches
                WHERE is_archived = 0
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
        return ImportBatch.from_row(row) if row else None

    def list_all(
        self,
        status: InvoiceStatus | str | None = None,
        batch_id: int | None = None,
        search: str | None = None,
        sort_by: str = "id",
        sort_dir: str = "desc",
    ) -> list[InvoiceRecord]:
        """List records, optionally filtering by status, batch and text search."""

        filters: list[str] = []
        values: list[object] = []
        if status:
            filters.append("islem_durumu = ?")
            values.append(str(status))
        if batch_id is not None:
            filters.append("batch_id = ?")
            values.append(batch_id)
        normalized_search = (search or "").strip()

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        order_clause = _record_order_clause(sort_by, sort_dir)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM invoice_records
                {where_clause}
                {order_clause}
                """,
                values,
            ).fetchall()
        records = [InvoiceRecord.from_row(row) for row in rows]
        if not normalized_search:
            return records

        search_value = normalized_search.casefold()
        return [
            record
            for record in records
            if search_value in record.ad.casefold()
            or search_value in record.soyad.casefold()
            or search_value in record.tc_kimlik_no
        ]

    def get(self, record_id: int) -> InvoiceRecord | None:
        """Return a single record by id."""

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM invoice_records
                WHERE id = ?
                """,
                (record_id,),
            ).fetchone()
        return InvoiceRecord.from_row(row) if row else None

    def list_selected(self, batch_id: int | None = None) -> list[InvoiceRecord]:
        """List records currently selected for batch preparation."""

        filters = ["secili_mi = 1"]
        values: list[object] = []
        if batch_id is not None:
            filters.append("batch_id = ?")
            values.append(batch_id)

        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM invoice_records
                WHERE {' AND '.join(filters)}
                ORDER BY id ASC
                """,
                values,
            ).fetchall()
        return [InvoiceRecord.from_row(row) for row in rows]

    def list_selected_for_batch(
        self,
        eligible_statuses: tuple[InvoiceStatus, ...] = BATCH_ELIGIBLE_STATUSES,
        batch_id: int | None = None,
    ) -> list[InvoiceRecord]:
        """List selected records that are allowed to enter a batch run."""

        status_values = tuple(status.value for status in eligible_statuses)
        placeholders = ",".join("?" for _ in status_values)
        batch_filter = "AND batch_id = ?" if batch_id is not None else ""
        values: list[object] = [*status_values]
        if batch_id is not None:
            values.append(batch_id)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM invoice_records
                WHERE secili_mi = 1
                  AND islem_durumu IN ({placeholders})
                  {batch_filter}
                ORDER BY id ASC
                """,
                values,
            ).fetchall()
        return [InvoiceRecord.from_row(row) for row in rows]

    def update_selection(self, selected_ids: list[int], batch_id: int | None = None) -> int:
        """Persist selected records and return the selected count.

        Only PENDING and SELECTED records are changed. Completed or failed records
        keep their current status and selection flag.
        """

        normalized_ids = sorted({int(record_id) for record_id in selected_ids})
        now = utc_timestamp()

        with self._connect() as connection:
            reset_batch_filter = "AND batch_id = ?" if batch_id is not None else ""
            reset_values: list[object] = [
                InvoiceStatus.PENDING.value,
                now,
                InvoiceStatus.SELECTED.value,
            ]
            if batch_id is not None:
                reset_values.append(batch_id)
            connection.execute(
                f"""
                UPDATE invoice_records
                SET secili_mi = 0,
                    islem_durumu = ?,
                    guncelleme_zamani = ?
                WHERE islem_durumu = ?
                  {reset_batch_filter}
                """,
                reset_values,
            )

            if normalized_ids:
                placeholders = ",".join("?" for _ in normalized_ids)
                batch_filter = "AND batch_id = ?" if batch_id is not None else ""
                values: list[object] = [
                    InvoiceStatus.SELECTED.value,
                    now,
                    *normalized_ids,
                    InvoiceStatus.PENDING.value,
                    InvoiceStatus.SELECTED.value,
                ]
                if batch_id is not None:
                    values.append(batch_id)
                connection.execute(
                    f"""
                    UPDATE invoice_records
                    SET secili_mi = 1,
                        islem_durumu = ?,
                        guncelleme_zamani = ?
                    WHERE id IN ({placeholders})
                      AND islem_durumu IN (?, ?)
                      {batch_filter}
                    """,
                    values,
                )

            selected_batch_filter = "AND batch_id = ?" if batch_id is not None else ""
            selected_values: list[object] = [InvoiceStatus.SELECTED.value]
            if batch_id is not None:
                selected_values.append(batch_id)
            row = connection.execute(
                f"""
                SELECT COUNT(*) AS total
                FROM invoice_records
                WHERE secili_mi = 1
                  AND islem_durumu = ?
                  {selected_batch_filter}
                """,
                selected_values,
            ).fetchone()

        return int(row["total"])

    def count_by_status(self, batch_id: int | None = None) -> dict[str, int]:
        """Return record counts grouped by status."""

        batch_filter = "WHERE batch_id = ?" if batch_id is not None else ""
        values: list[object] = []
        if batch_id is not None:
            values.append(batch_id)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT islem_durumu, COUNT(*) AS total
                FROM invoice_records
                {batch_filter}
                GROUP BY islem_durumu
                """,
                values,
            ).fetchall()
        return {str(row["islem_durumu"]): int(row["total"]) for row in rows}

    def update_processing_state(
        self,
        record_id: int,
        status: InvoiceStatus,
        portal_ref_no: str | None = None,
        hata_kodu: str | None = None,
        hata_mesaji: str | None = None,
        secili_mi: bool | None = None,
    ) -> InvoiceRecord:
        """Update processing status and return the refreshed record."""

        now = utc_timestamp()
        assignments = [
            "islem_durumu = ?",
            "portal_ref_no = ?",
            "hata_kodu = ?",
            "hata_mesaji = ?",
            "guncelleme_zamani = ?",
        ]
        values: list[object] = [
            status.value,
            portal_ref_no,
            hata_kodu,
            hata_mesaji,
            now,
        ]

        if secili_mi is not None:
            assignments.append("secili_mi = ?")
            values.append(int(secili_mi))

        values.append(record_id)

        with self._connect() as connection:
            connection.execute(
                f"""
                UPDATE invoice_records
                SET {", ".join(assignments)}
                WHERE id = ?
                """,
                values,
            )

        updated = self.get(record_id)
        if updated is None:
            raise RuntimeError(f"Invoice record not found after status update: {record_id}")
        return updated

    def claim_for_processing(self, record_id: int) -> InvoiceRecord | None:
        """Atomically move an eligible record to IN_PROGRESS.

        Returns the claimed record, or None when the record is not PENDING/SELECTED
        (already processed, in progress elsewhere, or awaiting review). The single
        conditional UPDATE is the idempotency guard against double submits.
        """

        eligible = tuple(status.value for status in BATCH_ELIGIBLE_STATUSES)
        placeholders = ",".join("?" for _ in eligible)
        with self._connect() as connection:
            cursor = connection.execute(
                f"""
                UPDATE invoice_records
                SET islem_durumu = ?,
                    guncelleme_zamani = ?
                WHERE id = ?
                  AND islem_durumu IN ({placeholders})
                """,
                (InvoiceStatus.IN_PROGRESS.value, utc_timestamp(), record_id, *eligible),
            )
            claimed = cursor.rowcount == 1
        return self.get(record_id) if claimed else None

    def recover_stale_in_progress(self) -> int:
        """Move records left IN_PROGRESS by a crash/restart to NEEDS_REVIEW.

        Nothing can be in progress when the application boots, so these records
        were interrupted at an unknown step and the portal must be checked by hand.
        """

        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE invoice_records
                SET islem_durumu = ?,
                    secili_mi = 0,
                    hata_kodu = ?,
                    hata_mesaji = ?,
                    guncelleme_zamani = ?
                WHERE islem_durumu = ?
                """,
                (
                    InvoiceStatus.NEEDS_REVIEW.value,
                    STALE_IN_PROGRESS_ERROR_CODE,
                    "Islem yarida kaldi (uygulama yeniden basladi). Portalda taslak olusup "
                    "olusmadigini kontrol edip kaydi manuel olarak sonuclandirin.",
                    utc_timestamp(),
                    InvoiceStatus.IN_PROGRESS.value,
                ),
            )
            return cursor.rowcount

    def reset_failed_to_pending(self, record_ids: list[int]) -> int:
        """Consciously return retryable failed records to PENDING.

        Only statuses in RETRYABLE_STATUSES are touched; SUCCESS, SKIPPED and
        NEEDS_REVIEW records are never reset by this action.
        """

        normalized_ids = sorted({int(record_id) for record_id in record_ids})
        if not normalized_ids:
            return 0
        retryable = tuple(status.value for status in RETRYABLE_STATUSES)
        id_placeholders = ",".join("?" for _ in normalized_ids)
        status_placeholders = ",".join("?" for _ in retryable)
        with self._connect() as connection:
            cursor = connection.execute(
                f"""
                UPDATE invoice_records
                SET islem_durumu = ?,
                    secili_mi = 0,
                    hata_kodu = NULL,
                    hata_mesaji = NULL,
                    guncelleme_zamani = ?
                WHERE id IN ({id_placeholders})
                  AND islem_durumu IN ({status_placeholders})
                """,
                (InvoiceStatus.PENDING.value, utc_timestamp(), *normalized_ids, *retryable),
            )
            return cursor.rowcount

    def resolve_needs_review(self, record_id: int, *, draft_exists: bool) -> InvoiceRecord | None:
        """Close a NEEDS_REVIEW record after the operator checked the portal.

        ``draft_exists=True`` marks it SUCCESS_DRAFT_CREATED; ``False`` returns it
        to PENDING so it can be selected again. Returns None when the record is
        not in NEEDS_REVIEW.
        """

        if draft_exists:
            target_status = InvoiceStatus.SUCCESS_DRAFT_CREATED
            note = "Portalda taslak varligi manuel olarak dogrulandi."
        else:
            target_status = InvoiceStatus.PENDING
            note = None
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE invoice_records
                SET islem_durumu = ?,
                    secili_mi = 0,
                    hata_kodu = NULL,
                    hata_mesaji = ?,
                    guncelleme_zamani = ?
                WHERE id = ?
                  AND islem_durumu = ?
                """,
                (
                    target_status.value,
                    note,
                    utc_timestamp(),
                    record_id,
                    InvoiceStatus.NEEDS_REVIEW.value,
                ),
            )
            resolved = cursor.rowcount == 1
        return self.get(record_id) if resolved else None

    def list_by_statuses(
        self,
        statuses: tuple[InvoiceStatus, ...],
        batch_id: int | None = None,
    ) -> list[InvoiceRecord]:
        """List records in any of the given statuses, oldest first."""

        status_values = tuple(status.value for status in statuses)
        placeholders = ",".join("?" for _ in status_values)
        batch_filter = "AND batch_id = ?" if batch_id is not None else ""
        values: list[object] = [*status_values]
        if batch_id is not None:
            values.append(batch_id)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM invoice_records
                WHERE islem_durumu IN ({placeholders})
                  {batch_filter}
                ORDER BY id ASC
                """,
                values,
            ).fetchall()
        return [InvoiceRecord.from_row(row) for row in rows]

    def list_import_batch_summaries(self) -> list[ImportBatchSummary]:
        """List every import/fatura period with record counts, newest first."""

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    b.*,
                    COUNT(r.id) AS record_count,
                    COALESCE(SUM(r.tutar_usd), 0) AS total_usd,
                    COALESCE(SUM(r.islem_durumu IN (?, ?)), 0) AS waiting_count,
                    COALESCE(SUM(r.islem_durumu = ?), 0) AS success_count,
                    COALESCE(SUM(
                        r.islem_durumu LIKE 'FAILED_%'
                        OR r.islem_durumu LIKE 'SKIPPED_%'
                        OR r.islem_durumu LIKE 'ABORTED_%'
                    ), 0) AS failed_count,
                    COALESCE(SUM(r.islem_durumu = ?), 0) AS review_count,
                    COALESCE(SUM(r.islem_durumu = ?), 0) AS in_progress_count
                FROM import_batches AS b
                LEFT JOIN invoice_records AS r ON r.batch_id = b.id
                GROUP BY b.id
                ORDER BY b.id DESC
                """,
                (
                    InvoiceStatus.PENDING.value,
                    InvoiceStatus.SELECTED.value,
                    InvoiceStatus.SUCCESS_DRAFT_CREATED.value,
                    InvoiceStatus.NEEDS_REVIEW.value,
                    InvoiceStatus.IN_PROGRESS.value,
                ),
            ).fetchall()
        return [
            ImportBatchSummary(
                batch=ImportBatch.from_row(row),
                record_count=int(row["record_count"]),
                total_usd=float(row["total_usd"]),
                waiting_count=int(row["waiting_count"]),
                success_count=int(row["success_count"]),
                failed_count=int(row["failed_count"]),
                review_count=int(row["review_count"]),
                in_progress_count=int(row["in_progress_count"]),
            )
            for row in rows
        ]

    def count_unassigned_records(self) -> int:
        """Count records that belong to no existing fatura period (legacy imports)."""

        with self._connect() as connection:
            row = connection.execute(
                f"""
                SELECT COUNT(*) AS total
                FROM invoice_records
                WHERE {_UNASSIGNED_RECORD_FILTER}
                """
            ).fetchone()
        return int(row["total"])

    def delete_records(self, record_ids: list[int], batch_id: int | None = None) -> int:
        """Delete local records and return the deleted count.

        IN_PROGRESS records are never deleted: the portal may be working on them.
        Drafts already created on the portal are not affected.
        """

        normalized_ids = sorted({int(record_id) for record_id in record_ids})
        if not normalized_ids:
            return 0
        id_placeholders = ",".join("?" for _ in normalized_ids)
        batch_filter = "AND batch_id = ?" if batch_id is not None else ""
        values: list[object] = [*normalized_ids, InvoiceStatus.IN_PROGRESS.value]
        if batch_id is not None:
            values.append(batch_id)
        with self._connect() as connection:
            cursor = connection.execute(
                f"""
                DELETE FROM invoice_records
                WHERE id IN ({id_placeholders})
                  AND islem_durumu != ?
                  {batch_filter}
                """,
                values,
            )
            return cursor.rowcount

    def delete_import_batch(self, batch_id: int) -> int | None:
        """Delete a fatura period and all of its records in one transaction.

        Returns the deleted record count, or None when the period does not exist.
        Raises DeletionBlockedError when one of its records is IN_PROGRESS.
        """

        with self._connect() as connection:
            batch_row = connection.execute(
                "SELECT id FROM import_batches WHERE id = ?",
                (batch_id,),
            ).fetchone()
            if batch_row is None:
                return None
            in_progress = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM invoice_records
                WHERE batch_id = ?
                  AND islem_durumu = ?
                """,
                (batch_id, InvoiceStatus.IN_PROGRESS.value),
            ).fetchone()
            if int(in_progress["total"]):
                raise DeletionBlockedError(
                    "Bu donemde su anda islenen kayit var; islem bitmeden donem silinemez."
                )
            cursor = connection.execute(
                "DELETE FROM invoice_records WHERE batch_id = ?",
                (batch_id,),
            )
            deleted_records = cursor.rowcount
            connection.execute("DELETE FROM import_batches WHERE id = ?", (batch_id,))
        return deleted_records

    def delete_unassigned_records(self) -> int:
        """Delete records that belong to no existing fatura period."""

        with self._connect() as connection:
            cursor = connection.execute(
                f"""
                DELETE FROM invoice_records
                WHERE {_UNASSIGNED_RECORD_FILTER}
                  AND islem_durumu != ?
                """,
                (InvoiceStatus.IN_PROGRESS.value,),
            )
            return cursor.rowcount

    def count(self) -> int:
        """Return total record count."""

        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS total FROM invoice_records").fetchone()
        return int(row["total"])


def _insert_record(connection: sqlite3.Connection, record: InvoiceRecordCreate, now: str) -> int:
    cursor = connection.execute(
        """
        INSERT INTO invoice_records (
            batch_id,
            ad,
            soyad,
            tc_kimlik_no,
            tutar_usd,
            aciklama,
            fatura_tipi_hedef,
            kaynak_dosya,
            kaynak_satir_no,
            secili_mi,
            islem_durumu,
            olusturma_zamani,
            guncelleme_zamani
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.batch_id,
            record.ad,
            record.soyad,
            record.tc_kimlik_no,
            record.tutar_usd,
            record.aciklama,
            record.fatura_tipi_hedef,
            record.kaynak_dosya,
            record.kaynak_satir_no,
            int(record.secili_mi),
            str(record.islem_durumu),
            now,
            now,
        ),
    )
    return int(cursor.lastrowid)


def _insert_import_batch(connection: sqlite3.Connection, batch: ImportBatchCreate, now: str) -> int:
    cursor = connection.execute(
        """
        INSERT INTO import_batches (
            name,
            source_file_name,
            sheet_name,
            created_at,
            status,
            is_archived
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            batch.name,
            batch.source_file_name,
            batch.sheet_name,
            now,
            batch.status,
            int(batch.is_archived),
        ),
    )
    return int(cursor.lastrowid)


def _record_order_clause(sort_by: str, sort_dir: str) -> str:
    sort_key = sort_by if sort_by in RECORD_SORT_COLUMNS else "id"
    direction = "ASC" if sort_dir.lower() == "asc" else "DESC"
    sort_expression = RECORD_SORT_COLUMNS[sort_key]

    if sort_key == "id":
        return f"ORDER BY {sort_expression} {direction}"

    return f"ORDER BY {sort_expression} {direction}, id DESC"
