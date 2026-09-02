# Changelog

All notable RunEXE changes are documented here.

## [0.6.0] - 2026-08-31

### Added

- Read-only Vulkan/GPU probing through `vulkaninfo`, DirectX API/translator
  classification, per-environment DXVK detection, and `runexe graphics` reports.
- Broader Windows runtime and component detection for versioned DirectX,
  Universal CRT, WebView2, DirectShow, DirectInput, Vulkan, and OpenGL imports.
- Validated temporary Proton tuning presets for diagnostics, WineD3D fallback,
  the DXVK HUD, fsync, and ntsync, persisted independently for each app.
- Compressed managed-environment backups, inventory, safe non-overwriting
  restore, backup deletion, and default backup-before-removal in GUI and CLI.
- Native environment maintenance tools through `runexe configure-environment`
  and a GUI Configure action for Wine settings, Regedit, Control Panel,
  uninstaller, and Explorer workflows.
- A one-command, pipx-free `install.sh` that creates an isolated user-level
  environment without invoking `sudo`, plus a marker-guarded `uninstall.sh`.
- `runexe desktop install` and `runexe desktop remove` commands for a
  freedesktop application-menu entry, themed logo, and Open With registration.

### Changed

- The Library page now reports backup storage and DXVK state, exposes backup,
  restore, configuration, and guarded removal actions, and keeps all inventory
  work off the UI thread.
- Compatibility reports explain likely DXVK/VKD3D translation and warn when
  Vulkan is unavailable without blocking a possible WineD3D fallback.
- Desktop integration refreshes available menu/icon caches when their standard
  tools are present and remains usable when they are absent.

### Safety

- Backup restore validates every archive path and link, rejects special files,
  extracts without `tarfile.extractall`, and never overwrites a live prefix.
- The uninstaller removes only a marker-verified `runexe/app` installation and
  matching command links. It preserves prefixes, Proton data, and app history.

### Verification

- The expanded automated suite covers installer ownership, desktop integration,
  DirectX/Vulkan/DXVK detection, Proton tuning isolation, native configuration,
  and traversal-safe backup/restore in addition to the existing GUI/CLI suite.
- All 91 tests pass in the Debian Qt environment; the 85-test headless suite
  passes independently on both Debian/glibc and Alpine/musl.

## [0.5.1] - 2026-08-30

### Added

- Application classification now detects Epic Online Services and GOG
  Galaxy imports, engine names in file metadata (Unreal Engine, Godot,
  GameMaker), and on-disk engine data markers (Unity's `_Data` folder,
  Unreal's `Engine`/`Content` pair, GameMaker's `data.win`, Godot's
  `.pck`) in addition to the existing Steam API and UnityPlayer.dll
  checks.
- Compatibility reports now include a classification confidence level
  and the specific signals behind a "game"/"application" verdict,
  surfaced in both the CLI output and `--json` reports.
- Read-only GPU and Vulkan capability detection (`runexe/gpu.py`): DRM
  render-node enumeration with PCI vendor and kernel driver identification,
  Vulkan ICD manifest discovery (respecting `VK_DRIVER_FILES`/
  `VK_ICD_FILENAMES`), and Vulkan loader detection, all without querying
  the GPU or creating a Wine prefix.
- `runexe doctor` reports a "Vulkan" capability check with a distro-specific
  install hint, and `runexe backends` shows Vulkan availability and detected
  GPU vendor(s) alongside Wine/Proton.
- `HostInfo.vulkan_supported` and `HostInfo.gpu_vendors`, populated by
  `detect_host()`, and a compatibility warning when a Direct3D 9-12
  application or Proton launch is detected without a hardware Vulkan
  driver, since DXVK and VKD3D-Proton require one.
- `vulkan` package hints for every supported package-manager family
  (apt, dnf, pacman, zypper, apk, xbps-install, emerge, eopkg) and NixOS.

### Changed

- `classify_application()` returns an `ApplicationClassification`
  (category, confidence, signals) instead of a bare string. This is a
  breaking change for any code calling it directly.

### Verification

- 15 new automated tests cover each classification signal path,
  including a negative case for an ambiguous single folder name.

## [0.5.0] - 2026-08-29

### Added

- A bounded local recent-application library stored under `XDG_STATE_HOME`,
  with atomic updates, corruption recovery, missing-source pruning, and CLI
  JSON output.
- Per-application launch presets for backend, Proton build, reported Windows
  version, dependency policy, custom prefix, and arguments.
- A fourth scalable GUI page for reopening recent software and inspecting
  RunEXE-owned Wine prefixes and Proton compat-data directories.
