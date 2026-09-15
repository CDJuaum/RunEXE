"""Presentation-agnostic Qt controller for the RunEXE desktop interface."""

from __future__ import annotations

import json
import os
import shlex
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import (
    Property,
    QAbstractListModel,
    QCoreApplication,
    QModelIndex,
    QObject,
    QProcess,
    QProcessEnvironment,
    QSettings,
    QStorageInfo,
    Qt,
    QThreadPool,
    QTimer,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QDesktopServices, QGuiApplication

from runexe import __version__
from runexe.analyzer import analyze_executable
from runexe.backups import (
    BackupInfo,
    create_environment_backup,
    discover_backups,
    remove_backup,
    restore_backup,
)
from runexe.compatibility import analyze_compatibility
from runexe.configuration import (
    CONFIGURATION_TOOLS,
    ConfigurationError,
    open_environment_configuration,
)
from runexe.environments import (
    EnvironmentInfo,
    discover_environments,
    format_size,
    remove_managed_environment,
)
from runexe.host import detect_host
from runexe.library import ApplicationLibrary, ApplicationRecord, LaunchPreset
from runexe.models import CompatibilityReport, ExecutableInfo, HostInfo
from runexe.platform_support import (
    find_executable,
    install_system_component,
    system_component_managed,
    uninstall_system_component,
)
from runexe.profiles import detect_runtime_issue
from runexe.proton import (
    PROTON_TUNING_PRESETS,
    ProtonInstallation,
    discover_proton_installations,
    install_managed_proton,
    managed_proton_root,
    remove_managed_proton,
)
from runexe.runner import (
    PreparedEnvironment,
    build_launch_spec,
    open_runtime_configuration,
    prepare_environment,
)
from runexe.umu import (
    ensure_umu_launcher,
    install_managed_umu,
    managed_umu_executable,
    remove_managed_umu,
)

from .workers import Worker


@dataclass(frozen=True)
class AnalysisBundle:
    source: Path
    executable: ExecutableInfo
    host: HostInfo
    compatibility: CompatibilityReport
    proton_installations: list[ProtonInstallation]


@dataclass(frozen=True)
class LibraryBundle:
    applications: list[ApplicationRecord]
    environments: list[EnvironmentInfo]
    backups: list[BackupInfo] = field(default_factory=list)


@dataclass(frozen=True)
class RuntimeBundle:
    host: HostInfo
    proton_installations: list[ProtonInstallation]
    managed_system_components: frozenset[str]


class DictListModel(QAbstractListModel):
    """Small role-based list model suitable for QML ListView delegates."""

    countChanged = Signal()

    def __init__(self, roles: tuple[str, ...], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._role_names = {
            Qt.ItemDataRole.UserRole + index: role.encode() for index, role in enumerate(roles)
        }
        self._role_lookup = {name.decode(): role for role, name in self._role_names.items()}
        self._rows: list[dict[str, Any]] = []

    def roleNames(self) -> dict[int, bytes]:  # noqa: N802 - Qt API
        return self._role_names

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802 - Qt API
        if parent is None:
            parent = QModelIndex()
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        name = self._role_names.get(role)
        if name is None:
            return None
        return self._rows[index.row()].get(name.decode())

    def replace(self, rows: list[dict[str, Any]]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()
        self.countChanged.emit()

    def item(self, index: int) -> dict[str, Any] | None:
        if 0 <= index < len(self._rows):
            return self._rows[index]
        return None

    def index_of(self, role: str, value: Any) -> int:
        if role not in self._role_lookup:
            return -1
        return next((index for index, row in enumerate(self._rows) if row.get(role) == value), -1)

    @Property(int, notify=countChanged)
    def count(self) -> int:
        return len(self._rows)

    @Slot(int, result="QVariantMap")
    def get(self, index: int) -> dict[str, Any]:
        return dict(self.item(index) or {})


class ActivityListModel(QAbstractListModel):
    """Append-only bounded activity model so QML never re-renders one huge string."""

    countChanged = Signal()
    _TEXT_ROLE = Qt.ItemDataRole.UserRole

    def __init__(self, parent: QObject | None = None, *, maximum: int = 3000) -> None:
        super().__init__(parent)
        self._rows: list[str] = []
        self._maximum = maximum

    def roleNames(self) -> dict[int, bytes]:  # noqa: N802 - Qt API
        return {self._TEXT_ROLE: b"text"}

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802 - Qt API
        if parent is None:
            parent = QModelIndex()
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if role != self._TEXT_ROLE or not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        return self._rows[index.row()]

    def append(self, text: str) -> None:
        overflow = max(0, len(self._rows) + 1 - self._maximum)
        if overflow:
            self.beginRemoveRows(QModelIndex(), 0, overflow - 1)
            del self._rows[:overflow]
            self.endRemoveRows()
        row = len(self._rows)
        self.beginInsertRows(QModelIndex(), row, row)
        self._rows.append(text)
        self.endInsertRows()
        self.countChanged.emit()

    def clear(self) -> None:
        if not self._rows:
            return
        self.beginResetModel()
        self._rows.clear()
        self.endResetModel()
        self.countChanged.emit()

    @Property(int, notify=countChanged)
    def count(self) -> int:
        return len(self._rows)


def _metric(value: str = "Not checked", detail: str = "", state: str = "neutral") -> dict[str, str]:
    return {"value": value, "detail": detail, "state": state}


def _local_path(value: str) -> Path:
    if value.startswith("file:"):
        local = QUrl(value).toLocalFile()
        if local:
            value = local
    return Path(value).expanduser()


class RunEXEController(QObject):
    """Own application state and actions while QML owns all visual presentation."""

    PAGE_OVERVIEW = 0
    PAGE_LAUNCH_SETUP = 1
    PAGE_APPLICATIONS = 2
    PAGE_BACKUPS = 3
    PAGE_ACTIVITY = 4
    PAGE_SETTINGS = 5
    PAGE_RUNTIMES = PAGE_SETTINGS
    PAGE_ENVIRONMENTS = PAGE_SETTINGS

    stateChanged = Signal()
    navigateRequested = Signal(int)
    profileFocusRequested = Signal()
    messageRequested = Signal(str, str, str)
    notificationRequested = Signal(str, str)
    closeConfirmationRequested = Signal()
    taskProgressRequested = Signal(str, str, int)
    settingsSectionRequested = Signal(str)

    def __init__(
        self,
        initial_file: Path | None = None,
        *,
        auto_refresh: bool = True,
        application_library: ApplicationLibrary | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.settings = QSettings("RunEXE", "RunEXE")
        self.application_library = application_library or ApplicationLibrary()
        self.auto_refresh = auto_refresh
        self.thread_pool = QThreadPool.globalInstance()
        self._workers: dict[str, Worker] = {}
        self.taskProgressRequested.connect(self._task_progress_requested)

        self.source_path: Path | None = None
        self.executable: ExecutableInfo | None = None
        self.host: HostInfo | None = None
        self.compatibility: CompatibilityReport | None = None
        self.proton_installations: list[ProtonInstallation] = []
        self._managed_system_components: frozenset[str] = frozenset()
        self._managed_environments: list[EnvironmentInfo] = []
        self._managed_backups: list[BackupInfo] = []
        self._application_rows: list[dict[str, Any]] = []

        self.application_process: QProcess | None = None
        self._active_launch_path: Path | None = None
        self._active_launch_preset: LaunchPreset | None = None
        self._application_output: list[str] = []

        self._task_status = "Ready"
        self._environment_status = "No application selected"
        self._header_status = "Checking runtimes"
        self._header_state = "warning"
        self._activity_lines: list[str] = []

        self._backend = str(self.settings.value("runtime/backend", "auto"))
        if self._backend not in {"auto", "wine", "proton"}:
            self._backend = "auto"
        self._proton = ""
        self._proton_tuning = "default"
        self._windows_version = str(self.settings.value("runtime/windows-version", "") or "")
        if self._windows_version not in {"", "7", "8", "8.1", "10", "11"}:
            self._windows_version = ""
        self._dependencies = str(self.settings.value("runtime/dependencies", "auto"))
        if self._dependencies not in {"auto", "install", "skip"}:
            self._dependencies = "auto"
        self._prefix = ""
        self._arguments = ""
        self._theme_mode = str(self.settings.value("application/theme", "system") or "system")
        if self._theme_mode not in {"system", "light", "dark"}:
            self._theme_mode = "system"
        self._notifications_enabled = bool(
            self.settings.value("notifications/enabled", True, type=bool)
        )
        self._task_progress_key = ""
        self._task_progress_label = ""
        self._task_progress_value = -1
        self.settings.remove("runtime/prefix")

        self._file_metric = _metric("Not analyzed", "Select Windows software to begin")
        self._arch_metric = _metric("Not analyzed", "Select Windows software to begin")
        self._runtime_metric = _metric("Not analyzed", "Select Windows software to begin")
        self._readiness_metric = _metric("Not analyzed", "Select Windows software to begin")
        self._compatibility_metric = _metric(
            "Not scored", "Analyze an application to calculate local readiness"
        )
        self._wine_metric = _metric("Checking", "Detecting Wine")
        self._proton_metric = _metric("Checking", "Detecting Proton")
        self._winetricks_metric = _metric("Checking", "Detecting Winetricks")
        self._vulkan_metric = _metric("Checking", "Detecting Vulkan")
        self._application_metric = _metric("0", "No applications analyzed yet")
        self._storage_metric = _metric("0 B", "0 isolated environment(s)")
        self._backup_metric = _metric("0 B", "0 restorable snapshot(s)")

        self._product = "-"
        self._subsystem = "-"
        self._dependency_text = "-"
        self._guidance = ["Analyze an application to see compatibility guidance."]
        self._compatibility_issues = []
        self._score_deductions = []
        self._compatibility_notes = ["Analyze an application to see compatibility guidance."]

        self._profile_visible = False
        self._profile_title = "Compatibility preset detected"
        self._profile_summary = ""
        self._profile_requirements = ""
        self._profile_button = "Apply recommended setup"
        self._environment_preview = "Select and analyze an application to preview its environment."

        self._application_search = ""
        self._selected_application_path = ""
        self._selected_environment_id = ""
        self._selected_backup_id = ""

        self._applications_model = DictListModel(
            ("path", "displayName", "headline", "subtitle", "detail", "exists"), self
        )
        self._environments_model = DictListModel(
            (
                "identifier",
                "application",
                "headline",
                "subtitle",
                "detail",
                "path",
                "backend",
            ),
            self,
        )
        self._backups_model = DictListModel(
            ("identifier", "application", "headline", "subtitle", "detail", "backend"), self
        )
        self._activity_model = ActivityListModel(self)

        if auto_refresh:
            QTimer.singleShot(80, self.refreshRuntimes)
            QTimer.singleShot(120, self.refreshLibrary)
        if initial_file is not None:
            QTimer.singleShot(150, lambda: self.analyzePath(str(initial_file)))

    # ---------------------------------------------------------------- Properties
    @Property(str, constant=True)
    def version(self) -> str:
        return __version__

    @Property(int, constant=True)
    def initialWindowWidth(self) -> int:
        return int(self.settings.value("window/qml-width", 1180))

    @Property(int, constant=True)
    def initialWindowHeight(self) -> int:
        return int(self.settings.value("window/qml-height", 790))

    @Property(str, notify=stateChanged)
    def selectedPath(self) -> str:
        return str(self.source_path) if self.source_path is not None else ""

    @Property(str, notify=stateChanged)
    def selectedName(self) -> str:
        return self.source_path.name if self.source_path is not None else ""

    @Property(bool, notify=stateChanged)
    def sourceSelected(self) -> bool:
        return self.source_path is not None

    @Property(bool, notify=stateChanged)
    def analyzed(self) -> bool:
        return self.executable is not None and self.compatibility is not None

    @Property(bool, notify=stateChanged)
    def busy(self) -> bool:
        return bool(self._workers)

    @Property(bool, notify=stateChanged)
    def blockingBusy(self) -> bool:
        return any(key != "library" for key in self._workers)

    @Property(bool, notify=stateChanged)
    def running(self) -> bool:
        return self._application_running()

    @Property(bool, notify=stateChanged)
    def interactionEnabled(self) -> bool:
        return not self.blockingBusy and not self.running

    @Property(bool, notify=stateChanged)
    def analyzeEnabled(self) -> bool:
        return self.sourceSelected and self.interactionEnabled

    @Property(bool, notify=stateChanged)
    def launchEnabled(self) -> bool:
        return bool(
            self.analyzed
            and self.compatibility is not None
            and not self.compatibility.blocking_issues
            and self.interactionEnabled
        )

    @Property(bool, notify=stateChanged)
    def prepareEnabled(self) -> bool:
        return self.launchEnabled

    @Property(bool, notify=stateChanged)
    def protonChoiceEnabled(self) -> bool:
        return bool(self.proton_installations) and self.interactionEnabled

    @Property(bool, notify=stateChanged)
    def protonTuningEnabled(self) -> bool:
        return bool(
            self.compatibility
            and self.compatibility.backend == "proton"
            and self.interactionEnabled
        )

    @Property(bool, notify=stateChanged)
    def wineConfigEnabled(self) -> bool:
        return bool(
            self.analyzed and self.host and self.host.wine_installed and self.interactionEnabled
        )

    @Property(bool, notify=stateChanged)
    def protonConfigEnabled(self) -> bool:
        return bool(
            self.analyzed and self.host and self.host.proton_installed and self.interactionEnabled
        )

    @Property(str, notify=stateChanged)
    def taskStatus(self) -> str:
        return self._task_status

    @Property(bool, notify=stateChanged)
    def taskProgressVisible(self) -> bool:
        return bool(self._task_progress_key and self._task_progress_key in self._workers)

    @Property(str, notify=stateChanged)
    def taskProgressLabel(self) -> str:
        return self._task_progress_label

    @Property(int, notify=stateChanged)
    def taskProgressValue(self) -> int:
        return max(0, self._task_progress_value)

    @Property(bool, notify=stateChanged)
    def taskProgressIndeterminate(self) -> bool:
        return self._task_progress_value < 0

    @Property(str, notify=stateChanged)
    def environmentStatus(self) -> str:
        return self._environment_status

    @Property(str, notify=stateChanged)
    def headerStatus(self) -> str:
        return self._header_status

    @Property(str, notify=stateChanged)
    def headerState(self) -> str:
        return self._header_state

    @Property("QVariantMap", notify=stateChanged)
    def fileMetric(self) -> dict[str, str]:
        return dict(self._file_metric)

    @Property("QVariantMap", notify=stateChanged)
    def architectureMetric(self) -> dict[str, str]:
        return dict(self._arch_metric)

    @Property("QVariantMap", notify=stateChanged)
    def runtimeMetric(self) -> dict[str, str]:
        return dict(self._runtime_metric)

    @Property("QVariantMap", notify=stateChanged)
    def readinessMetric(self) -> dict[str, str]:
        return dict(self._readiness_metric)

    @Property("QVariantMap", notify=stateChanged)
    def compatibilityMetric(self) -> dict[str, str]:
        return dict(self._compatibility_metric)

    @Property(bool, notify=stateChanged)
    def notificationsEnabled(self) -> bool:
        return self._notifications_enabled

    @Property(str, notify=stateChanged)
    def themeMode(self) -> str:
        return self._theme_mode

    @Property("QVariantList", constant=True)
    def themeOptions(self) -> list[dict[str, str]]:
        return [
            {"label": "System", "value": "system"},
            {"label": "Light", "value": "light"},
            {"label": "Dark", "value": "dark"},
        ]

    @Property("QVariantList", notify=stateChanged)
    def filePickerLocations(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        seen: set[str] = set()

        def add(label: str, path: str) -> None:
            candidate = str(Path(path).expanduser())
            if not candidate or candidate in seen:
                return
            seen.add(candidate)
            rows.append(
                {
                    "label": label,
                    "path": candidate,
                    "url": QUrl.fromLocalFile(candidate).toString(),
                }
            )

        add("Home", str(Path.home()))
        root = Path(Path.home().anchor or "/")
        add("Computer", str(root))
        for environment in self._managed_environments:
            relative_drive = "pfx/drive_c" if environment.backend == "proton" else "drive_c"
            drive_c = environment.path / relative_drive
            if drive_c.is_dir():
                add(f"Windows · {environment.application}", str(drive_c))
        for storage in QStorageInfo.mountedVolumes():
            if not storage.isValid() or not storage.isReady() or storage.bytesTotal() <= 0:
                continue
            path = storage.rootPath()
            if path.startswith(("/proc", "/sys", "/dev")):
                continue
            label = storage.displayName().strip() or Path(path).name or path
            add(label, path)
        return rows

    @Slot(str, result=str)
    def localFileUrl(self, path: str) -> str:
        return QUrl.fromLocalFile(str(Path(path).expanduser())).toString()

    @Slot(str, result=str)
    def localPathFromUrl(self, value: str) -> str:
        local = QUrl(value).toLocalFile()
        return local or value

    @Slot(str, str, result=str)
    def joinFileUrl(self, folder_url: str, name: str) -> str:
        folder = QUrl(folder_url).toLocalFile() or folder_url
        return QUrl.fromLocalFile(str(Path(folder) / name)).toString()

    @Property("QVariantMap", notify=stateChanged)
    def wineMetric(self) -> dict[str, str]:
        return dict(self._wine_metric)

    @Property("QVariantMap", notify=stateChanged)
    def protonMetric(self) -> dict[str, str]:
        return dict(self._proton_metric)

    @Property("QVariantMap", notify=stateChanged)
    def winetricksMetric(self) -> dict[str, str]:
        return dict(self._winetricks_metric)

    @Property("QVariantMap", notify=stateChanged)
    def vulkanMetric(self) -> dict[str, str]:
        return dict(self._vulkan_metric)

    @Property(bool, notify=stateChanged)
    def wineInstalled(self) -> bool:
        return bool(self.host and self.host.wine_installed)

    @Property(bool, notify=stateChanged)
    def winetricksInstalled(self) -> bool:
        return bool(self.host and self.host.winetricks_installed)

    @Property(bool, notify=stateChanged)
    def vulkanToolsInstalled(self) -> bool:
        return find_executable("vulkaninfo") is not None

    @Property(bool, notify=stateChanged)
    def managedProtonInstalled(self) -> bool:
        root = managed_proton_root().expanduser().resolve()
        return any(
            item.install_dir.expanduser().resolve().parent == root
            for item in self.proton_installations
        )

    @Property(bool, notify=stateChanged)
    def managedUmuInstalled(self) -> bool:
        return managed_umu_executable() is not None

    @Property(bool, notify=stateChanged)
    def runexeManagedWineInstalled(self) -> bool:
        return "wine" in self._managed_system_components

    @Property(bool, notify=stateChanged)
    def runexeManagedWinetricksInstalled(self) -> bool:
        return "winetricks" in self._managed_system_components

    @Property(bool, notify=stateChanged)
    def runexeManagedVulkanToolsInstalled(self) -> bool:
        return "vulkan" in self._managed_system_components

    @Property("QVariantMap", notify=stateChanged)
    def applicationMetric(self) -> dict[str, str]:
        return dict(self._application_metric)

    @Property("QVariantMap", notify=stateChanged)
    def storageMetric(self) -> dict[str, str]:
        return dict(self._storage_metric)

    @Property("QVariantMap", notify=stateChanged)
    def backupMetric(self) -> dict[str, str]:
        return dict(self._backup_metric)

    @Property(str, notify=stateChanged)
    def product(self) -> str:
        return self._product

    @Property(str, notify=stateChanged)
    def subsystem(self) -> str:
        return self._subsystem

    @Property(str, notify=stateChanged)
    def dependencyText(self) -> str:
        return self._dependency_text

    @Property("QStringList", notify=stateChanged)
    def guidance(self) -> list[str]:
        return list(self._guidance)

    @Property("QVariantList", notify=stateChanged)
    def compatibilityIssues(self) -> list[dict[str, str]]:
        return [dict(item) for item in self._compatibility_issues]

    @Property("QVariantList", notify=stateChanged)
    def scoreDeductions(self) -> list[dict[str, str]]:
        return [dict(item) for item in self._score_deductions]

    @Property("QStringList", notify=stateChanged)
    def compatibilityNotes(self) -> list[str]:
        return list(self._compatibility_notes)

    @Property(bool, notify=stateChanged)
    def profileVisible(self) -> bool:
        return self._profile_visible

    @Property(str, notify=stateChanged)
    def profileTitle(self) -> str:
        return self._profile_title

    @Property(str, notify=stateChanged)
    def profileSummary(self) -> str:
        return self._profile_summary

    @Property(str, notify=stateChanged)
    def profileRequirements(self) -> str:
        return self._profile_requirements

    @Property(str, notify=stateChanged)
    def profileButtonText(self) -> str:
        return self._profile_button

    @Property(bool, notify=stateChanged)
    def profileButtonEnabled(self) -> bool:
        profile = self.compatibility.profile if self.compatibility else None
        return bool(profile and profile.recommended_windows_version)

    @Property("QVariantList", constant=True)
    def backendOptions(self) -> list[dict[str, str]]:
        return [
            {"label": "Automatic (recommended)", "value": "auto"},
            {"label": "Wine", "value": "wine"},
            {"label": "Proton", "value": "proton"},
        ]

    @Property("QVariantList", notify=stateChanged)
    def protonOptions(self) -> list[dict[str, str]]:
        options = [{"label": "Best available build", "value": "", "description": ""}]
        for installation in self.proton_installations:
            label = installation.name
            if installation.version and installation.version not in installation.name:
                label += f" ({installation.version})"
            options.append(
                {
                    "label": label,
                    "value": str(installation.script),
                    "description": installation.name,
                }
            )
        return options

    @Property("QVariantList", constant=True)
    def tuningOptions(self) -> list[dict[str, str]]:
        return [
            {"label": preset.label, "value": preset.key, "description": preset.description}
            for preset in PROTON_TUNING_PRESETS
        ]

    @Property("QVariantList", constant=True)
    def windowsOptions(self) -> list[dict[str, str]]:
        return [
            {"label": "Runtime default", "value": ""},
            *(
                {"label": f"Windows {value}", "value": value}
                for value in ("11", "10", "8.1", "8", "7")
            ),
        ]

    @Property("QVariantList", constant=True)
    def dependencyOptions(self) -> list[dict[str, str]]:
        return [
            {"label": "Automatic (Wine on / Proton off)", "value": "auto"},
            {"label": "Install detected components", "value": "install"},
            {"label": "Skip dependency changes", "value": "skip"},
        ]

    @Property(str, notify=stateChanged)
    def backend(self) -> str:
        return self._backend

    @Property(str, notify=stateChanged)
    def proton(self) -> str:
        return self._proton

    @Property(str, notify=stateChanged)
    def protonTuning(self) -> str:
        return self._proton_tuning

    @Property(str, notify=stateChanged)
    def windowsVersion(self) -> str:
        return self._windows_version

    @Property(str, notify=stateChanged)
    def dependencyMode(self) -> str:
        return self._dependencies

    @Slot(bool)
    def setNotificationsEnabled(self, enabled: bool) -> None:
        self._notifications_enabled = enabled
        self.settings.setValue("notifications/enabled", enabled)
        self.stateChanged.emit()

    @Slot(str)
    def setThemeMode(self, value: str) -> None:
        if value not in {"system", "light", "dark"} or value == self._theme_mode:
            return
        self._theme_mode = value
        self.settings.setValue("application/theme", value)
        self.stateChanged.emit()

    @Property(str, notify=stateChanged)
    def prefix(self) -> str:
        return self._prefix

    @Property(str, notify=stateChanged)
    def arguments(self) -> str:
        return self._arguments

    @Property(str, notify=stateChanged)
    def environmentPreview(self) -> str:
        return self._environment_preview

    @Property(str, notify=stateChanged)
    def applicationSearch(self) -> str:
        return self._application_search

    @Property(QObject, constant=True)
    def applicationsModel(self) -> DictListModel:
        return self._applications_model

    @Property(QObject, constant=True)
    def environmentsModel(self) -> DictListModel:
        return self._environments_model

    @Property(QObject, constant=True)
    def backupsModel(self) -> DictListModel:
        return self._backups_model

    @Property(QObject, constant=True)
    def activityModel(self) -> ActivityListModel:
        return self._activity_model

    @Property(int, notify=stateChanged)
    def selectedApplicationIndex(self) -> int:
        return self.applicationsModel.index_of("path", self._selected_application_path)

    @Property(int, notify=stateChanged)
    def selectedEnvironmentIndex(self) -> int:
        return self.environmentsModel.index_of("identifier", self._selected_environment_id)

    @Property(int, notify=stateChanged)
    def selectedBackupIndex(self) -> int:
        return self.backupsModel.index_of("identifier", self._selected_backup_id)

    @Property(bool, notify=stateChanged)
    def applicationSelected(self) -> bool:
        return self.selectedApplicationIndex >= 0

    @Property(bool, notify=stateChanged)
    def environmentSelected(self) -> bool:
        return self._selected_environment() is not None

    @Property(bool, notify=stateChanged)
    def backupSelected(self) -> bool:
        return self._selected_backup() is not None

    @Property(bool, notify=stateChanged)
    def libraryActionsEnabled(self) -> bool:
        return not self._library_busy()

    @Property(str, notify=stateChanged)
    def activityText(self) -> str:
        return "\n".join(self._activity_lines)

    @Property(str, notify=stateChanged)
    def suggestedReportUrl(self) -> str:
        source_name = self.source_path.stem if self.source_path is not None else "session"
        return QUrl.fromLocalFile(str(Path.home() / f"runexe-{source_name}-report.json")).toString()

    @Property("QVariantList", constant=True)
    def configurationTools(self) -> list[dict[str, str]]:
        return [
            {"key": key, "label": label} for key, (label, _program) in CONFIGURATION_TOOLS.items()
        ]

    # ------------------------------------------------------------- Settings slots
    @Slot(str)
    def setBackend(self, value: str) -> None:
        if value not in {"auto", "wine", "proton"} or value == self._backend:
            return
        self._backend = value
        self.settings.setValue("runtime/backend", value)
        if self.executable is not None and self.host is not None:
            self.compatibility = analyze_compatibility(self.executable, self.host, value)
            self._update_analysis_state()
        self.stateChanged.emit()

    @Slot(str)
    def setProton(self, value: str) -> None:
        if value == self._proton:
            return
        self._proton = value
        self.stateChanged.emit()

    @Slot(str)
    def setProtonTuning(self, value: str) -> None:
        valid = {preset.key for preset in PROTON_TUNING_PRESETS}
        if value not in valid:
            return
        if value == self._proton_tuning:
            return
        self._proton_tuning = value or "default"
        self.stateChanged.emit()

    @Slot(str)
    def setWindowsVersion(self, value: str) -> None:
        if value not in {"", "7", "8", "8.1", "10", "11"}:
            return
        if value == self._windows_version:
            return
        self._windows_version = value
        self.settings.setValue("runtime/windows-version", value)
        self._update_profile_state()
        self._update_environment_preview()
        self.stateChanged.emit()

    @Slot(str)
    def setDependencyMode(self, value: str) -> None:
        if value not in {"auto", "install", "skip"} or value == self._dependencies:
            return
        self._dependencies = value
        self.settings.setValue("runtime/dependencies", value)
        self.stateChanged.emit()

    @Slot(str)
    def setPrefix(self, value: str) -> None:
        if value.startswith("file:"):
            value = QUrl(value).toLocalFile()
        if value == self._prefix:
            return
        self._prefix = value
        self._update_environment_preview()
        self.stateChanged.emit()

    @Slot(str)
    def setArguments(self, value: str) -> None:
        if value == self._arguments:
            return
        self._arguments = value
        self.stateChanged.emit()

    @Slot(int, int)
    def saveWindowSize(self, width: int, height: int) -> None:
        if width >= 920 and height >= 680:
            self.settings.setValue("window/qml-width", width)
            self.settings.setValue("window/qml-height", height)

    # ------------------------------------------------------------- Selection/models
    @Slot(str)
    def setApplicationSearch(self, value: str) -> None:
        self._application_search = value
        self._apply_application_filter()
        self.stateChanged.emit()

    @Slot(int)
    def selectApplication(self, index: int) -> None:
        row = self.applicationsModel.item(index)
        self._selected_application_path = str(row.get("path", "")) if row else ""
        self.stateChanged.emit()

    @Slot(int)
    def selectEnvironment(self, index: int) -> None:
        row = self.environmentsModel.item(index)
        self._selected_environment_id = str(row.get("identifier", "")) if row else ""
        self.stateChanged.emit()

    @Slot(int)
    def selectBackup(self, index: int) -> None:
        row = self.backupsModel.item(index)
        self._selected_backup_id = str(row.get("identifier", "")) if row else ""
        self.stateChanged.emit()

    # ------------------------------------------------------------- Analysis/library
    @Slot(str)
    def analyzePath(self, value: str) -> None:
        if not value:
            return
        path = _local_path(value)
        if any(key not in {"library", "runtimes"} for key in self._workers):
            message = "Wait for the current task to finish before analyzing another application"
            self._set_task_status(message)
            self.messageRequested.emit("info", "Analysis already in progress", message + ".")
            return
        if self._application_running():
            self.messageRequested.emit(
                "info",
                "Application still running",
                "Close the launched application before switching to another entry.",
            )
            return

        resolved = path.resolve()
        self.source_path = resolved
        self.executable = None
        self.compatibility = None
        self._profile_visible = False
        self._product = "Not analyzed"
        self._subsystem = "Not analyzed"
        self._dependency_text = "Not analyzed"
        self._file_metric = _metric("Pending", "Waiting for analysis")
        self._arch_metric = _metric("Pending", "Waiting for analysis")
        self._runtime_metric = _metric("Pending", "Waiting for analysis")
        self._readiness_metric = _metric("Analyzing", "Checking the selected file", "warning")
        self._compatibility_metric = _metric(
            "Pending", "Calculating local compatibility readiness", "warning"
        )
        self._guidance = ["Analysis is in progress. Launch is available after validation."]
        self._compatibility_issues = []
        self._score_deductions = []
        self._compatibility_notes = [
            "Analysis is in progress. Launch is available after validation."
        ]
        self._environment_status = "Awaiting analysis"
        self._update_environment_preview()

        saved_record = self.application_library.get(resolved)
        if saved_record is not None:
            preference = saved_record.preset.backend
        else:
            self._backend = str(self.settings.value("runtime/backend", "auto"))
            if self._backend not in {"auto", "wine", "proton"}:
                self._backend = "auto"
            self._dependencies = str(self.settings.value("runtime/dependencies", "auto"))
            if self._dependencies not in {"auto", "install", "skip"}:
                self._dependencies = "auto"
            self._windows_version = str(self.settings.value("runtime/windows-version", "") or "")
            if self._windows_version not in {"", "7", "8", "8.1", "10", "11"}:
                self._windows_version = ""
            self._prefix = ""
            self._arguments = ""
            self._proton_tuning = "default"
            self._proton = ""
            preference = self._backend
        self.stateChanged.emit()

        def inspect() -> AnalysisBundle:
            executable = analyze_executable(resolved)
            if not executable.valid:
                raise ValueError(executable.reason or "Invalid Windows executable")
            installations = discover_proton_installations()
            host = detect_host(proton_installations=installations)
            compatibility = analyze_compatibility(executable, host, preference)
            return AnalysisBundle(resolved, executable, host, compatibility, installations)

        self._start_task("analysis", f"Analyzing {resolved.name}", inspect, self._analysis_ready)

    @Slot()
    def analyzeSelected(self) -> None:
        if self.source_path is not None:
            self.analyzePath(str(self.source_path))

    def _analysis_ready(self, bundle: AnalysisBundle) -> None:
        self.source_path = bundle.source
        self.executable = bundle.executable
        self.host = bundle.host
        self.compatibility = bundle.compatibility
        self.proton_installations = bundle.proton_installations
        self._coerce_selected_proton()
        saved_record = self.application_library.get(bundle.source)
        if saved_record is not None:
            self._restore_application_preset(saved_record)
        self._update_runtime_state()
        self._update_analysis_state()
        self._remember_current_application()
        self._log(
            f"Analysis complete: {bundle.compatibility.architecture}, "
            f"{bundle.compatibility.backend}, "
            f"{len(bundle.compatibility.blocking_issues)} blocker(s)."
        )
        if self.auto_refresh:
            QTimer.singleShot(0, self.refreshLibrary)
        self.stateChanged.emit()

    def _analysis_failed(self, message: str, details: str) -> None:
        self._readiness_metric = _metric("Analysis failed", "Choose another file or retry", "error")
        self._file_metric = _metric("Unavailable", "Analysis did not complete", "error")
        self._arch_metric = _metric("Unavailable", "Analysis did not complete", "error")
        self._runtime_metric = _metric("Unavailable", "Analysis did not complete", "error")
        self._compatibility_metric = _metric("Unavailable", "Analysis did not complete", "error")
        self._guidance = [message]
        self._compatibility_issues = [{"kind": "error", "text": message}]
        self._score_deductions = []
        self._compatibility_notes = []
        self._task_failed(message, details)

    @Slot()
    def refreshLibrary(self) -> None:
        def load() -> LibraryBundle:
            return LibraryBundle(
                self.application_library.records(), discover_environments(), discover_backups()
            )

        self._start_task("library", "Refreshing application library", load, self._library_ready)

    def _library_ready(self, bundle: LibraryBundle) -> None:
        self._managed_environments = bundle.environments
        self._managed_backups = bundle.backups
        self._application_rows = [self._application_row(record) for record in bundle.applications]
        self._apply_application_filter()
        self.environmentsModel.replace(
            [self._environment_row(item) for item in bundle.environments]
        )
        self.backupsModel.replace([self._backup_row(item) for item in bundle.backups])

        if self.environmentsModel.index_of("identifier", self._selected_environment_id) < 0:
            self._selected_environment_id = ""
        if self.backupsModel.index_of("identifier", self._selected_backup_id) < 0:
            self._selected_backup_id = ""

        total_size = sum(item.size_bytes for item in bundle.environments)
        existing_apps = sum(record.exists for record in bundle.applications)
        self._application_metric = _metric(
            str(len(bundle.applications)),
            f"{existing_apps} source file(s) currently available",
            "success" if bundle.applications else "neutral",
        )
        self._storage_metric = _metric(
            format_size(total_size),
            f"{len(bundle.environments)} isolated environment(s)",
            "warning" if total_size >= 10 * 1024**3 else "neutral",
        )
        backup_size = sum(item.size_bytes for item in bundle.backups)
        self._backup_metric = _metric(
            format_size(backup_size),
            f"{len(bundle.backups)} restorable snapshot(s)",
            "success" if bundle.backups else "neutral",
        )
        self.stateChanged.emit()

    @staticmethod
    def _application_row(record: ApplicationRecord) -> dict[str, Any]:
        existence = "" if record.exists else "MISSING • "
        architecture = record.architecture or "unknown architecture"
        launches = f"{record.launch_count} launch{'es' if record.launch_count != 1 else ''}"
        last_result = (
            "not recorded" if record.last_exit_code is None else f"exit {record.last_exit_code}"
        )
        return {
            "path": record.path,
            "displayName": record.display_name,
            "headline": f"{existence}{record.display_name}",
            "subtitle": f"{architecture} • {launches}",
            "detail": (
                f"Last used: {record.last_used} • Backend: {record.preset.backend} • {last_result}"
            ),
            "exists": record.exists,
        }

    @staticmethod
    def _environment_row(environment: EnvironmentInfo) -> dict[str, Any]:
        state = "Ready" if environment.ready else "Incomplete"
        dxvk = (
            f"DXVK: {environment.dxvk_source}"
            if environment.dxvk_available
            else "DXVK: not detected"
            if environment.dxvk_available is False
            else "DXVK: unknown"
        )
        return {
            "identifier": environment.identifier,
            "application": environment.application,
            "headline": environment.application,
            "subtitle": (
                f"{environment.backend.upper()} • {format_size(environment.size_bytes)} • {state}"
            ),
            "detail": (
                f"{environment.runtime or environment.backend.title()} • {dxvk} • "
                f"{environment.path}"
            ),
            "path": str(environment.path),
            "backend": environment.backend,
        }

    @staticmethod
    def _backup_row(backup: BackupInfo) -> dict[str, Any]:
        return {
            "identifier": backup.identifier,
            "application": backup.application,
            "headline": backup.application,
            "subtitle": f"{backup.backend.upper()} • {format_size(backup.size_bytes)}",
            "detail": f"Created {backup.created_at} • {backup.identifier}",
            "backend": backup.backend,
        }

    def _apply_application_filter(self) -> None:
        query = self._application_search.strip().casefold()
        rows = [
            row
            for row in self._application_rows
            if not query
            or query in str(row["displayName"]).casefold()
            or query in str(row["path"]).casefold()
        ]
        self.applicationsModel.replace(rows)
        if self.applicationsModel.index_of("path", self._selected_application_path) < 0:
            self._selected_application_path = ""

    # ------------------------------------------------------------- Runtime management
    @Slot()
    def refreshRuntimes(self) -> None:
        def detect() -> RuntimeBundle:
            installations = discover_proton_installations()
            managed_components = frozenset(
                component
                for component in ("wine", "winetricks", "vulkan")
                if system_component_managed(component)
            )
            return RuntimeBundle(
                detect_host(proton_installations=installations),
                installations,
                managed_components,
            )

        self._start_task(
            "runtimes", "Refreshing Wine and Proton detection", detect, self._runtimes_ready
        )

    def _runtimes_ready(self, result: RuntimeBundle) -> None:
        self.host = result.host
        self.proton_installations = result.proton_installations
        self._managed_system_components = result.managed_system_components
        self._coerce_selected_proton()
        self._update_runtime_state()
        if self.executable is not None:
            self.compatibility = analyze_compatibility(self.executable, self.host, self._backend)
            self._update_analysis_state()
        self._log(
            "Runtime detection complete: "
            f"Wine={'yes' if self.host.wine_installed else 'no'}, "
            f"Proton={len(self.proton_installations)} build(s)."
        )
        self.stateChanged.emit()

    def _coerce_selected_proton(self) -> None:
        available = {str(item.script) for item in self.proton_installations}
        if self._proton and self._proton not in available:
            self._proton = ""

    @Slot(str)
    def installRuntimeComponent(self, component: str) -> None:
        if self._action_blocked():
            return
        if component not in {"wine", "winetricks", "vulkan"}:
            self.messageRequested.emit(
                "error", "Unsupported runtime component", f"RunEXE cannot install “{component}”."
            )
            return
        label = {
            "wine": "Wine",
            "winetricks": "Winetricks",
            "vulkan": "Vulkan tools",
        }[component]
        key = f"install-{component}"
        self._prepare_task_progress(key, f"Starting {label} installation", 0)
        self._start_task(
            key,
            f"Installing {label}",
            lambda: install_system_component(component, progress=self._progress_callback(key)),
            lambda _result: self._system_runtime_changed(label, "installed"),
        )

    def _system_runtime_changed(self, label: str, action: str) -> None:
        if label == "Vulkan tools" and action == "installed":
            self._log("Vulkan tools installation completed.")
        else:
            self._log(f"{label} {action} through the system package manager.")
        self._task_status = f"{label} {action}"
        self._set_header_status(f"{label} {action}", "ready")
        self._notify(f"{label} {action}", "Runtime detection is being refreshed.")
        QTimer.singleShot(0, self.refreshRuntimes)
        self.stateChanged.emit()

    @Slot()
    def installProton(self) -> None:
        if self._action_blocked():
            return
        self._prepare_task_progress("install-proton", "Starting GE-Proton installation", 0)

        def install_runtime() -> ProtonInstallation:
            report = self._progress_callback("install-proton")

            def proton_progress(label: str, value: int | None) -> None:
                report(label, None if value is None else int(value * 0.8))

            def umu_progress(label: str, value: int | None) -> None:
                report(label, None if value is None else 80 + int(value * 0.2))

            installation = install_managed_proton(progress=proton_progress)
            ensure_umu_launcher(progress=umu_progress)
            return installation

        self._start_task(
            "install-proton",
            "Installing GE-Proton and its UMU launcher",
            install_runtime,
            self._managed_proton_installed,
        )

    def _managed_proton_installed(self, installation: ProtonInstallation) -> None:
        self._log(f"Managed Proton ready: {installation.name} at {installation.install_dir}")
        self._task_status = f"Installed {installation.name}"
        self._set_header_status("Proton installed", "ready")
        self._notify("Proton installed", f"{installation.name} is ready to use.")
        QTimer.singleShot(0, self.refreshRuntimes)
        self.stateChanged.emit()

    @Slot()
    def installUmuLauncher(self) -> None:
        if self._action_blocked():
            return
        self._prepare_task_progress("install-umu", "Starting UMU Launcher installation", 0)
        self._start_task(
            "install-umu",
            "Installing UMU Launcher",
            lambda: install_managed_umu(progress=self._progress_callback("install-umu")),
            self._umu_launcher_installed,
        )

    def _umu_launcher_installed(self, executable: str | Path) -> None:
        self._log(f"UMU Launcher ready: {executable}")
        self._task_status = "UMU Launcher installed"
        self._set_header_status("UMU Launcher installed", "ready")
        self._notify(
            "UMU Launcher installed",
            "GE-Proton can now launch outside Steam through UMU.",
        )
        QTimer.singleShot(0, self.refreshRuntimes)
        self.stateChanged.emit()

    @Slot()
    def installVulkanTools(self) -> None:
        self.installRuntimeComponent("vulkan")

    def _vulkan_tools_installed(self, _result: object) -> None:
        self._log("Vulkan tools installation completed.")
        self._task_status = "Vulkan tools installed"
        self._set_header_status("Vulkan tools installed", "ready")
        self._notify("Vulkan tools installed", "Graphics readiness can now be checked again.")
        QTimer.singleShot(0, self.refreshRuntimes)
        self.stateChanged.emit()

    @Slot(str)
    def uninstallRuntimeComponent(self, component: str) -> None:
        if self._action_blocked():
            return

        if component == "proton":
            self._prepare_task_progress("remove-proton", "Removing RunEXE-managed Proton", 0)
            self._start_task(
                "remove-proton",
                "Removing RunEXE-managed Proton",
                remove_managed_proton,
                lambda removed: self._managed_runtime_removed("Proton", int(removed)),
            )
            return
        if component == "umu":
            self._prepare_task_progress("remove-umu", "Removing RunEXE-managed UMU Launcher", 0)
            self._start_task(
                "remove-umu",
                "Removing RunEXE-managed UMU Launcher",
                remove_managed_umu,
                lambda removed: self._managed_runtime_removed("UMU Launcher", int(bool(removed))),
            )
            return
        if component not in {"wine", "winetricks", "vulkan"}:
            self.messageRequested.emit(
                "error", "Unsupported runtime component", f"RunEXE cannot remove “{component}”."
            )
            return
        if component not in self._managed_system_components:
            self.messageRequested.emit(
                "info",
                "System-managed component",
                "RunEXE only removes system packages that it originally installed "
                "and can still verify.",
            )
            return

        label = {
            "wine": "Wine",
            "winetricks": "Winetricks",
            "vulkan": "Vulkan tools",
        }[component]
        key = f"remove-{component}"
        self._prepare_task_progress(key, f"Starting {label} removal", 0)
        self._start_task(
            key,
            f"Removing {label}",
            lambda: uninstall_system_component(component, progress=self._progress_callback(key)),
            lambda _result: self._system_runtime_changed(label, "removed"),
        )

    def _managed_runtime_removed(self, label: str, removed: int) -> None:
        detail = f"Removed {removed} managed installation(s)." if removed else "Nothing to remove."
        self._log(f"{label} removal completed. {detail}")
        self._task_status = f"{label} removed" if removed else f"No managed {label} found"
        self._set_header_status(self._task_status, "ready")
        self._notify(f"{label} removal complete", detail)
        QTimer.singleShot(0, self.refreshRuntimes)
        self.stateChanged.emit()

    # ------------------------------------------------------------- Launch setup/actions
    def _current_preset(self) -> LaunchPreset:
        return LaunchPreset(
            backend=self._backend,
            proton=self._proton or None,
            proton_tuning=self._proton_tuning or "default",
            windows_version=self._windows_version or None,
            dependencies=self._dependencies,
            prefix=self._prefix.strip() or None,
            arguments=self._arguments,
        )

    def _restore_application_preset(self, record: ApplicationRecord) -> None:
        preset = record.preset
        self._backend = preset.backend or "auto"
        self._proton = preset.proton or ""
        self._proton_tuning = preset.proton_tuning or "default"
        self._windows_version = preset.windows_version or ""
        self._dependencies = preset.dependencies or "auto"
        self._prefix = preset.prefix or ""
        self._arguments = preset.arguments
        self._coerce_selected_proton()

    def _application_display_name(self) -> str:
        if self.executable is None:
            return "Unknown application"
        if self.executable.package is not None:
            return self.executable.package.display_name or self.executable.package.identity_name
        if self.executable.version_info is not None:
            return (
                self.executable.version_info.strings.get("ProductName") or self.executable.path.stem
            )
        return self.executable.path.stem

    def _remember_current_application(self) -> None:
        if self.executable is None:
            return
        try:
            self.application_library.remember_analysis(
                self.executable.path,
                display_name=self._application_display_name(),
                architecture=self.executable.architecture,
                file_format=self.executable.format,
                preset=self._current_preset(),
            )
        except OSError as error:
            self._log(f"WARNING: Could not update application library: {error}")

    @Slot()
    def applyProfileRecommendation(self) -> None:
        profile = self.compatibility.profile if self.compatibility else None
        if profile is None:
            return
        if profile.recommended_windows_version is not None:
            self._windows_version = profile.recommended_windows_version
            self.settings.setValue("runtime/windows-version", self._windows_version)
        self._update_profile_state()
        self._update_environment_preview()
        self._task_status = f"Applied the {profile.name} setup"
        self.navigateRequested.emit(self.PAGE_LAUNCH_SETUP)
        self.stateChanged.emit()

    @Slot()
    def prepareSelectedEnvironment(self) -> None:
        if self._action_blocked():
            return
        selected = self._require_analysis()
        if selected is None:
            return
        executable, report = selected

        def prepare() -> PreparedEnvironment:
            return prepare_environment(
                executable,
                report,
                prefix=Path(self._prefix).expanduser() if self._prefix.strip() else None,
                install_dependencies=self._install_dependencies(report),
                proton=self._proton or None,
                proton_tuning=self._selected_proton_tuning(report),
                winver=self._windows_version or None,
            )

        self._start_task("prepare", "Preparing isolated environment", prepare, self._prepared)

    def _prepared(self, prepared: PreparedEnvironment) -> None:
        self._remember_current_application()
        self._log(
            f"Environment ready: {prepared.runtime_name} at {prepared.path} ({prepared.wine_arch})."
        )
        self._environment_status = f"READY | {prepared.runtime_name}"
        self._set_header_status("Environment ready", "ready")
        self._notify("Environment ready", f"{prepared.runtime_name} setup finished successfully.")
        self.stateChanged.emit()

    @Slot(str)
    def openRuntimeSettings(self, backend: str) -> None:
        if self._action_blocked():
            return
        selected = self._require_analysis()
        if selected is None or self.host is None:
            return
        executable, _current_report = selected
        report = analyze_compatibility(executable, self.host, backend)
        if report.blocking_issues:
            self.messageRequested.emit(
                "warning", "Runtime unavailable", "\n".join(report.blocking_issues)
            )
            return

        def configure() -> PreparedEnvironment:
            return open_runtime_configuration(
                executable,
                report,
                prefix=Path(self._prefix).expanduser() if self._prefix.strip() else None,
                proton=(self._proton or None) if backend == "proton" else None,
            )

        self._start_task(
            f"configure-{backend}",
            f"Opening {backend.title()} settings",
            configure,
            lambda prepared: self._log(
                f"Opened {prepared.runtime_name} settings for {prepared.path}."
            ),
        )

    @Slot()
    def launchApplication(self) -> None:
        if self._action_blocked():
            return
        selected = self._require_analysis()
        if selected is None:
            return
        executable, report = selected
        if report.blocking_issues:
            self.messageRequested.emit(
                "warning", "Launch blocked", "\n".join(report.blocking_issues)
            )
            return
        try:
            arguments = shlex.split(self._arguments)
        except ValueError as error:
            self.messageRequested.emit("warning", "Invalid arguments", str(error))
            return

        def prepare() -> PreparedEnvironment:
            return prepare_environment(
                executable,
                report,
                winver=self._windows_version or None,
                prefix=Path(self._prefix).expanduser() if self._prefix.strip() else None,
                install_dependencies=self._install_dependencies(report),
                proton=self._proton or None,
                proton_tuning=self._selected_proton_tuning(report),
            )

        self._start_task(
            "launch",
            f"Preparing {executable.path.name}",
            prepare,
            lambda prepared: self._start_application(executable, prepared, arguments),
        )

    def _selected_proton_tuning(self, report: CompatibilityReport) -> str:
        return self._proton_tuning if report.backend == "proton" else "default"

    def _install_dependencies(self, report: CompatibilityReport) -> bool:
        if self._dependencies == "install":
            return True
        if self._dependencies == "skip":
            return False
        return report.backend == "wine"

    def _require_analysis(self) -> tuple[ExecutableInfo, CompatibilityReport] | None:
        if self.executable is None or self.compatibility is None:
            self.messageRequested.emit(
                "info", "Select an application", "Analyze an application first."
            )
            self.navigateRequested.emit(self.PAGE_OVERVIEW)
            return None
        return self.executable, self.compatibility

    # ------------------------------------------------------------- Managed items
    @Slot()
    def openSelectedApplication(self) -> None:
        if self._action_blocked():
            return
        row = self.applicationsModel.item(self.selectedApplicationIndex)
        if not row:
            self._selection_required("application", self.PAGE_APPLICATIONS)
            return
        path = Path(str(row["path"]))
        if not path.exists():
            self.messageRequested.emit(
                "warning",
                "Application moved or removed",
                f"The saved source no longer exists:\n{path}\n\n"
                "Use Forget entry or Prune missing to remove it from the library.",
            )
            return
        self.navigateRequested.emit(self.PAGE_OVERVIEW)
        self.analyzePath(str(path))

    @Slot()
    def forgetSelectedApplication(self) -> None:
        row = self.applicationsModel.item(self.selectedApplicationIndex)
        if self._library_busy():
            self._library_action_blocked()
            return
        if not row:
            self._selection_required("application", self.PAGE_APPLICATIONS)
            return
        try:
            self.application_library.forget(Path(str(row["path"])))
        except OSError as error:
            self.messageRequested.emit("error", "Could not update library", str(error))
            return
        self._selected_application_path = ""
        self.refreshLibrary()

    @Slot()
    def pruneMissingApplications(self) -> None:
        if self._library_busy():
            self._library_action_blocked()
            return
        try:
            removed = self.application_library.prune_missing()
        except OSError as error:
            self.messageRequested.emit("error", "Could not update library", str(error))
            return
        self._task_status = (
            f"Removed {removed} missing application entr{'y' if removed == 1 else 'ies'}"
        )
        self.refreshLibrary()

    def _selected_environment(self) -> EnvironmentInfo | None:
        return next(
            (
                environment
                for environment in self._managed_environments
                if environment.identifier == self._selected_environment_id
            ),
            None,
        )

    def _selected_backup(self) -> BackupInfo | None:
        return next(
            (
                backup
                for backup in self._managed_backups
                if backup.identifier == self._selected_backup_id
            ),
            None,
        )

    @Slot()
    def openSelectedEnvironmentFolder(self) -> None:
        environment = self._selected_environment()
        if environment is None:
            self._selection_required("environment", self.PAGE_ENVIRONMENTS)
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(environment.path))):
            self.messageRequested.emit(
                "warning", "Could not open folder", f"Open this path manually:\n{environment.path}"
            )

    @Slot(str)
    def configureSelectedEnvironment(self, tool: str = "winecfg") -> None:
        if self._action_blocked():
            return
        environment = self._selected_environment()
        if environment is None:
            self._selection_required("environment", self.PAGE_ENVIRONMENTS)
            return
        if tool not in CONFIGURATION_TOOLS:
            self.messageRequested.emit(
                "error",
                "Configuration tool unavailable",
                "RunEXE does not recognize the selected configuration tool.",
            )
            return
        try:
            open_environment_configuration(environment, tool)
        except ConfigurationError as error:
            self.messageRequested.emit("error", "Could not open environment settings", str(error))
            return
        label = CONFIGURATION_TOOLS[tool][0]
        self._log(f"Opened {label} for {environment.identifier}.")
        self._task_status = f"Opened {label} for {environment.application}"
        self.stateChanged.emit()

    @Slot()
    def backupSelectedEnvironment(self) -> None:
        if self._library_busy():
            self._library_action_blocked()
            return
        environment = self._selected_environment()
        if environment is None:
            self._selection_required("environment", self.PAGE_ENVIRONMENTS)
            return
        self._start_task(
            "backup-environment",
            f"Backing up {environment.application}",
            lambda: create_environment_backup(environment),
            self._environment_backed_up,
        )

    def _environment_backed_up(self, backup: BackupInfo) -> None:
        self._log(f"Created environment backup: {backup.identifier}")
        self._task_status = f"Backup ready: {backup.identifier}"
        self._notify("Backup ready", f"Created {backup.application} environment backup.")
        QTimer.singleShot(0, self.refreshLibrary)
        self.stateChanged.emit()

    @Slot(bool)
    def removeSelectedEnvironment(self, with_backup: bool) -> None:
        if self._action_blocked():
            return
        if self._library_busy():
            self._library_action_blocked()
            return
        environment = self._selected_environment()
        if environment is None:
            self._selection_required("environment", self.PAGE_ENVIRONMENTS)
            return

        def remove() -> tuple[str, str | None]:
            backup = create_environment_backup(environment) if with_backup else None
            remove_managed_environment(environment.path)
            return environment.identifier, backup.identifier if backup else None

        self._start_task(
            "remove-environment",
            f"Removing {environment.application}'s isolated environment",
            remove,
            self._environment_removed,
        )

    def _environment_removed(self, result: tuple[str, str | None]) -> None:
        identifier, backup_identifier = result
        if backup_identifier:
            self._log(f"Created environment backup: {backup_identifier}")
        self._log(f"Removed managed environment: {identifier}")
        self._task_status = f"Removed {identifier}"
        self._selected_environment_id = ""
        self._notify("Environment removed", f"Removed managed environment {identifier}.")
        QTimer.singleShot(0, self.refreshLibrary)
        self.stateChanged.emit()

    @Slot()
    def restoreSelectedBackup(self) -> None:
        if self._action_blocked():
            return
        if self._library_busy():
            self._library_action_blocked()
            return
        backup = self._selected_backup()
        if backup is None:
            self._selection_required("backup", self.PAGE_BACKUPS)
            return
        self._start_task(
            "restore-backup",
            f"Restoring {backup.application}",
            lambda: restore_backup(backup),
            lambda target: self._backup_restored(backup.identifier, target),
        )

    def _backup_restored(self, identifier: str, target: Path) -> None:
        self._log(f"Restored backup {identifier}: {target}")
        self._task_status = f"Restored {identifier}"
        self._notify("Backup restored", f"Restored the environment to {target}.")
        QTimer.singleShot(0, self.refreshLibrary)
        self.stateChanged.emit()

    @Slot()
    def removeSelectedBackup(self) -> None:
        if self._library_busy():
            self._library_action_blocked()
            return
        backup = self._selected_backup()
        if backup is None:
            self._selection_required("backup", self.PAGE_BACKUPS)
            return
        self._start_task(
            "remove-backup",
            f"Deleting backup {backup.identifier}",
            lambda: (remove_backup(backup), backup.identifier)[1],
            self._backup_removed,
        )

    def _backup_removed(self, identifier: str) -> None:
        self._log(f"Removed environment backup: {identifier}")
        self._task_status = f"Removed backup {identifier}"
        self._selected_backup_id = ""
        QTimer.singleShot(0, self.refreshLibrary)
        self.stateChanged.emit()

    # ------------------------------------------------------------- Process/activity
    def _start_application(
        self, executable: ExecutableInfo, prepared: PreparedEnvironment, arguments: list[str]
    ) -> None:
        spec = build_launch_spec(executable, prepared, arguments)
        process = QProcess(self)
        process.setProgram(spec.command[0])
        process.setArguments(list(spec.command[1:]))
        process.setWorkingDirectory(str(spec.cwd))
        environment = QProcessEnvironment()
        for name, value in spec.env.items():
            environment.insert(name, value)
        process.setProcessEnvironment(environment)
        process.readyReadStandardOutput.connect(self._read_application_stdout)
        process.readyReadStandardError.connect(self._read_application_stderr)
        process.started.connect(self._application_started)
        process.finished.connect(self._application_finished)
        process.errorOccurred.connect(self._application_error)
        self.application_process = process
        self._active_launch_path = executable.path
        self._active_launch_preset = self._current_preset()
        self._application_output.clear()
        process.start()
        self._update_controls_state()

    def _read_application_stdout(self) -> None:
        if self.application_process is None:
            return
        output = bytes(self.application_process.readAllStandardOutput()).decode(errors="replace")
        if output:
            self._application_output.append(output)
            self._log("Application output:\n" + output.rstrip())

    def _read_application_stderr(self) -> None:
        if self.application_process is None:
            return
        output = bytes(self.application_process.readAllStandardError()).decode(errors="replace")
        if output:
            self._application_output.append(output)
            self._log("Application errors:\n" + output.rstrip())

    def _application_started(self) -> None:
        if self._active_launch_path is not None and self._active_launch_preset is not None:
            try:
                self.application_library.record_launch(
                    self._active_launch_path, self._active_launch_preset
                )
            except OSError as error:
                self._log(f"WARNING: Could not save launch preset: {error}")
        name = self._active_launch_path.name if self._active_launch_path else "application"
        self._log(f"Application started: {name}")
        self._task_status = "Application is running"
        self._update_controls_state()

    def _application_finished(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        self._read_application_stdout()
        self._read_application_stderr()
        self._log(f"Application exited with code {exit_code}.")
        diagnostic = detect_runtime_issue(
            "\n".join(self._application_output),
            exit_code,
            self.compatibility.profile if self.compatibility is not None else None,
        )
        completed_name = (
            self._active_launch_path.name if self._active_launch_path else "Application"
        )
        if self._active_launch_path is not None:
            try:
                self.application_library.record_exit(self._active_launch_path, exit_code)
            except OSError as error:
                self._log(f"WARNING: Could not save launch result: {error}")
        self._active_launch_path = None
        self._active_launch_preset = None
        if self.application_process is not None:
            self.application_process.deleteLater()
        self.application_process = None
        self._task_status = "Ready"
        if diagnostic is not None:
            self._log(f"DETECTED: {diagnostic.message}")
            if diagnostic.recommended_windows_version is not None:
                self._windows_version = diagnostic.recommended_windows_version
                self.settings.setValue("runtime/windows-version", self._windows_version)
            if self.compatibility is not None and self.compatibility.profile is not None:
                self._profile_summary = diagnostic.message
                self._profile_visible = True
            self.navigateRequested.emit(self.PAGE_OVERVIEW)
            self.profileFocusRequested.emit()
            self._task_status = diagnostic.title
            self._set_header_status(diagnostic.title, "warning")
            self.messageRequested.emit("warning", diagnostic.title, diagnostic.message)
            self._notify(diagnostic.title, diagnostic.message)
        else:
            self._set_header_status(
                "Launch completed" if exit_code == 0 else "Application failed",
                "ready" if exit_code == 0 else "error",
            )
            if exit_code != 0:
                self.messageRequested.emit(
                    "error",
                    "Application exited unexpectedly",
                    f"The application exited with code {exit_code}. "
                    "Open Activity to review its output and errors.",
                )
            self._notify(
                "Application finished" if exit_code == 0 else "Application exited unexpectedly",
                (
                    f"{completed_name} exited normally."
                    if exit_code == 0
                    else f"{completed_name} exited with code {exit_code}."
                ),
            )
        self._update_environment_preview()
        self._update_controls_state()

    def _application_error(self, error: QProcess.ProcessError) -> None:
        if self.application_process is None:
            return
        error_text = self.application_process.errorString()
        self._log(f"Application process error: {error_text}")
        if error == QProcess.ProcessError.FailedToStart:
            self.messageRequested.emit("error", "Could not start application", error_text)
            self.application_process.deleteLater()
            self.application_process = None
            self._active_launch_path = None
            self._active_launch_preset = None
            self._task_status = "Ready"
            self._set_header_status("Application failed", "error")
            self._update_controls_state()

    @Slot()
    def copyActivity(self) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self.activityText)
        self._set_task_status("Activity copied to clipboard")

    @Slot()
    def clearActivity(self) -> None:
        self._activity_lines.clear()
        self._activity_model.clear()
        self._set_task_status("Activity cleared")

    @Slot(str)
    def exportSupportReport(self, value: str) -> None:
        if not value:
            return
        target = _local_path(value)
        payload = {
            "schema": 1,
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "runexe_version": __version__,
            "source": str(self.source_path) if self.source_path is not None else None,
            "executable": asdict(self.executable) if self.executable is not None else None,
            "compatibility": asdict(self.compatibility) if self.compatibility is not None else None,
            "host": asdict(self.host) if self.host is not None else None,
            "launch_preset": asdict(self._current_preset()),
            "managed_environments": [item.as_dict() for item in self._managed_environments],
            "environment_backups": [item.as_dict() for item in self._managed_backups],
            "activity": list(self._activity_lines),
        }
        temporary = target.with_name(f".{target.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(
                json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8"
            )
            if os.name == "posix":
                temporary.chmod(0o600)
            temporary.replace(target)
        except OSError as error:
            self.messageRequested.emit("error", "Could not export report", str(error))
            return
        finally:
            temporary.unlink(missing_ok=True)
        self._log(f"Exported support report: {target}")
        self._set_task_status(f"Report saved to {target}")

    # ------------------------------------------------------------- Closing
    @Slot()
    def requestClose(self) -> None:
        if self._workers:
            self.messageRequested.emit(
                "info",
                "RunEXE is still working",
                "Wait for the current preparation task to finish before closing the window.",
            )
            return
        if self._application_running():
            self.closeConfirmationRequested.emit()
            return
        QCoreApplication.quit()

    @Slot()
    def confirmClose(self) -> None:
        if self.application_process is not None:
            self.application_process.kill()
            self.application_process.waitForFinished(3000)
        QCoreApplication.quit()

    # ------------------------------------------------------------- Derived state helpers
    def _update_analysis_state(self) -> None:
        executable = self.executable
        report = self.compatibility
        if executable is None or report is None:
            return
        self._file_metric = _metric(executable.format or "Unknown", report.application_type)
        self._arch_metric = _metric(report.architecture, report.wine_arch or "Unsupported")
        self._runtime_metric = _metric(
            report.recommended_runtime,
            report.backend.upper(),
            "error" if report.blocking_issues else "neutral",
        )
        if report.blocking_issues:
            self._readiness_metric = _metric(
                "Blocked", f"{len(report.blocking_issues)} issue(s)", "error"
            )
        elif report.warnings:
            self._readiness_metric = _metric(
                "Review warnings", f"{len(report.warnings)} warning(s)", "warning"
            )
        else:
            self._readiness_metric = _metric("Ready", "No blocking issues detected", "success")

        score = report.compatibility_score
        if score is None:
            self._compatibility_metric = _metric(
                "Not scored", "Local compatibility estimate unavailable"
            )
        else:
            score_state = (
                "error"
                if report.blocking_issues
                else "success"
                if score >= 90
                else "warning"
                if score < 75 or report.warnings
                else "neutral"
            )
            self._compatibility_metric = _metric(
                f"{score}/100", report.compatibility_rating, score_state
            )

        product = "Unknown product"
        if executable.version_info:
            product = executable.version_info.strings.get("ProductName", product)
        if executable.package:
            product = executable.package.display_name or executable.package.identity_name
        self._product = product
        self._subsystem = executable.subsystem or "Unknown"
        self._dependency_text = (
            ", ".join(item.name for item in report.dependencies) or "None detected"
        )
        self._guidance = [
            *(f"BLOCKED  {issue}" for issue in report.blocking_issues),
            *(f"WARNING  {warning}" for warning in report.warnings),
            *(f"SCORE  {factor}" for factor in report.compatibility_factors),
            *(f"INFO  {note}" for note in report.notes),
        ] or ["No compatibility concerns were detected."]
        self._compatibility_issues = []
        for issue in report.blocking_issues:
            self._compatibility_issues.append({"kind": "blocked", "text": issue})
        for warning in report.warnings:
            self._compatibility_issues.append({"kind": "warning", "text": warning})

        self._score_deductions = []
        for factor in report.compatibility_factors:
            if factor.startswith("-") and ":" in factor:
                impact, reason = factor.split(":", 1)
                self._score_deductions.append(
                    {"impact": f"{impact.strip()} points", "reason": reason.strip()}
                )

        self._compatibility_notes = list(report.notes)
        if not self._compatibility_issues and not self._score_deductions:
            self._compatibility_notes.insert(0, "No compatibility concerns were detected.")
        self._environment_status = f"{report.backend.upper()} | {report.architecture}"
        self._update_profile_state()
        self._update_environment_preview()
        self._update_controls_state()

    def _update_profile_state(self) -> None:
        profile = self.compatibility.profile if self.compatibility else None
        if profile is None:
            self._profile_visible = False
            self._profile_summary = ""
            self._profile_requirements = ""
            self._profile_button = "Apply recommended setup"
            return
        self._profile_visible = True
        self._profile_title = f"{profile.name} setup detected"
        self._profile_summary = profile.summary
        self._profile_requirements = " • ".join(profile.requirements)
        recommended = profile.recommended_windows_version
        if not self._windows_version and recommended is not None:
            self._windows_version = recommended
            self.settings.setValue("runtime/windows-version", self._windows_version)
        if recommended is None:
            self._profile_button = "Review requirements"
        elif self._windows_version == recommended:
            self._profile_button = f"Review Windows {recommended} setup"
        else:
            self._profile_button = f"Use Windows {recommended}"

    def _update_environment_preview(self) -> None:
        if self.executable is None or self.compatibility is None:
            self._environment_preview = (
                "Select and analyze an application to preview its environment."
            )
            return
        if self._prefix.strip():
            path = Path(self._prefix).expanduser()
        elif self.compatibility.backend == "proton":
            from runexe.proton import compat_data_path_for

            path = compat_data_path_for(self.executable.path)
        else:
            from runexe.runner import prefix_path_for

            path = prefix_path_for(self.executable)
        kind = "Proton compat data" if self.compatibility.backend == "proton" else "Wine prefix"
        version_text = (
            f"Windows {self._windows_version}"
            if self._windows_version
            else "runtime-default Windows version"
        )
        self._environment_preview = f"{kind}: {path}\nReports {version_text}"

    def _update_runtime_state(self) -> None:
        if self.host is None:
            return
        self._wine_metric = _metric(
            "Available" if self.host.wine_installed else "Not found",
            self.host.wine_version or "Install Wine to use this backend",
            "success" if self.host.wine_installed else "error",
        )
        proton_detail = (
            f"{len(self.proton_installations)} build(s) discovered"
            if self.proton_installations
            else "Install with RunEXE, Steam, or add a custom build"
        )
        self._proton_metric = _metric(
            "Available" if self.proton_installations else "Not found",
            proton_detail,
            "success" if self.proton_installations else "error",
        )
        self._winetricks_metric = _metric(
            "Available" if self.host.winetricks_installed else "Optional",
            "Automatic dependencies enabled"
            if self.host.winetricks_installed
            else "Required only for detected extra components",
            "success" if self.host.winetricks_installed else "warning",
        )
        if self.host.vulkan_available:
            devices = ", ".join(self.host.vulkan_devices) or "Vulkan-capable device detected"
            detail = (
                f"{devices} • Vulkan {self.host.vulkan_version}"
                if self.host.vulkan_version
                else devices
            )
            self._vulkan_metric = _metric("Ready", detail, "success")
        elif self.host.vulkan_available is False:
            self._vulkan_metric = _metric(
                "Unavailable",
                self.host.vulkan_error or "Check the GPU driver and Vulkan ICD",
                "error",
            )
        else:
            self._vulkan_metric = _metric(
                "Unknown", "Install vulkan-tools to verify DXVK/VKD3D readiness", "warning"
            )

    def _set_header_status(self, text: str, state: str) -> None:
        self._header_status = text
        self._header_state = state

    def _update_controls_state(self) -> None:
        if self._application_running():
            self._set_header_status("Application running", "ready")
        elif self._workers:
            self._set_header_status("Working", "warning")
        elif self.analyzed and self.compatibility and not self.compatibility.blocking_issues:
            self._set_header_status("Ready to launch", "ready")
        elif self.analyzed:
            self._set_header_status("Action required", "error")
        elif self.source_path is not None:
            self._set_header_status("Analysis required", "warning")
        elif self.host is not None:
            runtime_available = self.host.wine_installed or self.host.proton_installed
            self._set_header_status(
                "Runtimes detected" if runtime_available else "No runtime found",
                "ready" if runtime_available else "warning",
            )
        self.stateChanged.emit()

    def _library_busy(self) -> bool:
        return bool(
            {
                "library",
                "remove-environment",
                "backup-environment",
                "restore-backup",
                "remove-backup",
            }
            & self._workers.keys()
        )

    def _application_running(self) -> bool:
        return bool(
            self.application_process is not None
            and self.application_process.state() != QProcess.ProcessState.NotRunning
        )

    def _action_blocked(self) -> bool:
        blocking = [key for key in self._workers if key != "library"]
        if blocking:
            message = "Wait for the current task to finish"
            self._set_task_status(message)
            self.messageRequested.emit(
                "info", "Action unavailable while RunEXE is working", message + "."
            )
            return True
        if self._application_running():
            message = "Close the running application before changing its setup"
            self._set_task_status(message)
            self.messageRequested.emit("info", "Application is still running", message + ".")
            return True
        return False

    def _library_action_blocked(self) -> None:
        message = "Wait for the current library action to finish"
        self._set_task_status(message)
        self.messageRequested.emit("info", "Library action already in progress", message + ".")

    def _selection_required(self, item: str, page: int) -> None:
        article = "an" if item[:1].lower() in "aeiou" else "a"
        self.messageRequested.emit(
            "info",
            f"Select {article} {item}",
            f"Choose {article} {item} from the list before using this action.",
        )
        self.navigateRequested.emit(page)
        if item == "environment":
            self.settingsSectionRequested.emit("environments")

    # ------------------------------------------------------------- Background tasks
    def _prepare_task_progress(self, key: str, label: str, value: int = -1) -> None:
        self._task_progress_key = key
        self._task_progress_label = label
        self._task_progress_value = value

    def _progress_callback(self, key: str):
        def report(label: str, value: int | None = None) -> None:
            self.taskProgressRequested.emit(key, label, -1 if value is None else int(value))

        return report

    @Slot(str, str, int)
    def _task_progress_requested(self, key: str, label: str, value: int) -> None:
        if key not in self._workers:
            return
        self._task_progress_key = key
        self._task_progress_label = label
        self._task_progress_value = -1 if value < 0 else max(0, min(100, value))
        self.stateChanged.emit()

    def _start_task(self, key: str, label: str, function, on_result) -> None:
        if key in self._workers:
            message = f"{label} is already running"
            self._set_task_status(message)
            self.messageRequested.emit("info", "Action already in progress", message + ".")
            return
        worker = Worker(function)
        worker.signals.result.connect(on_result)
        worker.signals.error.connect(
            self._analysis_failed if key == "analysis" else self._task_failed
        )
        worker.signals.finished.connect(lambda: self._task_finished(key))
        self._workers[key] = worker
        self._task_status = label
        self._log(label)
        self._update_controls_state()
        self.thread_pool.start(worker)

    def _task_failed(self, message: str, details: str) -> None:
        self._log(f"ERROR: {message}")
        self._log(details.rstrip())
        self.messageRequested.emit("error", "RunEXE could not complete the action", message)
        self._notify("RunEXE action failed", message)
        self.stateChanged.emit()

    def _task_finished(self, key: str) -> None:
        self._workers.pop(key, None)
        if key == self._task_progress_key:
            self._task_progress_key = ""
            self._task_progress_label = ""
            self._task_progress_value = -1
        if not self._workers and self._task_status not in {
            "Activity copied to clipboard",
            "Activity cleared",
        }:
            self._task_status = "Ready"
        self._update_controls_state()

    def _set_task_status(self, text: str) -> None:
        self._task_status = text
        self.stateChanged.emit()

    def _notify(self, title: str, body: str) -> None:
        if self._notifications_enabled:
            self.notificationRequested.emit(title, body)

    def _log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] {message}"
        self._activity_lines.append(line)
        if len(self._activity_lines) > 3000:
            del self._activity_lines[: len(self._activity_lines) - 3000]
        self._activity_model.append(line)
        self.stateChanged.emit()
