"""Basic portal error detection hooks for draft creation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import logging

from invoice_automation.app.utils.exceptions import (
    DraftCreationError,
    EFaturaMukellefiError,
    InvalidTCKNError,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PortalErrorSnapshot:
    """Visible portal errors collected from known message containers."""

    messages: list[str]

    @property
    def combined_text(self) -> str:
        """Return all messages in one lower-case string for keyword matching."""

        return " ".join(self.messages).lower()


class PortalErrorDetector:
    """Detect customer and save errors without hard-wiring batch behavior."""

    error_selectors = (
        ".validation-summary-errors",
        ".field-validation-error",
        ".alert-danger",
        ".toast-message",
        "#toast-container",
        ".swal2-html-container",
    )
    invalid_tckn_keywords = ("tckn", "tc kimlik", "bulunamad", "gecersiz", "geçersiz")
    efatura_keywords = ("e-fatura", "efatura", "mukellef", "mükellef")

    def collect_errors(self, page: Any) -> PortalErrorSnapshot:
        """Collect visible text from known error containers."""

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

    def raise_if_portal_error(self, page: Any, stage: str) -> None:
        """Raise a typed exception if the portal exposes a known error."""

        snapshot = self.collect_errors(page)
        if not snapshot.messages:
            return

        combined = snapshot.combined_text
        logger.info("Portal error snapshot | stage=%s messages=%s", stage, snapshot.messages)

        if any(keyword in combined for keyword in self.efatura_keywords):
            raise EFaturaMukellefiError("; ".join(snapshot.messages))
        if any(keyword in combined for keyword in self.invalid_tckn_keywords):
            raise InvalidTCKNError("; ".join(snapshot.messages))
        raise DraftCreationError("; ".join(snapshot.messages))
