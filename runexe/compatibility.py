import json
from pathlib import Path

from runexe.constants import (
    ANTI_CHEAT_DLLS,
    DIRECT3D_VULKAN_APIS,
    GAME_ENGINE_DATA_DIR_SUFFIX,
    GAME_ENGINE_IDENTITY_MARKERS,
    GAME_ENGINE_SIBLING_EXTENSIONS,
    GAME_ENGINE_SIBLING_FILES,
    GAME_ENGINE_UNREAL_DIRS,
    GAME_PLATFORM_DLLS,
    GAME_SIGNAL_DLLS,
    IMAGE_DIRECTORY_ENTRY_COM_DESCRIPTOR,
    STEAM_API_DLLS,
    WINE_ARCH_BY_ARCHITECTURE,
)
from runexe.dependencies import (
    DOTNET_VERB,
    detect_dependencies,
    resolve_verbs_for_dependencies,
)
from runexe.graphics import detect_graphics_requirements
from runexe.models import (
    ApplicationClassification,
    CompatibilityReport,
    Dependency,
    ExecutableInfo,
    HostInfo,
)
from runexe.profiles import _identity_text, detect_application_profile
from runexe.resources import extract_requested_execution_level


def detect_anti_cheat_warnings(executable: ExecutableInfo) -> list[str]:
    """Return per-title compatibility warnings for known anti-cheat clients."""

    if not executable.imports:
        return []

    detected_products = set()

    for imported in executable.imports:
        dll_name = imported.name.lower()
        product = ANTI_CHEAT_DLLS.get(dll_name)

        if product is not None:
            detected_products.add(product)

    return [
        f"{product} anti-cheat detected. Proton support is configured per title; "
        f"verify this game's current compatibility before launching."
        for product in sorted(detected_products)
    ]


def _engine_identity_signal(executable: ExecutableInfo) -> str | None:
    """Return an engine name if it appears in the executable's local
    identity metadata (filename, VS_VERSIONINFO strings).

    This is what catches Unreal Engine and Godot: both statically link
    their runtime into the executable, so unlike Unity (which ships
    UnityPlayer.dll as a separate import) they leave no import-table
    trace at all. The engine's name showing up in ProductName/
    CompanyName/FileDescription is the only local, read-only signal
    available for them.
    """

    identity = _identity_text(executable)
    for marker, engine_name in GAME_ENGINE_IDENTITY_MARKERS.items():
        if marker in identity:
            return engine_name
    return None


def _engine_data_marker(executable_path: Path) -> str | None:
    """Return an engine name if a sibling file/directory next to the
    executable is that engine's known asset/data marker.

    These are the most resistant signal to a packed or obfuscated
    executable, since they're independent files on disk rather than
    something parsed out of the PE image. Best-effort: returns None if
    the directory can't be listed for any reason.
    """

    try:
        siblings = list(executable_path.parent.iterdir())
    except OSError:
        return None

    entries_by_name = {item.name.lower(): item for item in siblings}

    unity_data_dir = f"{executable_path.stem.lower()}{GAME_ENGINE_DATA_DIR_SUFFIX}"
    unity_match = entries_by_name.get(unity_data_dir)
    if unity_match is not None and unity_match.is_dir():
        return "Unity"

    if GAME_ENGINE_UNREAL_DIRS <= entries_by_name.keys() and all(
        entries_by_name[name].is_dir() for name in GAME_ENGINE_UNREAL_DIRS
    ):
        return "Unreal Engine"

    for item in siblings:
        if not item.is_file():
            continue

        engine = GAME_ENGINE_SIBLING_FILES.get(item.name.lower())
        if engine is not None:
            return engine

        engine = GAME_ENGINE_SIBLING_EXTENSIONS.get(item.suffix.lower())
        if engine is not None:
            return engine

    return None


