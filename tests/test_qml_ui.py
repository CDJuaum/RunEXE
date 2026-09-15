import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication, QEventLoop, QPoint, QPointF, QProcess, Qt, QTimer
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from runexe.gui.controller import RunEXEController
from runexe.gui.qml_app import _configure_application, _teardown_engine, create_engine
from runexe.library import ApplicationLibrary


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def make_shell(qt_app, tmp_path):
    controller = RunEXEController(
        auto_refresh=False,
        application_library=ApplicationLibrary(tmp_path / "library.json"),
    )
    engine = create_engine(controller)
    root = engine.rootObjects()[0]
    qt_app.processEvents()
    return controller, engine, root


def test_application_uses_explicit_close_policy(qt_app):
    previous = qt_app.quitOnLastWindowClosed()
    try:
        _configure_application(qt_app)
        assert qt_app.quitOnLastWindowClosed() is False
    finally:
        qt_app.setQuitOnLastWindowClosed(previous)


def test_linux_application_disables_native_dialogs(qt_app, monkeypatch):
    attribute = Qt.ApplicationAttribute.AA_DontUseNativeDialogs
    previous = QCoreApplication.testAttribute(attribute)
    try:
        QCoreApplication.setAttribute(attribute, False)
        monkeypatch.setattr(sys, "platform", "linux")

        _configure_application(qt_app)

        assert QCoreApplication.testAttribute(attribute) is True
    finally:
        QCoreApplication.setAttribute(attribute, previous)


def test_launched_process_exit_keeps_runexe_window_open(qt_app, tmp_path):
    previous = qt_app.quitOnLastWindowClosed()
    _configure_application(qt_app)
    controller, engine, root = make_shell(qt_app, tmp_path)
    process = QProcess(controller)
    process.setProgram(sys.executable)
    process.setArguments(["-c", "pass"])
    process.finished.connect(controller._application_finished)
    controller.application_process = process
    loop = QEventLoop()
    process.finished.connect(lambda *_: QTimer.singleShot(50, loop.quit))

    process.start()
    QTimer.singleShot(3000, loop.quit)
    loop.exec()

    assert controller.application_process is None
    assert root.isVisible() is True
    root.close()
    _teardown_engine(qt_app, engine, controller)
    qt_app.setQuitOnLastWindowClosed(previous)


@pytest.mark.parametrize(
    ("page", "object_name", "property_name"),
    [
        (RunEXEController.PAGE_OVERVIEW, "overviewPage", "openFileDialog"),
        (RunEXEController.PAGE_LAUNCH_SETUP, "launchSetupPage", "prefixDialog"),
        (RunEXEController.PAGE_ACTIVITY, "activityPage", "exportDialog"),
    ],
)
def test_loaded_pages_receive_shared_dialogs(qt_app, tmp_path, page, object_name, property_name):
    controller, engine, root = make_shell(qt_app, tmp_path)
    root.showPage(page)
    qt_app.processEvents()

    page_item = root.findChild(QQuickItem, object_name)
    assert page_item is not None
    assert page_item.property(property_name) is not None

    root.close()
    engine.deleteLater()
    controller.deleteLater()


def test_overview_choose_file_button_opens_dialog(qt_app, tmp_path):
    controller, engine, root = make_shell(qt_app, tmp_path)
    button = root.findChild(QQuickItem, "chooseFileButton")
    overview = root.findChild(QQuickItem, "overviewPage")
    assert button is not None
    assert overview is not None
    dialog = overview.property("openFileDialog")
    assert dialog is not None
    assert dialog.property("visible") is False

    point = button.mapToScene(QPointF(button.width() / 2, button.height() / 2))
    QTest.mouseClick(
        root, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point.toPoint()
    )
    qt_app.processEvents()

    assert dialog.property("visible") is True
    dialog.close()
    root.close()
    engine.deleteLater()
    controller.deleteLater()


