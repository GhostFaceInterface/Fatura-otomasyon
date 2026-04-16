"""Keep the local workstation awake only while invoice batches run."""

from __future__ import annotations

from dataclasses import dataclass
from types import TracebackType
from typing import Self
import ctypes
import logging
import platform
import shutil
import subprocess

from invoice_automation.app.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SleepPreventionSettings:
    """Runtime sleep prevention options."""

    enabled: bool
    platform_name: str
    keep_display_awake: bool

    @classmethod
    def from_settings(cls) -> "SleepPreventionSettings":
        """Create sleep prevention settings from environment-backed config."""

        return cls(
            enabled=settings.sleep_prevention_enabled,
            platform_name=settings.sleep_prevention_platform,
            keep_display_awake=settings.sleep_prevention_keep_display_awake,
        )


class SleepPreventionGuard:
    """Context manager that blocks OS sleep for the lifetime of a batch run."""

    def __init__(self, config: SleepPreventionSettings | None = None) -> None:
        self.config = config or SleepPreventionSettings.from_settings()
        self._process: subprocess.Popen[bytes] | None = None
        self._windows_active = False
        self.active = False
        self.backend: str | None = None

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.stop()

    def start(self) -> None:
        """Start platform-specific sleep prevention if enabled."""

        if not self.config.enabled:
            logger.info("Sleep prevention disabled by config")
            return

        platform_name = self._resolve_platform(self.config.platform_name)
        try:
            if platform_name == "macos":
                self._start_macos()
            elif platform_name == "windows":
                self._start_windows()
            elif platform_name == "linux":
                self._start_linux()
            elif platform_name == "disabled":
                logger.info("Sleep prevention disabled by platform config")
            else:
                logger.warning("Sleep prevention unsupported platform | platform=%s", platform_name)
        except Exception:
            logger.exception("Sleep prevention could not be started | platform=%s", platform_name)

    def stop(self) -> None:
        """Stop any sleep prevention assertion started by this guard."""

        if self._process is not None:
            process = self._process
            self._process = None
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
            logger.info("Sleep prevention stopped | backend=%s", self.backend)

        if self._windows_active:
            self._restore_windows()

        self.active = False
        self.backend = None

    def _start_macos(self) -> None:
        caffeinate = shutil.which("caffeinate")
        if not caffeinate:
            logger.warning("Sleep prevention skipped; caffeinate command not found")
            return

        args = [caffeinate, "-i", "-m", "-s"]
        if self.config.keep_display_awake:
            args.append("-d")
        self._process = subprocess.Popen(args)
        self.active = True
        self.backend = "caffeinate"
        logger.info(
            "Sleep prevention started | backend=%s pid=%s keep_display_awake=%s",
            self.backend,
            self._process.pid,
            self.config.keep_display_awake,
        )

    def _start_linux(self) -> None:
        systemd_inhibit = shutil.which("systemd-inhibit")
        sleep = shutil.which("sleep")
        if not systemd_inhibit or not sleep:
            logger.warning(
                "Sleep prevention skipped; systemd-inhibit or sleep command not found"
            )
            return

        self._process = subprocess.Popen(
            [
                systemd_inhibit,
                "--what=sleep:idle",
                "--why=e-Arsiv invoice automation batch is running",
                "--mode=block",
                sleep,
                "infinity",
            ]
        )
        self.active = True
        self.backend = "systemd-inhibit"
        logger.info("Sleep prevention started | backend=%s pid=%s", self.backend, self._process.pid)

    def _start_windows(self) -> None:
        kernel32 = ctypes.windll.kernel32
        es_continuous = 0x80000000
        es_system_required = 0x00000001
        es_display_required = 0x00000002
        flags = es_continuous | es_system_required
        if self.config.keep_display_awake:
            flags |= es_display_required

        result = kernel32.SetThreadExecutionState(flags)
        if result == 0:
            logger.warning("Sleep prevention skipped; SetThreadExecutionState failed")
            return

        self._windows_active = True
        self.active = True
        self.backend = "SetThreadExecutionState"
        logger.info(
            "Sleep prevention started | backend=%s keep_display_awake=%s",
            self.backend,
            self.config.keep_display_awake,
        )

    def _restore_windows(self) -> None:
        try:
            kernel32 = ctypes.windll.kernel32
            es_continuous = 0x80000000
            kernel32.SetThreadExecutionState(es_continuous)
            logger.info("Sleep prevention stopped | backend=SetThreadExecutionState")
        except Exception:
            logger.exception("Sleep prevention Windows restore failed")
        finally:
            self._windows_active = False

    def _resolve_platform(self, configured_platform: str) -> str:
        normalized = configured_platform.strip().casefold()
        if normalized in {"", "auto"}:
            system_name = platform.system().casefold()
            if system_name == "darwin":
                return "macos"
            if system_name == "windows":
                return "windows"
            if system_name == "linux":
                return "linux"
            return system_name
        if normalized in {"darwin", "mac", "macos", "osx"}:
            return "macos"
        if normalized in {"win", "windows"}:
            return "windows"
        if normalized in {"linux"}:
            return "linux"
        if normalized in {"off", "false", "disabled", "none"}:
            return "disabled"
        return normalized
