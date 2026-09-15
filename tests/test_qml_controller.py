import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from runexe.analyzer import analyze_executable
from runexe.compatibility import analyze_compatibility
from runexe.gui.controller import AnalysisBundle, LibraryBundle, RunEXEController
from runexe.library import ApplicationLibrary, LaunchPreset
from runexe.models import HostInfo
from runexe.proton import ProtonInstallation

from .helpers import make_pe


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def test_controller_exposes_analysis_state_without_widget_dependencies(qt_app, tmp_path):
    path = make_pe(tmp_path / "sample.exe", machine=0x8664)
    executable = analyze_executable(path)
    host = HostInfo("x86_64", True, "wine-11", True, True, True)
    report = analyze_compatibility(executable, host)
    controller = RunEXEController(
        auto_refresh=False,
        application_library=ApplicationLibrary(tmp_path / "library.json"),
    )

    controller._analysis_ready(AnalysisBundle(path, executable, host, report, []))

    assert controller.sourceSelected
    assert controller.analyzed
    assert controller.selectedPath == str(path)
    assert controller.fileMetric["value"] == executable.format
    assert controller.readinessMetric["state"] in {"neutral", "success", "warning"}
    assert controller.compatibilityMetric["value"] == f"{report.compatibility_score}/100"
    assert controller.compatibilityMetric["detail"] == report.compatibility_rating
    assert controller.launchEnabled
    assert controller.environmentPreview


def test_controller_desktop_notifications_can_be_disabled(qt_app, tmp_path):
    controller = RunEXEController(
        auto_refresh=False,
        application_library=ApplicationLibrary(tmp_path / "library.json"),
    )
    notifications = []
    controller.notificationRequested.connect(lambda *message: notifications.append(message))

    controller.setNotificationsEnabled(False)
    controller._notify("Hidden", "This should not be emitted")
    assert not controller.notificationsEnabled
    assert notifications == []

    controller.setNotificationsEnabled(True)
    controller._notify("Ready", "Background work completed")
    assert controller.notificationsEnabled
    assert notifications == [("Ready", "Background work completed")]


def test_controller_restores_per_application_launch_preset(qt_app, tmp_path):
    path = make_pe(tmp_path / "saved.exe", machine=0x8664)
    executable = analyze_executable(path)
    host = HostInfo("x86_64", True, "wine-11", True, True, True)
    report = analyze_compatibility(executable, host)
    library = ApplicationLibrary(tmp_path / "library.json")
    library.remember_analysis(
        path,
        display_name="Saved",
        architecture=executable.architecture,
        file_format=executable.format,
        preset=LaunchPreset(
            backend="wine",
            windows_version="10",
            dependencies="skip",
            arguments="--portable",
        ),
    )
    controller = RunEXEController(auto_refresh=False, application_library=library)

    controller._analysis_ready(AnalysisBundle(path, executable, host, report, []))

    assert controller.backend == "wine"
    assert controller.windowsVersion == "10"
    assert controller.dependencyMode == "skip"
    assert controller.arguments == "--portable"


def test_controller_library_model_filters_and_preserves_action_selection(qt_app, tmp_path):
    library = ApplicationLibrary(tmp_path / "library.json")
    editor = make_pe(tmp_path / "Editor.exe")
    calculator = make_pe(tmp_path / "Calculator.exe")
    for path in (editor, calculator):
        library.remember_analysis(
            path,
            display_name=path.stem,
            architecture="x86_64",
            file_format="PE32+",
        )
    controller = RunEXEController(auto_refresh=False, application_library=library)
    controller._library_ready(LibraryBundle(library.records(), []))

    assert controller.applicationsModel.count == 2
    controller.setApplicationSearch("editor")
    assert controller.applicationsModel.count == 1
    controller.selectApplication(0)
    assert controller.applicationSelected
    assert controller.applicationsModel.get(0)["displayName"] == "Editor"
    controller.setApplicationSearch("missing")
    assert controller.applicationsModel.count == 0
    assert not controller.applicationSelected


def test_controller_launch_guard_cannot_be_bypassed_while_busy(qt_app, tmp_path, monkeypatch):
    path = make_pe(tmp_path / "busy.exe", machine=0x8664)
    executable = analyze_executable(path)
    host = HostInfo("x86_64", True, "wine-11", True, True, True)
    report = analyze_compatibility(executable, host)
    controller = RunEXEController(
        auto_refresh=False,
        application_library=ApplicationLibrary(tmp_path / "library.json"),
    )
    controller._analysis_ready(AnalysisBundle(path, executable, host, report, []))
    started = []
    monkeypatch.setattr(controller, "_start_task", lambda *args: started.append(args[0]))
    controller._workers["prepare"] = object()

    controller.launchApplication()

    assert started == []
    assert "Wait for the current task" in controller.taskStatus
    controller._workers.clear()


