from invoice_automation.app.constants import STATUS_LABELS, InvoiceStatus, status_label, status_tone


def test_every_status_has_a_label() -> None:
    assert set(STATUS_LABELS) == set(InvoiceStatus)


def test_label_lookup_accepts_plain_strings() -> None:
    assert status_label("SUCCESS_DRAFT_CREATED") == "Taslak oluştu"
    assert status_tone("FAILED_INVALID_TCKN") == "danger"


def test_unknown_status_falls_back_to_code() -> None:
    assert status_label("SOMETHING_NEW") == "SOMETHING_NEW"
    assert status_tone("SOMETHING_NEW") == "neutral"


def test_period_target_keeps_the_search_of_the_same_period_only() -> None:
    from invoice_automation.app.routes.ui_routes import _period_target

    assert _period_target(15, "/periods/15?q=demir&group=waiting") == "/periods/15?q=demir&group=waiting"
    assert _period_target(15, "/periods/15") == "/periods/15"
    assert _period_target(15, "") == "/periods/15"
    assert _period_target(15, "/periods/150?q=x") == "/periods/15"
    assert _period_target(15, "//evil.example/periods/15") == "/periods/15"
    assert _period_target(15, "/records?q=x") == "/periods/15"