def classify_application(executable: ExecutableInfo) -> ApplicationClassification:
    """Classify the executable as "game" or "application", to drive the
    Wine vs. Proton recommendation.

    Signals are layered from most to least specific, and the first one
    that fires wins:

    1. A Steam API or other game-distribution SDK import (Epic Online
       Services, GOG Galaxy) -- strong, standalone.
    2. A known engine name in local identity metadata (filename or
       VS_VERSIONINFO strings) -- strong, standalone. Catches
       statically-linked engines (Unreal Engine, Godot, GameMaker)
       that never show up as a separate PE import.
    3. A known engine's on-disk data marker next to the executable
       (Unity's "<name>_Data" folder, Unreal's Engine+Content folders,
       GameMaker's data.win, Godot's .pck) -- strong, standalone, and
       the most resistant to a packed/obfuscated executable since it
       doesn't require parsing the binary at all.
    4. UnityPlayer.dll -- strong, standalone import-table signal.
    5. Generic graphics/input/audio/physics middleware imports (D3D,
       XInput, FMOD, PhysX, etc.) -- individually weak, since plenty of
       non-game applications also touch these (video players, CAD
       tools, DAWs); two or more together are treated as a combined,
       medium-confidence signal.

    Falls back to "application" at medium confidence when nothing
    above fires. There is no low-confidence "game" verdict -- a signal
    too weak to stand alone or combine with another simply isn't used.
    """

    imported_names = (
        {imported.name.lower() for imported in executable.imports} if executable.imports else set()
    )

    steam_matches = imported_names & STEAM_API_DLLS
    if steam_matches:
        return ApplicationClassification(
            category="game",
            confidence="high",
            signals=[f"Steam API import ({', '.join(sorted(steam_matches))})"],
        )

    for dll_name, platform_name in GAME_PLATFORM_DLLS.items():
        if dll_name in imported_names:
            return ApplicationClassification(
                category="game",
                confidence="high",
                signals=[f"{platform_name} import ({dll_name})"],
            )

    identity_engine = _engine_identity_signal(executable)
    if identity_engine is not None:
        return ApplicationClassification(
            category="game",
            confidence="high",
            signals=[f"{identity_engine} identified in file metadata"],
        )

    data_marker_engine = _engine_data_marker(executable.path)
    if data_marker_engine is not None:
        return ApplicationClassification(
            category="game",
            confidence="high",
            signals=[f"{data_marker_engine} data files found alongside the executable"],
        )

    game_signals = imported_names & GAME_SIGNAL_DLLS

    if "unityplayer.dll" in game_signals:
        return ApplicationClassification(
            category="game",
            confidence="high",
            signals=["Unity engine import (UnityPlayer.dll)"],
        )

    if len(game_signals) >= 2:
        return ApplicationClassification(
            category="game",
            confidence="medium",
            signals=[
                "Combined graphics/input/audio middleware imports "
                f"({', '.join(sorted(game_signals))})"
            ],
        )

    return ApplicationClassification(category="application", confidence="medium", signals=[])


def _find_runtimeconfig(executable_path: Path) -> Path | None:
    expected_name = f"{executable_path.stem}.runtimeconfig.json".lower()
    direct = executable_path.with_name(f"{executable_path.stem}.runtimeconfig.json")
    if direct.is_file():
        return direct
    try:
        return next(
            (
                item
                for item in executable_path.parent.iterdir()
                if item.is_file() and item.name.lower() == expected_name
            ),
            None,
        )
    except OSError:
        return None


def detect_apphost_dotnet(executable_path: Path) -> bool:
    """Detect modern .NET (Core 3.0+) apphost executables.

    Since .NET Core 3.0, `dotnet publish` produces a native launcher
    stub (no CLR Runtime Header -- see the COM Descriptor check below)
    alongside the actual managed assembly and a `<name>.runtimeconfig.json`
    describing which runtime to load. The stub loads `hostfxr.dll`
    dynamically at runtime, so there's no PE-level signal (no CLR
    header, no static import) that marks it as .NET -- the
    runtimeconfig.json sitting next to it is the only reliable tell.

    This only catches apps published as apphost stubs (the SDK
    default). Self-contained, single-file-trimmed publishes fold the
    runtimeconfig into the binary and won't have a separate JSON file
    -- that case isn't handled here and would need a different check
    (e.g. scanning for an embedded PE resource).
    """

    return _find_runtimeconfig(executable_path) is not None