def test_controller_launch_guard_explains_why_action_is_blocked(qt_app, tmp_path):
    controller = RunEXEController(
        auto_refresh=False,
        application_library=ApplicationLibrary(tmp_path / "library.json"),
    )
    messages = []
    controller.messageRequested.connect(lambda *message: messages.append(message))
    controller._workers["prepare"] = object()

    controller.launchApplication()

    assert messages[-1][0] == "info"
    assert "working" in messages[-1][1].lower()
    assert "current task" in messages[-1][2].lower()
    controller._workers.clear()


def test_managed_action_without_selection_shows_feedback_and_navigates(qt_app, tmp_path):
    controller = RunEXEController(
        auto_refresh=False,
        application_library=ApplicationLibrary(tmp_path / "library.json"),
    )
    messages = []
    pages = []
    controller.messageRequested.connect(lambda *message: messages.append(message))
    controller.navigateRequested.connect(pages.append)

    controller.openSelectedEnvironmentFolder()

    assert messages[-1] == (
        "info",
        "Select an environment",
        "Choose an environment from the list before using this action.",
    )
    assert pages[-1] == controller.PAGE_ENVIRONMENTS


def test_nonzero_application_exit_is_visible_to_user(qt_app, tmp_path):
    controller = RunEXEController(
        auto_refresh=False,
        application_library=ApplicationLibrary(tmp_path / "library.json"),
    )
    messages = []
    controller.messageRequested.connect(lambda *message: messages.append(message))

    controller._application_finished(17, None)

    assert messages[-1][0] == "error"
    assert messages[-1][1] == "Application exited unexpectedly"
    assert "code 17" in messages[-1][2]
    assert "Activity" in messages[-1][2]


def test_application_exit_never_requests_runexe_shutdown(qt_app, tmp_path, monkeypatch):
    controller = RunEXEController(
        auto_refresh=False,
        application_library=ApplicationLibrary(tmp_path / "library.json"),
    )
    quit_requests = []
    monkeypatch.setattr(
        "runexe.gui.controller.QCoreApplication.quit",
        lambda: quit_requests.append(True),
    )

    controller._application_finished(0, None)

    assert quit_requests == []
    assert controller.taskStatus == "Ready"


def test_controller_exports_same_support_report_schema(qt_app, tmp_path):
    target = tmp_path / "support.json"
    controller = RunEXEController(
        auto_refresh=False,
        application_library=ApplicationLibrary(tmp_path / "library.json"),
    )
    controller._log("Example diagnostic")

    controller.exportSupportReport(str(target))

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["schema"] == 1
    assert payload["source"] is None
    assert payload["activity"][-1].endswith("Example diagnostic")
    assert payload["launch_preset"]["backend"] in {"auto", "wine", "proton"}
    assert list(tmp_path.glob(".*.tmp")) == []


def test_runtime_provisioning_actions_use_background_hooks(qt_app, tmp_path, monkeypatch):
    controller = RunEXEController(auto_refresh=False)
    proton_dir = tmp_path / "GE-Proton"
    proton_dir.mkdir()
    proton_script = proton_dir / "proton"
    proton_script.touch()
    installation = ProtonInstallation("GE-Proton", proton_script, None, tmp_path)
    tasks = []
    refreshes = []
    vulkan_components = []
    umu_installs = []

    monkeypatch.setattr(
        "runexe.gui.controller.install_managed_proton",
        lambda *, progress=None: installation,
    )
    monkeypatch.setattr(
        "runexe.gui.controller.ensure_umu_launcher",
        lambda *, progress=None: umu_installs.append(True) or "/managed/umu-run",
    )
    monkeypatch.setattr(
        "runexe.gui.controller.install_system_component",
        lambda component, *, progress=None: vulkan_components.append(component) or object(),
    )
    monkeypatch.setattr(controller, "refreshRuntimes", lambda: refreshes.append(True))

    def run_task(key, label, function, on_result):
        tasks.append((key, label))
        on_result(function())

    monkeypatch.setattr(controller, "_start_task", run_task)
    controller.installProton()
    controller.installUmuLauncher()
    controller.installVulkanTools()
    qt_app.processEvents()

    assert [key for key, _label in tasks] == ["install-proton", "install-umu", "install-vulkan"]
    assert umu_installs == [True, True]
    assert vulkan_components == ["vulkan"]
    assert refreshes == [True, True, True]
    assert "Managed Proton ready" in controller.activityText
    assert "UMU Launcher ready" in controller.activityText
    assert "Vulkan tools installation completed" in controller.activityText


