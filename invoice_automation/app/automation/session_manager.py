"""Portal login and manual 2FA session management."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
import logging
from time import monotonic

from invoice_automation.app.automation.browser_manager import BrowserManager
from invoice_automation.app.automation.portal_selectors import PortalSelectors, portal_selectors
from invoice_automation.app.config import settings
from invoice_automation.app.utils.exceptions import (
    LoginFlowError,
    MissingPortalCredentialsError,
    PortalSessionError,
    SessionNotReadyError,
    TwoFactorTimeoutError,
)

logger = logging.getLogger(__name__)


class PortalSessionStatus(StrEnum):
    """Observable session states for UI and API responses."""

    IDLE = "IDLE"
    BROWSER_STARTED = "BROWSER_STARTED"
    LOGIN_PAGE_OPENED = "LOGIN_PAGE_OPENED"
    LOGIN_FORM_FILLED = "LOGIN_FORM_FILLED"
    TWO_FACTOR_WAITING = "TWO_FACTOR_WAITING"
    READY = "READY"
    FAILED = "FAILED"
    CLOSED = "CLOSED"


@dataclass(frozen=True)
class PortalSessionState:
    """Current state of the browser login session."""

    status: PortalSessionStatus
    message: str
    current_url: str | None
    updated_at: str

    def to_dict(self) -> dict[str, str | None]:
        """Return a JSON-serializable state."""

        return {
            "status": self.status.value,
            "message": self.message,
            "current_url": self.current_url,
            "updated_at": self.updated_at,
        }


class PortalSessionManager:
    """Run the portal login flow and track the open browser session."""

    def __init__(
        self,
        browser_manager: BrowserManager | None = None,
        app_settings: Any = settings,
        selectors: PortalSelectors = portal_selectors,
    ) -> None:
        self.settings = app_settings
        self.selectors = selectors
        self.browser_manager = browser_manager or BrowserManager(app_settings)
        self._state = self._make_state(
            PortalSessionStatus.IDLE,
            "Session henuz baslatilmadi.",
            None,
        )

    @property
    def state(self) -> PortalSessionState:
        """Return the latest known session state."""

        page = self.browser_manager.page
        if page is None:
            return self._state
        return self._make_state(self._state.status, self._state.message, self._safe_current_url(page))

    def start_login(self) -> PortalSessionState:
        """Open the portal, fill credentials, and wait until the 2FA page."""

        self._ensure_credentials()
        page = self.browser_manager.start()
        self._set_state(PortalSessionStatus.BROWSER_STARTED, "Browser acildi.", page)

        try:
            page.goto(
                self.settings.portal_login_url,
                wait_until="domcontentloaded",
                timeout=self.settings.playwright_timeout_ms,
            )
            logger.info("Login sayfasi acildi | url=%s", self.settings.portal_login_url)
            self._set_state(PortalSessionStatus.LOGIN_PAGE_OPENED, "Login sayfasi acildi.", page)

            page.get_by_role("textbox", name=self.selectors.username_textbox_name).fill(
                self.settings.username
            )
            page.get_by_role("textbox", name=self.selectors.password_textbox_name).fill(
                self.settings.password
            )
            logger.info("Credential alanlari dolduruldu")
            self._set_state(
                PortalSessionStatus.LOGIN_FORM_FILLED,
                "Kullanici adi ve sifre dolduruldu.",
                page,
            )

            page.get_by_role("button", name=self.selectors.login_button_name).click()
            logger.info("Giris butonuna tiklandi")

            post_login_status = self._wait_for_post_login_state(page)
        except PortalSessionError:
            raise
        except Exception as exc:
            self._fail(f"Login akisi tamamlanamadi: {exc}", page)
            raise LoginFlowError(f"Login akisi tamamlanamadi: {exc}") from exc

        if post_login_status == PortalSessionStatus.READY:
            self._set_state(PortalSessionStatus.READY, "Login tamamlandi, session hazir.", page)
            logger.info("Session 2FA olmadan hazir | url=%s", self._safe_current_url(page))
            return self._state

        self._set_state(
            PortalSessionStatus.TWO_FACTOR_WAITING,
            "2FA bekleniyor. Acik browser uzerinden mail kodunu manuel girip dogrulayin.",
            page,
        )
        logger.info("2FA tamamlanmasi bekleniyor")
        return self._state

    def confirm_manual_2fa_completed(self) -> PortalSessionState:
        """Wait until the manually completed 2FA flow results in a ready session."""

        page = self.browser_manager.page
        if page is None:
            self._fail("Aktif browser session bulunamadi.", None)
            raise SessionNotReadyError("Aktif browser session bulunamadi.")

        try:
            self._wait_for_session_ready(page)
        except PortalSessionError:
            raise
        except Exception as exc:
            self._fail(f"Session hazir kontrolu basarisiz: {exc}", page)
            raise SessionNotReadyError(f"Session hazir kontrolu basarisiz: {exc}") from exc

        self._set_state(PortalSessionStatus.READY, "2FA tamamlandi, session hazir.", page)
        logger.info("Session hazir | url=%s", self._safe_current_url(page))
        return self._state

    def close(self) -> PortalSessionState:
        """Close the active browser session."""

        self.browser_manager.close()
        self._set_state(PortalSessionStatus.CLOSED, "Browser session kapatildi.", None)
        return self._state

    def _ensure_credentials(self) -> None:
        missing_fields = []
        if not self.settings.portal_login_url:
            missing_fields.append("PORTAL_LOGIN_URL")
        if not self.settings.portal_2fa_url:
            missing_fields.append("PORTAL_2FA_URL")
        if not self.settings.username:
            missing_fields.append("PORTAL_USERNAME")
        if not self.settings.password:
            missing_fields.append("PORTAL_PASSWORD")

        if missing_fields:
            message = "Eksik portal config alanlari: " + ", ".join(missing_fields)
            self._fail(message, self.browser_manager.page)
            raise MissingPortalCredentialsError(message)

    def _wait_for_post_login_state(self, page: Any) -> PortalSessionStatus:
        """Detect whether login led to 2FA or directly to a ready session."""

        deadline = monotonic() + (self.settings.playwright_timeout_ms / 1_000)
        while monotonic() < deadline:
            current_url = self._safe_current_url(page) or ""
            if self.selectors.verification_url_marker in current_url or self._is_two_factor_code_visible(page):
                if not self._is_two_factor_code_visible(page):
                    self._fail("2FA kod alani gorunur degil.", page)
                    raise TwoFactorTimeoutError("2FA kod alani gorunur degil.")
                logger.info("2FA sayfasi algilandi | url=%s", current_url)
                return PortalSessionStatus.TWO_FACTOR_WAITING

            if self._looks_logged_in_by_url(current_url) or self._is_session_ready_signal_visible(page):
                logger.info("Login sonrasi session ready sinyali algilandi | url=%s", current_url)
                return PortalSessionStatus.READY

            try:
                page.wait_for_timeout(500)
            except Exception:
                break

        self._fail("Login sonrasi 2FA veya session ready sinyali algilanamadi.", page)
        raise TwoFactorTimeoutError("Login sonrasi 2FA veya session ready sinyali algilanamadi.")

    def _is_two_factor_code_visible(self, page: Any) -> bool:
        try:
            page.get_by_placeholder(self.selectors.two_factor_code_placeholder).wait_for(
                state="visible",
                timeout=2_000,
            )
            return True
        except Exception:
            return False

    def _wait_for_session_ready(self, page: Any) -> None:
        if self._looks_logged_in_by_url(self._safe_current_url(page) or ""):
            return
        if self._is_session_ready_signal_visible(page, timeout_ms=self.settings.playwright_timeout_ms):
            return
        self._fail("Session hazir degil; e-Arsiv menu linki gorunmedi.", page)
        raise SessionNotReadyError("Session hazir degil; e-Arsiv menu linki gorunmedi.")

    def _is_session_ready_signal_visible(self, page: Any, timeout_ms: int = 500) -> bool:
        try:
            page.get_by_role("link", name=self.selectors.earsiv_menu_link_name).wait_for(
                state="visible",
                timeout=timeout_ms,
            )
            return True
        except Exception:
            return False

    def _looks_logged_in_by_url(self, current_url: str) -> bool:
        if not current_url:
            return False
        if self.selectors.home_index_url_marker in current_url:
            return True
        return (
            self.selectors.verification_url_marker not in current_url
            and current_url.rstrip("/") != self.settings.portal_login_url.rstrip("/")
        )

    def _safe_current_url(self, page: Any | None) -> str | None:
        if page is None:
            return None
        try:
            return str(page.url)
        except Exception:
            return None

    def _set_state(
        self,
        status: PortalSessionStatus,
        message: str,
        page: Any | None,
    ) -> None:
        self._state = self._make_state(status, message, self._safe_current_url(page))

    def _fail(self, message: str, page: Any | None) -> None:
        logger.error(message)
        self._set_state(PortalSessionStatus.FAILED, message, page)

    def _make_state(
        self,
        status: PortalSessionStatus,
        message: str,
        current_url: str | None,
    ) -> PortalSessionState:
        return PortalSessionState(
            status=status,
            message=message,
            current_url=current_url,
            updated_at=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        )


portal_session_manager = PortalSessionManager()
