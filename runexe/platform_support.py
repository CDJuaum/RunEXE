"""Portable Linux host discovery and package-manager setup.

This module deliberately contains no Qt or Wine imports.  It is shared by the
CLI, GUI bootstrap, and runtime layer so every entry point resolves tools in
the same way on traditional, immutable, and rolling-release distributions.
"""

from __future__ import annotations

import os
import platform
import shlex
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LinuxDistribution:
    """Small, stable subset of freedesktop ``os-release`` metadata."""

    identifier: str = "unknown"
    id_like: tuple[str, ...] = ()
    pretty_name: str = "Unknown Linux"

    @property
    def family(self) -> str:
        candidates = {self.identifier, *self.id_like}
        families = (
            ("debian", {"debian", "ubuntu", "kali", "linuxmint", "pop", "raspbian"}),
            ("fedora", {"fedora", "rhel", "centos", "rocky", "almalinux", "nobara"}),
            ("arch", {"arch", "manjaro", "endeavouros", "cachyos"}),
            ("suse", {"suse", "opensuse", "opensuse-leap", "opensuse-tumbleweed"}),
            ("alpine", {"alpine"}),
            ("void", {"void"}),
            ("gentoo", {"gentoo"}),
            ("nixos", {"nixos"}),
            ("solus", {"solus"}),
        )
        for family, identifiers in families:
            if candidates & identifiers:
                return family
        return "unknown"


def _decode_os_release_value(value: str) -> str:
    try:
        parsed = shlex.split(value, comments=True, posix=True)
    except ValueError:
        return value.strip().strip("\"'")
    return " ".join(parsed)


def detect_linux_distribution(path: Path = Path("/etc/os-release")) -> LinuxDistribution:
    """Read distribution metadata without importing distro-specific modules."""

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return LinuxDistribution()

    values: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.replace("_", "").isalnum():
            values[key] = _decode_os_release_value(value)

    identifier = values.get("ID", "unknown").strip().lower()
    id_like = tuple(value.lower() for value in values.get("ID_LIKE", "").split())
    pretty_name = values.get("PRETTY_NAME") or values.get("NAME") or identifier
    return LinuxDistribution(identifier, id_like, pretty_name)


def _configured_executable(variable: str) -> str | None:
    configured = os.environ.get(variable)
    if not configured:
        return None
    expanded = str(Path(configured).expanduser())
    return shutil.which(expanded)


def find_executable(name: str) -> str | None:
    """Resolve a runtime helper, including portable/custom installations."""

    configuration = {
        "wine": ("RUNEXE_WINE_PATH", ("wine", "wine64")),
        "winetricks": ("RUNEXE_WINETRICKS_PATH", ("winetricks",)),
        "umu-run": ("RUNEXE_UMU_PATH", ("umu-run",)),
    }
    variable, candidates = configuration.get(name, (f"RUNEXE_{name.upper()}_PATH", (name,)))
    configured = _configured_executable(variable)
    if configured:
        return configured
    return next((path for candidate in candidates if (path := shutil.which(candidate))), None)