- Managed-environment metadata, readiness, disk-usage inventory, folder access,
  and guarded removal that accepts only direct children of RunEXE data roots.
- `runexe recent`, `runexe rerun`, `runexe forget-recent`, `runexe environments`,
  and the explicitly confirmed `runexe remove-environment IDENTIFIER --yes`
  console workflows.
- Exportable GUI support reports containing the active analysis, compatibility
  result, host state, launch preset, environment inventory, and activity log.

### Changed

- Custom environment paths are now per-application instead of a global GUI
  preference, preventing one application's prefix from leaking into another.
- The GUI prevents switching the analyzed source while a launched application
  is still running and performs environment inventory work off the UI thread.
- Successfully prepared environments receive best-effort metadata without
  allowing metadata failures to block application launch.

### Safety

- Environment cleanup rejects symlinks, nested paths, custom prefixes, and any
  target outside the two RunEXE-managed roots. The GUI warns that prefixes may
  contain Windows-side saves and settings before requesting confirmation.

### Verification

- 71 automated tests cover library persistence and recovery, per-app preset
  restoration, environment discovery and size reporting, direct-child deletion
  guards, desktop integration ownership, CLI behavior, and the four-page GUI shell.

## [0.4.3] - 2026-08-29

### Added

- Read-only `runexe doctor` diagnostics for Linux distribution, libc, package
  manager, architecture, Wine, Proton, Winetricks, display server, PySide6
  platform plugins, and their missing shared libraries.
- Package commands for Debian/Ubuntu/Kali, Fedora/RHEL, Arch, openSUSE,
  Alpine, Void, Gentoo, Solus, and NixOS families.
- `RUNEXE_WINE_PATH` and `RUNEXE_WINETRICKS_PATH` overrides for Nix,
  immutable, and portable runtime layouts.
- `--platform auto|xcb|wayland|offscreen|minimal` on both GUI entry points,
  plus `RUNEXE_SOFTWARE_RENDERING` for problematic graphics stacks.

### Changed

- Wine discovery accepts distributions that expose only `wine64`.
- Qt is configured before PySide6 imports, automatically preferring the active
  Wayland/X11 session with a compositor fallback.
- GUI startup preflights Qt platform plugins and shared libraries so missing
  host dependencies produce an actionable RunEXE error instead of Qt aborting.
- On Python 3.10-3.13 the GUI extra uses Qt 6.8.3's manylinux_2_28 wheel to
  retain compatibility with older glibc-based stable distributions; Python
  3.14 selects a newer compatible Qt build. Musl users can use their
  distribution's PySide6 package while the CLI remains dependency-free from Qt.

### Verification

- Cross-distribution unit coverage exercises os-release parsing, package hints,
  `wine64` fallback, custom runtime paths, Wayland/X11 selection, explicit QPA
  overrides, and headless behavior.

## [0.4.2] - 2026-08-29

### Fixed

- Removed page-wide and card opacity effects that could leave stale Overview frames composited over Runtime Setup on X11/Wayland.
- Scroll pages, stacked pages, dialogs, and combo-box popup viewports now paint explicit opaque theme backgrounds.
- Replaced unsafe fades with compositor-safe title/metric color transitions and layout-based recommendation expansion.
- README screenshot capture now waits for short UI transitions to settle before rendering.

### Verification

- Regression coverage confirms both stacked pages and the Paint.NET recommendation card have no graphics effects.
- Combo popup and scroll viewports are configured with explicit background filling.

## [0.4.1] - 2026-08-28

### Added

- Extensible application compatibility profiles, beginning with Paint.NET.
- Automatic Paint.NET selection of Windows 11 to satisfy its Windows 10 21H2/build 19044 minimum.
- Runtime diagnosis for the old-Windows error message and `ERROR_OLD_WIN_VERSION` exit code.
- Smooth interruptible wheel scrolling, touch scrolling, compositor-safe page/metric color transitions, recommendation expansion, and clearer drag feedback.
- An animated compatibility recommendation card with a direct route to the relevant runtime controls.

### Changed

- Runtime actions now use a responsive two-column layout at narrower window sizes.
- Windows-version and dependency preferences are persisted and reflected in the environment preview.
- CLI launches also apply detected application-profile Windows versions unless explicitly overridden.
- Scroll pages and combo popups now paint opaque backgrounds to prevent stale-frame ghosting on X11/Wayland compositors.

### Verification

- 41 automated tests cover the profile match, automatic GUI configuration, runtime diagnosis, and CLI behavior.

## [0.4.0] - 2026-08-28

