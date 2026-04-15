"""Screenshot helpers for portal automation failures."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
import logging
import re

from invoice_automation.app.config import settings

logger = logging.getLogger(__name__)


def capture_error_screenshot(
    page: Any,
    record_id: int,
    stage: str,
    screenshot_dir: Path | None = None,
) -> str | None:
    """Capture a full-page screenshot for an automation failure."""

    directory = screenshot_dir or settings.screenshot_dir
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    safe_stage = re.sub(r"[^a-zA-Z0-9_-]+", "_", stage).strip("_") or "unknown"
    screenshot_path = directory / f"record_{record_id}_{safe_stage}_{timestamp}.png"

    try:
        page.screenshot(path=str(screenshot_path), full_page=True)
        logger.info(
            "Hata screenshot alindi | record_id=%s stage=%s path=%s",
            record_id,
            stage,
            screenshot_path,
        )
        return str(screenshot_path)
    except Exception:
        logger.exception("Hata screenshot alinamadi | record_id=%s stage=%s", record_id, stage)
        return None
