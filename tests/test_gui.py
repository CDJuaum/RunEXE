import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from runexe.analyzer import analyze_executable
from runexe.compatibility import analyze_compatibility
from runexe.gui.widgets import DropZone, SmoothScrollArea
from runexe.gui.window import AnalysisBundle, LibraryBundle, RunEXEWindow
from runexe.library import ApplicationLibrary, LaunchPreset
from runexe.models import HostInfo

from .helpers import make_pe


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def test_desktop_shell_has_expandable_pages(qt_app):
    window = RunEXEWindow(auto_refresh=False)

    assert window.pages.count() == 4
    assert [button.text() for button in window.nav_buttons] == [
        "Overview",
        "Runtime setup",
        "Library",
        "Activity",
    ]
    assert window.minimumWidth() <= 920
    assert not window.launch_button.isEnabled()
    assert [action.text() for action in window.environment_configure_menu.actions()] == [
        "Wine settings",
        "Registry editor",
        "Windows control panel",
        "Installed applications",
        "Wine file explorer",
    ]
    window.deleteLater()


def test_analysis_updates_readiness_and_runtime_state(qt_app, tmp_path):
    path = make_pe(tmp_path / "sample.exe", machine=0x014C)
    executable = analyze_executable(path)
    host = HostInfo("x86_64", False, None, None, None, False)
    report = analyze_compatibility(executable, host)
    window = RunEXEWindow(
        auto_refresh=False,
        application_library=ApplicationLibrary(tmp_path / "library.json"),
    )

    window._analysis_ready(AnalysisBundle(path, executable, host, report, []))

    assert window.format_metric.value.text() == "PE32 (32-bit)"
    assert window.readiness_metric.value.text() == "Blocked"
    assert window.readiness_metric.value.property("metricState") == "error"
    assert not window.launch_button.isEnabled()
    window.deleteLater()


def test_drop_zone_elides_long_paths(qt_app, tmp_path):
    zone = DropZone()
    zone.resize(340, 150)
    path = tmp_path / ("very-long-directory-" * 8) / "application.exe"

    zone.set_path(path)

    assert zone.title.text() == "application.exe"
    assert zone.toolTip() == str(path)
    assert len(zone.subtitle.text()) < len(str(path))
    zone.deleteLater()


def test_paint_net_profile_applies_windows_11_setup(qt_app, tmp_path):
    path = make_pe(tmp_path / "PaintDotNet.exe", machine=0x8664)
    executable = analyze_executable(path)
    host = HostInfo("x86_64", True, "wine-11", True, True, True)
    report = analyze_compatibility(executable, host)
    window = RunEXEWindow(
        auto_refresh=False,
        application_library=ApplicationLibrary(tmp_path / "library.json"),
    )

    window._analysis_ready(AnalysisBundle(path, executable, host, report, []))

    assert isinstance(window.overview_scroll, SmoothScrollArea)
    assert not window.profile_card.isHidden()
    assert "Windows 10 21H2" in window.profile_summary.text()
    assert window.winver_combo.currentData() == "11"
    assert "Windows 11" in window.environment_preview.text()
    assert window.apply_profile_button.text() == "Review Windows 11 setup"
    window.apply_profile_button.click()
    qt_app.processEvents()
    assert window.pages.currentIndex() == 1
    assert window.pages.widget(0).graphicsEffect() is None
    assert window.pages.widget(1).graphicsEffect() is None
    assert window.profile_card.graphicsEffect() is None
    assert window.runtime_scroll.viewport().autoFillBackground()
    assert window.winver_combo.view().viewport().autoFillBackground()
    assert window.winver_combo.view().viewport().objectName() == "comboPopupViewport"
    window.deleteLater()


def test_library_restores_per_application_preset(qt_app, tmp_path):
    path = make_pe(tmp_path / "sample.exe", machine=0x8664)
    executable = analyze_executable(path)
    host = HostInfo("x86_64", True, "wine-11", True, True, True)
    report = analyze_compatibility(executable, host)
    library = ApplicationLibrary(tmp_path / "library.json")
    preset = LaunchPreset(
        backend="wine",
        windows_version="10",
        dependencies="skip",
        arguments="--portable",
    )
    record = library.remember_analysis(
        path,
        display_name="Sample",
        architecture="x86_64",
        file_format=executable.format,
        preset=preset,
    )
    window = RunEXEWindow(auto_refresh=False, application_library=library)

    window._analysis_ready(AnalysisBundle(path, executable, host, report, []))
    window._library_ready(LibraryBundle([record], []))

    assert window.winver_combo.currentData() == "10"
    assert window.dependencies_combo.currentData() == "skip"
    assert window.arguments_input.text() == "--portable"
    assert window.recent_list.count() == 1
    assert "Sample" in window.recent_list.item(0).text()
    assert window.library_apps_metric.value.text() == "1"
    window.deleteLater()


def test_activity_support_report_exports_local_session(qt_app, tmp_path, monkeypatch):
    target = tmp_path / "support.json"
    window = RunEXEWindow(
        auto_refresh=False,
        application_library=ApplicationLibrary(tmp_path / "library.json"),
    )
    window.activity_log.appendPlainText("Example diagnostic")
    monkeypatch.setattr(
        "runexe.gui.window.QFileDialog.getSaveFileName",
        lambda *_args, **_kwargs: (str(target), "JSON report (*.json)"),
    )

    window.export_support_report()

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["schema"] == 1
    assert payload["source"] is None
    assert payload["activity"] == ["Example diagnostic"]
    assert payload["launch_preset"]["backend"] in {"auto", "wine", "proton"}
    assert list(tmp_path.glob(".*.tmp")) == []
    window.deleteLater()
