"""Portal dialog and validation error detection for draft creation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import logging
import re
import unicodedata

from invoice_automation.app.constants import (
    EFATURA_MUKELLEFI_ERROR_PATTERN,
    HARMLESS_PORTAL_INFO_PATTERNS,
    INVALID_TCKN_ERROR_PATTERN,
    PORTAL_DIALOG_OK_BUTTON_NAME,
    PORTAL_DIALOG_TITLES,
    TURMOB_SERVICE_ERROR_PATTERN,
)
from invoice_automation.app.utils.exceptions import (
    DraftCreationError,
    EFaturaMukellefiError,
    InvalidTCKNError,
    TurmobServiceError,
    UnknownPortalError,
)
from invoice_automation.app.utils.screenshots import capture_error_screenshot

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PortalDialogSnapshot:
    """Detected modal dialog state."""

    title: str
    message: str
    stage: str
    screenshot_path: str | None = None

    @property
    def combined_text(self) -> str:
        """Return title and message as one lower-case string."""

        return normalize_portal_text(f"{self.title} {self.message}")

    @property
    def normalized_title(self) -> str:
        """Return normalized dialog title."""

        return normalize_portal_text(self.title)

    @property
    def normalized_message(self) -> str:
        """Return normalized dialog message."""

        return normalize_portal_text(self.message)


@dataclass(frozen=True)
class PortalErrorSnapshot:
    """Visible non-dialog portal errors collected from known message containers."""

    messages: list[str]

    @property
    def combined_text(self) -> str:
        """Return all messages in one lower-case string for keyword matching."""

        return normalize_portal_text(" ".join(self.messages))


def normalize_portal_text(text: str) -> str:
    """Normalize portal text for trim/case-insensitive matching."""

    casefolded = str(text).casefold()
    decomposed = unicodedata.normalize("NFKD", casefolded)
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    turkish_normalized = without_marks.replace("ı", "i")
    return re.sub(r"\s+", " ", turkish_normalized).strip()


class PortalErrorDetector:
    """Detect and classify portal errors after critical actions."""

    error_selectors = (
        ".validation-summary-errors",
        ".field-validation-error",
        ".alert-danger",
        ".toast-message",
        "#toast-container",
        ".swal2-html-container",
    )

    def raise_if_portal_error(
        self,
        page: Any,
        stage: str,
        record_id: int | None = None,
    ) -> None:
        """Raise a typed exception when a dialog or visible error exists."""

        dialog = self.detect_dialog(page, stage=stage, record_id=record_id)
        if dialog is not None:
            self._close_dialog(page, dialog)
            if self._is_harmless_dialog(dialog):
                logger.info(
                    "Portal bilgi dialogu hata sayilmadan gecildi | stage=%s title=%s message=%s normalized_title=%s normalized_message=%s",
                    stage,
                    dialog.title,
                    dialog.message,
                    dialog.normalized_title,
                    dialog.normalized_message,
                )
                return
            self._raise_for_dialog(dialog)

        snapshot = self.collect_inline_errors(page)
        if not snapshot.messages:
            return

        actionable_messages = [
            message for message in snapshot.messages if not self._is_harmless_text(message)
        ]
        if not actionable_messages:
            logger.info(
                "Portal inline bilgi mesaji hata sayilmadan gecildi | stage=%s messages=%s",
                stage,
                snapshot.messages,
            )
            return

        logger.info("Portal inline error snapshot | stage=%s messages=%s", stage, snapshot.messages)
        self._raise_for_text("; ".join(actionable_messages), stage=stage, screenshot_path=None)

    def detect_dialog(
        self,
        page: Any,
        stage: str,
        record_id: int | None = None,
        timeout_ms: int = 1_500,
    ) -> PortalDialogSnapshot | None:
        """Return the first known visible SweetAlert-style dialog."""

        for title in PORTAL_DIALOG_TITLES:
            try:
                dialog = page.get_by_role("dialog", name=title)
                dialog.wait_for(state="visible", timeout=timeout_ms)
                message = self._read_dialog_message(dialog)
                screenshot_path = (
                    capture_error_screenshot(page, record_id=record_id, stage=stage)
                    if record_id is not None
                    else None
                )
                snapshot = PortalDialogSnapshot(
                    title=title,
                    message=message,
                    stage=stage,
                    screenshot_path=screenshot_path,
                )
                logger.info(
                    "Portal dialog algilandi | stage=%s title=%s message=%s normalized_title=%s normalized_message=%s screenshot=%s",
                    stage,
                    title,
                    message,
                    snapshot.normalized_title,
                    snapshot.normalized_message,
                    screenshot_path,
                )
                return snapshot
            except Exception:
                continue
        return None

    def collect_inline_errors(self, page: Any) -> PortalErrorSnapshot:
        """Collect visible text from known non-dialog error containers."""

        messages: list[str] = []
        for selector in self.error_selectors:
            try:
                locator = page.locator(selector)
                for text in locator.all_text_contents():
                    normalized = " ".join(str(text).split())
                    if normalized:
                        messages.append(normalized)
            except Exception:
                continue
        return PortalErrorSnapshot(messages=messages)

    def _read_dialog_message(self, dialog: Any) -> str:
        try:
            text = dialog.inner_text(timeout=1_000)
        except Exception:
            try:
                text = dialog.text_content(timeout=1_000) or ""
            except Exception:
                text = ""
        return " ".join(str(text).split())

    def _close_dialog(self, page: Any, dialog: PortalDialogSnapshot) -> None:
        try:
            page.get_by_role("button", name=PORTAL_DIALOG_OK_BUTTON_NAME).click(timeout=2_000)
            self._wait_until_dialog_closed(page, dialog)
            logger.info(
                "Portal dialog OK ile kapatildi | stage=%s title=%s normalized_title=%s",
                dialog.stage,
                dialog.title,
                dialog.normalized_title,
            )
        except Exception:
            logger.exception(
                "Portal dialog kapatilamadi | stage=%s title=%s",
                dialog.stage,
                dialog.title,
            )

    def _wait_until_dialog_closed(self, page: Any, dialog: PortalDialogSnapshot) -> None:
        try:
            page.get_by_role("dialog", name=dialog.title).wait_for(state="hidden", timeout=2_000)
            return
        except Exception:
            pass

        try:
            page.wait_for_timeout(300)
        except Exception:
            logger.debug("Dialog kapanisi sonrasi stabilizasyon beklemesi basarisiz", exc_info=True)

    def _raise_for_dialog(self, dialog: PortalDialogSnapshot) -> None:
        self._raise_for_text(
            dialog.message,
            stage=dialog.stage,
            screenshot_path=dialog.screenshot_path,
        )

    def _is_harmless_dialog(self, dialog: PortalDialogSnapshot) -> bool:
        return self._is_harmless_text(dialog.message)

    def _is_harmless_text(self, text: str) -> bool:
        normalized_message = normalize_portal_text(text)
        return any(
            normalize_portal_text(pattern) in normalized_message
            for pattern in HARMLESS_PORTAL_INFO_PATTERNS
        )

    def _raise_for_text(
        self,
        text: str,
        stage: str,
        screenshot_path: str | None,
    ) -> None:
        normalized = normalize_portal_text(text)
        if normalize_portal_text(TURMOB_SERVICE_ERROR_PATTERN) in normalized:
            raise TurmobServiceError(text, stage=stage, screenshot_path=screenshot_path)
        if normalize_portal_text(INVALID_TCKN_ERROR_PATTERN) in normalized:
            raise InvalidTCKNError(text, stage=stage, screenshot_path=screenshot_path)
        if normalize_portal_text(EFATURA_MUKELLEFI_ERROR_PATTERN) in normalized:
            raise EFaturaMukellefiError(text, stage=stage, screenshot_path=screenshot_path)
        if text:
            raise UnknownPortalError(text, stage=stage, screenshot_path=screenshot_path)
        raise DraftCreationError("Portal hatasi algilandi ancak mesaj okunamadi.", stage=stage)