_PACKAGES: dict[str, dict[str, tuple[str, ...]]] = {
    "apt": {
        "wine": ("wine",),
        "winetricks": ("winetricks",),
        "vulkan": ("vulkan-tools",),
        "gui": (
            "libegl1",
            "libgl1",
            "libx11-6",
            "libx11-xcb1",
            "libdbus-1-3",
            "libfontconfig1",
            "libfreetype6",
            "libglib2.0-0",
            "libwayland-client0",
            "libwayland-cursor0",
            "libwayland-egl1",
            "libxcb1",
            "libxcb-cursor0",
            "libxcb-icccm4",
            "libxcb-image0",
            "libxcb-keysyms1",
            "libxcb-randr0",
            "libxcb-render-util0",
            "libxcb-render0",
            "libxcb-shape0",
            "libxcb-shm0",
            "libxcb-sync1",
            "libxcb-xfixes0",
            "libxcb-xkb1",
            "libxkbcommon0",
            "libxkbcommon-x11-0",
        ),
    },
    "dnf": {
        "wine": ("wine",),
        "winetricks": ("winetricks",),
        "vulkan": ("vulkan-tools",),
        "gui": (
            "dbus-libs",
            "fontconfig",
            "freetype",
            "glib2",
            "libX11",
            "libX11-xcb",
            "libxcb",
            "libxkbcommon",
            "libxkbcommon-x11",
            "mesa-libEGL",
            "mesa-libGL",
            "wayland-libs",
            "xcb-util-cursor",
            "xcb-util-image",
            "xcb-util-keysyms",
            "xcb-util-renderutil",
            "xcb-util-wm",
        ),
    },
    "pacman": {
        "wine": ("wine",),
        "winetricks": ("winetricks",),
        "vulkan": ("vulkan-tools",),
        "gui": (
            "dbus",
            "fontconfig",
            "freetype2",
            "glib2",
            "libglvnd",
            "libx11",
            "libxcb",
            "libxkbcommon",
            "libxkbcommon-x11",
            "wayland",
            "xcb-util-cursor",
            "xcb-util-image",
            "xcb-util-keysyms",
            "xcb-util-renderutil",
            "xcb-util-wm",
        ),
    },
    "zypper": {
        "wine": ("wine",),
        "winetricks": ("winetricks",),
        "vulkan": ("vulkan-tools",),
        "gui": (
            "fontconfig",
            "libdbus-1-3",
            "libfreetype6",
            "libglib-2_0-0",
            "libwayland-client0",
            "libX11-6",
            "libX11-xcb1",
            "libxcb1",
            "libxcb-cursor0",
            "libxcb-icccm4",
            "libxcb-image0",
            "libxcb-keysyms1",
            "libxcb-render-util0",
            "libxcb-xkb1",
            "libxkbcommon0",
            "libxkbcommon-x11-0",
            "Mesa-libEGL1",
            "Mesa-libGL1",
        ),
    },
    "apk": {
        "wine": ("wine",),
        "winetricks": ("winetricks",),
        "vulkan": ("vulkan-tools",),
        "gui": (
            "dbus-libs",
            "fontconfig",
            "freetype",
            "glib",
            "libx11",
            "libxcb",
            "libxkbcommon",
            "libxkbcommon-x11",
            "mesa-egl",
            "mesa-gl",
            "wayland-libs-client",
            "xcb-util-cursor",
            "xcb-util-image",
            "xcb-util-keysyms",
            "xcb-util-renderutil",
            "xcb-util-wm",
        ),
    },
    "xbps-install": {
        "wine": ("wine",),
        "winetricks": ("winetricks",),
        "vulkan": ("Vulkan-Tools",),
        "gui": (
            "dbus-libs",
            "fontconfig",
            "freetype",
            "glib",
            "libGL",
            "libX11",
            "libxcb",
            "libxkbcommon",
            "wayland",
            "xcb-util-cursor",
            "xcb-util-image",
            "xcb-util-keysyms",
            "xcb-util-renderutil",
            "xcb-util-wm",
        ),
    },
    "emerge": {
        "wine": ("app-emulation/wine-vanilla",),
        "winetricks": ("app-emulation/winetricks",),
        "vulkan": ("dev-util/vulkan-tools",),
        "gui": (
            "x11-libs/libxcb",
            "x11-libs/libxkbcommon",
            "dev-libs/dbus",
            "dev-libs/glib",
            "media-libs/fontconfig",
            "media-libs/freetype",
            "media-libs/mesa",
            "dev-libs/wayland",
        ),
    },
    "eopkg": {
        "wine": ("wine",),
        "winetricks": ("winetricks",),
        "vulkan": ("vulkan-tools",),
        "gui": (
            "dbus",
            "fontconfig",
            "freetype2",
            "glib2",
            "libglvnd",
            "libxcb",
            "libxkbcommon",
            "libx11",
            "wayland",
        ),
    },
}

_FAMILY_MANAGER = {
    "debian": "apt",
    "fedora": "dnf",
    "arch": "pacman",
    "suse": "zypper",
    "alpine": "apk",
    "void": "xbps-install",
    "gentoo": "emerge",
    "solus": "eopkg",
}


class SystemInstallError(RuntimeError):
    """Raised when RunEXE cannot install a requested host component."""


_INSTALL_ARGUMENTS: dict[str, tuple[str, ...]] = {
    "apt": ("install", "-y"),
    "dnf": ("install", "-y"),
    "pacman": ("-S", "--noconfirm", "--needed"),
    "zypper": ("--non-interactive", "install"),
    "apk": ("add",),
    "xbps-install": ("-Sy",),
    "emerge": ("--noreplace",),
    "eopkg": ("install", "-y"),
}


def detect_package_manager(distribution: LinuxDistribution | None = None) -> str | None:
    """Prefer an installed manager, then use os-release as a fallback."""

    for manager in _PACKAGES:
        if shutil.which(manager):
            return manager
    distribution = distribution or detect_linux_distribution()
    return _FAMILY_MANAGER.get(distribution.family)


