"""Repository layer for invoice records."""

from __future__ import annotations

from pathlib import Path
import sqlite3

from invoice_automation.app.constants import (
    BATCH_ELIGIBLE_STATUSES,
    InvoiceStatus,
)
from invoice_automation.app.db.database import get_connection, initialize_database
from invoice_automation.app.db.models import (
    ImportBatch,
    ImportBatchCreate,
    InvoiceRecord,
    InvoiceRecordCreate,
    utc_timestamp,
)


SELECTABLE_STATUSES = (InvoiceStatus.PENDING.value, InvoiceStatus.SELECTED.value)


class InvoiceRecordRepository:
    """SQLite-backed repository for invoice records."""

    def __init__(self, database_path: Path | None = None) -> None:
        self.database_path = database_path
        initialize_database(database_path)

    def _connect(self) -> sqlite3.Connection:
        return get_connection(self.database_path)

    def create(self, record: InvoiceRecordCreate) -> InvoiceRecord:
        """Insert a record and return the persisted row."""

        now = utc_timestamp()
        with self._connect() as connection:
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
            record_id = cursor.lastrowid

        persisted = self.get(record_id)
        if persisted is None:
            raise RuntimeError("Inserted invoice record could not be loaded.")
        return persisted

    def create_import_batch(self, batch: ImportBatchCreate) -> ImportBatch:
        """Create an import/fatura period and return it."""

        now = utc_timestamp()
        with self._connect() as connection:
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
            batch_id = cursor.lastrowid

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
        if normalized_search:
            filters.append("(ad LIKE ? OR soyad LIKE ? OR tc_kimlik_no LIKE ?)")
            search_value = f"%{normalized_search}%"
            values.extend([search_value, search_value, search_value])

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM invoice_records
                {where_clause}
                ORDER BY id DESC
                """,
                values,
            ).fetchall()
        return [InvoiceRecord.from_row(row) for row in rows]

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

    def count(self) -> int:
        """Return total record count."""

        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS total FROM invoice_records").fetchone()
        return int(row["total"])
