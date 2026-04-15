"""Small retry helpers for portal interactions."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar
import logging
import time

T = TypeVar("T")

logger = logging.getLogger(__name__)


def retry_with_backoff(
    action: Callable[[], T],
    *,
    attempts: int,
    base_delay_ms: int,
    description: str,
    page: object | None = None,
    retry_exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> T:
    """Run an action with short increasing waits between failures."""

    normalized_attempts = max(1, attempts)
    last_error: BaseException | None = None

    for attempt in range(1, normalized_attempts + 1):
        try:
            return action()
        except retry_exceptions as exc:
            last_error = exc
            if attempt >= normalized_attempts:
                break

            delay_ms = max(0, base_delay_ms) * attempt
            logger.warning(
                "Retryable action failed | description=%s attempt=%s attempts=%s delay_ms=%s error=%s",
                description,
                attempt,
                normalized_attempts,
                delay_ms,
                exc,
            )
            _wait(delay_ms, page)

    assert last_error is not None
    raise last_error


def _wait(delay_ms: int, page: object | None) -> None:
    if delay_ms <= 0:
        return

    wait_for_timeout = getattr(page, "wait_for_timeout", None)
    if callable(wait_for_timeout):
        try:
            wait_for_timeout(delay_ms)
            return
        except Exception:
            logger.debug("Page based retry wait failed; falling back to sleep", exc_info=True)

    time.sleep(delay_ms / 1_000)
