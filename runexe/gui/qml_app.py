"""Qt Quick/QML application bootstrap for the RunEXE desktop interface."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QEvent, Qt, QUrl
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from .controller import RunEXEController
from .notifications import DesktopNotifier

_live_engines: list[tuple[QQmlApplicationEngine, RunEXEController]] = []
_VMWARE_DMI_PATHS = (
    Path("/sys/class/dmi/id/product_name"),
    Path("/sys/class/dmi/id/sys_vendor"),
    Path("/sys/class/dmi/id/board_vendor"),
)


def _qml_path() -> Path:
    return Path(__file__).resolve().parent / "qml" / "Main.qml"


def _asset_path() -> Path:
    return Path(__file__).resolve().parent.parent / "assets" / "runexe-logo.png"


def _running_in_vmware() -> bool:
    """Return whether Linux DMI data identifies this machine as a VMware guest."""

    for path in _VMWARE_DMI_PATHS:
        try:
            if "vmware" in path.read_text(encoding="utf-8", errors="ignore").lower():
                return True
        except OSError:
            continue
    return False


def _use_qt_fallback_dialogs() -> bool:
    """Choose the Qt fallback only where native Linux dialogs are known to misbehave."""

    preference = os.environ.get("RUNEXE_DIALOG_BACKEND", "auto").strip().lower()
    if preference == "qt":
        return True
    if preference == "native":
        return False
    return _running_in_vmware()


def _configure_application(app: QGuiApplication) -> None:
    """Apply RunEXE-wide application metadata and lifecycle policy."""

    # VMware/X11 native dialogs can take an exclusive pointer grab and warp the
    # cursor back into the picker. Keep the Qt fallback for those guests only.
    # Normal Linux desktops (including Arch/KDE/GNOME) should use their native
    # platform/portal picker, which integrates much better with the desktop.
    # RUNEXE_DIALOG_BACKEND=qt|native can override auto-detection for debugging.
    if sys.platform.startswith("linux") and _use_qt_fallback_dialogs():
        QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, True)

    # RunEXE owns its close policy explicitly through Main.qml -> requestClose().
    # Do not let Qt end the event loop just because it believes the last window
    # closed while an external Wine/Proton process is being torn down.
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("RunEXE")
    app.setApplicationDisplayName("RunEXE")
    app.setOrganizationName("RunEXE")
    if _asset_path().is_file():
        app.setWindowIcon(QIcon(str(_asset_path())))


def create_engine(controller: RunEXEController) -> QQmlApplicationEngine:
    """Load the QML shell for an already-created controller."""

    qml = _qml_path()
    if not qml.is_file():
        raise RuntimeError(f"RunEXE QML shell is missing: {qml}")

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("controller", controller)
    engine.load(QUrl.fromLocalFile(str(qml)))
    if not engine.rootObjects():
        raise RuntimeError("RunEXE could not load its Qt Quick interface.")
    return engine


def _teardown_engine(
    app: QGuiApplication,
    engine: QQmlApplicationEngine,
    controller: RunEXEController,
) -> None:
    """Destroy QML before its context controller during application shutdown.

    The controller is exposed as a QML context property but is not owned by the
    engine.  Letting Python release both objects implicitly can therefore destroy
    the controller first, leaving live QML bindings evaluating against ``null``.
    Explicitly flushing deferred deletion in this order avoids that shutdown race.
    """

    engine.deleteLater()
    QCoreApplication.sendPostedEvents(engine, QEvent.Type.DeferredDelete)
    app.processEvents()
    controller.deleteLater()
    QCoreApplication.sendPostedEvents(controller, QEvent.Type.DeferredDelete)


def run_gui(initial_file: Path | None = None) -> int:
    """Create the Qt Quick application and display the QML shell."""

    app = QGuiApplication.instance()
    owns_application = app is None
    if app is None:
        QQuickStyle.setStyle("Basic")
        app = QGuiApplication(sys.argv)
    _configure_application(app)

    controller = RunEXEController(initial_file)
    engine = create_engine(controller)
    root_window = engine.rootObjects()[0]
    notifier = DesktopNotifier(root_window, _asset_path(), controller)
    controller.notificationRequested.connect(notifier.show)
    _live_engines.append((engine, controller))
    if owns_application:
        try:
            return app.exec()
        finally:
            _teardown_engine(app, engine, controller)
            _live_engines.clear()
    return 0