def test_qml_teardown_destroys_engine_before_controller(qt_app, tmp_path):
    controller, engine, root = make_shell(qt_app, tmp_path)
    destroyed = []
    engine.destroyed.connect(lambda: destroyed.append("engine"))
    controller.destroyed.connect(lambda: destroyed.append("controller"))

    root.close()
    _teardown_engine(qt_app, engine, controller)

    assert destroyed == ["engine", "controller"]


def test_qml_shell_loads_all_pages(qt_app, tmp_path):
    controller, engine, root = make_shell(qt_app, tmp_path)

    assert root.property("minimumWidth") == 920
    assert root.property("minimumHeight") == 680
    for page in range(8):
        root.showPage(page)
        qt_app.processEvents()
        assert root.property("currentPage") == page

    root.close()
    engine.deleteLater()
    controller.deleteLater()


def test_settings_and_runtime_progress_surfaces_are_available(qt_app, tmp_path):
    controller, engine, root = make_shell(qt_app, tmp_path)

    root.showPage(controller.PAGE_SETTINGS)
    qt_app.processEvents()
    assert root.findChild(QQuickItem, "settingsPage") is not None

    root.showPage(controller.PAGE_RUNTIMES)
    qt_app.processEvents()
    assert root.findChild(QQuickItem, "runtimeInstallProgress") is not None
    assert root.findChild(QQuickItem, "installUmuButton") is not None

    root.close()
    engine.deleteLater()
    controller.deleteLater()


def test_controller_navigation_signal_changes_qml_page(qt_app, tmp_path):
    controller, engine, root = make_shell(qt_app, tmp_path)

    controller.navigateRequested.emit(controller.PAGE_BACKUPS)
    qt_app.processEvents()

    assert root.property("currentPage") == controller.PAGE_BACKUPS
    root.close()
    engine.deleteLater()
    controller.deleteLater()


def test_qml_shell_compacts_at_supported_minimum_width(qt_app, tmp_path):
    controller, engine, root = make_shell(qt_app, tmp_path)
    root.setWidth(920)
    root.setHeight(680)
    qt_app.processEvents()

    assert root.property("compactSidebar") is True

    root.setWidth(1180)
    qt_app.processEvents()
    assert root.property("compactSidebar") is False
    root.close()
    engine.deleteLater()
    controller.deleteLater()


def test_activity_model_is_bounded_and_append_only_for_qml(qt_app, tmp_path):
    controller = RunEXEController(
        auto_refresh=False,
        application_library=ApplicationLibrary(tmp_path / "library.json"),
    )

    controller._log("first")
    controller._log("second")

    assert controller.activityModel.count == 2
    first = controller.activityModel.data(
        controller.activityModel.index(0, 0), Qt.ItemDataRole.UserRole
    )
    assert first.endswith("first")
    assert controller.activityText.endswith("second")
    controller.clearActivity()
    assert controller.activityModel.count == 0
    assert controller.activityText == ""


def test_applications_page_mouse_wheel_scrolls_list_from_rows_and_page_header(qt_app, tmp_path):
    controller, engine, root = make_shell(qt_app, tmp_path)
    controller.applicationsModel.replace(
        [
            {
                "path": f"/tmp/app-{index}.exe",
                "displayName": f"App {index}",
                "headline": f"App {index}",
                "subtitle": "x86_64 • test entry",
                "detail": f"Example application {index}",
                "exists": True,
            }
            for index in range(30)
        ]
    )
    root.setWidth(920)
    root.setHeight(680)
    root.showPage(controller.PAGE_APPLICATIONS)
    qt_app.processEvents()

    application_list = root.findChild(QQuickItem, "applicationList")
    assert application_list is not None
    assert application_list.property("contentHeight") > application_list.height()

    list_scene = application_list.mapToScene(QPointF(application_list.width() / 2, 0))
    header_point = QPointF(list_scene.x(), list_scene.y() - 45)
    QTest.wheelEvent(root, header_point, QPoint(0, -120))
    qt_app.processEvents()
    assert application_list.property("contentY") > 0

    application_list.setProperty("contentY", 0)
    row_point = application_list.mapToScene(
        QPointF(application_list.width() / 2, application_list.height() / 2)
    )
    QTest.wheelEvent(root, row_point, QPoint(0, -120))
    qt_app.processEvents()
    assert application_list.property("contentY") > 0

    root.close()
    engine.deleteLater()
    controller.deleteLater()


