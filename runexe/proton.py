"""Discovery and environment setup for standalone Proton launches."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path

PROTON_COMPAT_DIR = (
    Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "runexe" / "proton"
)


class ProtonError(RuntimeError):
    """Raised when Proton cannot be discovered or configured."""


@dataclass(frozen=True)
class ProtonInstallation:
    """One runnable Proton compatibility-tool installation."""

    name: str
    script: Path
    version: str | None
    steam_root: Path

    @property
    def install_dir(self) -> Path:
        return self.script.parent

    @property
    def dist_dir(self) -> Path | None:
        for name in ("files", "dist"):
            candidate = self.install_dir / name
            if candidate.is_dir():
                return candidate
        return None


@dataclass(frozen=True)
class ProtonTuningPreset:
    key: str
    label: str
    description: str
    environment: tuple[tuple[str, str], ...] = ()


PROTON_TUNING_PRESETS: tuple[ProtonTuningPreset, ...] = (
    ProtonTuningPreset("default", "Runtime defaults", "Do not override Proton behavior."),
    ProtonTuningPreset(
        "diagnostics",
        "Diagnostic logging",
        "Enable Proton, DXVK, and VKD3D logs for one application.",
        (("PROTON_LOG", "1"), ("DXVK_LOG_LEVEL", "info"), ("VKD3D_DEBUG", "warn")),
    ),
    ProtonTuningPreset(
        "wined3d",
        "WineD3D fallback",
        "Use OpenGL WineD3D instead of Vulkan DXVK for Direct3D 9-11.",
        (("PROTON_USE_WINED3D", "1"),),
    ),
    ProtonTuningPreset(
        "dxvk-hud",
        "DXVK device/FPS HUD",
        "Show the selected GPU, driver, and frame rate while troubleshooting.",
        (("DXVK_HUD", "devinfo,fps"),),
    ),
    ProtonTuningPreset(
        "no-fsync",
        "Disable fsync",
        "Disable futex-based synchronization for compatibility testing.",
        (("PROTON_NO_FSYNC", "1"),),
    ),
    ProtonTuningPreset(
        "no-ntsync",
        "Disable ntsync",
        "Disable the ntsync path for compatibility testing.",
        (("PROTON_NO_NTSYNC", "1"),),
    ),
)


def proton_tuning_preset(key: str) -> ProtonTuningPreset:
    preset = next((item for item in PROTON_TUNING_PRESETS if item.key == key), None)
    if preset is None:
        choices = ", ".join(item.key for item in PROTON_TUNING_PRESETS)
        raise ProtonError(f"Unknown Proton tuning preset '{key}'. Choose one of: {choices}.")
    return preset


def _apply_proton_tuning(env: dict[str, str], key: str) -> None:
    preset = proton_tuning_preset(key)
    env.update(preset.environment)
    if key == "diagnostics":
        state_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
        log_dir = state_home / "runexe" / "logs"
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        else:
            env["PROTON_LOG_DIR"] = str(log_dir)


def _common_steam_roots() -> list[Path]:
    roots = [
        Path.home() / ".steam" / "root",
        Path.home() / ".steam" / "steam",
        Path.home() / ".local" / "share" / "Steam",
        Path.home() / ".var" / "app" / "com.valvesoftware.Steam" / "data" / "Steam",
        Path.home() / "snap" / "steam" / "common" / ".local" / "share" / "Steam",
    ]
    configured = os.environ.get("STEAM_COMPAT_CLIENT_INSTALL_PATH") or os.environ.get("STEAM_DIR")
    if configured:
        roots.insert(0, Path(configured).expanduser())
    return roots


def _library_roots(steam_root: Path) -> list[Path]:
    roots = [steam_root]
    manifest = steam_root / "steamapps" / "libraryfolders.vdf"
    try:
        text = manifest.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return roots

    for raw_path in re.findall(r'"path"\s+"([^"]+)"', text, flags=re.IGNORECASE):
        decoded = raw_path.replace("\\\\", "\\")
        roots.append(Path(decoded).expanduser())
    return roots


def _read_version(install_dir: Path) -> str | None:
    version_file = install_dir / "version"
    try:
        if version_file.stat().st_size > 4096:
            return None
        return version_file.read_text(encoding="utf-8", errors="replace").splitlines()[0].strip()
    except (OSError, IndexError):
        return None


def _from_script(script: Path, steam_root: Path) -> ProtonInstallation | None:
    script = script.expanduser()
    if not script.is_file():
        return None
    if os.name == "posix" and not os.access(script, os.X_OK):
        return None
    install_dir = script.parent
    return ProtonInstallation(
        name=install_dir.name,
        script=script.resolve(),
        version=_read_version(install_dir),
        steam_root=steam_root.expanduser().resolve(),
    )


def _version_key(installation: ProtonInstallation) -> tuple[int, tuple[int, ...], str]:
    label = f"{installation.name} {installation.version or ''}".lower()
    numbers = tuple(int(value) for value in re.findall(r"\d+", label))
    # Experimental is Valve's rolling channel and is preferred when present.
    channel = 2 if "experimental" in label else 1
    return channel, numbers, label


def discover_proton_installations() -> list[ProtonInstallation]:
    """Find Valve and custom Proton builds across common Steam layouts."""

    installations: dict[Path, ProtonInstallation] = {}
    steam_roots = [root for root in _common_steam_roots() if root.is_dir()]
    fallback_root = steam_roots[0] if steam_roots else Path.home() / ".steam" / "root"

    custom_paths = os.environ.get("RUNEXE_PROTON_PATH", "")
    for value in filter(None, custom_paths.split(os.pathsep)):
        path = Path(value).expanduser()
        script = path / "proton" if path.is_dir() else path
        installation = _from_script(script, fallback_root)
        if installation:
            installations[installation.script] = installation

    for steam_root in steam_roots:
        for library in _library_roots(steam_root):
            common = library / "steamapps" / "common"
            if common.is_dir():
                for script in common.glob("*/proton"):
                    installation = _from_script(script, steam_root)
                    if installation:
                        installations[installation.script] = installation

        for compatibility_dir in (
            steam_root / "compatibilitytools.d",
            Path.home() / ".steam" / "root" / "compatibilitytools.d",
            Path.home() / ".steam" / "steam" / "compatibilitytools.d",
        ):
            if not compatibility_dir.is_dir():
                continue
            for script in compatibility_dir.glob("*/proton"):
                installation = _from_script(script, steam_root)
                if installation:
                    installations[installation.script] = installation

    for compatibility_dir in (
        Path("/usr/share/steam/compatibilitytools.d"),
        Path("/usr/local/share/steam/compatibilitytools.d"),
    ):
        if compatibility_dir.is_dir():
            for script in compatibility_dir.glob("*/proton"):
                installation = _from_script(script, fallback_root)
                if installation:
                    installations[installation.script] = installation

    return sorted(installations.values(), key=_version_key, reverse=True)


def select_proton(
    selector: str | Path | None = None,
    installations: list[ProtonInstallation] | None = None,
) -> ProtonInstallation:
    """Select Proton by path or unambiguous name; default to the best installed build."""

    available = installations if installations is not None else discover_proton_installations()
    if selector is None:
        if not available:
            raise ProtonError(
                "No Proton installation found. Install Proton in Steam, place a custom build "
                "in compatibilitytools.d, or set RUNEXE_PROTON_PATH."
            )
        return available[0]

    candidate = Path(selector).expanduser()
    if candidate.exists():
        script = candidate / "proton" if candidate.is_dir() else candidate
        steam_root = available[0].steam_root if available else Path.home() / ".steam" / "root"
        installation = _from_script(script, steam_root)
        if installation is None:
            raise ProtonError(f"Not a runnable Proton installation: {candidate}")
        return installation

    query = str(selector).casefold()
    exact = [
        item
        for item in available
        if query in {item.name.casefold(), (item.version or "").casefold()}
    ]
    if len(exact) == 1:
        return exact[0]
    matches = [
        item
        for item in available
        if query in item.name.casefold() or query in (item.version or "").casefold()
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ProtonError(f"No installed Proton build matches '{selector}'.")
    names = ", ".join(item.name for item in matches)
    raise ProtonError(f"Proton selector '{selector}' is ambiguous: {names}")


def compat_data_path_for(executable: Path) -> Path:
    resolved = str(executable.resolve())
    digest = hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:12]
    slug = re.sub(r"[^a-z0-9._-]+", "_", executable.stem.lower()).strip("._-") or "app"
    return PROTON_COMPAT_DIR / f"{slug}-{digest}"


def proton_environment(
    installation: ProtonInstallation,
    compat_data: Path,
    executable: Path,
    tuning: str = "default",
) -> dict[str, str]:
    """Build the environment expected by Proton's launcher script."""

    env = os.environ.copy()
    app_digest = hashlib.sha256(str(executable.resolve()).encode()).hexdigest()
    app_id = str(1_000_000_000 + int(app_digest[:8], 16) % 1_000_000_000)
    env.update(
        {
            "STEAM_COMPAT_DATA_PATH": str(compat_data),
            "STEAM_COMPAT_CLIENT_INSTALL_PATH": str(installation.steam_root),
            "STEAM_COMPAT_INSTALL_PATH": str(executable.resolve().parent),
            "STEAM_COMPAT_APP_ID": app_id,
            "SteamAppId": app_id,
            "SteamGameId": app_id,
        }
    )
    env.pop("WINEARCH", None)
    env.pop("WINEPREFIX", None)
    _apply_proton_tuning(env, tuning)
    return env


def proton_winetricks_environment(
    installation: ProtonInstallation,
    compat_data: Path,
) -> dict[str, str]:
    """Build the Wine environment Winetricks needs for a Proton prefix."""

    dist = installation.dist_dir
    if dist is None:
        raise ProtonError(f"Could not locate Proton runtime files under {installation.install_dir}")
    wine = dist / "bin" / "wine"
    wineserver = dist / "bin" / "wineserver"
    if not wine.is_file() or not wineserver.is_file():
        raise ProtonError(f"Proton Wine binaries are missing under {dist}")

    env = os.environ.copy()
    env.update(
        {
            "WINE": str(wine),
            "WINESERVER": str(wineserver),
            "WINEPREFIX": str(compat_data / "pfx"),
            "PROTON_PATH": str(installation.install_dir),
            "PROTON_DIST_PATH": str(dist),
            "PATH": str(dist / "bin") + os.pathsep + env.get("PATH", ""),
            "WINEDLLPATH": os.pathsep.join(
                str(path)
                for path in (dist / "lib64" / "wine", dist / "lib" / "wine")
                if path.is_dir()
            ),
        }
    )
    env.pop("WINEARCH", None)
    return env
