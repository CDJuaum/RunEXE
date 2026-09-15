"""Portable Linux host discovery and package-manager setup.

This module deliberately contains no Qt or Wine imports.  It is shared by the
CLI, GUI bootstrap, and runtime layer so every entry point resolves tools in
the same way on traditional, immutable, and rolling-release distributions.
"""

from __future__ import annotations

import json
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

_REMOVE_ARGUMENTS: dict[str, tuple[str, ...]] = {
    "apt": ("remove", "-y"),
    "dnf": ("remove", "-y"),
    "pacman": ("-R", "--noconfirm"),
    "zypper": ("--non-interactive", "remove"),
    "apk": ("del",),
    "xbps-install": ("-R",),
    "emerge": ("--unmerge",),
    "eopkg": ("remove", "-y"),
}

_PACKAGE_STATE_SCHEMA = 1


def managed_system_package_state_path() -> Path:
    state_home = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return state_home / "runexe" / "system-packages.json"


def _load_package_receipts() -> dict[str, dict[str, object]]:
    path = managed_system_package_state_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict) or payload.get("schema") != _PACKAGE_STATE_SCHEMA:
        return {}
    components = payload.get("components")
    if not isinstance(components, dict):
        return {}
    return {
        str(component): receipt
        for component, receipt in components.items()
        if isinstance(component, str) and isinstance(receipt, dict)
    }


def _write_package_receipts(receipts: dict[str, dict[str, object]]) -> None:
    path = managed_system_package_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(
                {"schema": _PACKAGE_STATE_SCHEMA, "components": receipts},
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        if os.name == "posix":
            temporary.chmod(0o600)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _receipt_packages(component: str, manager: str) -> tuple[str, ...]:
    receipt = _load_package_receipts().get(component)
    if not isinstance(receipt, dict) or receipt.get("manager") != manager:
        return ()
    packages = receipt.get("packages")
    if not isinstance(packages, list) or not packages:
        return ()
    known = set(_PACKAGES.get(manager, {}).get(component, ()))
    normalized = tuple(
        package for package in packages if isinstance(package, str) and package in known
    )
    if len(normalized) != len(packages) or len(set(normalized)) != len(normalized):
        return ()
    return normalized


def _record_package_receipt(component: str, manager: str, packages: tuple[str, ...]) -> None:
    receipts = _load_package_receipts()
    if packages:
        receipts[component] = {"manager": manager, "packages": list(packages)}
    else:
        receipts.pop(component, None)
    try:
        _write_package_receipts(receipts)
    except OSError:
        pass


def _query_package_installed(manager: str, package: str) -> bool | None:
    query: tuple[str, tuple[str, ...]] | None = {
        "apt": ("dpkg-query", ("-W", "-f=${Status}", package)),
        "dnf": ("rpm", ("-q", package)),
        "pacman": ("pacman", ("-Q", package)),
        "zypper": ("rpm", ("-q", package)),
        "apk": ("apk", ("info", "-e", package)),
        "xbps-install": ("xbps-query", ("-p", "pkgver", package)),
    }.get(manager)
    if query is None:
        return None
    executable = shutil.which(query[0])
    if executable is None:
        return None
    try:
        result = subprocess.run(
            [executable, *query[1]],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if manager == "apt":
        return result.returncode == 0 and "install ok installed" in result.stdout.lower()
    return result.returncode == 0


def managed_system_component_packages(
    component: str,
    distribution: LinuxDistribution | None = None,
) -> tuple[str, ...]:
    distribution = distribution or detect_linux_distribution()
    manager = detect_package_manager(distribution)
    if manager is None:
        return ()
    packages = _receipt_packages(component, manager)
    if not packages:
        return ()
    states = tuple(_query_package_installed(manager, package) for package in packages)
    if any(state is not True for state in states):
        return ()
    return packages


def system_component_managed(
    component: str,
    distribution: LinuxDistribution | None = None,
) -> bool:
    return bool(managed_system_component_packages(component, distribution))


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

    distribution = distribution or detect_linux_distribution()
    manager = detect_package_manager(distribution)
    known_packages = _PACKAGES.get(manager or "", {}).get(component, ())
    owned_before = _receipt_packages(component, manager) if manager is not None else ()
    before = (
        {package: _query_package_installed(manager, package) for package in known_packages}
        if manager is not None
        else {}
    )
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
    if (
        manager is not None
        and known_packages
        and all(value is not None for value in before.values())
    ):
        after = {package: _query_package_installed(manager, package) for package in known_packages}
        if all(value is not None for value in after.values()):
            newly_installed = {
                package
                for package in known_packages
                if before.get(package) is False and after.get(package) is True
            }
            still_owned = {package for package in owned_before if after.get(package) is True}
            owned = tuple(
                package for package in known_packages if package in newly_installed | still_owned
            )
            _record_package_receipt(component, manager, owned)
    if progress is not None:
        progress(f"Step 3 of 3 · {component.title()} packages installed", 100)
    return result


def package_remove_command(
    component: str,
    distribution: LinuxDistribution | None = None,
    *,
    packages: tuple[str, ...] | None = None,
) -> list[str]:
    """Build a safe argv command to remove a supported host component."""

    distribution = distribution or detect_linux_distribution()
    if distribution.family == "nixos":
        raise SystemInstallError(
            "Automatic system package removal is not supported on NixOS; "
            "remove the package from the profile or system configuration that installed it."
        )

    manager = detect_package_manager(distribution)
    if manager is None or manager not in _PACKAGES or manager not in _REMOVE_ARGUMENTS:
        raise SystemInstallError(
            f"Automatic package removal is not supported on {distribution.pretty_name}."
        )
    executable_name = "xbps-remove" if manager == "xbps-install" else manager
    executable = shutil.which(executable_name)
    if executable is None:
        raise SystemInstallError(f"Package manager '{executable_name}' is not available on PATH.")
    known_packages = _PACKAGES[manager].get(component)
    if known_packages is None:
        raise SystemInstallError(
            f"RunEXE does not know which {manager} packages provide '{component}'."
        )
    selected_packages = packages or known_packages
    if not selected_packages or any(package not in known_packages for package in selected_packages):
        raise SystemInstallError("Refusing to remove packages outside the known component mapping.")
    return [*_privilege_prefix(), executable, *_REMOVE_ARGUMENTS[manager], *selected_packages]


def uninstall_system_component(
    component: str,
    distribution: LinuxDistribution | None = None,
    *,
    timeout: int = 900,
    progress: Callable[[str, int | None], None] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Remove only system packages that RunEXE previously installed and still owns."""

    distribution = distribution or detect_linux_distribution()
    manager = detect_package_manager(distribution)
    if manager is None:
        raise SystemInstallError(
            f"Automatic package removal is not supported on {distribution.pretty_name}."
        )
    packages = managed_system_component_packages(component, distribution)
    if not packages:
        raise SystemInstallError(
            "RunEXE can only remove system packages that it installed itself and can still verify."
        )
    if progress is not None:
        progress(f"Step 1 of 3 · Resolving installed packages for {component}", 10)
    command = package_remove_command(component, distribution, packages=packages)
    if progress is not None:
        progress(
            "Step 2 of 3 · Removing system packages · administrator approval may be required",
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
        raise SystemInstallError(f"System package removal failed{suffix}") from error
    except subprocess.TimeoutExpired as error:
        raise SystemInstallError("System package removal timed out.") from error
    except OSError as error:
        raise SystemInstallError(f"Could not start system package removal: {error}") from error
    _record_package_receipt(component, manager, ())
    if progress is not None:
        progress(f"Step 3 of 3 · {component.title()} packages removed", 100)
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