@pytest.mark.parametrize(
    ("page", "object_name"),
    [
        (RunEXEController.PAGE_OVERVIEW, "overviewPage"),
        (RunEXEController.PAGE_LAUNCH_SETUP, "launchSetupPage"),
    ],
)
def test_scroll_pages_accept_physical_mouse_wheel(qt_app, tmp_path, page, object_name):
    controller, engine, root = make_shell(qt_app, tmp_path)
    root.setWidth(920)
    root.setHeight(680)
    root.showPage(page)
    qt_app.processEvents()

    page_item = root.findChild(QQuickItem, object_name)
    assert page_item is not None
    assert page_item.property("contentHeight") > page_item.height()

    point = page_item.mapToScene(QPointF(page_item.width() / 2, page_item.height() / 2))
    QTest.wheelEvent(root, point, QPoint(0, -120))
    qt_app.processEvents()

    assert page_item.property("contentY") > 0
    root.close()
    engine.deleteLater()
    controller.deleteLater()


def test_activity_page_mouse_wheel_scrolls_output_from_header_and_output(qt_app, tmp_path):
    controller, engine, root = make_shell(qt_app, tmp_path)
    for index in range(120):
        controller._log(f"Activity line {index}: example output that fills the activity view")

    root.setWidth(920)
    root.setHeight(680)
    root.showPage(controller.PAGE_ACTIVITY)
    qt_app.processEvents()
    activity_list = root.findChild(QQuickItem, "activityList")
    assert activity_list is not None
    assert activity_list.property("contentHeight") > activity_list.height()

    activity_list.setProperty("contentY", 0)
    list_scene = activity_list.mapToScene(QPointF(activity_list.width() / 2, 0))
    header_point = QPointF(list_scene.x(), list_scene.y() - 35)
    QTest.wheelEvent(root, header_point, QPoint(0, -120))
    qt_app.processEvents()
    assert activity_list.property("contentY") > 0

    activity_list.setProperty("contentY", 0)
    output_point = activity_list.mapToScene(
        QPointF(activity_list.width() / 2, activity_list.height() / 2)
    )
    QTest.wheelEvent(root, output_point, QPoint(0, -120))
    qt_app.processEvents()
    assert activity_list.property("contentY") > 0

    root.close()
    engine.deleteLater()
    controller.deleteLater()


def test_activity_live_output_respects_user_scroll_until_tail(qt_app, tmp_path):
    controller, engine, root = make_shell(qt_app, tmp_path)
    root.setWidth(920)
    root.setHeight(680)
    root.showPage(controller.PAGE_ACTIVITY)
    for index in range(120):
        controller._log(f"Activity line {index}: example output that fills the activity view")
    qt_app.processEvents()
    qt_app.processEvents()

    activity_list = root.findChild(QQuickItem, "activityList")
    assert activity_list is not None
    assert activity_list.property("atYEnd") is True

    activity_list.setProperty("contentY", max(0, activity_list.property("contentY") - 300))
    qt_app.processEvents()
    scrolled_position = activity_list.property("contentY")
    assert activity_list.property("followTail") is False

    controller._log("new output while reviewing earlier activity")
    qt_app.processEvents()
    qt_app.processEvents()
    assert activity_list.property("contentY") == pytest.approx(scrolled_position, abs=1)

    output_point = activity_list.mapToScene(
        QPointF(activity_list.width() / 2, activity_list.height() / 2)
    )
    for _ in range(20):
        QTest.wheelEvent(root, output_point, QPoint(0, -120))
        qt_app.processEvents()
        if activity_list.property("atYEnd"):
            break

    assert activity_list.property("atYEnd") is True
    assert activity_list.property("followTail") is True

    controller._log("new output while following the tail")
    qt_app.processEvents()
    qt_app.processEvents()
    assert activity_list.property("atYEnd") is True

    root.close()
    engine.deleteLater()
    controller.deleteLater()
