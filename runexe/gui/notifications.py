"""Best-effort Linux desktop notifications for the Qt Quick frontend."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QStandardPaths, Slot
from PySide6.QtGui import QWindow


class DesktopNotifier(QObject):
    """Deliver completion notifications when RunEXE is not the active window."""

    def __init__(
        self,
        window: QWindow | None,
        icon: Path | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._window = window
        self._icon = icon if icon is not None and icon.is_file() else None

    # Keep this a void Qt slot. PySide 6.10.x on Linux can segfault when a
    # void Signal(str, str) invokes a Python slot declared with ``result=bool``.
    # Direct Python callers can still use the method's return value.
    @Slot(str, str)
    def show(self, title: str, body: str) -> bool:
        """Show a notification through the freedesktop notification helper when available."""

        if not sys.platform.startswith("linux"):
            return False
        if self._window is not None and self._window.isActive():
            return False

        executable = QStandardPaths.findExecutable("notify-send")
        if not executable:
            return False

        arguments = ["--app-name=RunEXE"]
        if self._icon is not None:
            arguments.extend(["--icon", str(self._icon)])
        arguments.extend([title, body])
        started, _pid = QProcess.startDetached(executable, arguments)
        return started
