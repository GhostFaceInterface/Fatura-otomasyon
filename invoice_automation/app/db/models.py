"""Domain models for invoice records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from invoice_automation.app.constants import DEFAULT_INVOICE_TARGET_TYPE, InvoiceStatus


@dataclass(frozen=True)
class InvoiceRecordCreate:
    """Data needed to create a local invoice record."""

    ad: str
    soyad: str
    tc_kimlik_no: str
    tutar_usd: float
    batch_id: int | None = None
    aciklama: str | None = None
    fatura_tipi_hedef: str = DEFAULT_INVOICE_TARGET_TYPE
    kaynak_dosya: str | None = None
    kaynak_satir_no: int | None = None
    secili_mi: bool = False
    islem_durumu: InvoiceStatus = InvoiceStatus.PENDING


@dataclass(frozen=True)
class InvoiceRecord:
    """Persisted invoice record."""

    id: int
    batch_id: int | None
    ad: str
    soyad: str
    tc_kimlik_no: str
    tutar_usd: float
    aciklama: str | None
    fatura_tipi_hedef: str
    kaynak_dosya: str | None
    kaynak_satir_no: int | None
    secili_mi: bool
    islem_durumu: str
    portal_ref_no: str | None
    hata_kodu: str | None
    hata_mesaji: str | None
    olusturma_zamani: str
    guncelleme_zamani: str

    @classmethod
    def from_row(cls, row: Any) -> "InvoiceRecord":
        """Build an invoice record from a sqlite row."""

        return cls(
            id=row["id"],
            batch_id=row["batch_id"],
            ad=row["ad"],
            soyad=row["soyad"],
            tc_kimlik_no=row["tc_kimlik_no"],
            tutar_usd=row["tutar_usd"],
            aciklama=row["aciklama"],
            fatura_tipi_hedef=row["fatura_tipi_hedef"],
            kaynak_dosya=row["kaynak_dosya"],
            kaynak_satir_no=row["kaynak_satir_no"],
            secili_mi=bool(row["secili_mi"]),
            islem_durumu=row["islem_durumu"],
            portal_ref_no=row["portal_ref_no"],
            hata_kodu=row["hata_kodu"],
            hata_mesaji=row["hata_mesaji"],
            olusturma_zamani=row["olusturma_zamani"],
            guncelleme_zamani=row["guncelleme_zamani"],
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary."""

        return {
            "id": self.id,
            "batch_id": self.batch_id,
            "ad": self.ad,
            "soyad": self.soyad,
            "tc_kimlik_no": self.tc_kimlik_no,
            "tutar_usd": self.tutar_usd,
            "aciklama": self.aciklama,
            "fatura_tipi_hedef": self.fatura_tipi_hedef,
            "kaynak_dosya": self.kaynak_dosya,
            "kaynak_satir_no": self.kaynak_satir_no,
            "secili_mi": self.secili_mi,
            "islem_durumu": self.islem_durumu,
            "portal_ref_no": self.portal_ref_no,
            "hata_kodu": self.hata_kodu,
            "hata_mesaji": self.hata_mesaji,
            "olusturma_zamani": self.olusturma_zamani,
            "guncelleme_zamani": self.guncelleme_zamani,
        }


@dataclass(frozen=True)
class ImportBatchCreate:
    """Data needed to create an import/fatura period."""

    name: str
    source_file_name: str
    sheet_name: str | None = None
    status: str = "ACTIVE"
    is_archived: bool = False


@dataclass(frozen=True)
class ImportBatch:
    """Persisted import/fatura period."""

    id: int
    name: str
    source_file_name: str
    sheet_name: str | None
    created_at: str
    status: str
    is_archived: bool

    @classmethod
    def from_row(cls, row: Any) -> "ImportBatch":
        """Build an import batch from a sqlite row."""

        return cls(
            id=row["id"],
            name=row["name"],
            source_file_name=row["source_file_name"],
            sheet_name=row["sheet_name"],
            created_at=row["created_at"],
            status=row["status"],
            is_archived=bool(row["is_archived"]),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary."""

        return {
            "id": self.id,
            "name": self.name,
            "source_file_name": self.source_file_name,
            "sheet_name": self.sheet_name,
            "created_at": self.created_at,
            "status": self.status,
            "is_archived": self.is_archived,
        }


def utc_timestamp() -> str:
    """Return an ISO timestamp in UTC."""

    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
