"""Visual system for the RunEXE desktop application."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

COLORS = {
    "background": "#101417",
    "surface": "#181e23",
    "surface_raised": "#202930",
    "surface_hover": "#29353d",
    "border": "#303b43",
    "border_focus": "#218c7e",
    "text": "#edf3f5",
    "muted": "#a0afb8",
    "cyan": "#65d9c3",
    "blue": "#218c7e",
    "amber": "#efbc72",
    "green": "#78dba9",
    "red": "#ff8a94",
}

CHEVRON_PATH = (Path(__file__).resolve().parent.parent / "assets" / "chevron-down.svg").as_posix()

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
    background: #141a1e;
    border-right: 1px solid {COLORS["border"]};
}}
QFrame#header, QFrame#statusBar {{
    border-bottom: 1px solid {COLORS["border"]};
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
    background: rgba(101, 217, 195, 0.06);
    border: 1px solid rgba(101, 217, 195, 0.35);
    border-radius: 14px;
}}
QFrame#dropZone {{
    background: {COLORS["surface"]};
    border: 1px dashed #52646f;
    border-radius: 16px;
}}
QFrame#dropZone[dragActive="true"] {{
    background: rgba(101, 217, 195, 0.12);
    border-color: {COLORS["cyan"]};
}}
QFrame#dropZone:hover {{
    background: {COLORS["surface_raised"]};
    border-color: {COLORS["cyan"]};
}}
QLabel#pageTitle {{
    font-size: 28px;
    font-weight: 700;
}}
QLabel#heroTitle {{
    font-size: 23px;
    font-weight: 700;
}}
QLabel#brandTitle {{
    font-size: 20px;
    font-weight: 700;
}}
QLabel#sectionTitle {{
    font-size: 17px;
    font-weight: 600;
}}
QLabel#metricValue {{
    font-size: 20px;
    font-weight: 700;
    color: {COLORS["text"]};
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
    border-color: #52646f;
}}
QPushButton:focus {{
    border-color: {COLORS["cyan"]};
}}
QPushButton:pressed {{
    background: #131b20;
}}
QPushButton:disabled {{
    color: #82919a;
    background: #171e23;
    border-color: #2a343c;
}}
QPushButton[primary="true"] {{
    color: white;
    background: {COLORS["blue"]};
    border-color: {COLORS["blue"]};
}}
QPushButton[primary="true"]:hover {{
    background: #299e8f;
    border-color: #74dcc7;
}}
QPushButton[accent="true"] {{
    color: #171006;
    background: {COLORS["amber"]};
    border-color: {COLORS["amber"]};
}}
QPushButton[accent="true"]:hover {{
    background: #f6ca8a;
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
    background: rgba(101, 217, 195, 0.10);
    border-color: rgba(101, 217, 195, 0.25);
}}
QLineEdit, QComboBox, QSpinBox {{
    min-height: 38px;
    padding: 0 11px;
    background: #12191e;
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
QComboBox::down-arrow {{
    image: url("{CHEVRON_PATH}");
    width: 16px;
    height: 16px;
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
    background: #11171b;
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
    border-bottom: 1px solid #28343c;
}}
QListWidget::item:selected {{
    background: rgba(101, 217, 195, 0.12);
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
    background: #3a4b55;
    border-radius: 4px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{
    background: #5a707c;
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
    background: #28343c;
}}
QProgressBar::chunk {{
    background: {COLORS["cyan"]};
}}
QSplitter::handle {{
    background: {COLORS["border"]};
    width: 1px;
}}
QLabel#eyebrow {{
    color: {COLORS["muted"]};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 2px;
}}
QLabel#shortcutHint {{
    color: {COLORS["muted"]};
    font-size: 12px;
}}
QFrame#dropZone:focus {{
    border: 2px solid {COLORS["cyan"]};
}}
QFrame#dropZone[selected="true"] {{
    background: #192b2a;
    border: 1px solid #35564e;
}}
QPushButton[danger="true"] {{
    color: {COLORS["red"]};
}}
QPushButton[danger="true"]:hover {{
    background: #3b252b;
    border-color: {COLORS["red"]};
}}
QPushButton[primary="true"]:pressed, QPushButton[accent="true"]:pressed {{
    background: #226c61;
    color: white;
}}
QPushButton[primary="true"]:disabled, QPushButton[accent="true"]:disabled,
QPushButton[danger="true"]:disabled {{
    color: #82919a;
    background: #171e23;
    border-color: #303b43;
}}
QPushButton[nav="true"]:focus {{
    border-color: {COLORS["cyan"]};
}}
QLineEdit:disabled, QComboBox:disabled {{
    color: #82919a;
    background: #171e23;
}}
QListWidget::item {{
    margin: 3px 0;
    padding: 12px;
    border-radius: 6px;
}}
QListWidget::item:hover {{
    background: {COLORS["surface_raised"]};
}}
QListWidget::item:selected {{
    color: {COLORS["text"]};
    background: #263e3c;
    border: 1px solid #427467;
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
