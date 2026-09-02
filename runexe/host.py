"""Read-only detection of host capabilities relevant to Wine and Proton."""

from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path

from .gpu import detect_gpu
from .graphics import probe_vulkan
from .models import ExecutableInfo, HostInfo
from .platform_support import find_executable
from .proton import discover_proton_installations


def _normalize_architecture(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_")
    aliases = {
        "amd64": "x86_64",
        "x64": "x86_64",
        "i386": "x86",
        "i486": "x86",
        "i586": "x86",
        "i686": "x86",
        "arm64": "aarch64",
    }
    return aliases.get(normalized, normalized)


def _wine_supports_wow64(wine_binary: str) -> bool | None:
    """Look for a WoW64 loader without creating or changing a prefix.

    ``None`` means the installed layout is inconclusive. Modern unified
    Wine builds are not required to expose a separate ``wine64`` binary,
    so absence is not proof that WoW64 is unavailable.
    """

    wine_path = Path(wine_binary).resolve()
    candidates = [
        wine_path.parent / "wine64",
        wine_path.parent.parent / "bin" / "wine64",
        wine_path.parent.parent / "lib" / "wine" / "x86_64-windows",
        wine_path.parent.parent / "lib64" / "wine" / "x86_64-windows",
    ]
    if any(path.is_dir() or (path.is_file() and os.access(path, os.X_OK)) for path in candidates):
        return True
    return None


def _wine_supports_32bit_prefix(wine_binary: str) -> bool | None:
    """Return a read-only signal for traditional 32-bit Wine support."""

    wine_path = Path(wine_binary).resolve()
    candidates = [
        wine_path.parent / "wine32",
        wine_path.parent.parent / "lib" / "wine" / "i386-windows",
        wine_path.parent.parent / "lib32" / "wine" / "i386-windows",
    ]
    if any(path.is_dir() or (path.is_file() and os.access(path, os.X_OK)) for path in candidates):
        return True
    return None


def detect_host(executable: ExecutableInfo | None = None) -> HostInfo:
    """Detect host capabilities without initializing a temporary prefix.

    ``executable`` remains accepted for API compatibility but detection is
    host-wide. Actual prefix support is ultimately validated during launch.
    """

    del executable
    architecture = _normalize_architecture(platform.machine())
    wine_binary = find_executable("wine")
    wine_installed = wine_binary is not None
    wine_version = None
    wine_wow64: bool | None = False
    wine_32bit_prefix: bool | None = False

    if wine_binary:
        wine_wow64 = _wine_supports_wow64(wine_binary)
        wine_32bit_prefix = _wine_supports_32bit_prefix(wine_binary)
        try:
            result = subprocess.run(
                [wine_binary, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0:
                wine_version = (result.stdout or result.stderr).strip() or None
        except (subprocess.TimeoutExpired, OSError):
            pass

    proton_installations = discover_proton_installations()
    vulkan = probe_vulkan()
    gpu = detect_gpu()

    return HostInfo(
        architecture=architecture,
        wine_installed=wine_installed,
        wine_version=wine_version,
        wine_wow64=wine_wow64,
        wine_32bit_prefix=wine_32bit_prefix,
        winetricks_installed=find_executable("winetricks") is not None,
        proton_installed=bool(proton_installations),
        proton_versions=[item.name for item in proton_installations],
        vulkan_available=vulkan.available,
        vulkan_version=vulkan.version,
        vulkan_devices=list(vulkan.devices),
        vulkan_error=vulkan.error,
        vulkan_supported=gpu.vulkan_supported,
        gpu_vendors=list(gpu.gpu_vendors),
    )
