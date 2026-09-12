"""Refresh the README screenshot using a deterministic demonstration state."""

# ruff: noqa: E402 - path and Qt platform bootstrapping must precede GUI imports.

from __future__ import annotations

import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Headless Linux builders can refresh the Qt Quick scene through the offscreen
# platform and software scene graph.
if sys.platform != "win32" and not os.environ.get("DISPLAY"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtCore import QEventLoop, QSettings, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuickControls2 import QQuickStyle

from runexe.gui.controller import AnalysisBundle, LibraryBundle, RunEXEController
from runexe.gui.qml_app import create_engine
from runexe.library import ApplicationLibrary
from runexe.models import CompatibilityReport, ExecutableInfo, HostInfo, VersionInfo
from runexe.proton import ProtonInstallation


def main() -> None:
    QQuickStyle.setStyle("Basic")
    app = QGuiApplication.instance() or QGuiApplication([])
    source = Path.home() / "Downloads" / "Aurora Studio.exe"
    executable = ExecutableInfo(
        source,
        True,
        format="PE32+ (64-bit)",
        architecture="x86_64",
        subsystem="Windows GUI",
        version_info=VersionInfo(product_version="2.4", strings={"ProductName": "Aurora Studio"}),
    )
    host = HostInfo(
        "x86_64",
        True,
        "wine-11.0",
        True,
        True,
        True,
        proton_installed=True,
        proton_versions=["Proton Experimental"],
        vulkan_available=True,
        vulkan_version="1.3.290",
        vulkan_devices=["Example Vulkan GPU"],
    )
    compatibility = CompatibilityReport(
        application_type="Native Windows",
        architecture="x86_64",
        category="application",
        backend="wine",
        recommended_runtime="Wine 11.0",
        wine_arch="win64",
        notes=[
            "64-bit Windows executable detected.",
            "An isolated per-application Wine prefix will be used.",
        ],
    )
    proton = ProtonInstallation(
        "Proton Experimental",
        Path.home() / ".steam" / "root" / "steamapps" / "common" / "Proton Experimental" / "proton",
        "experimental",
        Path.home() / ".steam" / "root",
    )

    with TemporaryDirectory(prefix="runexe-screenshot-") as temporary:
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, temporary)
        controller = RunEXEController(
            auto_refresh=False,
            application_library=ApplicationLibrary(Path(temporary) / "library.json"),
        )
        if os.environ.get("RUNEXE_SCREENSHOT_EMPTY") != "1":
            controller._analysis_ready(
                AnalysisBundle(source, executable, host, compatibility, [proton])
            )
        engine = create_engine(controller)
        roots = engine.rootObjects()
        if not roots:
            raise RuntimeError("RunEXE QML screenshot window did not load")
        window = roots[0]
        window.setWidth(int(os.environ.get("RUNEXE_SCREENSHOT_WIDTH", "1180")))
        window.setHeight(int(os.environ.get("RUNEXE_SCREENSHOT_HEIGHT", "790")))
        app.processEvents()
        selected_page = os.environ.get("RUNEXE_SCREENSHOT_PAGE", "overview")
        if selected_page in {"applications", "library", "environments", "backups"}:
            controller._library_ready(LibraryBundle(controller.application_library.records(), []))
        page_indices = {
            "overview": controller.PAGE_OVERVIEW,
            "launch": controller.PAGE_LAUNCH_SETUP,
            "launch-setup": controller.PAGE_LAUNCH_SETUP,
            "runtime": controller.PAGE_RUNTIMES,
            "runtimes": controller.PAGE_RUNTIMES,
            "applications": controller.PAGE_APPLICATIONS,
            "library": controller.PAGE_APPLICATIONS,
            "environments": controller.PAGE_ENVIRONMENTS,
            "backups": controller.PAGE_BACKUPS,
            "activity": controller.PAGE_ACTIVITY,
        }
        if selected_page not in page_indices:
            raise ValueError(f"Unknown RUNEXE_SCREENSHOT_PAGE: {selected_page}")
        controller.navigateRequested.emit(page_indices[selected_page])
        app.processEvents()
        settle = QEventLoop()
        QTimer.singleShot(260, settle.quit)
        settle.exec()
        configured_target = os.environ.get("RUNEXE_SCREENSHOT_TARGET")
        target = (
            Path(configured_target).expanduser().resolve()
            if configured_target
            else Path(__file__).resolve().parent.parent / "assets" / "runexe-gui.png"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        if not window.grabWindow().save(str(target), "PNG"):
            raise RuntimeError(f"Could not save GUI screenshot to {target}")
        print(target)
        window.close()
        engine.deleteLater()


if __name__ == "__main__":
    main()
