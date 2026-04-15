"""Application-wide constants and status values."""

from enum import StrEnum


class InvoiceStatus(StrEnum):
    """Supported lifecycle statuses for invoice records."""

    PENDING = "PENDING"
    SELECTED = "SELECTED"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESS_DRAFT_CREATED = "SUCCESS_DRAFT_CREATED"
    FAILED_INVALID_TCKN = "FAILED_INVALID_TCKN"
    SKIPPED_EFATURA_MUKELLEFI = "SKIPPED_EFATURA_MUKELLEFI"
    FAILED_PORTAL_TIMEOUT = "FAILED_PORTAL_TIMEOUT"
    FAILED_UNKNOWN = "FAILED_UNKNOWN"
    ABORTED_SESSION_LOST = "ABORTED_SESSION_LOST"


DEFAULT_INVOICE_TARGET_TYPE = "earshiv"

REQUIRED_IMPORT_COLUMNS = ("ad", "soyad", "tc_kimlik_no", "tutar_usd", "aciklama")
SUPPORTED_IMPORT_EXTENSIONS = (".csv", ".xlsx", ".xls")
