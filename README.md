# RunEXE

Analyze Windows software and run it on Linux through Wine or Proton, from a native Qt desktop app or a full command-line interface.

<p align="center">
  <img src="assets/runexe-logo-v2.png" alt="RunEXE logo" width="340">
</p>

<p align="center">
  <a href="https://github.com/CDJuaum/RunEXE/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/CDJuaum/RunEXE"></a>
  <a href="https://github.com/CDJuaum/RunEXE/actions/workflows/release-linux.yml"><img alt="Linux release workflow" src="https://github.com/CDJuaum/RunEXE/actions/workflows/release-linux.yml/badge.svg"></a>
  <img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-blue">
  <img alt="License LGPL-2.1" src="https://img.shields.io/badge/license-LGPL--2.1-green">
  <img alt="Status stable" src="https://img.shields.io/badge/status-stable-brightgreen">
</p>

<p align="center">
  <a href="https://runexe.rrmtools.uk/">Website</a> ·
  <a href="https://github.com/CDJuaum/RunEXE/releases/latest">Latest release</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="#documentation">Documentation</a> ·
  <a href="CHANGELOG.md">Changelog</a> ·
  <a href="https://github.com/CDJuaum/RunEXE/issues">Issues</a>
</p>

RunEXE inspects PE executables and AppX/MSIX packages before launch, reports likely compatibility requirements, discovers installed Wine and Proton runtimes, and creates isolated per-application environments. Games can prefer Proton, ordinary applications can prefer Wine, and every automatic choice remains overrideable.

## Desktop app

<p align="center">
  <img src="assets/runexe-gui.png" alt="RunEXE desktop interface showing application readiness and runtime controls" width="920">
</p>

The desktop interface is built with Qt Quick/QML and uses the same analysis, runtime, environment, and launch services as the CLI. It provides focused pages for launch setup, runtimes, applications, environments, backups, and activity without maintaining a separate compatibility implementation.

## Why RunEXE

- **Analyze before launch.** Inspect architecture, imports, manifests, version data, .NET requirements, DirectX signals, AppX/MSIX metadata, and known compatibility patterns without executing the file.
- **Choose Wine or Proton with context.** Discover installed runtimes, prefer a sensible backend, select Proton builds explicitly, or install a managed GE-Proton release without root.
- **Keep applications isolated.** Stable per-app Wine prefixes or Proton compat-data directories preserve launch choices without turning one global prefix into a dependency tangle.
- **Provision known dependencies.** Detect common Windows runtimes and use Winetricks for supported Wine-side dependencies when requested.
- **Understand graphics readiness.** Report Vulkan availability, detected GPUs, likely DirectX translation paths, and DXVK state where available.
- **Manage environments safely.** Inspect disk use, open native Wine tools, create backups, restore snapshots, and remove only validated RunEXE-managed paths.
- **Keep failures debuggable.** Live process output, host diagnostics, notifications, activity history, JSON output, and exportable support reports make runtime problems easier to inspect.

## Quick start

Install RunEXE for the current user without cloning the repository or changing the system Python:

```bash
curl -fsSL https://raw.githubusercontent.com/CDJuaum/RunEXE/main/install.sh | sh
```

The installer resolves the latest published GitHub release and installs that tagged source by default, so work in progress on `main` is not pulled into normal installs. To quickly test the current `main` branch instead:

```bash
curl -fsSL https://raw.githubusercontent.com/CDJuaum/RunEXE/main/install.sh | sh -s -- --main
```

Check the Linux host before the first launch:

```bash
runexe doctor
```

Open the desktop app:

```bash
runexe-gui
```

Or inspect and run a Windows application from the CLI:

```bash
runexe analyze path/to/app.exe
runexe run path/to/app.exe
```

Open a file directly in the desktop app:

```bash
runexe-gui path/to/app.exe
```

`runexe analyze` is read-only and can inspect a PE file without initializing Wine. See [CLI reference](docs/cli.md) for JSON output, AppX/MSIX, explicit backend selection, Proton builds, graphics diagnostics, environments, backups, and automation-oriented commands.

## Install

### Official Linux release packages

Every release is built and smoke-tested in clean Linux environments before publication.

| Download | Intended systems | Includes |
| --- | --- | --- |
| `*.deb` | Debian, Ubuntu, Kali, Mint and compatible systems | CLI, desktop GUI, Python, Qt, desktop integration |
| `*.rpm` | Fedora and compatible RPM systems | CLI, desktop GUI, Python, Qt, desktop integration |
| `runexe-bin-*.pkg.tar.zst` | Arch Linux, Manjaro and compatible systems | CLI, desktop GUI, Python, Qt, desktop integration |
| `*-linux-x86_64-glibc.tar.gz` | Portable glibc 2.35+ Linux | CLI, desktop GUI, Python, Qt |
| `*-linux-x86_64-musl.tar.gz` | Alpine 3.22+ | CLI and Python |

