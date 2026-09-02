"""Safe backup and restore for RunEXE-managed Wine and Proton environments."""

from __future__ import annotations

import json
import os
import posixpath
import re
import shutil
import tarfile
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from .environments import EnvironmentInfo, managed_roots

BACKUP_SCHEMA = 1
MAX_METADATA_BYTES = 64 * 1024
MARKER_NAME = ".runexe-backup.json"


class BackupError(RuntimeError):
    """Raised when an environment backup cannot be handled safely."""


@dataclass(frozen=True)
class BackupInfo:
    identifier: str
    environment_identifier: str
    backend: str
    environment_name: str
    application: str
    source: str | None
    created_at: str
    archive: Path
    size_bytes: int

    def as_dict(self) -> dict:
        value = asdict(self)
        value["archive"] = str(self.archive)
        return value


def backup_root(override: Path | None = None) -> Path:
    if override is not None:
        return override.expanduser()
    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return data_home / "runexe" / "backups"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_environment_name(value: str) -> bool:
    return bool(value) and Path(value).name == value and value not in {".", ".."}


def _safe_backup_identifier(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value))


def _validated_environment_path(
    environment: EnvironmentInfo,
    roots: tuple[Path, Path] | None = None,
) -> Path:
    candidate = environment.path.expanduser()
    if candidate.is_symlink():
        raise BackupError(f"Environment path is unsafe: {candidate}")
    resolved = candidate.resolve()
    resolved_roots = tuple(root.expanduser().resolve() for root in (roots or managed_roots()))
    if resolved.parent not in resolved_roots or not resolved.is_dir():
        raise BackupError("Only direct children of RunEXE-managed roots can be backed up.")
    return resolved


def _atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        if os.name == "posix":
            temporary.chmod(0o600)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def create_environment_backup(
    environment: EnvironmentInfo,
    *,
    destination: Path | None = None,
    roots: tuple[Path, Path] | None = None,
) -> BackupInfo:
    """Create an atomic compressed snapshot without following prefix symlinks."""

    source_path = _validated_environment_path(environment, roots)
    root = backup_root(destination)
    root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    identifier = f"{timestamp}-{uuid.uuid4().hex[:10]}"
    archive = root / f"{identifier}.tar.gz"
    metadata = root / f"{identifier}.json"
    temporary = root / f".{identifier}.{os.getpid()}.tmp"

    try:
        with tarfile.open(temporary, "w:gz", format=tarfile.PAX_FORMAT, dereference=False) as tar:
            tar.add(source_path, arcname="environment", recursive=True)
        if os.name == "posix":
            temporary.chmod(0o600)
        temporary.replace(archive)
        info = BackupInfo(
            identifier=identifier,
            environment_identifier=environment.identifier,
            backend=environment.backend,
            environment_name=source_path.name,
            application=environment.application,
            source=environment.source,
            created_at=_now(),
            archive=archive,
            size_bytes=archive.stat().st_size,
        )
        _atomic_json(metadata, {"schema": BACKUP_SCHEMA, **info.as_dict()})
        return info
    except (OSError, tarfile.TarError) as error:
        archive.unlink(missing_ok=True)
        metadata.unlink(missing_ok=True)
        raise BackupError(f"Could not back up {environment.identifier}: {error}") from error
    finally:
        temporary.unlink(missing_ok=True)


def _backup_from_metadata(path: Path) -> BackupInfo | None:
    try:
        if path.stat().st_size > MAX_METADATA_BYTES:
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict) or value.get("schema") != BACKUP_SCHEMA:
        return None
    required = (
        "identifier",
        "environment_identifier",
        "backend",
        "environment_name",
        "application",
        "created_at",
        "archive",
    )
    if not all(isinstance(value.get(key), str) and value[key] for key in required):
        return None
    identifier = value["identifier"]
    if (
        not _safe_backup_identifier(identifier)
        or path.name != f"{identifier}.json"
        or value["backend"] not in {"wine", "proton"}
        or not _safe_environment_name(value["environment_name"])
    ):
        return None
    archive = Path(value["archive"]).expanduser()
    if (
        archive.name != f"{identifier}.tar.gz"
        or archive.parent.resolve() != path.parent.resolve()
        or not archive.is_file()
    ):
        return None
    try:
        size = archive.stat().st_size
    except OSError:
        return None
    source = value.get("source")
    return BackupInfo(
        identifier=identifier,
        environment_identifier=value["environment_identifier"],
        backend=value["backend"],
        environment_name=value["environment_name"],
        application=value["application"],
        source=source if isinstance(source, str) else None,
        created_at=value["created_at"],
        archive=archive.resolve(),
        size_bytes=size,
    )


def discover_backups(destination: Path | None = None) -> list[BackupInfo]:
    root = backup_root(destination)
    try:
        candidates = list(root.glob("*.json"))
    except OSError:
        return []
    backups = [item for path in candidates if (item := _backup_from_metadata(path)) is not None]
    return sorted(backups, key=lambda item: item.created_at, reverse=True)


