"""Playwright browser lifecycle management."""

from __future__ import annotations

from typing import Any
import logging

from invoice_automation.app.config import settings
from invoice_automation.app.utils.exceptions import BrowserLaunchError

logger = logging.getLogger(__name__)


class BrowserManager:
    """Start, reuse, and close a Playwright browser session."""

    def __init__(self, app_settings: Any = settings) -> None:
        self.settings = app_settings
        self._playwright: Any | None = None
        self._browser: Any | None = None
        self._context: Any | None = None
        self._page: Any | None = None

    @property
    def page(self) -> Any | None:
        """Return the active page if one exists."""

        if self._page is None:
            return None
        if hasattr(self._page, "is_closed") and self._page.is_closed():
            return None
        return self._page

    def start(self) -> Any:
        """Start a headful browser context and return the active page."""

        existing_page = self.page
        if existing_page is not None:
            logger.info("Browser already running; reusing existing page")
            return existing_page

        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise BrowserLaunchError(
                "Playwright kurulu degil. `pip install -r requirements.txt` ve "
                "`playwright install chromium` komutlarini calistirin."
            ) from exc

        try:
            self._playwright = sync_playwright().start()
            browser_launcher = getattr(self._playwright, self.settings.browser_type)
            self._browser = browser_launcher.launch(headless=self.settings.playwright_headless)
            self._context = self._browser.new_context()
            self._context.set_default_timeout(self.settings.playwright_timeout_ms)
            self._page = self._context.new_page()
            self._page.set_default_timeout(self.settings.playwright_timeout_ms)
        except Exception as exc:
            self.close()
            raise BrowserLaunchError(f"Browser baslatilamadi: {exc}") from exc

        logger.info(
            "Browser baslatildi | type=%s headless=%s timeout_ms=%s",
            self.settings.browser_type,
            self.settings.playwright_headless,
            self.settings.playwright_timeout_ms,
        )
        return self._page

    def close(self) -> None:
        """Close page, context, browser, and Playwright runtime."""

        for resource_name, resource in (
            ("context", self._context),
            ("browser", self._browser),
            ("playwright", self._playwright),
        ):
            if resource is None:
                continue
            try:
                if resource_name == "playwright":
                    resource.stop()
                else:
                    resource.close()
            except Exception:
                logger.exception("Playwright %s kapatilirken hata olustu", resource_name)

        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None
        logger.info("Browser session kapatildi")
