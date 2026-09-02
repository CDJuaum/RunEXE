"""Persistent recent-application library and per-app launch presets."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "runexe"
DEFAULT_LIBRARY_PATH = STATE_DIR / "applications.json"
SCHEMA_VERSION = 1
MAX_LIBRARY_BYTES = 2 * 1024 * 1024


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalized_path(path: Path | str) -> str:
    return str(Path(path).expanduser().resolve())


def application_id(path: Path | str) -> str:
    normalized = _normalized_path(path)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class LaunchPreset:
    """User-controlled launch choices that are safe to restore per application."""

    backend: str = "auto"
    proton: str | None = None
    proton_tuning: str = "default"
    windows_version: str | None = None
    dependencies: str = "auto"
    prefix: str | None = None
    arguments: str = ""

    @classmethod
    def from_dict(cls, value: object) -> LaunchPreset:
        if not isinstance(value, dict):
            return cls()
        backend = value.get("backend")
        dependencies = value.get("dependencies")
        return cls(
            backend=backend if backend in {"auto", "wine", "proton"} else "auto",
            proton=value.get("proton") if isinstance(value.get("proton"), str) else None,
            proton_tuning=(
                value.get("proton_tuning")
                if value.get("proton_tuning")
                in {"default", "diagnostics", "wined3d", "dxvk-hud", "no-fsync", "no-ntsync"}
                else "default"
            ),
            windows_version=(
                value.get("windows_version")
                if value.get("windows_version") in {"7", "8", "8.1", "10", "11"}
                else None
            ),
            dependencies=(dependencies if dependencies in {"auto", "install", "skip"} else "auto"),
            prefix=value.get("prefix") if isinstance(value.get("prefix"), str) else None,
            arguments=value.get("arguments") if isinstance(value.get("arguments"), str) else "",
        )


@dataclass(frozen=True)
class ApplicationRecord:
    identifier: str
    path: str
    display_name: str
    last_used: str
    launch_count: int = 0
    last_exit_code: int | None = None
    architecture: str | None = None
    file_format: str | None = None
    preset: LaunchPreset = LaunchPreset()

    @property
    def exists(self) -> bool:
        return Path(self.path).exists()

    @classmethod
    def from_dict(cls, value: object) -> ApplicationRecord | None:
        if not isinstance(value, dict):
            return None
        path = value.get("path")
        if not isinstance(path, str) or not path:
            return None
        display_name = value.get("display_name")
        last_used = value.get("last_used")
        launch_count = value.get("launch_count")
        last_exit_code = value.get("last_exit_code")
        return cls(
            identifier=(
                value.get("identifier")
                if isinstance(value.get("identifier"), str)
                else application_id(path)
            ),
            path=path,
            display_name=(
                display_name if isinstance(display_name, str) and display_name else Path(path).stem
            ),
            last_used=last_used if isinstance(last_used, str) else _now(),
            launch_count=max(0, launch_count) if isinstance(launch_count, int) else 0,
            last_exit_code=last_exit_code if isinstance(last_exit_code, int) else None,
            architecture=(
                value.get("architecture") if isinstance(value.get("architecture"), str) else None
            ),
            file_format=(
                value.get("file_format") if isinstance(value.get("file_format"), str) else None
            ),
            preset=LaunchPreset.from_dict(value.get("preset")),
        )


class ApplicationLibrary:
    """Bounded JSON store with atomic replacement and corruption recovery."""

    def __init__(self, path: Path | None = None, *, max_entries: int = 50) -> None:
        self.path = path or DEFAULT_LIBRARY_PATH
        self.max_entries = max(1, max_entries)

    def records(self) -> list[ApplicationRecord]:
        try:
            if self.path.stat().st_size > MAX_LIBRARY_BYTES:
                return []
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        applications = value.get("applications") if isinstance(value, dict) else None
        if not isinstance(applications, list):
            return []
        records = [record for item in applications if (record := ApplicationRecord.from_dict(item))]
        records.sort(key=lambda record: record.last_used, reverse=True)
        return records[: self.max_entries]

    def get(self, path: Path | str) -> ApplicationRecord | None:
        identifier = application_id(path)
        return next(
            (record for record in self.records() if record.identifier == identifier),
            None,
        )

    def remember_analysis(
        self,
        path: Path | str,
        *,
        display_name: str,
        architecture: str | None,
        file_format: str | None,
        preset: LaunchPreset | None = None,
    ) -> ApplicationRecord:
        normalized = _normalized_path(path)
        records = self.records()
        identifier = application_id(normalized)
        existing = next((item for item in records if item.identifier == identifier), None)
        record = ApplicationRecord(
            identifier=identifier,
            path=normalized,
            display_name=display_name or Path(normalized).stem,
            last_used=_now(),
            launch_count=existing.launch_count if existing else 0,
            last_exit_code=existing.last_exit_code if existing else None,
            architecture=architecture,
            file_format=file_format,
            preset=preset or (existing.preset if existing else LaunchPreset()),
        )
        self._save([record, *(item for item in records if item.identifier != identifier)])
        return record

    def record_launch(self, path: Path | str, preset: LaunchPreset) -> ApplicationRecord | None:
        records = self.records()
        identifier = application_id(path)
        existing = next((item for item in records if item.identifier == identifier), None)
        if existing is None:
            return None
        updated = replace(
            existing,
            last_used=_now(),
            launch_count=existing.launch_count + 1,
            last_exit_code=None,
            preset=preset,
        )
        self._save([updated, *(item for item in records if item.identifier != identifier)])
        return updated

    def record_exit(self, path: Path | str, exit_code: int) -> ApplicationRecord | None:
        records = self.records()
        identifier = application_id(path)
        existing = next((item for item in records if item.identifier == identifier), None)
        if existing is None:
            return None
        updated = replace(existing, last_used=_now(), last_exit_code=exit_code)
        self._save([updated, *(item for item in records if item.identifier != identifier)])
        return updated

    def forget(self, path: Path | str) -> bool:
        records = self.records()
        identifier = application_id(path)
        retained = [item for item in records if item.identifier != identifier]
        if len(retained) == len(records):
            return False
        self._save(retained)
        return True

    def prune_missing(self) -> int:
        records = self.records()
        retained = [record for record in records if record.exists]
        removed = len(records) - len(retained)
        if removed:
            self._save(retained)
        return removed

    def _save(self, records: list[ApplicationRecord]) -> None:
        ordered = sorted(records, key=lambda record: record.last_used, reverse=True)[
            : self.max_entries
        ]
        payload = {
            "schema": SCHEMA_VERSION,
            "applications": [
                {**asdict(record), "preset": asdict(record.preset)} for record in ordered
            ],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            if os.name == "posix":
                temporary.chmod(0o600)
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)
