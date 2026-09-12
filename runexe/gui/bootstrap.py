"""Qt bootstrap that runs before importing any Qt GUI modules."""

from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import subprocess
from collections.abc import MutableMapping
from pathlib import Path

HEADLESS_PLATFORMS = {"offscreen", "minimal", "linuxfb", "eglfs", "vnc"}
KNOWN_PLATFORMS = {"auto", "xcb", "wayland", *HEADLESS_PLATFORMS}


def choose_qt_platform(
    requested: str | None = None,
    *,
    environment: MutableMapping[str, str] | None = None,
    system: str | None = None,
) -> str | None:
    """Choose a QPA backend with a session-aware X11/Wayland fallback."""

    environment = environment if environment is not None else os.environ
    system = system or platform.system()
    requested = requested or environment.get("RUNEXE_QT_PLATFORM") or "auto"
    requested = requested.strip().lower()
    if requested not in KNOWN_PLATFORMS:
        choices = ", ".join(sorted(KNOWN_PLATFORMS))
        raise ValueError(f"Unknown Qt platform '{requested}'. Choose one of: {choices}.")

    if requested != "auto":
        return requested
    if environment.get("QT_QPA_PLATFORM"):
        return environment["QT_QPA_PLATFORM"]
    if system != "Linux":
        return None
    if environment.get("WAYLAND_DISPLAY"):
        return "wayland;xcb" if environment.get("DISPLAY") else "wayland"
    if environment.get("DISPLAY"):
        return "xcb;wayland"
    return None


def prepare_qt_environment(requested: str | None = None) -> str | None:
    """Configure QPA before PySide6 loads and reject accidental headless starts."""

    selected = choose_qt_platform(requested)
    if platform.system() == "Linux" and selected is None:
        raise RuntimeError(
            "No Wayland or X11 session was detected. Start runexe-gui from a graphical "
            "desktop, or keep using the console UI. For automated rendering, pass "
            "--platform offscreen."
        )
    if selected:
        os.environ["QT_QPA_PLATFORM"] = selected
    if os.environ.get("RUNEXE_SOFTWARE_RENDERING", "").lower() in {"1", "true", "yes", "on"}:
        os.environ.setdefault("QT_OPENGL", "software")
        os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
    return selected


def _pyside_platform_dir() -> Path | None:
    try:
        spec = importlib.util.find_spec("PySide6")
    except (ImportError, ModuleNotFoundError, ValueError):
        return None
    if spec is None or not spec.submodule_search_locations:
        return None
    package = Path(next(iter(spec.submodule_search_locations)))
    return next(
        (
            candidate
            for candidate in (
                package / "plugins" / "platforms",
                package / "Qt" / "plugins" / "platforms",
            )
            if candidate.is_dir()
        ),
        package / "plugins" / "platforms",
    )


def _plugin_candidates(name: str) -> tuple[str, ...]:
    return {
        "xcb": ("libqxcb.so",),
        "wayland": ("libqwayland-generic.so", "libqwayland-egl.so"),
        "offscreen": ("libqoffscreen.so",),
        "minimal": ("libqminimal.so",),
    }.get(name.split(":", 1)[0], ())


def _missing_libraries(plugin: Path) -> tuple[str, ...]:
    ldd = shutil.which("ldd")
    if platform.system() != "Linux" or not ldd:
        return ()
    try:
        result = subprocess.run(
            [ldd, str(plugin)], capture_output=True, text=True, timeout=8, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return ()
    missing = {
        line.strip().split()[0]
        for line in f"{result.stdout}\n{result.stderr}".splitlines()
        if "not found" in line.lower()
    }
    return tuple(sorted(missing))


def preflight_qt_platform(selected: str | None) -> str | None:
    """Avoid Qt's process-aborting plugin error when dependencies are absent."""

    if platform.system() != "Linux" or not selected:
        return selected
    plugin_dir = _pyside_platform_dir()
    if plugin_dir is None:
        return selected

    healthy: list[str] = []
    problems: list[str] = []
    for name in selected.split(";"):
        candidates = tuple(plugin_dir / value for value in _plugin_candidates(name))
        existing = next((candidate for candidate in candidates if candidate.is_file()), None)
        if not candidates:
            healthy.append(name)
        elif existing is None:
            problems.append(f"{name}: plugin is not installed")
        else:
            missing = _missing_libraries(existing)
            if missing:
                problems.append(f"{name}: missing {', '.join(missing)}")
            else:
                healthy.append(name)

    if not healthy:
        detail = "; ".join(problems) or "no compatible Qt platform plugin was found"
        raise RuntimeError(
            f"The desktop interface cannot initialize ({detail}). Run 'runexe doctor' "
            "for the package command recommended for this distribution."
        )
    filtered = ";".join(healthy)
    if filtered != selected:
        os.environ["QT_QPA_PLATFORM"] = filtered
    return filtered