def detect_apphost_dotnet_version(
    executable_path: Path,
) -> tuple[str | None, bool]:
    """Return (version, is_desktop) from an apphost runtimeconfig.

    `is_desktop` tells us whether the app targets
    Microsoft.WindowsDesktop.App (WPF/WinForms -- needs a
    `dotnetdesktopN` Winetricks verb) rather than plain
    Microsoft.NETCore.App (console/headless -- needs `dotnetN`).
    Getting this wrong is exactly what caused RunEXE to queue the
    wrong verb for Paint.NET, so both pieces of information have to
    travel together rather than just returning a bare version string.

    Returns (None, False) if the runtimeconfig can't be found or
    doesn't contain a usable framework entry.
    """

    version, is_desktop, _self_contained = _detect_apphost_dotnet_details(executable_path)
    return version, is_desktop


def _detect_apphost_dotnet_details(
    executable_path: Path,
) -> tuple[str | None, bool, bool]:
    """Return version, desktop-runtime flag, and self-contained flag."""

    runtimeconfig = _find_runtimeconfig(executable_path)

    if runtimeconfig is None:
        return None, False, False

    try:
        if runtimeconfig.stat().st_size > 1024 * 1024:
            return None, False, False
        # dotnet publish emits runtimeconfig.json with a UTF-8 BOM in
        # some SDK versions (confirmed on a real Paint.NET 5.x publish);
        # utf-8-sig strips it if present and behaves like plain utf-8
        # if not, so it's the safe choice either way.
        with runtimeconfig.open(
            "r",
            encoding="utf-8-sig",
        ) as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return None, False, False

    if not isinstance(data, dict):
        return None, False, False
    runtime_options = data.get("runtimeOptions", {})
    if not isinstance(runtime_options, dict):
        return None, False, False

    framework = runtime_options.get("framework")

    if isinstance(framework, dict):
        version = framework.get("version")

        if isinstance(version, str):
            return (
                version,
                framework.get("name") == "Microsoft.WindowsDesktop.App",
                False,
            )

    def _pick_desktop_or_core(
        entries: list,
    ) -> tuple[str | None, bool]:
        """Scan a list of {"name", "version"} framework entries and
        prefer the Desktop one -- an app that references both is a
        desktop app that also needs the base runtime, and the desktop
        verb pulls the base runtime in too."""

        desktop_version = None
        core_version = None

        for entry in entries:
            if not isinstance(entry, dict):
                continue

            name = entry.get("name")
            version = entry.get("version")

            if not isinstance(version, str):
                continue

            if name == "Microsoft.WindowsDesktop.App":
                desktop_version = version
            elif name == "Microsoft.NETCore.App":
                core_version = version

        if desktop_version is not None:
            return desktop_version, True

        if core_version is not None:
            return core_version, False

        return None, False

    # "frameworks" (plural): framework-dependent apps that reference
    # more than one shared framework (e.g. ASP.NET Core apps pulling
    # in both the ASP.NET Core and base runtime shared frameworks).
    frameworks = runtime_options.get("frameworks")

    if isinstance(frameworks, list):
        version, is_desktop = _pick_desktop_or_core(frameworks)

        if version is not None:
            return version, is_desktop, False

    # "includedFrameworks": self-contained publishes, where every
    # framework version bundled with the app is listed here instead
    # of "framework"/"frameworks". This is the shape Paint.NET 5.x's
    # apphost actually uses.
    included_frameworks = runtime_options.get("includedFrameworks")

    if isinstance(included_frameworks, list):
        version, is_desktop = _pick_desktop_or_core(included_frameworks)

        if version is not None:
            return version, is_desktop, True

    return None, False, False


