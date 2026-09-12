import sys

import pytest

pytest.importorskip("PySide6")

from runexe.gui.notifications import DesktopNotifier


class FakeWindow:
    def __init__(self, *, active: bool) -> None:
        self.active = active

    def isActive(self) -> bool:  # noqa: N802 - mirrors QWindow API
        return self.active


def test_desktop_notifier_uses_notify_send_when_window_is_inactive(tmp_path, monkeypatch):
    icon = tmp_path / "runexe.png"
    icon.touch()
    calls = []
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(
        "runexe.gui.notifications.QStandardPaths.findExecutable",
        lambda name: "/usr/bin/notify-send" if name == "notify-send" else "",
    )
    monkeypatch.setattr(
        "runexe.gui.notifications.QProcess.startDetached",
        lambda program, arguments: calls.append((program, arguments)) or (True, 42),
    )

    notifier = DesktopNotifier(FakeWindow(active=False), icon)

    assert notifier.show("Environment ready", "Setup finished")
    assert calls == [
        (
            "/usr/bin/notify-send",
            [
                "--app-name=RunEXE",
                "--icon",
                str(icon),
                "Environment ready",
                "Setup finished",
            ],
        )
    ]


def test_desktop_notifier_suppresses_notifications_while_window_is_active(monkeypatch):
    calls = []
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(
        "runexe.gui.notifications.QProcess.startDetached",
        lambda *args: calls.append(args) or (True, 42),
    )

    notifier = DesktopNotifier(FakeWindow(active=True))

    assert not notifier.show("Done", "No notification needed")
    assert calls == []


def test_desktop_notifier_is_optional_when_notify_send_is_unavailable(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr("runexe.gui.notifications.QStandardPaths.findExecutable", lambda _name: "")

    notifier = DesktopNotifier(FakeWindow(active=False))

    assert not notifier.show("Done", "RunEXE stays usable without libnotify")
