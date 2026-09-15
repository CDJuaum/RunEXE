"""Discovery and environment setup for standalone Proton launches."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import tarfile
import tempfile
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROTON_COMPAT_DIR = (
    Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "runexe" / "proton"
)
GE_PROTON_LATEST_RELEASE_URL = (
    "https://api.github.com/repos/GloriousEggroll/proton-ge-custom/releases/latest"
)


class ProtonError(RuntimeError):
    """Raised when Proton cannot be discovered or configured."""


def managed_proton_root() -> Path:
    """Return the user-owned directory used for RunEXE-managed Proton builds."""

    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return data_home / "runexe" / "runtimes" / "proton"


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


def _normalized_host_architecture() -> str:
    machine = platform.machine().strip().lower()
    aliases = {
        "amd64": "x86_64",
        "x64": "x86_64",
        "arm64": "aarch64",
    }
    return aliases.get(machine, machine)


def _installation_matches_host(installation: ProtonInstallation) -> bool:
    """Reject architecture-specific Proton builds that do not match this host."""

    label = f"{installation.name}-{installation.version or ''}".lower()
    host = _normalized_host_architecture()
    if re.search(r"(?:^|[-_.])(aarch64|arm64)(?:$|[-_.])", label):
        return host == "aarch64"
    if re.search(r"(?:^|[-_.])(x86_64|amd64|x64)(?:$|[-_.])", label):
        return host == "x86_64"
    return True


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

    managed_root = managed_proton_root()
    if managed_root.is_dir():
        for script in managed_root.glob("*/proton"):
            installation = _from_script(script, managed_root)
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

    compatible = (item for item in installations.values() if _installation_matches_host(item))
    return sorted(compatible, key=_version_key, reverse=True)


def _github_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "RunEXE"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read(2 * 1024 * 1024 + 1)
    except OSError as error:
        raise ProtonError(f"Could not query GE-Proton releases: {error}") from error
    if len(payload) > 2 * 1024 * 1024:
        raise ProtonError("GE-Proton release metadata was unexpectedly large.")
    try:
        parsed = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProtonError("GitHub returned invalid GE-Proton release metadata.") from error
    if not isinstance(parsed, dict):
        raise ProtonError("GitHub returned invalid GE-Proton release metadata.")
    return parsed


def _latest_ge_proton_asset() -> tuple[str, str]:
    release = _github_json(GE_PROTON_LATEST_RELEASE_URL)
    tag = release.get("tag_name")
    assets = release.get("assets")
    if not isinstance(tag, str) or not tag.strip() or not isinstance(assets, list):
        raise ProtonError("The latest GE-Proton release metadata is incomplete.")

    host = _normalized_host_architecture()
    if host == "x86_64":
        architecture_suffix = "-x86_64.tar.gz"
    elif host == "aarch64":
        architecture_suffix = "-aarch64.tar.gz"
    else:
        raise ProtonError(
            f"GE-Proton is not available for host architecture '{platform.machine() or host}'."
        )

    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = asset.get("name")
        url = asset.get("browser_download_url")
        if (
            isinstance(name, str)
            and isinstance(url, str)
            and name.endswith(architecture_suffix)
            and "sha512" not in name.lower()
        ):
            release_name = name[: -len(".tar.gz")]
            if not re.fullmatch(r"[A-Za-z0-9._+-]+", release_name):
                raise ProtonError("The latest GE-Proton release name is unsafe for a local path.")
            return release_name, url
    raise ProtonError(f"The latest GE-Proton release does not contain a {host} runtime asset.")


def _download_file(
    url: str,
    destination: Path,
    *,
    max_bytes: int = 4 * 1024**3,
    progress: Callable[[int, int | None], None] | None = None,
) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "RunEXE"})
    try:
        with (
            urllib.request.urlopen(request, timeout=60) as response,
            destination.open("wb") as output,
        ):
            expected: int | None = None
            content_length = response.headers.get("Content-Length")
            if content_length:
                try:
                    parsed_length = int(content_length)
                except ValueError:
                    parsed_length = 0
                if parsed_length > 0:
                    expected = parsed_length
            total = 0
            if progress is not None:
                progress(total, expected)
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > max_bytes:
                    raise ProtonError("GE-Proton download exceeded the safety size limit.")
                output.write(chunk)
                if progress is not None:
                    progress(total, expected)
    except ProtonError:
        raise
    except OSError as error:
        raise ProtonError(f"Could not download GE-Proton: {error}") from error


def _validate_tar_member(member: tarfile.TarInfo, destination: Path) -> None:
    root = destination.resolve()
    target = (destination / member.name).resolve()
    try:
        target.relative_to(root)
    except ValueError as error:
        raise ProtonError(f"Unsafe path in GE-Proton archive: {member.name}") from error

    if member.ischr() or member.isblk() or member.isfifo():
        raise ProtonError(f"Unsupported special file in GE-Proton archive: {member.name}")
    if member.issym() or member.islnk():
        link_target = Path(member.linkname)
        if link_target.is_absolute():
            resolved_link = link_target.resolve()
        elif member.islnk():
            resolved_link = (root / link_target).resolve()
        else:
            resolved_link = (target.parent / link_target).resolve()
        try:
            resolved_link.relative_to(root)
        except ValueError as error:
            raise ProtonError(f"Unsafe link in GE-Proton archive: {member.name}") from error


def _extract_ge_proton(archive: Path, destination: Path) -> Path:
    try:
        with tarfile.open(archive, mode="r:gz") as bundle:
            members = bundle.getmembers()
            for member in members:
                _validate_tar_member(member, destination)
            bundle.extractall(destination, members=members)
    except ProtonError:
        raise
    except (OSError, tarfile.TarError) as error:
        raise ProtonError(f"Could not extract GE-Proton: {error}") from error

    roots = [path for path in destination.iterdir() if path.is_dir()]
    if len(roots) != 1 or not (roots[0] / "proton").is_file():
        raise ProtonError("GE-Proton archive did not contain one runnable Proton installation.")
    return roots[0]


def install_managed_proton(
    destination_root: Path | None = None,
    *,
    progress: Callable[[str, int | None], None] | None = None,
) -> ProtonInstallation:
    """Install the latest official GE-Proton release into RunEXE's user data directory."""

    root = (destination_root or managed_proton_root()).expanduser().resolve()
    if progress is not None:
        progress("Step 1 of 5 · Checking the latest GE-Proton release", 5)
    tag, asset_url = _latest_ge_proton_asset()
    root.mkdir(parents=True, exist_ok=True)

    existing = root / tag
    if existing.is_dir():
        installation = _from_script(existing / "proton", root)
        if installation:
            if progress is not None:
                progress(f"{tag} is already installed", 100)
            return installation

    with tempfile.TemporaryDirectory(prefix=".runexe-proton-", dir=root) as temporary:
        staging = Path(temporary)
        archive = staging / "ge-proton.tar.gz"
        extracted = staging / "extracted"
        extracted.mkdir()
        if progress is not None:
            progress(f"Step 2 of 5 · Downloading {tag}", 15)
        last_download_percent = -1

        def download_progress(received: int, expected: int | None) -> None:
            nonlocal last_download_percent
            if progress is None:
                return
            if expected:
                fraction = min(1.0, received / expected)
                current = 15 + int(fraction * 50)
                detail = f"{received / 1024**2:.0f} / {expected / 1024**2:.0f} MiB"
            else:
                current = 35
                detail = f"{received / 1024**2:.0f} MiB"
            if current == last_download_percent:
                return
            last_download_percent = current
            progress(f"Step 2 of 5 · Downloading {tag} · {detail}", current)

        _download_file(asset_url, archive, progress=download_progress)
        if progress is not None:
            progress(f"Step 3 of 5 · Verifying and extracting {tag}", 70)
        install_dir = _extract_ge_proton(archive, extracted)
        final = root / tag
        if final.exists():
            installation = _from_script(final / "proton", root)
            if installation:
                if progress is not None:
                    progress(f"{tag} is ready", 100)
                return installation
            raise ProtonError(f"Managed Proton destination already exists but is invalid: {final}")
        if progress is not None:
            progress(f"Step 4 of 5 · Finalizing {tag}", 90)
        try:
            install_dir.replace(final)
        except OSError as error:
            raise ProtonError(f"Could not finalize managed Proton installation: {error}") from error

    installation = _from_script(final / "proton", root)
    if installation is None:
        shutil.rmtree(final, ignore_errors=True)
        raise ProtonError("The installed GE-Proton runtime is not runnable.")
    if progress is not None:
        progress(f"Step 5 of 5 · {tag} is ready", 100)
    return installation