### Added

- Optional PySide6 desktop interface with responsive pages for overview, runtime setup, and activity.
- Drag-and-drop input, readiness metrics, persistent preferences, keyboard shortcuts, and live process output.
- One-click isolated Wine/Proton environment preparation plus buttons for opening each runtime's native Wine configuration.
- Background analysis and provisioning workers so long-running setup does not freeze the interface.
- Dedicated `runexe-gui` launcher and `runexe gui [FILE]` CLI command; the console workflow remains fully available.
- Packaged application logo, deterministic README screenshot tooling, and GUI regression tests.
- Reusable prepared-environment and launch-spec APIs shared by both front ends.

### Changed

- Refactored launch preparation away from the synchronous console runner so GUI launches can use Qt's non-blocking process API without duplicating Wine or Proton logic.
- Improved long-path display, semantic ready/error colors, control accessibility labels, and window scaling behavior after native Windows visual inspection.
- Bumped the package version to 0.4.0 and added the optional `gui` dependency extra.

### Verification

- 37 automated tests passed, including GUI state, runtime preparation, launch specification, and optional-dependency behavior.
- Ruff lint and format checks passed.
- Source distribution and wheel builds passed with the GUI modules and logo included.
- The built wheel and its `gui` extra passed an isolated installation and desktop-shell smoke test.
- Wine/Proton execution still requires final integration testing on a Linux host with those runtimes installed.

## [0.3.0] - 2026-08-28

### Added

- Proton runtime discovery across Steam libraries, Valve builds, Proton Experimental, GE-Proton, Flatpak, Snap, and custom installations.
- Backend selection with `--backend auto|wine|proton`, direct `--proton` selection, the `backends` command, and `RUNEXE_PROTON_PATH` support.
- Standalone Proton launching with isolated compatibility data and the Steam compatibility environment variables Proton expects.
- AppX/MSIX and AppX/MSIX bundle input support, including manifest parsing, architecture-aware package selection, declared executable discovery, and reusable package caching.
- Safe package extraction with archive size/file-count limits, symbolic-link rejection, and path-traversal protection.
- Rich terminal presentation with launch plans, summary tables, status colors, runtime hints, and an ASCII-safe brand mark for legacy CMD code pages, CI, and SSH sessions.
- `python -m runexe` invocation support.
- Project logo assets and README branding.
- Regression coverage for Proton discovery, runtime selection, package handling, backend conflicts, and launch environment construction.

### Changed

- Bumped the package version to 0.3.0 and updated the package description, classifiers, metadata, and roadmap.
- Game compatibility now prefers Proton when a suitable installation is available, while ordinary applications continue to prefer Wine.
- Users can explicitly override runtime selection when automatic classification is not appropriate.
- Proton dependency installation is opt-in; Wine dependency provisioning remains automatic by default.
- CLI help, error handling, JSON output, argument forwarding, timeout handling, and launch diagnostics were refined for more predictable automation.
- README usage, requirements, runtime behavior, package limitations, and development verification instructions were expanded.

### Compatibility notes

- AppX/MSIX packages are launched through their declared executable. Package identity, Microsoft Store services, and UWP-only behavior are not recreated.
- Proton is invoked directly through its `proton run` interface. Some games may still require Steam services or title-specific configuration.
- Wine/Proton integration was not exercised in the Windows development environment; runtime behavior should be verified on a Linux host with the target compatibility tools installed.

### Verification

- 30 automated tests passed.
- Ruff lint and format checks passed.
- Source distribution and wheel build passed.
- ASCII-codepage CLI smoke test passed.

## [0.2.0] - 2026-08-28

### Added

- Defensive, bounded PE parsing for headers, sections, imports, manifests, and version resources.
- Safer .NET detection, including apphost `runtimeconfig.json` files and Desktop versus Runtime classification.
- Broader runtime dependency detection for Visual C++, DirectX, XInput, OpenAL, XAudio, Windows codecs, RichEdit, and related libraries.
- Deterministic Wine prefixes with architecture validation, Windows version overrides, custom prefix paths, dependency controls, timeouts, and working-directory-aware launches.
- JSON compatibility reports and host-check controls.
- Initial AppX/MSIX materialization support and packaged Win32 launch warnings.
- Development tooling, initial regression suite, and project-level ignore rules.

### Changed

- Compatibility reporting now separates blocking issues, warnings, notes, selected backend, and required Winetricks verbs.
- Game classification became conservative to avoid treating ordinary graphics applications as games.
- Anti-cheat findings became compatibility warnings rather than automatic blockers where Proton support may be title-specific.
