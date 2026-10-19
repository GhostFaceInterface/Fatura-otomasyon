"""Application-wide constants and status values."""

from enum import StrEnum


class InvoiceStatus(StrEnum):
    """Supported lifecycle statuses for invoice records."""

    PENDING = "PENDING"
    SELECTED = "SELECTED"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESS_DRAFT_CREATED = "SUCCESS_DRAFT_CREATED"
    FAILED_INVALID_TCKN = "FAILED_INVALID_TCKN"
    FAILED_NAME_MISMATCH = "FAILED_NAME_MISMATCH"
    FAILED_TURMOB_SERVICE_ERROR = "FAILED_TURMOB_SERVICE_ERROR"
    SKIPPED_EFATURA_MUKELLEFI = "SKIPPED_EFATURA_MUKELLEFI"
    FAILED_PORTAL_TIMEOUT = "FAILED_PORTAL_TIMEOUT"
    FAILED_UNKNOWN = "FAILED_UNKNOWN"
    ABORTED_SESSION_LOST = "ABORTED_SESSION_LOST"
    NEEDS_REVIEW = "NEEDS_REVIEW"


DEFAULT_INVOICE_TARGET_TYPE = "earshiv"

REQUIRED_IMPORT_COLUMNS = ("ad", "soyad", "tc_kimlik_no", "tutar_usd")
OPTIONAL_IMPORT_COLUMNS = ("aciklama",)
SUPPORTED_IMPORT_EXTENSIONS = (".csv", ".xlsx", ".xls")
DEFAULT_IMPORT_BATCH_STATUS = "ACTIVE"

PORTAL_DIALOG_TITLES = ("Hata Oluştu", "Bilgi")
PORTAL_DIALOG_OK_BUTTON_NAME = "OK"
TURMOB_SERVICE_ERROR_PATTERN = "Servis hatası oluştu"
INVALID_TCKN_ERROR_PATTERN = "geçerli bir VKN/TCKN değeri değildir"
EFATURA_MUKELLEFI_ERROR_PATTERN = "e-Fatura Mükellefine e-Arşiv Fatura Kesilemez"
HARMLESS_PORTAL_INFO_PATTERNS = (
    "Fatura Tipi ISTISNA olarak değiştirilmiştir",
    "Fatura Tipi İSTİSNA olarak değiştirilmiştir",
)
EARCHIVE_DRAFTS_PATH = "/EArchive/Drafts"
EARCHIVE_DRAFTS_SUCCESS_TEXTS = (
    "Taslaklar",
    "E-Arşiv Taslaklar",
    "e-Arşiv Taslaklar",
)

BATCH_ELIGIBLE_STATUSES = (
    InvoiceStatus.PENDING,
    InvoiceStatus.SELECTED,
)
BATCH_CONTINUE_STATUSES = (
    InvoiceStatus.SUCCESS_DRAFT_CREATED,
    InvoiceStatus.FAILED_INVALID_TCKN,
    InvoiceStatus.FAILED_NAME_MISMATCH,
    InvoiceStatus.FAILED_TURMOB_SERVICE_ERROR,
    InvoiceStatus.SKIPPED_EFATURA_MUKELLEFI,
    InvoiceStatus.FAILED_PORTAL_TIMEOUT,
    InvoiceStatus.FAILED_UNKNOWN,
    InvoiceStatus.NEEDS_REVIEW,
)
BATCH_ABORT_STATUSES = (
    InvoiceStatus.ABORTED_SESSION_LOST,
)
# Statuses that may be consciously reset to PENDING by the operator. Every one of
# them is reached before "Taslak Kaydet" is confirmed as clicked, so a retry cannot
# create a duplicate draft. NEEDS_REVIEW is deliberately excluded.
RETRYABLE_STATUSES = (
    InvoiceStatus.FAILED_INVALID_TCKN,
    InvoiceStatus.FAILED_NAME_MISMATCH,
    InvoiceStatus.FAILED_TURMOB_SERVICE_ERROR,
    InvoiceStatus.FAILED_PORTAL_TIMEOUT,
    InvoiceStatus.FAILED_UNKNOWN,
    InvoiceStatus.ABORTED_SESSION_LOST,
)
STALE_IN_PROGRESS_ERROR_CODE = "StaleInProgressRecovered"
