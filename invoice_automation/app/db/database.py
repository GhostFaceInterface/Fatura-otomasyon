"""SQLite connection and schema management."""

from __future__ import annotations

from pathlib import Path
import sqlite3

from invoice_automation.app.config import ensure_runtime_directories, settings


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS invoice_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ad TEXT NOT NULL,
    soyad TEXT NOT NULL,
    tc_kimlik_no TEXT NOT NULL,
    tutar_usd REAL NOT NULL,
    aciklama TEXT,
    fatura_tipi_hedef TEXT NOT NULL DEFAULT 'earshiv',
    kaynak_dosya TEXT,
    kaynak_satir_no INTEGER,
    secili_mi INTEGER NOT NULL DEFAULT 0,
    islem_durumu TEXT NOT NULL DEFAULT 'PENDING',
    portal_ref_no TEXT,
    hata_kodu TEXT,
    hata_mesaji TEXT,
    olusturma_zamani TEXT NOT NULL,
    guncelleme_zamani TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_invoice_records_status
ON invoice_records (islem_durumu);

CREATE INDEX IF NOT EXISTS idx_invoice_records_tckn
ON invoice_records (tc_kimlik_no);
"""


def get_connection(database_path: Path | None = None) -> sqlite3.Connection:
    """Return a SQLite connection with row access by column name."""

    ensure_runtime_directories()
    db_path = database_path or settings.database_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database(database_path: Path | None = None) -> None:
    """Create database tables and indexes if they do not exist."""

    with get_connection(database_path) as connection:
        connection.executescript(SCHEMA_SQL)
