# Installation and platform support

This guide covers RunEXE installation choices, Linux runtime prerequisites, upgrades, uninstalling, desktop-platform notes, and custom compatibility-runtime paths.

## Recommended user installation

Install RunEXE for the current user without changing the system Python or using `sudo`:

```bash
curl -fsSL https://raw.githubusercontent.com/CDJuaum/RunEXE/main/install.sh | sh
```

The installer resolves the latest published GitHub release and installs that tagged source. Changes on `main` therefore do not reach normal installs until they are released. It creates an isolated application environment under `$XDG_DATA_HOME/runexe/app`, exposes `runexe` and `runexe-gui` through `~/.local/bin`, and adds RunEXE to the desktop application menu.

For a quick test of the current unreleased `main` branch, opt in explicitly:

```bash
curl -fsSL https://raw.githubusercontent.com/CDJuaum/RunEXE/main/install.sh | sh -s -- --main
```

Run the host check afterward:

```bash
runexe doctor
```

For a console-only or menu-free installation:

```bash
curl -fsSL https://raw.githubusercontent.com/CDJuaum/RunEXE/main/install.sh | sh -s -- --cli-only
curl -fsSL https://raw.githubusercontent.com/CDJuaum/RunEXE/main/install.sh | sh -s -- --no-desktop
```

If you prefer to inspect the script first, download [`install.sh`](../install.sh), review it, and run it locally.

## Official release packages

The [latest GitHub release](https://github.com/CDJuaum/RunEXE/releases/latest) publishes tested x86-64 packages and portable bundles:

| Format | Systems | Notes |
| --- | --- | --- |
| `.deb` | Debian, Ubuntu, Kali, Mint and compatible systems | Native package with desktop integration and declared display dependencies |
| `.rpm` | Fedora and compatible RPM systems | Native package with desktop integration |
| `.pkg.tar.zst` | Arch Linux, Manjaro and compatible systems | Native pacman package with desktop integration |
| glibc `.tar.gz` | glibc 2.35+ Linux | Portable CLI + Qt desktop bundle |
| musl `.tar.gz` | Alpine 3.22+ | Portable CLI bundle |

Install native packages with the matching package manager:

```bash
sudo apt install ./runexe-*.deb
sudo dnf install ./runexe-*.rpm
sudo pacman -U ./runexe-bin-*.pkg.tar.zst
```

For a portable archive, extract it and keep the entire `runexe/` directory together:

```bash
./runexe/runexe --help
./runexe/runexe-gui
```

Verify release files with the published checksum file:

```bash
sha256sum -c SHA256SUMS
```

## Wine, Proton, and Winetricks

RunEXE does not bundle your system Wine build or GPU drivers. Install the compatibility runtime appropriate for your distribution, or use RunEXE's managed GE-Proton installer.

Typical distro packages:

| Distribution family | Runtime packages |
| --- | --- |
| Debian, Ubuntu, Kali, Mint | `sudo apt install wine winetricks` |
| Fedora, RHEL derivatives | `sudo dnf install wine winetricks` |
| Arch, Manjaro | `sudo pacman -S wine winetricks` |
| openSUSE | `sudo zypper install wine winetricks` |
| Alpine | `sudo apk add wine winetricks` |
| Void | `sudo xbps-install -S wine winetricks` |
| Gentoo | `sudo emerge --ask app-emulation/wine-vanilla app-emulation/winetricks` |
| NixOS | `nix profile install nixpkgs#wineWowPackages.stable nixpkgs#winetricks` |

Install a managed GE-Proton release into RunEXE's per-user data directory with:

```bash
runexe proton install
```

This does not require root and is discovered alongside Steam, custom, Flatpak, and other supported Proton layouts.

## pipx installation

If pipx is already installed:

```bash
pipx install "runexe[gui] @ git+https://github.com/CDJuaum/RunEXE.git"
runexe desktop install
```

Upgrade or uninstall that installation with:

```bash
pipx upgrade runexe
runexe desktop remove
pipx uninstall runexe
```

## Upgrade or uninstall the user installation

Rerun the same installer to upgrade an installation created by `install.sh`.

Remove application files and desktop integration with:

```bash
curl -fsSL https://raw.githubusercontent.com/CDJuaum/RunEXE/main/uninstall.sh | sh
```

The uninstaller deliberately preserves recent-application history and managed Wine/Proton environments under `$XDG_DATA_HOME/runexe`. Remove those separately through the GUI or CLI when you no longer need them.

## Source installation

```bash
git clone https://github.com/CDJuaum/RunEXE.git
cd RunEXE
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[gui]'
runexe doctor
```

For a CLI-only installation, replace `.[gui]` with `.`.

## Python and Qt support

RunEXE itself requires Python 3.10 or newer for Python/source installations.

For Python 3.10-3.13, the GUI extra selects Qt 6.8.3 because its official x86-64 wheel supports glibc 2.28 and newer. Python 3.14 selects a newer ABI-compatible PySide6 build. PyPI does not publish a musllinux PySide6-Essentials wheel, so Alpine users can use the official musl CLI bundle or install their distribution's PySide6 package and install RunEXE without the `gui` extra.

The official glibc desktop release bundle already includes Python and Qt.

## Wayland, X11, and software rendering

Automatic mode chooses a Qt platform before the GUI imports PySide6, preferring the current desktop session while retaining the other Linux backend as a fallback.

Override the platform only when troubleshooting:

```bash
runexe-gui --platform wayland
runexe gui --platform xcb
RUNEXE_SOFTWARE_RENDERING=1 runexe-gui
```

`runexe doctor` reports missing Qt platform plugins and shared libraries with distro-specific repair guidance.

## Custom Wine, Winetricks, or Proton paths

Portable, Nix, and custom layouts can be supplied without modifying `PATH`:

```bash
RUNEXE_WINE_PATH=/path/to/wine runexe run app.exe
RUNEXE_WINETRICKS_PATH=/path/to/winetricks runexe run app.exe
RUNEXE_PROTON_PATH=/path/to/Proton runexe run game.exe
```

The equivalent explicit Proton path is also accepted with `--proton`.

## Distribution portability

RunEXE detects `apt`, `dnf`, `pacman`, `zypper`, `apk`, `xbps-install`, `emerge`, `eopkg`, and NixOS. Normal analysis and launch flows do not install system packages. An explicit action such as `runexe graphics --install-tools` may invoke the detected system package manager and request administrator authentication.

No compatibility frontend can guarantee that every Windows application works on every distribution. Wine/Proton versions, GPU drivers, kernel features, Windows APIs, DRM, anti-cheat, and application-specific behavior still matter. RunEXE's goal is to detect and explain host differences rather than encode assumptions about one distribution.
