"""Managed UMU launcher support for running GE-Proton outside Steam."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tarfile
import tempfile
import urllib.request
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from .platform_support import find_executable
from .proton import ProtonInstallation, proton_environment

UMU_LATEST_RELEASE_URL = (
    "https://api.github.com/repos/Open-Wine-Components/umu-launcher/releases/latest"
)
UMU_DOWNLOAD_LIMIT = 32 * 1024**2
UMU_EXECUTABLE_LIMIT = 16 * 1024**2


class UmuError(RuntimeError):
    """Raised when UMU cannot be discovered, downloaded, or prepared."""


def managed_umu_root() -> Path:
    """Return RunEXE's user-owned directory for the UMU launcher."""

    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return data_home / "runexe" / "runtimes" / "umu"


def managed_umu_executable(root: Path | None = None) -> Path | None:
    """Return the already-installed managed UMU executable, if present."""

    executable = (root or managed_umu_root()).expanduser().resolve() / "umu-run"
    return executable if executable.is_file() else None


def requires_umu(installation: ProtonInstallation) -> bool:
    """Return whether this Proton build should run through UMU outside Steam."""

    label = f"{installation.name} {installation.install_dir.name}".lower()
    return "ge-proton" in label


def umu_environment(
    installation: ProtonInstallation,
    compat_data: Path,
    executable: Path,
    tuning: str = "default",
    *,
    verb: str = "run",
) -> dict[str, str]:
    """Build the environment for a selected GE-Proton build running through UMU."""

    env = proton_environment(installation, compat_data, executable, tuning)
    prefix = compat_data / "pfx"
    prefix.mkdir(parents=True, exist_ok=True)
    env.update(
        {
            "WINEPREFIX": str(prefix),
            "PROTONPATH": str(installation.install_dir),
            "PROTON_VERB": verb,
            "GAMEID": "umu-default",
            "STORE": "none",
        }
    )
    return env


def _github_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "RunEXE"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read(2 * 1024 * 1024 + 1)
    except OSError as error:
        raise UmuError(f"Could not query UMU releases: {error}") from error
    if len(payload) > 2 * 1024 * 1024:
        raise UmuError("UMU release metadata was unexpectedly large.")
    try:
        parsed = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise UmuError("GitHub returned invalid UMU release metadata.") from error
    if not isinstance(parsed, dict):
        raise UmuError("GitHub returned invalid UMU release metadata.")
    return parsed


def _latest_umu_asset() -> tuple[str, str, str | None]:
    release = _github_json(UMU_LATEST_RELEASE_URL)
    tag = release.get("tag_name")
    assets = release.get("assets")
    if not isinstance(tag, str) or not tag.strip() or not isinstance(assets, list):
        raise UmuError("The latest UMU release metadata is incomplete.")

    normalized_tag = tag.strip()
    if not re.fullmatch(r"[A-Za-z0-9._+-]+", normalized_tag):
        raise UmuError("The latest UMU release tag is unsafe for a local path.")

    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = asset.get("name")
        url = asset.get("browser_download_url")
        digest = asset.get("digest")
        if isinstance(name, str) and isinstance(url, str) and name.endswith("-zipapp.tar"):
            return normalized_tag, url, digest if isinstance(digest, str) else None
    raise UmuError("The latest UMU release does not contain a zipapp archive.")


def _download_file(
    url: str,
    destination: Path,
    digest: str | None,
    *,
    max_bytes: int = UMU_DOWNLOAD_LIMIT,
    progress: Callable[[int, int | None], None] | None = None,
) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "RunEXE"})
    hasher = hashlib.sha256()
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
                    raise UmuError("UMU download exceeded the safety size limit.")
                hasher.update(chunk)
                output.write(chunk)
                if progress is not None:
                    progress(total, expected)
    except UmuError:
        raise
    except OSError as error:
        raise UmuError(f"Could not download UMU: {error}") from error

    if digest and digest.startswith("sha256:"):
        expected_digest = digest.removeprefix("sha256:").strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", expected_digest):
            raise UmuError("GitHub returned an invalid UMU asset digest.")
        if hasher.hexdigest() != expected_digest:
            raise UmuError("The downloaded UMU archive failed SHA-256 verification.")