def test_controller_exposes_persistent_app_theme_setting(qt_app, tmp_path):
    controller = RunEXEController(
        auto_refresh=False,
        application_library=ApplicationLibrary(tmp_path / "library.json"),
    )
    original = controller.themeMode
    target = "dark" if original != "dark" else "light"
    try:
        controller.setThemeMode(target)
        assert controller.themeMode == target
        assert {option["value"] for option in controller.themeOptions} == {
            "system",
            "light",
            "dark",
        }

        controller.setThemeMode("invalid")
        assert controller.themeMode == target
    finally:
        controller.setThemeMode(original)


def test_runtime_refresh_reuses_one_proton_snapshot(qt_app, monkeypatch):
    controller = RunEXEController(auto_refresh=False)
    installations = []
    discoveries = []
    host = HostInfo("x86_64", False, None, None, None, False)

    def discover():
        discoveries.append(True)
        return installations

    def detect(*, proton_installations):
        assert proton_installations is installations
        return host

    monkeypatch.setattr("runexe.gui.controller.discover_proton_installations", discover)
    monkeypatch.setattr("runexe.gui.controller.detect_host", detect)
    monkeypatch.setattr(controller, "_start_task", lambda key, label, run, done: done(run()))

    controller.refreshRuntimes()

    assert discoveries == [True]
    assert controller.host is host


def test_failed_new_analysis_clears_previous_launch_state(qt_app, tmp_path, monkeypatch):
    valid = make_pe(tmp_path / "valid.exe")
    executable = analyze_executable(valid)
    host = HostInfo("x86_64", True, "wine-11", True, True, True)
    controller = RunEXEController(
        auto_refresh=False,
        application_library=ApplicationLibrary(tmp_path / "library.json"),
    )
    controller._analysis_ready(
        AnalysisBundle(valid, executable, host, analyze_compatibility(executable, host), [])
    )
    assert controller.launchEnabled
    invalid = tmp_path / "invalid.exe"
    invalid.write_bytes(b"not an executable")
    monkeypatch.setattr(controller.thread_pool, "start", lambda worker: worker.run())

    controller.analyzePath(str(invalid))

    assert controller.executable is None
    assert controller.compatibility is None
    assert controller.selectedPath == str(invalid.resolve())
    assert not controller.launchEnabled
    assert not controller.prepareEnabled
    assert controller.readinessMetric["value"] == "Analysis failed"
    assert str(valid) not in controller.environmentPreview


def test_overlapping_analysis_does_not_replace_selected_file(qt_app, tmp_path):
    controller = RunEXEController(auto_refresh=False)
    original = tmp_path / "original.exe"
    controller.source_path = original
    controller._workers["analysis"] = object()

    controller.analyzePath(str(tmp_path / "second.exe"))

    assert controller.source_path == original
    assert "Wait for the current task" in controller.taskStatus
    controller._workers.clear()


def test_runtime_detection_can_overlap_initial_analysis(qt_app, tmp_path, monkeypatch):
    controller = RunEXEController(auto_refresh=False)
    controller._workers["runtimes"] = object()
    tasks = []
    monkeypatch.setattr(controller, "_start_task", lambda key, *args: tasks.append(key))
    source = tmp_path / "initial.exe"

    controller.analyzePath(str(source))

    assert tasks == ["analysis"]
    assert controller.source_path == source.resolve()
    controller._workers.clear()


def test_known_profile_applies_recommended_windows_version_and_navigation(qt_app, tmp_path):
    path = make_pe(tmp_path / "PaintDotNet.exe", machine=0x8664)
    executable = analyze_executable(path)
    host = HostInfo("x86_64", True, "wine-11", True, True, True)
    report = analyze_compatibility(executable, host)
    controller = RunEXEController(
        auto_refresh=False,
        application_library=ApplicationLibrary(tmp_path / "library.json"),
    )
    navigated = []
    controller.navigateRequested.connect(navigated.append)

    controller._analysis_ready(AnalysisBundle(path, executable, host, report, []))

    assert controller.profileVisible
    assert "Windows 10 21H2" in controller.profileSummary
    assert controller.windowsVersion == "11"
    assert "Windows 11" in controller.environmentPreview
    assert controller.profileButtonText == "Review Windows 11 setup"
    controller.applyProfileRecommendation()
    assert navigated[-1] == controller.PAGE_LAUNCH_SETUP
