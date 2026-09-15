"""AppX/MSIX package discovery and safe materialization for Wine launches."""

from __future__ import annotations

import hashlib
import os
import platform
import re
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree

from .models import PackageInfo

PACKAGE_EXTENSIONS = {".appx", ".msix", ".appxbundle", ".msixbundle"}
PACKAGE_CACHE_DIR = (
    Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "runexe" / "packages"
)
MAX_PACKAGE_FILES = 20_000
BASE_PACKAGE_BYTES = 512 * 1024 * 1024
MAX_PACKAGE_BYTES = 32 * 1024 * 1024 * 1024
PACKAGE_EXPANSION_FACTOR = 16
PACKAGE_DISK_RESERVE_BYTES = 256 * 1024 * 1024


class PackageError(ValueError):
    """Raised when a package cannot be inspected safely."""


def _format_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def _package_byte_limit(archive_size: int) -> int:
    """Return an automatic extraction allowance for an archive of *archive_size* bytes."""

    return min(
        MAX_PACKAGE_BYTES,
        max(BASE_PACKAGE_BYTES, archive_size * PACKAGE_EXPANSION_FACTOR),
    )


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(parent: ElementTree.Element, name: str) -> ElementTree.Element | None:
    return next((item for item in parent if _local_name(item.tag) == name), None)


def _children(parent: ElementTree.Element, name: str) -> list[ElementTree.Element]:
    return [item for item in parent.iter() if _local_name(item.tag) == name]


def _safe_relative_path(value: str) -> Path:
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise PackageError(f"Unsafe package path in manifest: {value}")
    if re.match(r"^[A-Za-z]:", normalized):
        raise PackageError(f"Unsafe package path in manifest: {value}")
    return Path(*path.parts)


def _parse_manifest(manifest_path: Path, source: Path, root: Path) -> tuple[PackageInfo, Path]:
    try:
        document = ElementTree.parse(manifest_path)
    except (ElementTree.ParseError, OSError) as error:
        raise PackageError(f"Could not read package manifest: {manifest_path}") from error

    identity = next(
        (item for item in document.getroot() if _local_name(item.tag) == "Identity"), None
    )
    if identity is None or not identity.get("Name"):
        raise PackageError("Package manifest has no usable Identity element")

    properties = next(
        (item for item in document.getroot() if _local_name(item.tag) == "Properties"), None
    )
    display_name = None
    if properties is not None:
        display = _child(properties, "DisplayName")
        display_name = display.text.strip() if display is not None and display.text else None

    applications = _children(document.getroot(), "Application")
    candidates: list[tuple[ElementTree.Element, Path]] = []
    for application in applications:
        executable_name = application.get("Executable")
        if not executable_name:
            continue
        relative = _safe_relative_path(executable_name)
        executable = (root / relative).resolve()
        if root.resolve() not in executable.parents or not executable.is_file():
            continue
        candidates.append((application, executable))

    if not candidates:
        raise PackageError("Package manifest does not declare an executable available to Wine")

    application, executable = candidates[0]
    # Keep the selected path in the package metadata without adding a second public model
    # field; callers can derive it from the manifest and package root.
    return PackageInfo(
        source=source,
        root=root,
        manifest=manifest_path,
        identity_name=identity.get("Name", ""),
        version=identity.get("Version"),
        publisher=identity.get("Publisher"),
        display_name=display_name
        if display_name and not display_name.startswith("ms-resource:")
        else None,
        application_id=application.get("Id"),
        package_type="AppX/MSIX",
    ), executable


def _package_manifest(root: Path) -> Path:
    manifest = root / "AppxManifest.xml"
    if manifest.is_file():
        return manifest
    manifests = sorted(root.rglob("AppxManifest.xml"))
    if len(manifests) == 1:
        return manifests[0]
    if not manifests:
        raise PackageError(f"No AppxManifest.xml found in package: {root}")
    raise PackageError("Package contains multiple AppxManifest.xml files")