def _extract_zipapp(archive: Path, destination: Path) -> None:
    """Extract only the regular ``umu-run`` zipapp from the upstream tar archive."""

    try:
        with tarfile.open(archive, mode="r:*") as bundle:
            matches = []
            for member in bundle.getmembers():
                path = PurePosixPath(member.name)
                if path.name != "umu-run":
                    continue
                if path.is_absolute() or ".." in path.parts or not member.isfile():
                    raise UmuError(f"Unsafe UMU archive member: {member.name}")
                if member.size <= 0 or member.size > UMU_EXECUTABLE_LIMIT:
                    raise UmuError("UMU zipapp had an unexpected size.")
                matches.append(member)
            if len(matches) != 1:
                raise UmuError("UMU archive did not contain exactly one runnable umu-run zipapp.")
            source = bundle.extractfile(matches[0])
            if source is None:
                raise UmuError("Could not read umu-run from the UMU archive.")
            with source, destination.open("wb") as output:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
    except UmuError:
        raise
    except (OSError, tarfile.TarError) as error:
        raise UmuError(f"Could not extract UMU: {error}") from error
    destination.chmod(0o755)


def install_managed_umu(
    destination_root: Path | None = None,
    *,
    progress: Callable[[str, int | None], None] | None = None,
) -> Path:
    """Download the latest official UMU zipapp into RunEXE's user data directory."""

    root = (destination_root or managed_umu_root()).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    if progress is not None:
        progress("Step 1 of 4 · Checking the latest UMU release", 5)
    tag, asset_url, digest = _latest_umu_asset()

    with tempfile.TemporaryDirectory(prefix=".runexe-umu-", dir=root) as temporary:
        staging = Path(temporary)
        archive = staging / "umu.zipapp.tar"
        staged_executable = staging / "umu-run"
        if progress is not None:
            progress(f"Step 2 of 4 · Downloading UMU {tag}", 15)
        last_download_percent = -1

        def download_progress(received: int, expected: int | None) -> None:
            nonlocal last_download_percent
            if progress is None:
                return
            if expected:
                fraction = min(1.0, received / expected)
                current = 15 + int(fraction * 50)
            else:
                current = 35
            if current == last_download_percent:
                return
            last_download_percent = current
            progress(f"Step 2 of 4 · Downloading UMU {tag}", current)

        _download_file(asset_url, archive, digest, progress=download_progress)
        if progress is not None:
            verification = "verified" if digest and digest.startswith("sha256:") else "downloaded"
            progress(f"Step 3 of 4 · Extracting {verification} UMU zipapp", 75)
        _extract_zipapp(archive, staged_executable)

        final = root / "umu-run"
        try:
            staged_executable.replace(final)
            (root / "VERSION").write_text(f"{tag}\n", encoding="utf-8")
        except OSError as error:
            raise UmuError(f"Could not finalize managed UMU installation: {error}") from error

    if not final.is_file():
        raise UmuError("The managed UMU launcher was not installed correctly.")
    if progress is not None:
        progress(f"Step 4 of 4 · UMU {tag} is ready", 100)
    return final


def remove_managed_umu() -> bool:
    """Remove only the UMU launcher installed in RunEXE's user-owned runtime directory."""

    configured_root = managed_umu_root().expanduser()
    if configured_root.is_symlink():
        raise UmuError("Refusing to remove UMU from a symlinked managed runtime directory.")
    if not configured_root.exists():
        return False
    if not configured_root.is_dir():
        raise UmuError("Managed UMU runtime path is not a directory.")
    root = configured_root.resolve()
    removed = False
    for name in ("umu-run", "VERSION"):
        candidate = root / name
        if candidate.is_symlink():
            raise UmuError(f"Refusing to remove unsafe managed UMU path: {candidate}")
        if not candidate.exists():
            continue
        if not candidate.is_file() or candidate.resolve().parent != root:
            raise UmuError(f"Refusing to remove unsafe managed UMU path: {candidate}")
        candidate.unlink()
        removed = True
    try:
        root.rmdir()
    except OSError:
        pass
    return removed


def ensure_umu_launcher(
    *,
    progress: Callable[[str, int | None], None] | None = None,
) -> str:
    """Return an UMU executable, installing the official zipapp if necessary."""

    system = find_executable("umu-run")
    if system:
        if progress is not None:
            progress("System UMU launcher is ready", 100)
        return system
    managed = managed_umu_executable()
    if managed is not None:
        if progress is not None:
            progress("Managed UMU launcher is ready", 100)
        return str(managed)
    return str(install_managed_umu(progress=progress))
