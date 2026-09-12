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

# Use the platform's font and controls. Headless Linux builders can refresh the
# screenshot with Qt's offscreen backend.
if sys.platform != "win32" and not os.environ.get("DISPLAY"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QSettings, QTimer
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from runexe.gui.theme import apply_theme
from runexe.gui.window import AnalysisBundle, LibraryBundle, RunEXEWindow
from runexe.library import ApplicationLibrary
from runexe.models import CompatibilityReport, ExecutableInfo, HostInfo, VersionInfo
from runexe.proton import ProtonInstallation


def main() -> None:
    app = QApplication.instance() or QApplication([])
    # Explicit schemes make visual QA repeatable without changing user settings.
    scheme = os.environ.get("RUNEXE_SCREENSHOT_SCHEME", "system")
    if scheme in {"light", "dark"}:
        palette = QPalette()
        dark = scheme == "dark"
        for role, light, dark_color in (
            (QPalette.ColorRole.Window, "#eff0f1", "#202225"),
            (QPalette.ColorRole.Base, "#ffffff", "#292c30"),
            (QPalette.ColorRole.AlternateBase, "#e7e9eb", "#33373c"),
            (QPalette.ColorRole.Button, "#eff0f1", "#34383d"),
            (QPalette.ColorRole.Text, "#232629", "#eff0f1"),
            (QPalette.ColorRole.WindowText, "#232629", "#eff0f1"),
            (QPalette.ColorRole.ButtonText, "#232629", "#eff0f1"),
            (QPalette.ColorRole.PlaceholderText, "#60666c", "#a9adb2"),
            (QPalette.ColorRole.Highlight, "#287fac", "#287fac"),
            (QPalette.ColorRole.HighlightedText, "#ffffff", "#ffffff"),
        ):
            palette.setColor(role, QColor(dark_color if dark else light))
        for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
            palette.setColor(
                QPalette.ColorGroup.Disabled, role, QColor("#92979c" if dark else "#74797e")
            )
        app.setStyle("Fusion")
        app.setPalette(palette)
    apply_theme(app)
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
        window = RunEXEWindow(
            auto_refresh=False,
            application_library=ApplicationLibrary(Path(temporary) / "library.json"),
        )
        window.resize(
            int(os.environ.get("RUNEXE_SCREENSHOT_WIDTH", "1180")),
            int(os.environ.get("RUNEXE_SCREENSHOT_HEIGHT", "790")),
        )
        if os.environ.get("RUNEXE_SCREENSHOT_EMPTY") != "1":
            window._analysis_ready(
                AnalysisBundle(source, executable, host, compatibility, [proton])
            )
        window.show()
        app.processEvents()
        selected_page = os.environ.get("RUNEXE_SCREENSHOT_PAGE", "overview")
        if selected_page in {"applications", "library", "environments", "backups"}:
            window._library_ready(LibraryBundle(window.application_library.records(), []))
        page_indices = {
            "overview": window.PAGE_OVERVIEW,
            "launch": window.PAGE_LAUNCH_SETUP,
            "launch-setup": window.PAGE_LAUNCH_SETUP,
            "runtime": window.PAGE_RUNTIMES,
            "runtimes": window.PAGE_RUNTIMES,
            "applications": window.PAGE_APPLICATIONS,
            "library": window.PAGE_APPLICATIONS,
            "environments": window.PAGE_ENVIRONMENTS,
            "backups": window.PAGE_BACKUPS,
            "activity": window.PAGE_ACTIVITY,
        }
        if selected_page not in page_indices:
            raise ValueError(f"Unknown RUNEXE_SCREENSHOT_PAGE: {selected_page}")
        window._show_page(page_indices[selected_page])
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
        if not window.grab().save(str(target), "PNG"):
            raise RuntimeError(f"Could not save GUI screenshot to {target}")
        print(target)
        window.close()


if __name__ == "__main__":
    main()