def _validated_members(archive: tarfile.TarFile) -> list[tarfile.TarInfo]:
    members = archive.getmembers()
    if not members or not any(item.name == "environment" and item.isdir() for item in members):
        raise BackupError("Backup archive does not contain an environment root.")
    for member in members:
        path = PurePosixPath(member.name)
        if path.is_absolute() or not path.parts or path.parts[0] != "environment":
            raise BackupError(f"Unsafe backup path: {member.name}")
        if any(part in {"", ".", ".."} for part in path.parts):
            raise BackupError(f"Unsafe backup path: {member.name}")
        if member.ischr() or member.isblk() or member.isfifo() or member.isdev():
            raise BackupError(f"Unsupported special file in backup: {member.name}")
        if member.issym():
            link = member.linkname
            if not link:
                raise BackupError(f"Unsafe backup link: {member.name}")
            base = posixpath.dirname(member.name)
            normalized = posixpath.normpath(posixpath.join(base, link))
            is_drive_mapping = member.name.startswith("environment/dosdevices/")
            if (
                PurePosixPath(link).is_absolute()
                or (normalized != "environment" and not normalized.startswith("environment/"))
            ) and not is_drive_mapping:
                raise BackupError(f"Backup link escapes the environment: {member.name}")
        elif member.islnk():
            link = member.linkname
            if not link or PurePosixPath(link).is_absolute():
                raise BackupError(f"Unsafe backup hard link: {member.name}")
            normalized = posixpath.normpath(link)
            if normalized != "environment" and not normalized.startswith("environment/"):
                raise BackupError(f"Backup hard link escapes the environment: {member.name}")
    return members


def _safe_parent(root: Path, relative: PurePosixPath) -> Path:
    current = root
    for part in relative.parts[:-1]:
        current /= part
        if current.is_symlink():
            raise BackupError(f"Backup path crosses a symlink: {relative}")
        current.mkdir(exist_ok=True)
    return root.joinpath(*relative.parts)


def _extract_members(
    archive: tarfile.TarFile,
    members: list[tarfile.TarInfo],
    staging: Path,
) -> None:
    hardlinks: list[tuple[Path, PurePosixPath]] = []
    for member in members:
        relative = PurePosixPath(member.name)
        target = _safe_parent(staging, relative)
        if member.isdir():
            if target.is_symlink():
                raise BackupError(f"Backup directory collides with a symlink: {member.name}")
            target.mkdir(exist_ok=True)
            continue
        if target.exists() or target.is_symlink():
            raise BackupError(f"Duplicate backup path: {member.name}")
        if member.isfile():
            source = archive.extractfile(member)
            if source is None:
                raise BackupError(f"Could not read backup member: {member.name}")
            with source, target.open("xb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)
            target.chmod(member.mode & 0o777)
        elif member.issym():
            target.symlink_to(member.linkname)
        elif member.islnk():
            hardlinks.append((target, PurePosixPath(member.linkname)))
        else:
            raise BackupError(f"Unsupported backup member: {member.name}")

    for target, linkname in hardlinks:
        source = staging.joinpath(*linkname.parts)
        if not source.is_file() or source.is_symlink():
            raise BackupError(f"Invalid hard link target: {linkname}")
        os.link(source, target)


def restore_backup(
    backup: BackupInfo,
    *,
    roots: tuple[Path, Path] | None = None,
) -> Path:
    """Restore into a missing managed path; existing environments are never replaced."""

    if not _safe_backup_identifier(backup.identifier):
        raise BackupError("Backup contains an unsafe identifier.")
    if backup.backend not in {"wine", "proton"}:
        raise BackupError("Backup contains an unsupported environment backend.")
    if not _safe_environment_name(backup.environment_name):
        raise BackupError("Backup contains an unsafe environment name.")
    selected_roots = roots or managed_roots()
    root = selected_roots[0] if backup.backend == "wine" else selected_roots[1]
    root = root.expanduser().resolve()
    target = root / backup.environment_name
    if target.exists() or target.is_symlink():
        raise BackupError(f"Refusing to overwrite the existing environment: {target}")
    root.mkdir(parents=True, exist_ok=True)
    staging = root / f".runexe-restoring-{backup.identifier}-{uuid.uuid4().hex[:8]}"
    staging.mkdir()
    try:
        with tarfile.open(backup.archive, "r:gz") as archive:
            members = _validated_members(archive)
            _extract_members(archive, members, staging)
        restored = staging / "environment"
        if not restored.is_dir() or restored.is_symlink():
            raise BackupError("Restored backup does not contain a safe environment directory.")
        restored.rename(target)
    except (OSError, tarfile.TarError) as error:
        raise BackupError(f"Could not restore {backup.identifier}: {error}") from error
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return target


def remove_backup(backup: BackupInfo) -> None:
    if not _safe_backup_identifier(backup.identifier):
        raise BackupError("Backup contains an unsafe identifier.")
    root = backup.archive.parent.resolve()
    metadata = root / f"{backup.identifier}.json"
    if (
        backup.archive.name != f"{backup.identifier}.tar.gz"
        or backup.archive.resolve().parent != root
        or metadata.parent.resolve() != root
    ):
        raise BackupError("Refusing to remove a backup outside its managed directory.")
    try:
        backup.archive.unlink(missing_ok=True)
        metadata.unlink(missing_ok=True)
    except OSError as error:
        raise BackupError(f"Could not remove backup {backup.identifier}: {error}") from error
