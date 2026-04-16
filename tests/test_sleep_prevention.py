from invoice_automation.app.utils.sleep_prevention import SleepPreventionGuard, SleepPreventionSettings


class FakeProcess:
    def __init__(self) -> None:
        self.pid = 123
        self.terminated = False
        self.killed = False

    def poll(self):
        return None

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: int | None = None) -> None:
        return None

    def kill(self) -> None:
        self.killed = True


def test_sleep_prevention_disabled_does_not_start_process(monkeypatch) -> None:
    popen_calls = []
    monkeypatch.setattr("subprocess.Popen", lambda args: popen_calls.append(args))

    guard = SleepPreventionGuard(
        SleepPreventionSettings(
            enabled=False,
            platform_name="macos",
            keep_display_awake=True,
        )
    )

    with guard:
        assert guard.active is False

    assert popen_calls == []


def test_sleep_prevention_starts_and_stops_macos_caffeinate(monkeypatch) -> None:
    process = FakeProcess()
    popen_calls = []

    monkeypatch.setattr(
        "shutil.which",
        lambda command: "/usr/bin/caffeinate" if command == "caffeinate" else None,
    )
    monkeypatch.setattr(
        "subprocess.Popen",
        lambda args: popen_calls.append(args) or process,
    )

    guard = SleepPreventionGuard(
        SleepPreventionSettings(
            enabled=True,
            platform_name="macos",
            keep_display_awake=True,
        )
    )

    with guard:
        assert guard.active is True
        assert guard.backend == "caffeinate"

    assert popen_calls == [["/usr/bin/caffeinate", "-i", "-m", "-s", "-d"]]
    assert process.terminated is True
