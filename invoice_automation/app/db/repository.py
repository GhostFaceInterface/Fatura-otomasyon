"""Repository layer for invoice records."""

from __future__ import annotations

from pathlib import Path
import sqlite3

from invoice_automation.app.constants import InvoiceStatus
from invoice_automation.app.db.database import get_connection, initialize_database
from invoice_automation.app.db.models import InvoiceRecord, InvoiceRecordCreate, utc_timestamp


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
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
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

    def list_all(self, status: InvoiceStatus | str | None = None) -> list[InvoiceRecord]:
        """List records, optionally filtering by status."""

        with self._connect() as connection:
            if status:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM invoice_records
                    WHERE islem_durumu = ?
                    ORDER BY id DESC
                    """,
                    (str(status),),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM invoice_records
                    ORDER BY id DESC
                    """
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

    def list_selected(self) -> list[InvoiceRecord]:
        """List records currently selected for batch preparation."""

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM invoice_records
                WHERE secili_mi = 1
                ORDER BY id ASC
                """
            ).fetchall()
        return [InvoiceRecord.from_row(row) for row in rows]

    def update_selection(self, selected_ids: list[int]) -> int:
        """Persist selected records and return the selected count.

        Only PENDING and SELECTED records are changed. Completed or failed records
        keep their current status and selection flag.
        """

        normalized_ids = sorted({int(record_id) for record_id in selected_ids})
        now = utc_timestamp()

        with self._connect() as connection:
            connection.execute(
                """
                UPDATE invoice_records
                SET secili_mi = 0,
                    islem_durumu = ?,
                    guncelleme_zamani = ?
                WHERE islem_durumu = ?
                """,
                (InvoiceStatus.PENDING.value, now, InvoiceStatus.SELECTED.value),
            )

            if normalized_ids:
                placeholders = ",".join("?" for _ in normalized_ids)
                connection.execute(
                    f"""
                    UPDATE invoice_records
                    SET secili_mi = 1,
                        islem_durumu = ?,
                        guncelleme_zamani = ?
                    WHERE id IN ({placeholders})
                      AND islem_durumu IN (?, ?)
                    """,
                    (
                        InvoiceStatus.SELECTED.value,
                        now,
                        *normalized_ids,
                        InvoiceStatus.PENDING.value,
                        InvoiceStatus.SELECTED.value,
                    ),
                )

            row = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM invoice_records
                WHERE secili_mi = 1
                  AND islem_durumu = ?
                """,
                (InvoiceStatus.SELECTED.value,),
            ).fetchone()

        return int(row["total"])

    def count_by_status(self) -> dict[str, int]:
        """Return record counts grouped by status."""

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT islem_durumu, COUNT(*) AS total
                FROM invoice_records
                GROUP BY islem_durumu
                """
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
