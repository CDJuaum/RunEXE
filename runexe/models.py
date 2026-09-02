from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PEDataDirectory:
    virtual_address: int
    size: int


@dataclass
class PESection:
    name: str
    virtual_size: int
    virtual_address: int
    raw_size: int
    raw_offset: int


@dataclass
class PEImport:
    name: str
    functions: list[str] = field(default_factory=list)


@dataclass
class VersionInfo:
    """Parsed VS_VERSIONINFO resource (RT_VERSION)."""

    file_version: str | None = None
    product_version: str | None = None
    # Raw StringTable key/value pairs, e.g. "ProductName", "CompanyName",
    # "FileDescription".
    strings: dict[str, str] = field(default_factory=dict)


@dataclass
class PackageInfo:
    """Metadata for an AppX/MSIX package materialized for Wine."""

    source: Path
    root: Path
    manifest: Path
    identity_name: str
    version: str | None = None
    publisher: str | None = None
    display_name: str | None = None
    application_id: str | None = None
    package_type: str = "AppX/MSIX"


@dataclass
class ExecutableInfo:
    path: Path
    valid: bool
    format: str | None = None
    architecture: str | None = None
    subsystem: str | None = None
    reason: str | None = None
    sections: list[PESection] | None = None
    data_directories: list[PEDataDirectory] | None = None
    imports: list[PEImport] | None = None
    manifest: str | None = None
    version_info: VersionInfo | None = None
    package: PackageInfo | None = None


@dataclass(frozen=True)
class Dependency:
    """A runtime or Windows component detected from an executable."""

    name: str
    category: str
    confidence: str = "high"
    winetricks_verb: str | None = None


@dataclass(frozen=True)
class GraphicsRequirements:
    """Graphics APIs inferred from PE imports and their likely translators."""

    apis: tuple[str, ...] = ()
    translators: tuple[str, ...] = ()
    vulkan_recommended: bool = False
    vulkan_required: bool = False


@dataclass(frozen=True)
class ApplicationClassification:
    """Result of classify_application(): the game/application verdict
    plus enough detail to see why it was reached.

    `confidence` is "high" when a single signal is specific enough to
    stand on its own (Steam API, a known engine/platform SDK, an
    on-disk engine data marker) and "medium" when the verdict rests on
    multiple weaker signals combined. There is no "low"-confidence
    "game" result -- a signal too weak to combine with another one
    isn't used at all, so uncertain cases fall back to "application"
    with confidence "medium" instead of guessing.
    """

    category: str
    confidence: str
    signals: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ApplicationProfile:
    """Known compatibility requirements for a detected application family."""

    key: str
    name: str
    recommended_windows_version: str | None = None
    minimum_windows_build: int | None = None
    summary: str = ""
    requirements: tuple[str, ...] = ()


@dataclass
class CompatibilityReport:
    application_type: str
    architecture: str
    # "game" or "application" - drives the Wine vs. Proton recommendation.
    category: str
    # "wine", "proton", or "unsupported".
    backend: str
    # Human-readable version of `backend`, e.g. "Proton (Steam Play)".
    recommended_runtime: str
    wine_arch: str | None = None
    supported: bool = True
    # Detected reasons the app is unlikely to run at all regardless of
    # backend (e.g. kernel-level anti-cheat), separate from `notes`
    # so callers can act on this without parsing free text.
    blocking_issues: list[str] = field(default_factory=list)
    # Important but non-deterministic compatibility concerns, such as
    # per-title anti-cheat enablement.
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    # Winetricks verbs (e.g. "vcrun2015", "dotnet48") that should be
    # installed into the prefix before launch, inferred from imports
    # and the CLR header. See dependencies.py.
    required_verbs: list[str] = field(default_factory=list)
    dependencies: list[Dependency] = field(default_factory=list)
    profile: ApplicationProfile | None = None
    graphics: GraphicsRequirements | None = None
    # "high" or "medium" -- see ApplicationClassification. Defaults to
    # "medium" for reports built without going through
    # classify_application (e.g. hand-built test fixtures).
    classification_confidence: str = "medium"
    # Human-readable reasons behind `category`, e.g. "Steam API import
    # (steam_api64.dll)". Empty when category was set some other way.
    classification_signals: list[str] = field(default_factory=list)


@dataclass
class HostInfo:
    architecture: str
    wine_installed: bool
    wine_version: str | None
    # None means that read-only inspection could not prove support either
    # way. Prefix creation performs the definitive capability check.
    wine_wow64: bool | None
    wine_32bit_prefix: bool | None
    winetricks_installed: bool
    proton_installed: bool = False
    proton_versions: list[str] = field(default_factory=list)
    # None means vulkaninfo is unavailable and readiness is unknown.
    vulkan_available: bool | None = None
    vulkan_version: str | None = None
    vulkan_devices: list[str] = field(default_factory=list)
    vulkan_error: str | None = None
    # True when a hardware-backed Vulkan driver is loadable, which DXVK
    # and VKD3D-Proton require to translate Direct3D. See gpu.py.
    vulkan_supported: bool = False
    gpu_vendors: list[str] = field(default_factory=list)
