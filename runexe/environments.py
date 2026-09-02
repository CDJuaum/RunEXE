"""Inventory and guarded lifecycle operations for RunEXE-owned environments."""

from __future__ import annotations

import json
import os
import shutil
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .graphics import detect_dxvk

METADATA_NAME = ".runexe-environment.json"
MAX_METADATA_BYTES = 64 * 1024


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def managed_roots() -> tuple[Path, Path]:
    # Lazy imports avoid a cycle: runner writes metadata after preparation.
    from .proton import PROTON_COMPAT_DIR
    from .runner import PREFIXES_DIR

    return PREFIXES_DIR, PROTON_COMPAT_DIR


@dataclass(frozen=True)
class EnvironmentInfo:
    identifier: str
    backend: str
    path: Path
    application: str
    source: str | None
    architecture: str | None
    runtime: str | None
    runtime_path: str | None
    windows_version: str | None
    dxvk_available: bool | None
    dxvk_source: str
    dxvk_components: tuple[str, ...]
    size_bytes: int
    modified_at: str
    ready: bool

    def as_dict(self) -> dict:
        value = asdict(self)
        value["path"] = str(self.path)
        return value


def write_environment_metadata(
    path: Path,
    *,
    backend: str,
    source: Path,
    architecture: str,
    runtime: str,
    windows_version: str | None,
    runtime_path: str | None = None,
) -> None:
    """Atomically tag an initialized environment for later management."""

    metadata_path = path / METADATA_NAME
    created_at = _now()
    existing: dict = {}
    try:
        existing = _read_metadata(path)
        if isinstance(existing.get("created_at"), str):
            created_at = existing["created_at"]
    except OSError:
        pass
    value = {
        "schema": 1,
        "backend": backend,
        "source": str(source.expanduser().resolve()),
        "application": source.stem,
        "architecture": architecture,
        "runtime": runtime,
        "runtime_path": runtime_path,
        "windows_version": (
            windows_version
            if windows_version is not None
            else existing.get("windows_version")
            if isinstance(existing.get("windows_version"), str)
            else None
        ),
        "created_at": created_at,
        "last_used": _now(),
    }
    path.mkdir(parents=True, exist_ok=True)
    temporary = metadata_path.with_name(
        f".{metadata_path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    )
    try:
        temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        if os.name == "posix":
            temporary.chmod(0o600)
        temporary.replace(metadata_path)
    finally:
        temporary.unlink(missing_ok=True)


def _read_metadata(path: Path) -> dict:
    metadata_path = path / METADATA_NAME
    try:
        if metadata_path.stat().st_size > MAX_METADATA_BYTES:
            return {}
        value = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def directory_size(path: Path) -> int:
    """Return allocated file sizes without following environment symlinks."""

    total = 0
    stack = [path]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            total += entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue
        except OSError:
            continue
    return total


def discover_environments(
    roots: tuple[Path, Path] | None = None,
) -> list[EnvironmentInfo]:
    """Find only direct children of RunEXE's managed Wine and Proton roots."""

    wine_root, proton_root = roots or managed_roots()
    result: list[EnvironmentInfo] = []
    for backend, root in (("wine", wine_root), ("proton", proton_root)):
        try:
            candidates = list(root.iterdir())
        except OSError:
            continue
        for path in candidates:
            if not path.is_dir() or path.is_symlink() or path.name.startswith(".runexe-"):
                continue
            metadata = _read_metadata(path)
            source = metadata.get("source") if isinstance(metadata.get("source"), str) else None
            application = metadata.get("application")
            if not isinstance(application, str) or not application:
                application = path.name.rsplit("-", 1)[0].replace("_", " ")
            try:
                modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(
                    timespec="seconds"
                )
            except OSError:
                modified = "unknown"
            last_used = metadata.get("last_used")
            runtime_path = (
                metadata.get("runtime_path")
                if isinstance(metadata.get("runtime_path"), str)
                else None
            )
            if backend == "proton" and runtime_path is None:
                try:
                    marker_lines = (
                        (path / ".runexe-proton")
                        .read_text(encoding="utf-8", errors="replace")
                        .splitlines()
                    )
                except OSError:
                    marker_lines = []
                runtime_path = marker_lines[0] if marker_lines else None
            dxvk = detect_dxvk(
                path / "pfx" if backend == "proton" else path,
                backend=backend,
                proton_script=Path(runtime_path) if runtime_path else None,
            )
            result.append(
                EnvironmentInfo(
                    identifier=f"{backend}:{path.name}",
                    backend=backend,
                    path=path.resolve(),
                    application=application,
                    source=source,
                    architecture=(
                        metadata.get("architecture")
                        if isinstance(metadata.get("architecture"), str)
                        else None
                    ),
                    runtime=(
                        metadata.get("runtime")
                        if isinstance(metadata.get("runtime"), str)
                        else None
                    ),
                    runtime_path=runtime_path,
                    windows_version=(
                        metadata.get("windows_version")
                        if isinstance(metadata.get("windows_version"), str)
                        else None
                    ),
                    dxvk_available=dxvk.available,
                    dxvk_source=dxvk.source,
                    dxvk_components=dxvk.components,
                    size_bytes=directory_size(path),
                    modified_at=last_used if isinstance(last_used, str) else modified,
                    ready=(path / "drive_c").is_dir()
                    if backend == "wine"
                    else (path / "pfx" / "drive_c").is_dir(),
                )
            )
    return sorted(result, key=lambda item: item.modified_at, reverse=True)


def remove_managed_environment(
    path: Path,
    roots: tuple[Path, Path] | None = None,
) -> None:
    """Delete one validated direct child of a RunEXE environment root."""

    expanded = path.expanduser()
    if expanded.is_symlink():
        raise ValueError(f"Managed environment does not exist or is unsafe: {expanded}")
    candidate = expanded.resolve()
    resolved_roots = tuple(root.expanduser().resolve() for root in (roots or managed_roots()))
    if candidate.parent not in resolved_roots:
        raise ValueError("Refusing to remove a directory outside RunEXE's managed roots.")
    if not candidate.is_dir() or candidate.is_symlink():
        raise ValueError(f"Managed environment does not exist or is unsafe: {candidate}")
    quarantine = candidate.parent / f".runexe-removing-{candidate.name}-{uuid.uuid4().hex[:8]}"
    candidate.rename(quarantine)
    try:
        shutil.rmtree(quarantine)
    except OSError as error:
        raise OSError(
            f"Environment was isolated at {quarantine}, but could not be fully removed: {error}"
        ) from error


def format_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"
