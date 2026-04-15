import pytest

from invoice_automation.app.services.validation_service import (
    validate_import_row,
    validate_positive_usd_amount,
    validate_required_columns,
    validate_tckn,
)
from invoice_automation.app.utils.exceptions import ImportValidationError


def test_validate_required_columns_accepts_minimum_columns() -> None:
    validate_required_columns(["ad", "soyad", "tc_kimlik_no", "tutar_usd", "aciklama"])


def test_validate_required_columns_rejects_missing_columns() -> None:
    with pytest.raises(ImportValidationError):
        validate_required_columns(["ad", "soyad", "tc_kimlik_no"])


def test_validate_tckn_accepts_11_digit_value() -> None:
    assert validate_tckn("12345678901") == "12345678901"


@pytest.mark.parametrize("value", ["", "123", "1234567890a", "123456789012"])
def test_validate_tckn_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        validate_tckn(value)


def test_validate_positive_usd_amount_accepts_positive_number() -> None:
    assert validate_positive_usd_amount("1250.50") == 1250.50


@pytest.mark.parametrize("value", ["", "abc", "0", "-10"])
def test_validate_positive_usd_amount_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        validate_positive_usd_amount(value)


def test_validate_import_row_returns_errors_without_crashing() -> None:
    validated, errors = validate_import_row(
        {
            "ad": "",
            "soyad": "Yilmaz",
            "tc_kimlik_no": "bad",
            "tutar_usd": "-5",
            "aciklama": "Test",
        }
    )

    assert validated is None
    assert len(errors) == 3