def install_hint(component: str, distribution: LinuxDistribution | None = None) -> str:
    """Return a copy/paste package command appropriate for the current distro."""

    distribution = distribution or detect_linux_distribution()
    if distribution.family == "nixos":
        packages = {
            "wine": "nixpkgs#wineWowPackages.stable",
            "winetricks": "nixpkgs#winetricks",
            "vulkan": "nixpkgs#vulkan-tools",
            "gui": (
                "nixpkgs#dbus nixpkgs#glib nixpkgs#libxcb nixpkgs#libxkbcommon "
                "nixpkgs#fontconfig nixpkgs#freetype nixpkgs#libglvnd nixpkgs#wayland"
            ),
        }
        package = packages.get(component, f"nixpkgs#{component}")
        return f"nix profile install {package}"

    manager = detect_package_manager(distribution)
    if manager is None or manager not in _PACKAGES:
        return f"Install {component} with your distribution's package manager"
    packages = _PACKAGES[manager].get(component, (component,))
    prefix = {
        "apt": "sudo apt install",
        "dnf": "sudo dnf install",
        "pacman": "sudo pacman -S",
        "zypper": "sudo zypper install",
        "apk": "sudo apk add",
        "xbps-install": "sudo xbps-install -S",
        "emerge": "sudo emerge --ask",
        "eopkg": "sudo eopkg install",
    }[manager]
    return f"{prefix} {' '.join(packages)}"


def _privilege_prefix() -> tuple[str, ...]:
    """Return an argv prefix for an administrator package-manager invocation."""

    geteuid = getattr(os, "geteuid", None)
    if geteuid is not None and geteuid() == 0:
        return ()
    for helper in ("pkexec", "sudo"):
        if executable := shutil.which(helper):
            return (executable,)
    raise SystemInstallError("Installing system packages requires pkexec or sudo.")


def package_install_command(
    component: str,
    distribution: LinuxDistribution | None = None,
) -> list[str]:
    """Build a safe argv command to install a supported host component."""

    distribution = distribution or detect_linux_distribution()
    if distribution.family == "nixos":
        raise SystemInstallError(
            "Automatic system package installation is not supported on NixOS; "
            f"use `{install_hint(component, distribution)}` instead."
        )

    manager = detect_package_manager(distribution)
    if manager is None or manager not in _PACKAGES or manager not in _INSTALL_ARGUMENTS:
        raise SystemInstallError(
            f"Automatic package installation is not supported on {distribution.pretty_name}."
        )
    executable = shutil.which(manager)
    if executable is None:
        raise SystemInstallError(f"Package manager '{manager}' is not available on PATH.")
    packages = _PACKAGES[manager].get(component)
    if packages is None:
        raise SystemInstallError(
            f"RunEXE does not know which {manager} packages provide '{component}'."
        )
    return [*_privilege_prefix(), executable, *_INSTALL_ARGUMENTS[manager], *packages]


def install_system_component(
    component: str,
    distribution: LinuxDistribution | None = None,
    *,
    timeout: int = 900,
    progress: Callable[[str, int | None], None] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Install a known host component with the distribution package manager."""

    if progress is not None:
        progress(f"Step 1 of 3 · Resolving packages for {component}", 10)
    command = package_install_command(component, distribution)
    if progress is not None:
        progress(
            "Step 2 of 3 · Installing system packages · administrator approval may be required",
            None,
        )
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or "").strip()
        suffix = f": {detail}" if detail else ""
        raise SystemInstallError(f"System package installation failed{suffix}") from error
    except subprocess.TimeoutExpired as error:
        raise SystemInstallError("System package installation timed out.") from error
    except OSError as error:
        raise SystemInstallError(f"Could not start system package installation: {error}") from error
    if progress is not None:
        progress(f"Step 3 of 3 · {component.title()} packages installed", 100)
    return result


def detect_libc() -> tuple[str, str | None]:
    """Detect glibc or musl without assuming a particular ``ldd`` format."""

    name, version = platform.libc_ver()
    normalized = name.lower()
    if normalized:
        return ("glibc" if normalized in {"glibc", "gnu libc"} else normalized), version or None

    ldd = shutil.which("ldd")
    if ldd:
        try:
            result = subprocess.run(
                [ldd, "--version"], capture_output=True, text=True, timeout=5, check=False
            )
            output = f"{result.stdout}\n{result.stderr}".lower()
            if "musl" in output:
                return "musl", None
            if "glibc" in output or "gnu libc" in output:
                return "glibc", None
        except (OSError, subprocess.TimeoutExpired):
            pass
    return "unknown", None
