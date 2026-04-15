"""Runtime configuration loaded from environment variables."""

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")


def _bool_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return int(raw_value)


def _optional_env(name: str) -> str | None:
    raw_value = os.getenv(name)
    if raw_value is None:
        return None
    value = raw_value.strip()
    return value or None


def _playwright_timeout_ms() -> int:
    if os.getenv("PLAYWRIGHT_TIMEOUT_MS"):
        return _int_env("PLAYWRIGHT_TIMEOUT_MS", 30_000)
    return _int_env("TIMEOUT_SECONDS", 30) * 1_000


@dataclass(frozen=True)
class Settings:
    """Typed application settings."""

    app_name: str = os.getenv("APP_NAME", "e-Arsiv Fatura Otomasyonu")
    host: str = os.getenv("APP_HOST", "127.0.0.1")
    port: int = int(os.getenv("APP_PORT", "8000"))
    debug: bool = _bool_env("APP_DEBUG", False)

    database_path: Path = Path(
        os.getenv("DATABASE_PATH", str(ROOT_DIR / "data" / "invoice_automation.sqlite3"))
    )
    log_file_path: Path = Path(os.getenv("LOG_FILE_PATH", str(ROOT_DIR / "data" / "logs" / "app.log")))
    import_dir: Path = Path(os.getenv("IMPORT_DIR", str(ROOT_DIR / "data" / "imports")))

    portal_login_url: str = os.getenv("PORTAL_LOGIN_URL", "https://portal.hizliteknoloji.com.tr/")
    portal_new_invoice_url: str = os.getenv("PORTAL_NEW_INVOICE_URL", "")
    portal_2fa_url: str = os.getenv(
        "PORTAL_2FA_URL",
        "https://portal.hizliteknoloji.com.tr/User/VerificationUser?verificationType=Mail",
    )
    username: str = os.getenv("PORTAL_USERNAME", "")
    password: str = os.getenv("PORTAL_PASSWORD", "")
    browser_type: str = os.getenv("BROWSER_TYPE", "chromium")
    headless: bool = _bool_env("HEADLESS", False)
    playwright_headless: bool = _bool_env("PLAYWRIGHT_HEADLESS", _bool_env("HEADLESS", False))
    playwright_timeout_ms: int = _playwright_timeout_ms()
    timeout_seconds: int = int(os.getenv("TIMEOUT_SECONDS", "30"))
    retry_count: int = int(os.getenv("RETRY_COUNT", "2"))

    mal_hizmet_adi: str = os.getenv("MAL_HIZMET_ADI", "YURT DIŞI KONAKLAMA BEDELİ")
    miktar: str = os.getenv("MIKTAR", "1")
    kdv_orani: str = os.getenv("KDV_ORANI", "0")
    istisna_kodu: str = os.getenv("ISTISNA_KODU", "302.11")
    istisna_target_text: str = os.getenv(
        "ISTISNA_TARGET_TEXT",
        "302-11/1-a Hizmet ihracatı",
    )
    istisna_option_value: str | None = _optional_env("ISTISNA_OPTION_VALUE")
    para_birimi: str = os.getenv("PARA_BIRIMI", "USD")
    kur_tipi: str = os.getenv("KUR_TIPI", "Dolar")
    default_il: str = os.getenv("DEFAULT_IL", "**")
    default_ilce: str = os.getenv("DEFAULT_ILCE", "**")
    draft_mode: bool = _bool_env("DRAFT_MODE", True)


settings = Settings()


def ensure_runtime_directories() -> None:
    """Create runtime directories needed by the application."""

    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    settings.log_file_path.parent.mkdir(parents=True, exist_ok=True)
    settings.import_dir.mkdir(parents=True, exist_ok=True)
