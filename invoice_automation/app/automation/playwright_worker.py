"""Single dedicated thread for every sync Playwright call.

Sync Playwright objects are bound to the thread that created them. FastAPI runs
``def`` routes on a threadpool, so two requests may land on different threads.
Every Playwright-touching entry point is therefore routed through this worker,
which owns exactly one long-lived thread.
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from functools import wraps
from typing import Any, Callable, TypeVar
import logging
import threading

from invoice_automation.app.utils.exceptions import PlaywrightWorkerBusyError

logger = logging.getLogger(__name__)

T = TypeVar("T")

WORKER_THREAD_NAME = "playwright-worker"


class PlaywrightWorker:
    """Serialize Playwright work onto one persistent thread."""

    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=WORKER_THREAD_NAME)
        self._thread_ident: int | None = None
        self._background_active = threading.Event()
        self._submit_lock = threading.Lock()
        # Pin the worker thread id up front so is_worker_thread() is reliable.
        self._executor.submit(self._capture_thread_ident).result()

    def _capture_thread_ident(self) -> None:
        self._thread_ident = threading.get_ident()

    @property
    def thread_ident(self) -> int | None:
        """Return the worker thread identifier."""

        return self._thread_ident

    def is_worker_thread(self) -> bool:
        """Return True when the caller already runs on the worker thread."""

        return threading.get_ident() == self._thread_ident

    @property
    def background_active(self) -> bool:
        """Return True while a long-running background job owns the worker."""

        return self._background_active.is_set()

    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Run ``func`` on the worker thread and wait for its result.

        Calls made from the worker thread itself run inline, so decorated methods
        may call each other freely. Calls from other threads are rejected while a
        background job (batch) owns the browser instead of blocking for its whole
        duration.
        """

        if self.is_worker_thread():
            return func(*args, **kwargs)
        with self._submit_lock:
            if self.background_active:
                raise PlaywrightWorkerBusyError(
                    "Toplu taslak islemi devam ediyor. Once islemin bitmesini bekleyin veya durdurun."
                )
            future = self._executor.submit(func, *args, **kwargs)
        return future.result()

    def submit_background(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> Future[T]:
        """Queue a long-running job; other callers are rejected until it finishes."""

        def _run() -> T:
            try:
                return func(*args, **kwargs)
            finally:
                self._background_active.clear()

        with self._submit_lock:
            if self.background_active:
                raise PlaywrightWorkerBusyError("Playwright worker zaten bir arka plan isi calistiriyor.")
            self._background_active.set()
            try:
                return self._executor.submit(_run)
            except Exception:
                self._background_active.clear()
                raise

    def shutdown(self) -> None:
        """Stop accepting work; pending queued calls are cancelled."""

        self._executor.shutdown(wait=False, cancel_futures=True)


playwright_worker = PlaywrightWorker()


def on_playwright_thread(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator that routes a function or method through ``playwright_worker``."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        return playwright_worker.call(func, *args, **kwargs)

    return wrapper
