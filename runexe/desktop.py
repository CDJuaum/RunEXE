"""Freedesktop menu integration for user-level RunEXE installations."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

DESKTOP_FILENAME = "runexe.desktop"
ICON_FILENAME = "runexe.png"
MANAGED_MARKER = "X-RunEXE-Managed=true"


class DesktopIntegrationError(RuntimeError):
    """Raised when a desktop entry cannot be changed safely."""


@dataclass(frozen=True)
class DesktopPaths:
    desktop_file: Path
    icon_file: Path


def _data_home(override: Path | None = None) -> Path:
    if override is not None:
        return override.expanduser()
    configured = os.environ.get("XDG_DATA_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".local" / "share"


def desktop_paths(data_home: Path | None = None) -> DesktopPaths:
    root = _data_home(data_home)
    return DesktopPaths(
        desktop_file=root / "applications" / DESKTOP_FILENAME,
        icon_file=root / "icons" / "hicolor" / "256x256" / "apps" / ICON_FILENAME,
    )


def _require_linux(platform_name: str | None = None) -> None:
    current = platform_name or sys.platform
    if not current.startswith("linux"):
        raise DesktopIntegrationError("Desktop-menu integration is available on Linux only.")


def _icon_bytes() -> bytes:
    return resources.files("runexe").joinpath("assets", "runexe-logo.png").read_bytes()


def _quote_exec_argument(value: str) -> str:
    if "\n" in value or "\r" in value:
        raise DesktopIntegrationError("The GUI executable path contains an invalid newline.")
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    escaped = escaped.replace("`", "\\`").replace("$", "\\$").replace("%", "%%")
    return f'"{escaped}"'


def _desktop_contents(gui_executable: Path) -> str:
    executable = _quote_exec_argument(str(gui_executable))
    return "\n".join(
        (
            "[Desktop Entry]",
            "Version=1.5",
            "Type=Application",
            "Name=RunEXE",
            "GenericName=Windows Compatibility Launcher",
            "Comment=Analyze and run Windows software through Wine or Proton",
            f"Exec={executable} %f",
            "Icon=runexe",
            "Terminal=false",
            "Categories=Utility;",
            "Keywords=Wine;Proton;Windows;EXE;MSIX;AppX;",
            "MimeType=application/x-ms-dos-executable;application/vnd.microsoft.portable-executable;application/vnd.ms-appx;application/vnd.ms-appx.bundle;",
            "StartupNotify=true",
            "StartupWMClass=RunEXE",
            MANAGED_MARKER,
            "",
        )
    )


def _atomic_write(path: Path, data: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_bytes(data)
        temporary.chmod(mode)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _refresh_desktop_caches(paths: DesktopPaths) -> None:
    commands = (
        ("update-desktop-database", str(paths.desktop_file.parent)),
        (
            "gtk-update-icon-cache",
            "--force",
            "--ignore-theme-index",
            str(paths.icon_file.parents[3]),
        ),
    )
    for command in commands:
        if shutil.which(command[0]) is None:
            continue
        try:
            subprocess.run(
                command,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
            )
        except OSError:
            continue


def install_desktop_entry(
    gui_executable: Path | None = None,
    *,
    data_home: Path | None = None,
    refresh: bool = True,
    platform_name: str | None = None,
) -> DesktopPaths:
    """Install a per-user desktop entry and themed icon."""

    _require_linux(platform_name)
    selected = gui_executable
    if selected is None:
        discovered = shutil.which("runexe-gui")
        if discovered is None:
            raise DesktopIntegrationError(
                "runexe-gui was not found on PATH. Install RunEXE with the gui extra first."
            )
        selected = Path(discovered)
    selected = selected.expanduser().resolve()
    if not selected.is_file() or not os.access(selected, os.X_OK):
        raise DesktopIntegrationError(f"GUI executable is missing or not executable: {selected}")

    paths = desktop_paths(data_home)
    if paths.desktop_file.exists():
        try:
            existing = paths.desktop_file.read_text(encoding="utf-8")
        except OSError as error:
            raise DesktopIntegrationError(str(error)) from error
        if MANAGED_MARKER not in existing:
            raise DesktopIntegrationError(
                f"Refusing to replace an unmanaged desktop entry: {paths.desktop_file}"
            )

    try:
        _atomic_write(paths.icon_file, _icon_bytes(), 0o644)
        _atomic_write(
            paths.desktop_file,
            _desktop_contents(selected).encode("utf-8"),
            0o644,
        )
    except OSError as error:
        raise DesktopIntegrationError(str(error)) from error
    if refresh:
        _refresh_desktop_caches(paths)
    return paths


def remove_desktop_entry(
    *,
    data_home: Path | None = None,
    refresh: bool = True,
    platform_name: str | None = None,
) -> tuple[DesktopPaths, bool]:
    """Remove only the desktop files previously managed by RunEXE."""

    _require_linux(platform_name)
    paths = desktop_paths(data_home)
    removed = False
    if paths.desktop_file.exists():
        try:
            existing = paths.desktop_file.read_text(encoding="utf-8")
        except OSError as error:
            raise DesktopIntegrationError(str(error)) from error
        if MANAGED_MARKER not in existing:
            raise DesktopIntegrationError(
                f"Refusing to remove an unmanaged desktop entry: {paths.desktop_file}"
            )
        paths.desktop_file.unlink()
        removed = True

    if paths.icon_file.exists():
        try:
            managed_icon = paths.icon_file.read_bytes() == _icon_bytes()
        except OSError as error:
            raise DesktopIntegrationError(str(error)) from error
        if managed_icon:
            paths.icon_file.unlink()
            removed = True

    if refresh:
        _refresh_desktop_caches(paths)
    return paths, removed
