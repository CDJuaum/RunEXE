"""Optional Qt desktop interface for RunEXE."""

from __future__ import annotations

import argparse
from pathlib import Path


class GuiUnavailableError(RuntimeError):
    """Raised when the optional desktop dependencies are not installed."""


def launch_gui(initial_file: Path | None = None, qt_platform: str | None = None) -> int:
    """Start the desktop application, importing Qt only when requested."""

    from .bootstrap import preflight_qt_platform, prepare_qt_environment

    try:
        selected_platform = prepare_qt_environment(qt_platform)
        preflight_qt_platform(selected_platform)
        from .qml_app import run_gui
    except ModuleNotFoundError as error:
        if error.name and error.name.startswith("PySide6"):
            raise GuiUnavailableError(
                "The desktop interface is not installed. Run "
                "'python -m pip install runexe[gui]' and try again."
            ) from error
        raise
    except (ImportError, OSError, RuntimeError, ValueError) as error:
        raise GuiUnavailableError(str(error)) from error
    return run_gui(initial_file)


def main() -> None:
    """Entry point for the dedicated ``runexe-gui`` command."""

    parser = argparse.ArgumentParser(description="Open the RunEXE desktop interface.")
    parser.add_argument(
        "file",
        nargs="?",
        type=Path,
        help="optional EXE, AppX, or MSIX to analyze when the window opens",
    )
    parser.add_argument(
        "--platform",
        choices=("auto", "xcb", "wayland", "offscreen", "minimal"),
        default="auto",
        help="Qt display backend (default: detect Wayland/X11 with fallback)",
    )
    arguments = parser.parse_args()
    try:
        exit_code = launch_gui(arguments.file, arguments.platform)
    except GuiUnavailableError as error:
        parser.error(str(error))
    raise SystemExit(exit_code)
