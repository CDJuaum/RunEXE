"""Launch native Wine/Proton maintenance tools for managed environments."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .environments import EnvironmentInfo
from .platform_support import find_executable, install_hint
from .proton import ProtonError, proton_environment, select_proton

CONFIGURATION_TOOLS: dict[str, tuple[str, str]] = {
    "winecfg": ("Wine settings", "winecfg"),
    "regedit": ("Registry editor", "regedit"),
    "control": ("Windows control panel", "control"),
    "uninstaller": ("Installed applications", "uninstaller"),
    "explorer": ("Wine file explorer", "explorer"),
}


class ConfigurationError(RuntimeError):
    """Raised when a native environment tool cannot be started."""


def _wine_arch(environment: EnvironmentInfo) -> str:
    marker = environment.path / ".runexe-winearch"
    try:
        value = marker.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        value = ""
    if value in {"win32", "win64"}:
        return value
    return "win32" if environment.architecture == "x86" else "win64"


def open_environment_configuration(
    environment: EnvironmentInfo,
    tool: str = "winecfg",
) -> subprocess.Popen:
    """Open a supported prefix tool without guessing or changing the target path."""

    selected = CONFIGURATION_TOOLS.get(tool)
    if selected is None:
        choices = ", ".join(CONFIGURATION_TOOLS)
        raise ConfigurationError(f"Unknown configuration tool '{tool}'. Choose one of: {choices}.")
    if not environment.ready or not environment.path.is_dir():
        raise ConfigurationError(f"Environment is incomplete or missing: {environment.path}")
    program = selected[1]

    if environment.backend == "proton":
        if not environment.runtime_path:
            raise ConfigurationError("The Proton launcher for this environment is unknown.")
        try:
            installation = select_proton(Path(environment.runtime_path))
        except ProtonError as error:
            raise ConfigurationError(str(error)) from error
        source = Path(environment.source) if environment.source else environment.path
        command = [str(installation.script), "runinprefix", program]
        env = proton_environment(installation, environment.path, source)
    else:
        helper = find_executable(program)
        wine = find_executable("wine")
        if helper:
            command = [helper]
        elif wine:
            command = [wine, program]
        else:
            raise ConfigurationError(f"Wine was not found. {install_hint('wine')}.")
        env = os.environ.copy()
        env.update(
            {
                "WINEPREFIX": str(environment.path),
                "WINEARCH": _wine_arch(environment),
            }
        )
        env.setdefault("WINEDEBUG", "-all")

    try:
        return subprocess.Popen(command, cwd=environment.path, env=env)
    except OSError as error:
        raise ConfigurationError(f"Could not open {selected[0]}: {error}") from error
