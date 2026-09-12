"""Small reusable widgets shared by RunEXE desktop pages."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRect,
    QSize,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import (
    QDragEnterEvent,
    QDragLeaveEvent,
    QDropEvent,
    QIcon,
    QKeyEvent,
    QMouseEvent,
    QResizeEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QScroller,
    QStackedWidget,
    QStyle,
    QVBoxLayout,
    QWidget,
)


def navigation_icon(kind: int) -> QIcon:
    """Use desktop theme icons with portable Qt fallbacks."""
    names = ("application-x-executable", "configure", "folder", "utilities-terminal")
    fallbacks = (
        QStyle.StandardPixmap.SP_DesktopIcon,
        QStyle.StandardPixmap.SP_ComputerIcon,
        QStyle.StandardPixmap.SP_DirIcon,
        QStyle.StandardPixmap.SP_FileDialogDetailedView,
    )
    return QIcon.fromTheme(names[kind], QApplication.style().standardIcon(fallbacks[kind]))


class NavigationRail(QFrame):
    """Compactable sidebar navigation with a lightweight animated selection marker."""

    currentChanged = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("navigationRail")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Main navigation")
        self._buttons: list[QPushButton] = []
        self._labels: list[str] = []
        self._tooltips: list[str] = []
        self._current_index = -1
        self._compact = False

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(5)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._indicator = QFrame(self)
        self._indicator.setObjectName("navIndicator")
        self._indicator.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._indicator.hide()
        self._indicator_animation = QPropertyAnimation(self._indicator, b"geometry", self)
        self._indicator_animation.setDuration(140)
        self._indicator_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def addTab(self, icon: QIcon, text: str) -> int:  # noqa: N802 - mirrors QTabBar's API
        index = len(self._buttons)
        button = QPushButton(icon, text, self)
        button.setObjectName("navButton")
        button.setCheckable(True)
        button.setAutoExclusive(True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setIconSize(QSize(19, 19))
        button.setAccessibleName(text)
        button.clicked.connect(
            lambda _checked=False, selected=index: self.setCurrentIndex(selected)
        )
        self._buttons.append(button)
        self._labels.append(text)
        self._tooltips.append("")
        self._layout.addWidget(button)
        if self._current_index < 0:
            self._current_index = 0
            button.setChecked(True)
            QTimer.singleShot(0, lambda: self._place_indicator(0, animate=False))
        return index

    def tabText(self, index: int) -> str:  # noqa: N802 - compatibility with QTabBar callers
        return self._labels[index]

    def setTabToolTip(self, index: int, text: str) -> None:  # noqa: N802
        self._tooltips[index] = text
        self._buttons[index].setToolTip(text)

    def currentIndex(self) -> int:  # noqa: N802
        return self._current_index

    def setCurrentIndex(self, index: int) -> None:  # noqa: N802
        if not 0 <= index < len(self._buttons):
            return
        changed = index != self._current_index
        self._current_index = index
        self._buttons[index].setChecked(True)
        self._place_indicator(index, animate=self.isVisible())
        if changed:
            self.currentChanged.emit(index)

    def setCompact(self, compact: bool) -> None:  # noqa: N802
        if self._compact == compact:
            return
        self._compact = compact
        for index, button in enumerate(self._buttons):
            button.setText("" if compact else self._labels[index])
            button.setToolTip(self._tooltips[index] or self._labels[index])
            button.setAccessibleName(self._labels[index])
        QTimer.singleShot(0, lambda: self._place_indicator(self._current_index, animate=False))

    def isCompact(self) -> bool:  # noqa: N802
        return self._compact

    def _indicator_geometry(self, index: int) -> QRect:
        button = self._buttons[index]
        height = max(18, button.height() - 16)
        return QRect(1, button.y() + (button.height() - height) // 2, 3, height)

    def _place_indicator(self, index: int, *, animate: bool) -> None:
        if not 0 <= index < len(self._buttons):
            return
        target = self._indicator_geometry(index)
        self._indicator_animation.stop()
        if not self._indicator.isVisible() or not animate:
            self._indicator.setGeometry(target)
            self._indicator.show()
            self._indicator.raise_()
            return
        self._indicator_animation.setStartValue(self._indicator.geometry())
        self._indicator_animation.setEndValue(target)
        self._indicator_animation.start()
        self._indicator.raise_()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 - Qt API
        self._place_indicator(self._current_index, animate=False)
        super().resizeEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt API
        if not self._buttons:
            super().keyPressEvent(event)
            return
        if event.key() in {Qt.Key.Key_Down, Qt.Key.Key_Right}:
            self.setCurrentIndex((self._current_index + 1) % len(self._buttons))
            event.accept()
            return
        if event.key() in {Qt.Key.Key_Up, Qt.Key.Key_Left}:
            self.setCurrentIndex((self._current_index - 1) % len(self._buttons))
            event.accept()
            return
        if event.key() == Qt.Key.Key_Home:
            self.setCurrentIndex(0)
            event.accept()
            return
        if event.key() == Qt.Key.Key_End:
            self.setCurrentIndex(len(self._buttons) - 1)
            event.accept()
            return
        super().keyPressEvent(event)


class AnimatedStackedWidget(QStackedWidget):
    """Stacked pages with one reusable, GPU-cheap position transition."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("pageStack")
        self._transition = QPropertyAnimation(None, b"pos", self)
        self._transition.setDuration(125)
        self._transition.setEasingCurve(QEasingCurve.Type.OutCubic)

    @property
    def transition_animation(self) -> QPropertyAnimation:
        return self._transition

    def show_page(self, index: int) -> None:
        if not 0 <= index < self.count():
            return
        if self.currentIndex() == index:
            return
        self._transition.stop()
        self.setCurrentIndex(index)
        page = self.currentWidget()
        if page is None or not self.isVisible():
            return
        end = page.pos()
        self._transition.setTargetObject(page)
        self._transition.setStartValue(QPoint(end.x() + 10, end.y()))
        self._transition.setEndValue(end)
        self._transition.start()


