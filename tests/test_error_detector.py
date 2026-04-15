from pathlib import Path

import pytest

from invoice_automation.app.automation.error_detector import PortalErrorDetector
from invoice_automation.app.utils.exceptions import (
    EFaturaMukellefiError,
    InvalidTCKNError,
    TurmobServiceError,
)


class FakeRoleLocator:
    def __init__(self, page: "FakeDialogPage", role: str, name: str) -> None:
        self.page = page
        self.role = role
        self.name = name

    def wait_for(self, state: str = "visible", timeout: int = 0) -> None:
        if self.role == "dialog" and self.name == self.page.dialog_title and state == "visible":
            self.page.actions.append(("wait_for_dialog", self.name, state, timeout))
            return
        if self.role == "dialog" and self.name == self.page.dialog_title and state == "hidden":
            self.page.actions.append(("wait_for_dialog", self.name, state, timeout))
            return
        raise RuntimeError(f"{self.role}:{self.name} not visible")

    def inner_text(self, timeout: int = 0) -> str:
        return f"{self.page.dialog_title}\n{self.page.dialog_message}\nOK"

    def text_content(self, timeout: int = 0) -> str:
        return self.inner_text(timeout=timeout)

    def click(self, timeout: int = 0) -> None:
        self.page.actions.append(("click", self.role, self.name, timeout))
        if self.role == "button" and self.name == "OK":
            self.page.ok_clicked = True


class FakeEmptyLocator:
    def all_text_contents(self) -> list[str]:
        return []


class FakeDialogPage:
    def __init__(self, title: str, message: str, screenshot_dir: Path) -> None:
        self.dialog_title = title
        self.dialog_message = message
        self.screenshot_dir = screenshot_dir
        self.ok_clicked = False
        self.actions: list[tuple] = []

    def get_by_role(self, role: str, name: str) -> FakeRoleLocator:
        return FakeRoleLocator(self, role, name)

    def locator(self, selector: str) -> FakeEmptyLocator:
        return FakeEmptyLocator()

    def screenshot(self, path: str, full_page: bool = True) -> None:
        Path(path).write_bytes(b"fake screenshot")
        self.actions.append(("screenshot", path, full_page))

    def wait_for_timeout(self, timeout_ms: int) -> None:
        self.actions.append(("wait_for_timeout", timeout_ms))


def test_detector_maps_turmob_service_dialog(tmp_path: Path) -> None:
    page = FakeDialogPage("Hata Oluştu", "Servis hatası oluştu !", tmp_path)

    with pytest.raises(TurmobServiceError) as exc_info:
        PortalErrorDetector().raise_if_portal_error(page, stage="turmob_lookup", record_id=7)

    assert page.ok_clicked is True
    assert exc_info.value.stage == "turmob_lookup"
    assert exc_info.value.screenshot_path is not None
    assert ("wait_for_dialog", "Hata Oluştu", "hidden", 2_000) in page.actions


def test_detector_normalizes_dialog_text_for_matching(tmp_path: Path) -> None:
    page = FakeDialogPage("Hata Oluştu", "  SERVİS   HATASI   OLUŞTU !  ", tmp_path)

    with pytest.raises(TurmobServiceError):
        PortalErrorDetector().raise_if_portal_error(page, stage="turmob_lookup", record_id=10)

    assert page.ok_clicked is True


def test_detector_maps_invalid_tckn_dialog(tmp_path: Path) -> None:
    page = FakeDialogPage(
        "Hata Oluştu",
        "123 değeri geçerli bir VKN/TCKN değeri değildir.",
        tmp_path,
    )

    with pytest.raises(InvalidTCKNError):
        PortalErrorDetector().raise_if_portal_error(page, stage="turmob_lookup", record_id=8)

    assert page.ok_clicked is True


def test_detector_maps_efatura_dialog(tmp_path: Path) -> None:
    page = FakeDialogPage(
        "Bilgi",
        "Hata :e-Fatura Mükellefine e-Arşiv Fatura Kesilemez!",
        tmp_path,
    )

    with pytest.raises(EFaturaMukellefiError):
        PortalErrorDetector().raise_if_portal_error(page, stage="save_draft", record_id=9)

    assert page.ok_clicked is True