def dotnet_version_to_verb(
    dotnet_version: str | None,
    is_desktop: bool,
) -> str | None:
    """Return the Winetricks verb for a detected .NET runtime version.

    `is_desktop` selects between the `dotnetdesktopN` verbs (WPF/
    WinForms apps -- includes the base runtime) and the plain
    `dotnetN` verbs (console/headless apps). Returns None for versions
    without a known verb (e.g. pre-8.0 base runtime, or anything not
    in the maps below) -- callers should surface a note rather than
    silently install nothing.
    """

    if dotnet_version is None:
        return None

    parts = dotnet_version.split(".")

    if len(parts) < 2:
        return None

    major_minor = f"{parts[0]}.{parts[1]}"

    desktop_version_to_verb = {
        "3.1": "dotnetcoredesktop3",
        "6.0": "dotnetdesktop6",
        "7.0": "dotnetdesktop7",
        "8.0": "dotnetdesktop8",
        "9.0": "dotnetdesktop9",
        "10.0": "dotnetdesktop10",
    }

    runtime_version_to_verb = {
        "3.1": "dotnetcore3",
        "6.0": "dotnet6",
        "7.0": "dotnet7",
        "8.0": "dotnet8",
        "9.0": "dotnet9",
        "10.0": "dotnet10",
    }

    verb_map = desktop_version_to_verb if is_desktop else runtime_version_to_verb

    return verb_map.get(major_minor)


