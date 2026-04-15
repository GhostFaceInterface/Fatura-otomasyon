"""Validation helpers for import files and invoice rows."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal, InvalidOperation
from typing import Any

from invoice_automation.app.constants import REQUIRED_IMPORT_COLUMNS
from invoice_automation.app.utils.exceptions import ImportValidationError


def validate_required_columns(columns: Iterable[str]) -> None:
    """Ensure the import file contains all required columns."""

    present_columns = set(columns)
    missing_columns = [column for column in REQUIRED_IMPORT_COLUMNS if column not in present_columns]
    if missing_columns:
        missing = ", ".join(missing_columns)
        required = ", ".join(REQUIRED_IMPORT_COLUMNS)
        raise ImportValidationError(
            f"Eksik kolonlar: {missing}. Gerekli kolonlar: {required}."
        )


def validate_tckn(value: Any) -> str:
    """Validate and normalize a TCKN value as an 11-digit string."""

    normalized = str(value).strip()
    if normalized.endswith(".0"):
        normalized = normalized[:-2]
    if not normalized.isdigit() or len(normalized) != 11:
        raise ValueError("TCKN 11 haneli ve sadece rakamlardan olmalidir.")
    return normalized


def validate_positive_usd_amount(value: Any) -> float:
    """Validate and normalize a positive USD amount."""

    normalized = str(value).strip().replace(",", ".")
    if not normalized:
        raise ValueError("tutar_usd bos olamaz.")
    try:
        amount = Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError("tutar_usd sayisal bir deger olmalidir.") from exc
    if amount <= 0:
        raise ValueError("tutar_usd pozitif olmalidir.")
    return float(amount)


def validate_import_row(row: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    """Validate one normalized import row."""

    errors: list[str] = []

    ad = str(row.get("ad", "")).strip()
    soyad = str(row.get("soyad", "")).strip()
    aciklama = str(row.get("aciklama", "")).strip()

    if not ad:
        errors.append("ad bos olamaz.")
    if not soyad:
        errors.append("soyad bos olamaz.")

    try:
        tc_kimlik_no = validate_tckn(row.get("tc_kimlik_no", ""))
    except ValueError as exc:
        errors.append(str(exc))
        tc_kimlik_no = ""

    try:
        tutar_usd = validate_positive_usd_amount(row.get("tutar_usd", ""))
    except ValueError as exc:
        errors.append(str(exc))
        tutar_usd = 0.0

    if errors:
        return None, errors

    return {
        "ad": ad,
        "soyad": soyad,
        "tc_kimlik_no": tc_kimlik_no,
        "tutar_usd": tutar_usd,
        "aciklama": aciklama,
    }, []
