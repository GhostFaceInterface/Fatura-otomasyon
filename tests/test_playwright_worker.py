import threading
from types import SimpleNamespace

import pytest

from invoice_automation.app.automation.playwright_worker import (
    PlaywrightWorker,
    on_playwright_thread,
    playwright_worker,
)
from invoice_automation.app.automation.session_manager import PortalSessionManager, PortalSessionStatus
from invoice_automation.app.utils.exceptions import PlaywrightWorkerBusyError, PortalSessionError


def test_decorated_calls_from_different_threads_share_one_worker_thread() -> None:
    seen: list[int] = []

    @on_playwright_thread
    def record_thread() -> int:
        seen.append(threading.get_ident())
        return threading.get_ident()

    caller_idents: list[int] = []

    def call_from_request_thread() -> None:
        caller_idents.append(threading.get_ident())
        record_thread()

    threads = [threading.Thread(target=call_from_request_thread) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    record_thread()

    assert len(seen) == 5
    assert set(seen) == {playwright_worker.thread_ident}
    assert playwright_worker.thread_ident not in caller_idents
    assert threading.get_ident() != playwright_worker.thread_ident


def test_nested_decorated_calls_run_inline_without_deadlock() -> None:
    @on_playwright_thread
    def inner() -> int:
        return threading.get_ident()

    @on_playwright_thread
    def outer() -> tuple[int, int]:
        return threading.get_ident(), inner()

    outer_ident, inner_ident = outer()

    assert outer_ident == inner_ident == playwright_worker.thread_ident


def test_worker_rejects_foreground_calls_while_background_job_runs() -> None:
    worker = PlaywrightWorker()
    release = threading.Event()
    started = threading.Event()

    def long_job() -> str:
        started.set()
        release.wait(timeout=5)
        return "done"

    future = worker.submit_background(long_job)
    assert started.wait(timeout=5)

    with pytest.raises(PlaywrightWorkerBusyError):
        worker.call(lambda: "should not run")
    with pytest.raises(PlaywrightWorkerBusyError):
        worker.submit_background(lambda: "second job")
    assert issubclass(PlaywrightWorkerBusyError, PortalSessionError)

    release.set()
    assert future.result(timeout=5) == "done"
    assert worker.background_active is False
    assert worker.call(lambda: "after") == "after"
    worker.shutdown()


class UnreachablePortalPage:
    url = "about:blank"

    def __init__(self) -> None:
        self.goto_threads: list[int] = []

    def goto(self, url: str, wait_until: str, timeout: int) -> None:
        self.goto_threads.append(threading.get_ident())
        raise RuntimeError("portal unreachable in tests")


class ThreadRecordingBrowserManager:
    def __init__(self) -> None:
        self.page = None
        self.start_threads: list[int] = []
        self.close_threads: list[int] = []

    def start(self):
        self.start_threads.append(threading.get_ident())
        self.page = UnreachablePortalPage()
        return self.page

    def close(self) -> None:
        self.close_threads.append(threading.get_ident())
        self.page = None


def test_session_manager_lifecycle_runs_on_worker_thread() -> None:
    browser_manager = ThreadRecordingBrowserManager()
    settings = SimpleNamespace(
        portal_login_url="https://portal.test/",
        portal_2fa_url="https://portal.test/User/VerificationUser",
        username="user",
        password="secret",
        playwright_timeout_ms=1_000,
    )
    manager = PortalSessionManager(browser_manager=browser_manager, app_settings=settings)

    with pytest.raises(PortalSessionError):
        manager.start_login()
    page = browser_manager.page
    state = manager.close()

    assert state.status == PortalSessionStatus.CLOSED
    assert browser_manager.start_threads == [playwright_worker.thread_ident]
    assert page.goto_threads == [playwright_worker.thread_ident]
    assert browser_manager.close_threads == [playwright_worker.thread_ident]
