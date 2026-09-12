"""Restrained, palette-aware Qt styling based on KDE's desktop HIG."""

from __future__ import annotations

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication


def apply_theme(app: QApplication) -> None:
    """Keep the platform font, controls and color scheme; style only layout roles."""
    palette = app.palette()
    dark = palette.color(QPalette.ColorRole.Window).lightness() < 128
    muted = "#a9adb2" if dark else "#60666c"
    border = "#55595e" if dark else "#cdd1d5"
    success = "#8bd5a0" if dark else "#246b38"
    warning = "#f0c477" if dark else "#865b09"
    error = "#f59999" if dark else "#b52b35"
    # Native controls retain the active platform style. No global font override.
    app.setStyleSheet(f"""
        QFrame#header {{ border-bottom: 1px solid {border}; }}
        QFrame#statusBar {{ border-top: 1px solid {border}; }}
        QFrame[card="true"] {{
            background: palette(base);
            border: 1px solid {border};
            border-radius: 4px;
        }}
        QFrame[metric="true"] {{ background: transparent; border: none; }}
        QFrame[recommendation="true"] {{ border-left: 3px solid {warning}; }}
        QFrame#dropZone {{
            background: palette(base);
            border: 1px solid {border};
            border-radius: 4px;
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
        QPushButton {{ min-height: 28px; padding: 2px 12px; }}
        QPushButton[primary="true"]:enabled {{
            background: palette(highlight);
            color: palette(highlighted-text);
            border: 1px solid palette(highlight);
            border-radius: 4px;
        }}
        QPushButton[primary="true"]:hover:enabled {{ border-color: palette(text); }}
        QPushButton[primary="true"]:focus {{ border: 2px solid palette(text); }}
        QPushButton[danger="true"]:enabled {{ color: {error}; }}
        QLineEdit, QComboBox {{ min-height: 28px; }}
        QTabBar::tab {{
            min-width: 116px;
            padding: 10px 18px;
            background: transparent;
            border: none;
            border-bottom: 2px solid transparent;
        }}
        QTabBar::tab:selected {{
            border-bottom-color: palette(highlight);
            font-weight: 600;
        }}
        QTabBar::tab:hover {{ background: palette(alternate-base); }}
        QScrollArea {{ border: none; background: transparent; }}
        QListWidget {{
            background: palette(base);
            border: 1px solid {border};
            border-radius: 2px;
        }}
        QListWidget::item {{ padding: 9px; }}
        QListWidget::item:selected {{
            background: palette(highlight);
            color: palette(highlighted-text);
        }}
        QPlainTextEdit {{ border: 1px solid {border}; }}
        QProgressBar {{ max-height: 3px; border: none; }}
        QProgressBar::chunk {{ background: palette(highlight); }}
    """)
