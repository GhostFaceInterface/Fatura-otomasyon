from types import SimpleNamespace

import pytest

from invoice_automation.app.automation.session_manager import (
    PortalSessionManager,
    PortalSessionStatus,
)
from invoice_automation.app.utils.exceptions import MissingPortalCredentialsError


class FakeLocator:
    def __init__(self, page: "FakePage", locator_name: str) -> None:
        self.page = page
        self.locator_name = locator_name

    def fill(self, value: str) -> None:
        self.page.actions.append(("fill", self.locator_name, value))

    def click(self) -> None:
        self.page.actions.append(("click", self.locator_name))

    def wait_for(self, state: str = "visible", timeout: int = 0) -> None:
        self.page.actions.append(("wait_for", self.locator_name, state, timeout))
        if self.locator_name in self.page.wait_failures:
            raise RuntimeError(f"{self.locator_name} not visible")


class FakePage:
    def __init__(self) -> None:
        self.url = "about:blank"
        self.actions: list[tuple] = []
        self.wait_failures: set[str] = set()

    def goto(self, url: str, wait_until: str, timeout: int) -> None:
        self.url = url
        self.actions.append(("goto", url, wait_until, timeout))

    def wait_for_url(self, pattern: str, timeout: int) -> None:
        self.url = "https://portal.hizliteknoloji.com.tr/User/VerificationUser?verificationType=Mail"
        self.actions.append(("wait_for_url", pattern, timeout))

    def get_by_role(self, role: str, name: str) -> FakeLocator:
        return FakeLocator(self, f"role:{role}:{name}")

    def get_by_placeholder(self, placeholder: str) -> FakeLocator:
        return FakeLocator(self, f"placeholder:{placeholder}")

    def is_closed(self) -> bool:
        return False


class FakeBrowserManager:
    def __init__(self, page: FakePage) -> None:
        self._page = page
        self.closed = False

    @property
    def page(self) -> FakePage:
        return self._page

    def start(self) -> FakePage:
        return self._page

    def close(self) -> None:
        self.closed = True


def _settings(username: str = "user", password: str = "password") -> SimpleNamespace:
    return SimpleNamespace(
        portal_login_url="https://portal.hizliteknoloji.com.tr/",
        portal_2fa_url=(
            "https://portal.hizliteknoloji.com.tr/User/VerificationUser?verificationType=Mail"
        ),
        username=username,
        password=password,
        browser_type="chromium",
        playwright_headless=False,
        playwright_timeout_ms=30_000,
    )


def test_start_login_fills_credentials_and_waits_for_2fa() -> None:
    page = FakePage()
    manager = PortalSessionManager(FakeBrowserManager(page), _settings())

    state = manager.start_login()

    assert state.status == PortalSessionStatus.TWO_FACTOR_WAITING
    assert ("fill", "role:textbox:Kullanıcı Adı", "user") in page.actions
    assert ("fill", "role:textbox:Şifre", "password") in page.actions
    assert ("click", "role:button:Giriş") in page.actions
    assert any(action[0] == "wait_for_url" for action in page.actions)
    assert any(action[1] == "placeholder:Kod" for action in page.actions if action[0] == "wait_for")


def test_confirm_manual_2fa_marks_session_ready_when_earsiv_link_visible() -> None:
    page = FakePage()
    page.url = "https://portal.hizliteknoloji.com.tr/Dashboard"
    manager = PortalSessionManager(FakeBrowserManager(page), _settings())

    state = manager.confirm_manual_2fa_completed()

    assert state.status == PortalSessionStatus.READY
    assert ("wait_for", "role:link: e-Arşiv ", "visible", 30_000) in page.actions


def test_start_login_requires_credentials() -> None:
    manager = PortalSessionManager(FakeBrowserManager(FakePage()), _settings(username=""))

    with pytest.raises(MissingPortalCredentialsError):
        manager.start_login()

    assert manager.state.status == PortalSessionStatus.FAILED
