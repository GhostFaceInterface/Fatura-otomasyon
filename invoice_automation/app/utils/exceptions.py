"""Custom exceptions used by the application."""


class InvoiceAutomationError(Exception):
    """Base exception for expected application errors."""


class ImportValidationError(InvoiceAutomationError):
    """Raised when an import file cannot be processed."""


class UnsupportedFileTypeError(ImportValidationError):
    """Raised when the uploaded file type is not supported."""
