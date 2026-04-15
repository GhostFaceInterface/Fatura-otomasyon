"""Portal navigation helpers for e-Arsiv draft creation."""

from __future__ import annotations

from typing import Any
import logging

from invoice_automation.app.automation.portal_selectors import PortalSelectors, portal_selectors
from invoice_automation.app.config import settings
from invoice_automation.app.utils.exceptions import ElementNotFoundError, PortalTimeoutError

logger = logging.getLogger(__name__)


class EArchiveNavigation:
    """Navigate from a ready portal session to the e-Arsiv create screen."""

    def __init__(
        self,
        selectors: PortalSelectors = portal_selectors,
        timeout_ms: int | None = None,
    ) -> None:
        self.selectors = selectors
        self.timeout_ms = timeout_ms or settings.playwright_timeout_ms

    def open_create_invoice_page(self, page: Any) -> None:
        """Open and verify the e-Arsiv create invoice page."""

        try:
            logger.info("e-Arsiv menusu aciliyor")
            page.get_by_role("link", name=self.selectors.earsiv_menu_link_name).click(
                timeout=self.timeout_ms
            )

            logger.info("e-Arsiv olustur sayfasi aciliyor")
            page.get_by_role("link", name=self.selectors.earsiv_create_link_name).click(
                timeout=self.timeout_ms
            )

            self.wait_until_create_form_ready(page)
        except PortalTimeoutError:
            raise
        except Exception as exc:
            raise PortalTimeoutError(f"e-Arsiv olustur sayfasi acilamadi: {exc}") from exc

    def wait_until_create_form_ready(self, page: Any) -> None:
        """Wait until the first stable field on the create form is visible."""

        try:
            page.locator(self.selectors.document_currency_selector).wait_for(
                state="visible",
                timeout=self.timeout_ms,
            )
        except Exception as exc:
            raise ElementNotFoundError(
                "e-Arsiv olustur formu yuklenmedi; para birimi alani gorunmedi."
            ) from exc

        logger.info("e-Arsiv olustur formu hazir")

    def open_next_create_invoice_page(self, page: Any) -> None:
        """Open a fresh create page after a draft save for later batch phases."""

        try:
            page.get_by_role("link", name=self.selectors.earsiv_create_link_name).click(
                timeout=self.timeout_ms
            )
            self.wait_until_create_form_ready(page)
        except Exception as exc:
            raise PortalTimeoutError(f"Yeni e-Arsiv olustur sayfasi acilamadi: {exc}") from exc
