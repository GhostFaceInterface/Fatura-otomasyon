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


class DraftAutomationError(InvoiceAutomationError):
    """Base exception for draft invoice automation errors."""

    def __init__(
        self,
        message: str,
        *,
        stage: str | None = None,
        screenshot_path: str | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.screenshot_path = screenshot_path


class InvalidTCKNError(DraftAutomationError):
    """Raised when portal customer lookup rejects the TCKN."""


class TurmobServiceError(DraftAutomationError):
    """Raised when Turmob lookup returns a portal service error."""


class EFaturaMukellefiError(DraftAutomationError):
    """Raised when the customer cannot be processed as e-Arsiv."""


class PortalTimeoutError(DraftAutomationError):
    """Raised when a portal interaction times out."""


class ElementNotFoundError(DraftAutomationError):
    """Raised when an expected portal element cannot be found."""


class SessionLostError(DraftAutomationError):
    """Raised when the logged-in portal session is not usable."""


class DraftCreationError(DraftAutomationError):
    """Raised when draft creation fails for an unknown portal reason."""


class UnknownPortalError(DraftAutomationError):
    """Raised when an unclassified portal dialog or error appears."""
