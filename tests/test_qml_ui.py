import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from runexe.gui.controller import RunEXEController
from runexe.gui.qml_app import create_engine
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


def test_qml_shell_loads_all_seven_pages(qt_app, tmp_path):
    controller, engine, root = make_shell(qt_app, tmp_path)

    assert root.property("minimumWidth") == 920
    assert root.property("minimumHeight") == 680
    for page in range(7):
        root.showPage(page)
        qt_app.processEvents()
        assert root.property("currentPage") == page

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
