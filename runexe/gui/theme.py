"""Visual system for the RunEXE desktop application."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

COLORS = {
    "background": "#08111f",
    "surface": "#0d192b",
    "surface_raised": "#12223a",
    "surface_hover": "#172b48",
    "border": "#223a5f",
    "border_focus": "#3478ff",
    "text": "#f4f8ff",
    "muted": "#91a2bd",
    "cyan": "#16d9ff",
    "blue": "#3478ff",
    "amber": "#ffb21a",
    "green": "#41d98a",
    "red": "#ff6577",
}


STYLESHEET = f"""
* {{
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 14px;
    color: {COLORS["text"]};
}}
QMainWindow, QDialog, QMessageBox, QStackedWidget, QWidget#appRoot, QWidget#scrollContent,
QWidget#scrollViewport, QWidget#comboPopupViewport {{
    background: {COLORS["background"]};
}}
QFrame#sidebar {{
    background: #091526;
    border-right: 1px solid {COLORS["border"]};
}}
QFrame#header, QFrame#statusBar {{
    background: {COLORS["background"]};
}}
QFrame[card="true"] {{
    background: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 14px;
}}
QFrame[metric="true"] {{
    background: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 12px;
}}
QFrame[recommendation="true"] {{
    background: rgba(52, 120, 255, 0.10);
    border: 1px solid rgba(22, 217, 255, 0.45);
    border-radius: 14px;
}}
QFrame#dropZone {{
    background: {COLORS["surface"]};
    border: 2px dashed {COLORS["border_focus"]};
    border-radius: 16px;
}}
QFrame#dropZone[dragActive="true"] {{
    background: rgba(52, 120, 255, 0.18);
    border-color: {COLORS["cyan"]};
}}
QFrame#dropZone:hover {{
    background: {COLORS["surface_raised"]};
    border-color: {COLORS["cyan"]};
}}
QLabel#pageTitle {{
    font-size: 26px;
    font-weight: 700;
}}
QLabel#heroTitle {{
    font-size: 24px;
    font-weight: 700;
}}
QLabel#brandTitle {{
    font-size: 20px;
    font-weight: 700;
}}
QLabel#sectionTitle {{
    font-size: 17px;
    font-weight: 650;
}}
QLabel#metricValue {{
    font-size: 20px;
    font-weight: 700;
    color: {COLORS["cyan"]};
}}
QLabel#metricValue[metricState="success"] {{
    color: {COLORS["green"]};
}}
QLabel#metricValue[metricState="warning"] {{
    color: {COLORS["amber"]};
}}
QLabel#metricValue[metricState="error"] {{
    color: {COLORS["red"]};
}}
QLabel[muted="true"] {{
    color: {COLORS["muted"]};
}}
QLabel[status="ready"] {{
    color: {COLORS["green"]};
    background: rgba(65, 217, 138, 0.10);
    border: 1px solid rgba(65, 217, 138, 0.35);
    border-radius: 10px;
    padding: 4px 10px;
    font-weight: 600;
}}
QLabel[status="warning"] {{
    color: {COLORS["amber"]};
    background: rgba(255, 178, 26, 0.10);
    border: 1px solid rgba(255, 178, 26, 0.35);
    border-radius: 10px;
    padding: 4px 10px;
    font-weight: 600;
}}
QLabel[status="error"] {{
    color: {COLORS["red"]};
    background: rgba(255, 101, 119, 0.10);
    border: 1px solid rgba(255, 101, 119, 0.35);
    border-radius: 10px;
    padding: 4px 10px;
    font-weight: 600;
}}
QPushButton {{
    min-height: 38px;
    padding: 0 16px;
    border-radius: 9px;
    border: 1px solid {COLORS["border"]};
    background: {COLORS["surface_raised"]};
    font-weight: 600;
}}
QPushButton:hover {{
    background: {COLORS["surface_hover"]};
    border-color: #355987;
}}
QPushButton:focus {{
    border-color: {COLORS["cyan"]};
}}
QPushButton:pressed {{
    background: #0b1728;
}}
QPushButton:disabled {{
    color: #61718a;
    background: #0b1524;
    border-color: #192a43;
}}
QPushButton[primary="true"] {{
    color: white;
    background: {COLORS["blue"]};
    border-color: {COLORS["blue"]};
}}
QPushButton[primary="true"]:hover {{
    background: #4385ff;
    border-color: #69a0ff;
}}
QPushButton[accent="true"] {{
    color: #171006;
    background: {COLORS["amber"]};
    border-color: {COLORS["amber"]};
}}
QPushButton[accent="true"]:hover {{
    background: #ffc14a;
}}
QPushButton[nav="true"] {{
    min-height: 46px;
    padding: 0 16px;
    text-align: left;
    color: {COLORS["muted"]};
    background: transparent;
    border: 1px solid transparent;
}}
QPushButton[nav="true"]:hover {{
    color: {COLORS["text"]};
    background: {COLORS["surface_raised"]};
}}
QPushButton[nav="true"]:checked {{
    color: {COLORS["cyan"]};
    background: rgba(52, 120, 255, 0.14);
    border-color: rgba(52, 120, 255, 0.40);
}}
QLineEdit, QComboBox, QSpinBox {{
    min-height: 38px;
    padding: 0 11px;
    background: #091525;
    border: 1px solid {COLORS["border"]};
    border-radius: 8px;
    selection-background-color: {COLORS["blue"]};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border-color: {COLORS["border_focus"]};
}}
QComboBox::drop-down {{
    width: 28px;
    border: none;
}}
QComboBox QAbstractItemView {{
    background: {COLORS["surface_raised"]};
    border: 1px solid {COLORS["border"]};
    selection-background-color: {COLORS["blue"]};
    padding: 4px;
}}
QComboBox QAbstractItemView::item {{
    background: {COLORS["surface_raised"]};
    min-height: 34px;
}}
QComboBox QAbstractItemView::item:selected {{
    background: {COLORS["blue"]};
}}
QMenu {{
    background: {COLORS["surface_raised"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 8px;
    padding: 6px;
}}
QMenu::item {{
    min-width: 190px;
    padding: 9px 14px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background: {COLORS["blue"]};
    color: white;
}}
QPlainTextEdit, QListWidget {{
    background: #07101d;
    border: 1px solid {COLORS["border"]};
    border-radius: 10px;
    padding: 8px;
    selection-background-color: {COLORS["blue"]};
}}
QPlainTextEdit {{
    font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 13px;
}}
QListWidget::item {{
    padding: 8px;
    border-bottom: 1px solid #172943;
}}
QListWidget::item:selected {{
    background: rgba(52, 120, 255, 0.18);
}}
QScrollArea {{
    border: none;
    background: transparent;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: #2d4568;
    border-radius: 4px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{
    background: #426894;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}
QToolTip {{
    color: {COLORS["text"]};
    background: {COLORS["surface_raised"]};
    border: 1px solid {COLORS["border_focus"]};
    padding: 6px;
}}
QProgressBar {{
    max-height: 4px;
    border: none;
    background: #172943;
}}
QProgressBar::chunk {{
    background: {COLORS["cyan"]};
}}
QSplitter::handle {{
    background: {COLORS["border"]};
    width: 1px;
}}
"""


def apply_theme(app: QApplication) -> None:
    """Apply a deterministic dark palette and the RunEXE component theme."""

    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(COLORS["background"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(COLORS["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(COLORS["surface"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(COLORS["surface_raised"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(COLORS["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(COLORS["surface_raised"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(COLORS["text"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(COLORS["blue"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)
    app.setStyleSheet(STYLESHEET)