Download the current files from the [latest GitHub release](https://github.com/CDJuaum/RunEXE/releases/latest) and verify them with the published `SHA256SUMS` file.

Native package examples:

```bash
sudo apt install ./runexe-*.deb
sudo dnf install ./runexe-*.rpm
sudo pacman -U ./runexe-bin-*.pkg.tar.zst
```

Wine, Proton, graphics drivers, and your Linux display stack remain system-managed. Official desktop binaries target x86-64 Linux.

### Requirements

- Linux on x86-64 for the official desktop binaries
- Wine, Proton, or both to launch Windows software
- Winetricks for automatic Wine-side dependency provisioning
- Vulkan-capable drivers for DXVK/VKD3D paths used by many modern games and graphics applications

Python 3.10+ is required for source/Python installations. The official glibc desktop bundles include Python and Qt.

For pipx installs, CLI-only setups, upgrades, uninstalling, distro runtime packages, Wayland/X11 troubleshooting, and custom Wine/Proton paths, see [Installation and platform support](docs/installation.md).

## Usage

### Analyze without launching

```bash
runexe analyze path/to/app.exe
runexe analyze path/to/app.exe --imports
runexe analyze path/to/app.exe --json
runexe analyze path/to/app.exe --no-host
```

AppX/MSIX packages and unpacked package directories are supported too:

```bash
runexe analyze Paint.msix
runexe run Paint.msix --no-deps
```

### Choose a runtime explicitly

Automatic backend selection is the default. Override it when you know which runtime works best:

```bash
runexe run app.exe --backend wine
runexe run game.exe --backend proton
runexe run game.exe --proton "Proton Experimental"
```

Inspect available runtimes or install a managed GE-Proton build:

```bash
runexe backends
runexe proton install
```

### Check graphics and host readiness

```bash
runexe doctor
runexe graphics
```

The [CLI reference](docs/cli.md) covers argument forwarding, Windows-version overrides, runtime tuning, recent applications, environment configuration, backups, JSON output, storage locations, and guarded cleanup.

## What RunEXE checks

| Area | Examples |
| --- | --- |
| Executable | Architecture, imports, subsystem, embedded manifest, version info, .NET/CLR, DirectX and input signals |
| Application type | Conservative game/application classification, engine and Steam signals, anti-cheat warnings |
| Host | Distribution, libc, package manager, Wine, Winetricks, Proton, display session, Qt runtime |
| Graphics | Vulkan loader/ICDs, GPU vendors, DXVK state, likely DirectX translation path |
| Dependencies | Visual C++, .NET Framework, D3D helpers, OpenAL, XInput and other known runtime needs |
| Managed state | Recent apps, launch presets, Wine/Proton environments, disk usage, backups |

The compatibility score is an explainable summary of local blockers, warnings, dependency setup, and host readiness. It is not a probability that an application will work.

## Tested applications

These applications have been run through RunEXE without manual setup beyond what the tool provisions automatically:

| Application | Notes |
| --- | --- |
| Notepad++ | Native 64-bit build |
| Notepad++ | 32-bit build |
| PuTTY | Native Windows executable |
| KeePass | .NET application |

Application compatibility still depends on Wine/Proton versions, graphics drivers, kernel features, Windows API usage, DRM/anti-cheat, and the application itself. Broader community compatibility data remains on the roadmap.

## Data and safety

- `runexe analyze` is read-only and does not initialize Wine prefixes.
- RunEXE never modifies the original EXE/AppX/MSIX source file.
- AppX/MSIX package signatures are not verified; only run packages you trust.
- Wine and Proton are compatibility layers, **not security sandboxes**. Use a VM or dedicated sandbox for untrusted software.
- Managed prefixes may contain application settings or save files. RunEXE creates a backup by default before managed-environment removal unless you explicitly disable it.
- Recent-application state and managed environments stay on the local machine. The RunEXE website does not receive this state.
- Game classification, dependency detection, and anti-cheat detection are best-effort signals, not guarantees.

## Documentation

- [Installation and platform support](docs/installation.md) — release packages, pipx, upgrades, uninstalling, distro prerequisites, Qt, Wayland/X11, custom runtime paths
- [CLI reference](docs/cli.md) — analysis, launch flags, backends, Proton, graphics, recent apps, environments, backups, state paths
- [Desktop UI design](docs/desktop-ui.md) — Qt Quick/QML structure and desktop interaction conventions
- [Release process](docs/releasing.md) — tag builds, package formats, smoke-test matrix, release workflow behavior
- [Changelog](CHANGELOG.md) — release history and compatibility changes
- [Project website](https://runexe.rrmtools.uk/) — downloads, overview, and an introductory guide to running EXE files on Linux

## Roadmap

The completed pre-1.0 work is preserved in the [changelog](CHANGELOG.md). Current longer-term goals include:

- Launch existing Steam titles by App ID
- Extend compatibility scoring with broader application-specific evidence
- Flatpak and AppImage packages
- A community application compatibility database

Feature requests and compatibility reports are welcome in [GitHub Issues](https://github.com/CDJuaum/RunEXE/issues).

## Development

```bash
git clone https://github.com/CDJuaum/RunEXE.git
cd RunEXE
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev,gui]'
```

Run the standard checks:

```bash
ruff check .
ruff format --check .
pytest
python -m build
```

The GUI is a client of the same backend services as the CLI; new compatibility behavior should live in reusable backend code rather than desktop-only logic.

## Contributing

Contributions are welcome. Please open an issue when a change affects user-visible compatibility behavior, packaging, or a significant interface decision so the expected behavior can be discussed and reproduced.

## License

RunEXE is licensed under the [LGPL-2.1](LICENSE).

## Support

For bugs, compatibility reports, or feature requests, use the [GitHub issue tracker](https://github.com/CDJuaum/RunEXE/issues).
