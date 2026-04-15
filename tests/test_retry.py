from invoice_automation.app.utils.retry import retry_with_backoff


class FakePage:
    def __init__(self) -> None:
        self.waits: list[int] = []

    def wait_for_timeout(self, timeout_ms: int) -> None:
        self.waits.append(timeout_ms)


def test_retry_with_backoff_retries_until_success() -> None:
    page = FakePage()
    attempts = {"count": 0}

    def action() -> str:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("temporary")
        return "ok"

    result = retry_with_backoff(
        action,
        attempts=3,
        base_delay_ms=100,
        description="test",
        page=page,
    )

    assert result == "ok"
    assert attempts["count"] == 3
    assert page.waits == [100, 200]
