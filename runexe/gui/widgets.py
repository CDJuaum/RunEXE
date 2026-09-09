"""Small reusable widgets shared by RunEXE desktop pages."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QSize,
    Qt,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDropEvent,
    QIcon,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QResizeEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QScrollArea,
    QScroller,
    QVBoxLayout,
    QWidget,
)

from .theme import COLORS


def navigation_icon(kind: int) -> QIcon:
    """Draw crisp, consistent navigation marks without platform icon dependencies."""
    pixmap = QPixmap(40, 40)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(COLORS["muted"]), 2.5))
    if kind == 0:
        for x, y in ((6, 6), (24, 6), (6, 24), (24, 24)):
            painter.drawRoundedRect(x, y, 10, 10, 2, 2)
    elif kind == 1:
        for y, x in ((10, 14), (20, 27), (30, 18)):
            painter.drawLine(5, y, 35, y)
            painter.setBrush(QColor(COLORS["surface"]))
            painter.drawEllipse(x - 3, y - 3, 6, 6)
    elif kind == 2:
        painter.drawRoundedRect(5, 8, 30, 27, 3, 3)
        painter.drawLine(5, 16, 35, 16)
        painter.drawLine(15, 23, 25, 23)
    else:
        painter.drawLine(6, 12, 14, 20)
        painter.drawLine(14, 20, 6, 28)
        painter.drawLine(21, 28, 34, 28)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)


class MetricGrid(QWidget):
    """Keep summary cards in a single row when the workspace has room."""

    def __init__(self, cards: list[QWidget]) -> None:
        super().__init__()
        self._cards = cards
        self._columns = 0
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(12)
        self._reflow(2)

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
        self._reflow(len(self._cards) if event.size().width() >= 820 else 2)
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
            distance = -pixel_delta
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
        self._color_animation = QVariantAnimation(self)
        self._color_animation.setDuration(180)
        self._color_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(5)
        self.caption = QLabel(caption)
        self.caption.setProperty("muted", True)
        self.value = QLabel("Not analyzed")
        self.value.setObjectName("metricValue")
        self.value.setWordWrap(True)
        self._color_animation.valueChanged.connect(
            lambda color: self.value.setStyleSheet(f"color: {color.name()};")
        )
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
        self.value.setProperty("metricState", state)
        self.value.style().unpolish(self.value)
        self.value.style().polish(self.value)
        colors = {
            "success": QColor(COLORS["green"]),
            "warning": QColor(COLORS["amber"]),
            "error": QColor(COLORS["red"]),
            "neutral": QColor(COLORS["text"]),
        }
        self._color_animation.stop()
        self._color_animation.setStartValue(QColor(COLORS["muted"]))
        self._color_animation.setEndValue(colors.get(state, colors["neutral"]))
        self._color_animation.start()


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
        self.setMinimumHeight(124)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._path: Path | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(7)
        self.title = QLabel("Drop an EXE, AppX, or MSIX here")
        self.title.setObjectName("sectionTitle")
        self.title.setWordWrap(True)
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle = QLabel("or click to browse your files")
        self.subtitle.setProperty("muted", True)
        self.subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle.setWordWrap(False)
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)

    @property
    def path(self) -> Path | None:
        return self._path

    def set_path(self, path: Path) -> None:
        self._path = path
        self.setProperty("selected", True)
        self.style().unpolish(self)
        self.style().polish(self)
        self.title.setText(path.name)
        self.setToolTip(str(path))
        self._refresh_path_text(self.size())

    def _refresh_path_text(self, size: QSize) -> None:
        if self._path is None:
            return
        available = max(120, size.width() - 80)
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
