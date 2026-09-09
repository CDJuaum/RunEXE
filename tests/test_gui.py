import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from runexe.analyzer import analyze_executable
from runexe.compatibility import analyze_compatibility
from runexe.gui.widgets import DropZone, MetricCard, MetricGrid, SmoothScrollArea
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


def test_navigation_reuses_animation(qt_app):
    from PySide6.QtCore import QVariantAnimation

    window = RunEXEWindow(auto_refresh=False)
    window._show_page(1)
    animation = window._page_animation
    count = len(window.findChildren(QVariantAnimation))
    for index in range(100):
        window._show_page(index % 4)
    assert window._page_animation is animation
    assert len(window.findChildren(QVariantAnimation)) == count
    window.deleteLater()


def test_runtime_refresh_uses_one_installation_snapshot(qt_app, monkeypatch):
    window = RunEXEWindow(auto_refresh=False)
    installations = []
    discoveries = []
    host = HostInfo("x86_64", False, None, None, None, False)

    def discover():
        discoveries.append(True)
        return installations

    def detect(*, proton_installations):
        assert proton_installations is installations
        return host

    monkeypatch.setattr("runexe.gui.window.discover_proton_installations", discover)
    monkeypatch.setattr("runexe.gui.window.detect_host", detect)
    monkeypatch.setattr(window, "_start_task", lambda key, label, run, done: done(run()))
    window.refresh_runtimes()
    assert len(discoveries) == 1
    assert window.host is host
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


def test_failed_new_analysis_cannot_launch_previous_app(qt_app, tmp_path, monkeypatch):
    valid = make_pe(tmp_path / "valid.exe")
    executable = analyze_executable(valid)
    host = HostInfo("x86_64", True, "wine-11", True, True, True)
    window = RunEXEWindow(
        auto_refresh=False,
        application_library=ApplicationLibrary(tmp_path / "library.json"),
    )
    window._analysis_ready(
        AnalysisBundle(valid, executable, host, analyze_compatibility(executable, host), [])
    )
    assert window.launch_button.isEnabled()
    invalid = tmp_path / "invalid.exe"
    invalid.write_bytes(b"not an executable")
    monkeypatch.setattr(window.thread_pool, "start", lambda worker: worker.run())
    monkeypatch.setattr("runexe.gui.window.QMessageBox.critical", lambda *args: None)

    window.analyze_path(invalid)

    assert window.executable is None
    assert window.compatibility is None
    assert window.drop_zone.path == invalid.resolve()
    assert not window.launch_button.isEnabled()
    assert not window.prepare_button.isEnabled()
    assert window.readiness_metric.value.text() == "Analysis failed"
    assert str(valid) not in window.environment_preview.text()
    window.deleteLater()


def test_overlapping_analysis_does_not_change_selected_file(qt_app, tmp_path):
    window = RunEXEWindow(auto_refresh=False)
    original = tmp_path / "original.exe"
    window.source_path = original
    window.drop_zone.set_path(original)
    window._workers["analysis"] = object()
    window.analyze_path(tmp_path / "second.exe")
    assert window.source_path == original
    assert window.drop_zone.path == original
    window._workers.clear()
    window.deleteLater()


def test_startup_runtime_detection_does_not_discard_initial_file(qt_app, tmp_path, monkeypatch):
    window = RunEXEWindow(auto_refresh=False)
    window._workers["runtimes"] = object()
    tasks = []
    monkeypatch.setattr(window, "_start_task", lambda key, *args: tasks.append(key))
    source = tmp_path / "initial.exe"
    window.analyze_path(source)
    assert tasks == ["analysis"]
    assert window.source_path == source.resolve()
    window._workers.clear()
    window.deleteLater()


def test_library_search_and_refresh_preserve_selection(qt_app, tmp_path):
    library = ApplicationLibrary(tmp_path / "library.json")
    for name in ("Editor", "Calculator"):
        library.remember_analysis(
            tmp_path / f"{name}.exe", display_name=name, architecture="x86", file_format="PE32"
        )
    window = RunEXEWindow(auto_refresh=False, application_library=library)
    bundle = LibraryBundle(library.records(), [])
    window._library_ready(bundle)
    window.library_search.setText("EDITOR")
    matches = [
        window.recent_list.item(i) for i in range(2) if not window.recent_list.item(i).isHidden()
    ]
    assert len(matches) == 1
    window.recent_list.setCurrentItem(matches[0])
    window._library_ready(bundle)
    assert "Editor" in window.recent_list.currentItem().text()
    assert window.recent_open_button.isEnabled()
    window.library_search.setText("no match")
    assert not window.recent_open_button.isEnabled()
    assert window.library_empty.text() == "No applications match your search."
    window.library_search.clear()
    assert window.recent_open_button.isEnabled()
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


def test_summary_cards_reflow_without_losing_widgets(qt_app):
    cards = [MetricCard(caption) for caption in ("Format", "Architecture", "Runtime", "Readiness")]
    grid = MetricGrid(cards)
    grid.resize(900, 220)
    grid.show()
    qt_app.processEvents()
    assert grid.layout().itemAtPosition(0, 3).widget() is cards[3]

    grid.resize(620, 300)
    qt_app.processEvents()
    assert grid.layout().itemAtPosition(1, 1).widget() is cards[3]
    assert grid.layout().count() == 4

    grid.resize(900, 220)
    qt_app.processEvents()
    assert grid.layout().itemAtPosition(0, 3).widget() is cards[3]
    grid.close()
    grid.deleteLater()


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
