"""Qt Quick/QML application bootstrap for the RunEXE desktop interface."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from .controller import RunEXEController

_live_engines: list[tuple[QQmlApplicationEngine, RunEXEController]] = []


def _qml_path() -> Path:
    return Path(__file__).resolve().parent / "qml" / "Main.qml"


def _asset_path() -> Path:
    return Path(__file__).resolve().parent.parent / "assets" / "runexe-logo.png"


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


def run_gui(initial_file: Path | None = None) -> int:
    """Create the Qt Quick application and display the QML shell."""

    app = QGuiApplication.instance()
    owns_application = app is None
    if app is None:
        QQuickStyle.setStyle("Basic")
        app = QGuiApplication(sys.argv)
    app.setApplicationName("RunEXE")
    app.setApplicationDisplayName("RunEXE")
    app.setOrganizationName("RunEXE")
    if _asset_path().is_file():
        app.setWindowIcon(QIcon(str(_asset_path())))

    controller = RunEXEController(initial_file)
    engine = create_engine(controller)
    _live_engines.append((engine, controller))
    if owns_application:
        try:
            return app.exec()
        finally:
            _live_engines.clear()
    return 0
