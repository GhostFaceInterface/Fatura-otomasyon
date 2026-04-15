"""Custom exceptions used by the application."""


class InvoiceAutomationError(Exception):
    """Base exception for expected application errors."""


class ImportValidationError(InvoiceAutomationError):
    """Raised when an import file cannot be processed."""


class UnsupportedFileTypeError(ImportValidationError):
    """Raised when the uploaded file type is not supported."""


class PortalSessionError(InvoiceAutomationError):
    """Raised when the portal browser session cannot be established."""


class MissingPortalCredentialsError(PortalSessionError):
    """Raised when required portal credentials are not configured."""


class BrowserLaunchError(PortalSessionError):
    """Raised when Playwright cannot start a browser."""


class LoginFlowError(PortalSessionError):
    """Raised when the login form cannot be completed."""


class TwoFactorTimeoutError(PortalSessionError):
    """Raised when the 2FA screen cannot be reached or detected."""


class SessionNotReadyError(PortalSessionError):
    """Raised when login completed state cannot be verified."""