class MetricGrid(QWidget):
    """Keep summary cards in a single row when the workspace has room."""

    def __init__(self, cards: list[QWidget], *, narrow_columns: int = 2) -> None:
        super().__init__()
        self._cards = cards
        self._narrow_columns = narrow_columns
        self._columns = 0
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(12)
        self._reflow(narrow_columns)

    def _reflow(self, columns: int) -> None:
        if columns == self._columns:
            return
        for card in self._cards:
            self._grid.removeWidget(card)
        for column in range(len(self._cards)):
            self._grid.setColumnStretch(column, int(column < columns))
        for index, card in enumerate(self._cards):
            self._grid.addWidget(card, index // columns, index % columns)
        self._columns = columns

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 - Qt API
        self._reflow(len(self._cards) if event.size().width() >= 820 else self._narrow_columns)
        super().resizeEvent(event)


class SmoothScrollArea(QScrollArea):
    """A touch-friendly scroll area with short, interruptible wheel easing."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setAutoFillBackground(True)
        self.viewport().setObjectName("scrollViewport")
        self.viewport().setAutoFillBackground(True)
        self.verticalScrollBar().setSingleStep(36)
        self._scroll_target = 0
        self._scroll_animation = QVariantAnimation(self)
        self._scroll_animation.setDuration(170)
        self._scroll_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._scroll_animation.valueChanged.connect(
            lambda value: self.verticalScrollBar().setValue(int(value))
        )
        QScroller.grabGesture(self.viewport(), QScroller.ScrollerGestureType.TouchGesture)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 - Qt API
        pixel_delta = event.pixelDelta().y()
        angle_delta = event.angleDelta().y()
        if pixel_delta:
            # Touchpads already deliver smooth pixels; do not add animation lag.
            self._scroll_animation.stop()
            bar = self.verticalScrollBar()
            bar.setValue(bar.value() - pixel_delta)
            self._scroll_target = bar.value()
            event.accept()
            return
        elif angle_delta:
            distance = int(-angle_delta / 120 * 108)
        else:
            super().wheelEvent(event)
            return

        bar = self.verticalScrollBar()
        if self._scroll_animation.state() != QAbstractAnimation.State.Running:
            self._scroll_target = bar.value()
        self._scroll_target = max(bar.minimum(), min(bar.maximum(), self._scroll_target + distance))
        self._scroll_animation.stop()
        self._scroll_animation.setStartValue(bar.value())
        self._scroll_animation.setEndValue(self._scroll_target)
        self._scroll_animation.start()
        event.accept()


class Card(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("card", True)


class MetricCard(QFrame):
    def __init__(self, caption: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("metric", True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(5)
        self.caption = QLabel(caption)
        self.caption.setProperty("muted", True)
        self.value = QLabel("Not analyzed")
        self.value.setObjectName("metricValue")
        self.value.setWordWrap(True)
        value_font = self.value.font()
        value_font.setPointSizeF(value_font.pointSizeF() + 2)
        self.value.setFont(value_font)
        self.detail = QLabel("Select Windows software to begin")
        self.detail.setProperty("muted", True)
        self.detail.setWordWrap(True)
        layout.addWidget(self.caption)
        layout.addWidget(self.value)
        layout.addWidget(self.detail)

    def set_data(self, value: str, detail: str = "", state: str = "neutral") -> None:
        if (
            self.value.text() == value
            and self.detail.text() == detail
            and self.value.property("metricState") == state
        ):
            return
        self.value.setText(value)
        self.detail.setText(detail)
        if self.value.property("metricState") != state:
            self.value.setProperty("metricState", state)
            self.value.style().unpolish(self.value)
            self.value.style().polish(self.value)


class StatusPill(QLabel):
    def __init__(self, text: str = "Not checked", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.set_status(text, "warning")

    def set_status(self, text: str, state: str) -> None:
        if self.text() == text and self.property("status") == state:
            return
        self.setText(text)
        self.setProperty("status", state)
        self.style().unpolish(self)
        self.style().polish(self)


class DropZone(QFrame):
    file_selected = Signal(str)
    browse_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Application file picker")
        self.setMinimumHeight(88)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._path: Path | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(16)
        icon = QLabel()
        icon.setPixmap(navigation_icon(0).pixmap(40, 40))
        layout.addWidget(icon)
        text = QVBoxLayout()
        text.setSpacing(4)
        self.title = QLabel("Open a Windows application")
        self.title.setObjectName("fileTitle")
        title_font = self.title.font()
        title_font.setPointSizeF(title_font.pointSizeF() + 3)
        self.title.setFont(title_font)
        self.title.setWordWrap(True)
        self.subtitle = QLabel("Drop an EXE, AppX, or MSIX here, or choose Open.")
        self.subtitle.setProperty("muted", True)
        self.subtitle.setWordWrap(False)
        text.addWidget(self.title)
        text.addWidget(self.subtitle)
        layout.addLayout(text, 1)

    @property
    def path(self) -> Path | None:
        return self._path

    def set_path(self, path: Path) -> None:
        self._path = path
        self.title.setText(path.name)
        self.setToolTip(str(path))
        self._refresh_path_text(self.size())

    def _refresh_path_text(self, size: QSize) -> None:
        if self._path is None:
            return
        available = max(80, size.width() - 108)
        self.subtitle.setText(
            self.subtitle.fontMetrics().elidedText(
                str(self._path), Qt.TextElideMode.ElideMiddle, available
            )
        )

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 - Qt API
        self._refresh_path_text(event.size())
        super().resizeEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802 - Qt API
        if event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):
            self.setProperty("dragActive", True)
            self.style().unpolish(self)
            self.style().polish(self)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:  # noqa: N802 - Qt API
        self.setProperty("dragActive", False)
        self.style().unpolish(self)
        self.style().polish(self)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802 - Qt API
        local = next(
            (url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()), ""
        )
        if local:
            self.setProperty("dragActive", False)
            self.style().unpolish(self)
            self.style().polish(self)
            self.file_selected.emit(local)
            event.acceptProposedAction()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton:
            self.browse_requested.emit()
        super().mousePressEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt API
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space}:
            self.browse_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)
