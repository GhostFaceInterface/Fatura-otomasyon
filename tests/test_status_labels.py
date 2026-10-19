from invoice_automation.app.constants import STATUS_LABELS, InvoiceStatus, status_label, status_tone


def test_every_status_has_a_label() -> None:
    assert set(STATUS_LABELS) == set(InvoiceStatus)


def test_label_lookup_accepts_plain_strings() -> None:
    assert status_label("SUCCESS_DRAFT_CREATED") == "Taslak oluştu"
    assert status_tone("FAILED_INVALID_TCKN") == "danger"


def test_unknown_status_falls_back_to_code() -> None:
    assert status_label("SOMETHING_NEW") == "SOMETHING_NEW"
    assert status_tone("SOMETHING_NEW") == "neutral"