def _extract_archive(archive: Path, destination: Path) -> None:
    try:
        with zipfile.ZipFile(archive) as package:
            members = package.infolist()
            if len(members) > MAX_PACKAGE_FILES:
                raise PackageError("Package contains too many files")

            archive_size = archive.stat().st_size
            byte_limit = _package_byte_limit(archive_size)
            total_size = 0
            validated_members: list[tuple[zipfile.ZipInfo, Path]] = []
            for member in members:
                relative = _safe_relative_path(member.filename)
                mode = member.external_attr >> 16
                if mode & 0o170000 == 0o120000:
                    raise PackageError("Symbolic links are not allowed in packages")
                total_size += member.file_size
                if total_size > byte_limit:
                    raise PackageError(
                        "Package expands beyond its automatic safety limit "
                        f"({_format_bytes(total_size)} required, {_format_bytes(byte_limit)} "
                        "allowed)."
                    )
                validated_members.append((member, relative))

            free_bytes = shutil.disk_usage(destination).free
            required_bytes = total_size + PACKAGE_DISK_RESERVE_BYTES
            if required_bytes > free_bytes:
                raise PackageError(
                    "Not enough free disk space to extract package "
                    f"({_format_bytes(required_bytes)} needed including safety reserve, "
                    f"{_format_bytes(free_bytes)} available)."
                )

            for member, relative in validated_members:
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                if not member.is_dir():
                    with package.open(member) as source, target.open("wb") as output:
                        shutil.copyfileobj(source, output, length=1024 * 1024)
    except zipfile.BadZipFile as error:
        raise PackageError(f"Not a valid AppX/MSIX archive: {archive}") from error
    except OSError as error:
        raise PackageError(f"Could not extract package: {archive}") from error


def _cache_key(path: Path) -> str:
    stat = path.stat()
    value = f"{path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}".encode()
    return hashlib.sha256(value).hexdigest()[:20]


def _materialize_archive(path: Path) -> Path:
    destination = PACKAGE_CACHE_DIR / f"{path.stem.lower()}-{_cache_key(path)}"
    marker = destination / ".complete"
    if marker.is_file():
        return destination

    PACKAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".extract-", dir=PACKAGE_CACHE_DIR))
    try:
        _extract_archive(path, temporary)
        marker_path = temporary / ".complete"
        marker_path.write_text("ok\n", encoding="utf-8")
        temporary.replace(destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def _architecture_preference() -> list[str]:
    machine = platform.machine().lower()
    if machine in {"x86_64", "amd64"}:
        return ["x64", "neutral", "x86", "arm64"]
    if machine in {"aarch64", "arm64"}:
        return ["arm64", "neutral", "x64", "x86"]
    return ["x86", "neutral", "x64", "arm64"]


def _select_bundle_member(root: Path) -> Path:
    members = list(root.rglob("*.appx")) + list(root.rglob("*.msix"))
    if not members:
        raise PackageError("Bundle contains no application AppX/MSIX package")
    for architecture in _architecture_preference():
        matches = [
            item
            for item in members
            if re.search(rf"(?:_|\.){re.escape(architecture)}(?:\.|_|$)", item.name.lower())
        ]
        if matches:
            return sorted(matches, key=lambda item: item.name.lower())[0]
    return sorted(members, key=lambda item: item.name.lower())[0]


def _find_manifest_ancestor(path: Path) -> Path | None:
    current = path if path.is_dir() else path.parent
    for candidate in (current, *current.parents):
        if (candidate / "AppxManifest.xml").is_file():
            return candidate
    return None


def resolve_input(path: Path) -> tuple[Path, PackageInfo | None]:
    """Return an executable path and package metadata for a supported input."""

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if path.is_file() and path.suffix.lower() in PACKAGE_EXTENSIONS:
        materialized = _materialize_archive(path)
        if path.suffix.lower() in {".appxbundle", ".msixbundle"}:
            member = _select_bundle_member(materialized)
            materialized = _materialize_archive(member)
        manifest = _package_manifest(materialized)
        package, executable = _parse_manifest(manifest, path, materialized)
        if path.suffix.lower() in {".appxbundle", ".msixbundle"}:
            package.package_type = "AppX/MSIX bundle"
        return executable, package

    package_root = _find_manifest_ancestor(path)
    if package_root is None:
        return path, None

    manifest = package_root / "AppxManifest.xml"
    package, declared_executable = _parse_manifest(manifest, path, package_root)
    if path.is_dir():
        return declared_executable, package
    return path, package
