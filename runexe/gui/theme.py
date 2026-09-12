"""Restrained, palette-aware Qt styling based on KDE's desktop HIG."""

from __future__ import annotations

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication


def apply_theme(app: QApplication) -> None:
    """Keep the platform font, controls and color scheme; style only layout roles."""
    palette = app.palette()
    dark = palette.color(QPalette.ColorRole.Window).lightness() < 128
    muted = "#a9adb2" if dark else "#60666c"
    border = "#4b5056" if dark else "#d4d8dc"
    soft_border = "#3c4147" if dark else "#e3e6e9"
    sidebar = "#202328" if dark else "#f5f6f7"
    hover = "#2d3238" if dark else "#e9ecef"
    pressed = "#353b42" if dark else "#dfe3e7"
    scroll_handle = "#616870" if dark else "#aeb4ba"
    scroll_hover = "#7b838c" if dark else "#8f979f"
    success = "#8bd5a0" if dark else "#246b38"
    warning = "#f0c477" if dark else "#865b09"
    error = "#f59999" if dark else "#b52b35"
    # Native controls retain the active platform style. No global font override.
    app.setStyleSheet(f"""
        QWidget#appRoot {{ background: palette(window); }}
        QFrame#sidebar {{
            background: {sidebar};
            border-right: 1px solid {border};
        }}
        QFrame#header {{ border-bottom: 1px solid {soft_border}; }}
        QFrame#statusBar {{ border-top: 1px solid {soft_border}; }}
        QFrame#navigationRail {{ background: transparent; border: none; }}
        QLabel#navSection {{
            color: {muted};
            font-size: 9pt;
            font-weight: 600;
            padding: 8px 10px 2px 10px;
        }}
        QFrame#navIndicator {{
            background: palette(highlight);
            border: none;
            border-radius: 1px;
        }}
        QPushButton#navButton {{
            min-height: 40px;
            padding: 4px 12px;
            text-align: left;
            background: transparent;
            border: 1px solid transparent;
            border-radius: 9px;
        }}
        QPushButton#navButton:hover {{ background: {hover}; }}
        QPushButton#navButton:pressed {{ background: {pressed}; }}
        QPushButton#navButton:checked {{
            background: {hover};
            font-weight: 600;
        }}
        QPushButton#navButton:focus {{ border-color: palette(highlight); }}
        QFrame[card="true"] {{
            background: palette(base);
            border: 1px solid {border};
            border-radius: 10px;
        }}
        QFrame[metric="true"] {{ background: transparent; border: none; }}
        QFrame[recommendation="true"] {{ border-left: 3px solid {warning}; }}
        QFrame#dropZone {{
            background: palette(base);
            border: 1px solid {border};
            border-radius: 12px;
        }}
        QFrame#dropZone:hover, QFrame#dropZone:focus,
        QFrame#dropZone[dragActive="true"] {{ border: 1px solid palette(highlight); }}
        QLabel#brandTitle, QLabel#sectionTitle {{ font-weight: 600; }}
        QLabel#fileTitle {{ font-weight: 600; }}
        QLabel#metricValue {{ font-weight: 600; }}
        QLabel[muted="true"] {{ color: {muted}; }}
        QLabel#metricValue[metricState="success"], QLabel[status="ready"] {{
            color: {success};
        }}
        QLabel#metricValue[metricState="warning"], QLabel[status="warning"] {{
            color: {warning};
        }}
        QLabel#metricValue[metricState="error"], QLabel[status="error"] {{
            color: {error};
        }}
        QPushButton {{
            min-height: 30px;
            padding: 3px 12px;
            border-radius: 7px;
        }}
        QPushButton[primary="true"]:enabled {{
            background: palette(highlight);
            color: palette(highlighted-text);
            border: 1px solid palette(highlight);
            border-radius: 7px;
        }}
        QPushButton[primary="true"]:hover:enabled {{ border-color: palette(text); }}
        QPushButton[primary="true"]:focus {{ border: 2px solid palette(text); }}
        QPushButton[danger="true"]:enabled {{ color: {error}; }}
        QLineEdit, QComboBox {{
            min-height: 30px;
            padding-left: 6px;
            padding-right: 6px;
            border: 1px solid {border};
            border-radius: 7px;
            background: palette(base);
        }}
        QLineEdit:focus, QComboBox:focus {{ border-color: palette(highlight); }}
        QScrollArea {{ border: none; background: transparent; }}
        QScrollBar:vertical {{
            width: 12px;
            margin: 3px 2px 3px 2px;
            background: transparent;
        }}
        QScrollBar::handle:vertical {{
            min-height: 40px;
            background: {scroll_handle};
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical:hover,
        QScrollBar::handle:vertical:pressed {{ background: {scroll_hover}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: transparent;
        }}
        QScrollBar:horizontal {{
            height: 12px;
            margin: 2px 3px 2px 3px;
            background: transparent;
        }}
        QScrollBar::handle:horizontal {{
            min-width: 40px;
            background: {scroll_handle};
            border-radius: 4px;
        }}
        QScrollBar::handle:horizontal:hover,
        QScrollBar::handle:horizontal:pressed {{ background: {scroll_hover}; }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
            background: transparent;
        }}
        QListWidget {{
            background: palette(base);
            border: 1px solid {border};
            border-radius: 8px;
        }}
        QListWidget::item {{ padding: 9px; border-radius: 5px; }}
        QListWidget::item:selected {{
            background: palette(highlight);
            color: palette(highlighted-text);
        }}
        QPlainTextEdit {{ border: 1px solid {border}; border-radius: 8px; }}
        QProgressBar {{ max-height: 3px; border: none; }}
        QProgressBar::chunk {{ background: palette(highlight); }}
    """)