def remove_managed_proton() -> int:
    """Remove only Proton builds installed inside RunEXE's managed runtime directory."""

    configured_root = managed_proton_root().expanduser()
    if configured_root.is_symlink():
        raise ProtonError("Refusing to remove Proton from a symlinked managed runtime directory.")
    if not configured_root.exists():
        return 0
    if not configured_root.is_dir():
        raise ProtonError("Managed Proton runtime path is not a directory.")
    root = configured_root.resolve()
    removed = 0
    for child in tuple(configured_root.iterdir()):
        if child.is_symlink():
            continue
        candidate = child.resolve()
        if candidate.parent != root:
            continue
        if candidate.is_dir() and (candidate / "proton").is_file():
            shutil.rmtree(candidate)
            removed += 1
    try:
        root.rmdir()
    except OSError:
        pass
    return removed


def select_proton(
    selector: str | Path | None = None,
    installations: list[ProtonInstallation] | None = None,
) -> ProtonInstallation:
    """Select Proton by path or unambiguous name; default to the best installed build."""

    available = installations if installations is not None else discover_proton_installations()
    if selector is None:
        if not available:
            raise ProtonError(
                "No Proton installation found. Install a managed build with RunEXE, install "
                "Proton in Steam, place a custom build in compatibilitytools.d, or set "
                "RUNEXE_PROTON_PATH."
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