def analyze_compatibility(
    executable: ExecutableInfo,
    host: HostInfo | None = None,
    backend_preference: str = "auto",
) -> CompatibilityReport:
    if backend_preference not in {"auto", "wine", "proton"}:
        raise ValueError(f"Unknown backend preference: {backend_preference}")
    notes = []
    profile = detect_application_profile(executable)
    if profile is not None:
        notes.append(f"{profile.name} compatibility profile detected.")
        if profile.summary:
            notes.append(profile.summary)

    # Determine application architecture.
    architecture = executable.architecture or "Unknown"

    if architecture == "x86":
        notes.append("32-bit Windows executable detected.")

    elif architecture == "x86_64":
        notes.append("64-bit Windows executable detected.")

    elif architecture == "ARM64":
        notes.append("Windows ARM64 executable detected.")

    else:
        notes.append("Unknown executable architecture.")

    # Map the architecture to a WINEARCH value.
    if architecture == "x86":
        if host is not None and host.wine_wow64:
            # Default to 64-bit Wine prefix if WoW64 is supported,
            # since it can run both 32-bit and 64-bit apps.
            wine_arch = "win64"

            notes.append("Wine WoW64 support detected.")
            notes.append("The application will run through a 64-bit Wine prefix.")
            supported = True

        elif host is not None and host.wine_32bit_prefix:
            wine_arch = "win32"
            notes.append("Traditional 32-bit Wine prefix support is available.")
            supported = True

        else:
            # Read-only inspection cannot conclusively detect every modern
            # unified-WoW64 layout. Choose the appropriate prefix and let
            # wineboot provide the definitive check during launch.
            wine_arch = "win64" if host and host.architecture == "x86_64" else "win32"
            supported = True
            notes.append(
                "32-bit Wine capability could not be verified without creating "
                "a prefix; it will be validated during launch."
            )

    else:
        # x86 is fully handled above; WINE_ARCH_BY_ARCHITECTURE only
        # ever gets consulted here for x86_64/ARM64/unknown.
        wine_arch = WINE_ARCH_BY_ARCHITECTURE.get(architecture)
        supported = wine_arch is not None

        if wine_arch is None:
            notes.append("Could not determine a WINEARCH value for this architecture.")

    if architecture == "ARM64":
        notes.append(
            "ARM64 Windows applications are not supported by RunEXE's "
            "current x86/x86_64 Wine backend."
        )

    # ---------------------------------------------------------
    # Host compatibility
    # ---------------------------------------------------------

    blocking_issues = []

    if host is not None:
        notes.append(f"Host architecture: {host.architecture}")

        if architecture == "x86_64":
            if host.architecture != "x86_64":
                supported = False
                blocking_issues.append("This executable requires an x86_64 host.")

        elif architecture == "x86":
            if host.architecture not in {"x86", "x86_64"}:
                supported = False
                blocking_issues.append("This executable requires an x86-compatible host.")

        if host.wine_installed:
            notes.append(
                f"Wine detected: {host.wine_version}" if host.wine_version else "Wine is installed."
            )
        if host.proton_installed:
            notes.append("Proton detected: " + ", ".join(host.proton_versions))

    # ---------------------------------------------------------
    # Classify as game vs. application
    # ---------------------------------------------------------

    classification = classify_application(executable)
    category = classification.category

    if classification.signals:
        notes.append(
            f"Classified as {category} ({classification.confidence} confidence): "
            + "; ".join(classification.signals)
        )

    wine_available = host is None or host.wine_installed
    proton_available = host is None or host.proton_installed

    if not supported:
        backend = "unsupported"
        recommended_runtime = "Unsupported"
    elif backend_preference != "auto":
        backend = backend_preference
        if backend == "proton" and host and host.proton_versions:
            recommended_runtime = host.proton_versions[0]
        else:
            recommended_runtime = "Proton" if backend == "proton" else "Wine"
    elif category == "game" and proton_available:
        backend = "proton"
        selected = host.proton_versions[0] if host and host.proton_versions else "Proton"
        recommended_runtime = selected
        notes.append(
            "Game-related imports detected; Proton is selected for its DirectX "
            "translation and game-focused compatibility patches."
        )
    elif wine_available:
        backend = "wine"
        recommended_runtime = "Wine"
        if category == "game":
            notes.append("Proton may work better for this game, but no installation was detected.")
    elif proton_available:
        backend = "proton"
        selected = host.proton_versions[0] if host and host.proton_versions else "Proton"
        recommended_runtime = selected
        notes.append("Wine is unavailable, so Proton is selected as the installed fallback.")
    else:
        backend = "wine"
        recommended_runtime = "Unavailable"

    if backend == "wine" and host is not None and not host.wine_installed:
        blocking_issues.append("Wine is not installed. Use --backend proton or install Wine.")
    elif backend == "proton":
        wine_arch = "win64"
        if host is not None and not host.proton_installed:
            blocking_issues.append(
                "Proton is not installed. Install it through Steam or provide --proton PATH."
            )

    if executable.package is not None:
        package_name = executable.package.display_name or executable.package.identity_name
        notes.append(
            f"Packaged app detected: {package_name}. RunEXE will launch its declared "
            "executable directly; Windows Store/UWP package identity is not recreated."
        )
        warnings = [
            "This package may depend on Windows Store services or package identity that "
            "Wine cannot provide.",
        ]
    else:
        warnings = []

    # ---------------------------------------------------------
    # Anti-cheat / DRM. EAC and BattlEye can work in Proton when a game
    # publisher enables support, so an import alone is not a hard blocker.
    # ---------------------------------------------------------

    warnings.extend(detect_anti_cheat_warnings(executable))

    # ---------------------------------------------------------
    # .NET detection
    # ---------------------------------------------------------

    is_dotnet = False
    is_dotnet_apphost = False

    if (
        executable.data_directories
        and len(executable.data_directories) > IMAGE_DIRECTORY_ENTRY_COM_DESCRIPTOR
    ):
        clr_directory = executable.data_directories[IMAGE_DIRECTORY_ENTRY_COM_DESCRIPTOR]

        if clr_directory.virtual_address != 0 and clr_directory.size != 0:
            is_dotnet = True

    if not is_dotnet and detect_apphost_dotnet(executable.path):
        is_dotnet = True
        is_dotnet_apphost = True

    dotnet_version = None
    dotnet_is_desktop = False
    dotnet_self_contained = False

    # Determine application type.
    if is_dotnet:
        application_type = ".NET"

        if is_dotnet_apphost:
            (
                dotnet_version,
                dotnet_is_desktop,
                dotnet_self_contained,
            ) = _detect_apphost_dotnet_details(executable.path)
            notes.append(
                "Modern .NET apphost detected via runtimeconfig.json "
                "(no CLR Runtime Header present -- this is a native "
                "launcher stub, not a managed executable)."
            )
        else:
            notes.append("CLR Runtime Header detected.")

    else:
        application_type = "Native Windows"

    # ---------------------------------------------------------
    # Dependencies
    # ---------------------------------------------------------

    dependencies = detect_dependencies(executable.imports or [])
    graphics = detect_graphics_requirements(executable.imports)

    if graphics.apis:
        notes.append("Graphics APIs detected: " + ", ".join(graphics.apis) + ".")
    if graphics.translators:
        notes.append("Likely translation path: " + ", ".join(graphics.translators) + ".")
    if host is not None and graphics.vulkan_recommended:
        if host.vulkan_available:
            device = ", ".join(host.vulkan_devices) or "Vulkan device detected"
            version = f" (Vulkan {host.vulkan_version})" if host.vulkan_version else ""
            notes.append(f"Vulkan ready: {device}{version}.")
        elif host.vulkan_available is False:
            message = (
                "Vulkan is unavailable, but this application is likely to use "
                + ", ".join(graphics.translators)
                + "."
            )
            if graphics.vulkan_required:
                warnings.append(message + " Direct3D 12/native Vulkan may not run.")
            else:
                warnings.append(message + " Try the Proton WineD3D tuning preset.")
        else:
            notes.append(
                "Vulkan readiness is unknown because vulkaninfo is unavailable; "
                "run `runexe graphics` for setup guidance."
            )

    # DXVK and VKD3D-Proton translate Direct3D 9-12 through Vulkan, and
    # Proton always relies on them, so a missing hardware Vulkan driver is
    # worth surfacing even though RunEXE does not install one itself.
    direct3d_imports = {dep.name for dep in dependencies if dep.category == "graphics"}
    needs_vulkan = backend == "proton" or bool(direct3d_imports & DIRECT3D_VULKAN_APIS)
    if needs_vulkan and host is not None and not host.vulkan_supported:
        warnings.append(
            "No hardware Vulkan driver was detected. DXVK/VKD3D-Proton need one to "
            "translate Direct3D, so this application may fall back to software "
            "rendering or fail to start."
        )

    # .NET is detected structurally through the CLR Runtime Header,
    # rather than through an imported DLL.
    if is_dotnet:
        if not is_dotnet_apphost:
            dependencies.append(
                Dependency(
                    name="Older .NET Framework",
                    category="runtime",
                    confidence="high",
                    winetricks_verb=DOTNET_VERB,
                )
            )
        else:
            verb = (
                None
                if dotnet_self_contained
                else dotnet_version_to_verb(dotnet_version, dotnet_is_desktop)
            )

            if dotnet_version is not None:
                kind = "Desktop" if dotnet_is_desktop else "Runtime"
                distribution = "self-contained" if dotnet_self_contained else "apphost"
                name = f".NET {dotnet_version} ({kind}, {distribution})"
            else:
                name = ".NET apphost (version unknown)"

            dependencies.append(
                Dependency(
                    name=name,
                    category="runtime",
                    confidence="high" if verb or dotnet_self_contained else "low",
                    winetricks_verb=verb,
                )
            )

            if dotnet_self_contained:
                notes.append(
                    "The .NET runtime is bundled with this self-contained application; "
                    "no shared .NET runtime will be installed."
                )
            elif verb is None:
                notes.append(
                    "Could not determine the Winetricks verb for this "
                    "app's .NET runtime from runtimeconfig.json; "
                    "install the matching .NET "
                    + ("Desktop Runtime" if dotnet_is_desktop else "Runtime")
                    + " manually."
                )

    required_verbs = resolve_verbs_for_dependencies(dependencies)

    if required_verbs and host is not None and not host.winetricks_installed:
        notes.append(
            "Winetricks is not installed, so automatic dependency provisioning is unavailable."
        )

    # ---------------------------------------------------------
    # Subsystem
    # ---------------------------------------------------------

    if executable.subsystem == "Windows Console":
        notes.append("Console application; a terminal window will be used.")

    elif executable.subsystem == "Windows GUI":
        notes.append("Windows GUI application.")

    # ---------------------------------------------------------
    # Manifest
    # ---------------------------------------------------------

    if executable.manifest:
        execution_level = extract_requested_execution_level(executable.manifest)

        if execution_level == "requireAdministrator":
            notes.append(
                "Manifest requests administrator privileges; may "
                "require additional Wine/Proton configuration."
            )

    return CompatibilityReport(
        application_type=application_type,
        architecture=architecture,
        category=category,
        backend=backend,
        recommended_runtime=recommended_runtime,
        wine_arch=wine_arch,
        supported=supported,
        blocking_issues=blocking_issues,
        warnings=warnings,
        notes=notes,
        dependencies=dependencies,
        required_verbs=required_verbs,
        profile=profile,
        graphics=graphics,
        classification_confidence=classification.confidence,
        classification_signals=classification.signals,
    )
