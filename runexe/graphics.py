"""Read-only DirectX, Vulkan, GPU, and DXVK capability detection."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .models import GraphicsRequirements, PEImport
from .platform_support import find_executable


@dataclass(frozen=True)
class VulkanProbe:
    available: bool | None
    version: str | None = None
    devices: tuple[str, ...] = ()
    error: str | None = None
    executable: str | None = None


@dataclass(frozen=True)
class DXVKStatus:
    available: bool | None
    source: str
    components: tuple[str, ...] = ()


def detect_graphics_requirements(imports: list[PEImport] | None) -> GraphicsRequirements:
    names = {item.name.lower() for item in imports or []}
    apis: list[str] = []
    translators: list[str] = []

    def add_api(label: str, translator: str | None = None) -> None:
        if label not in apis:
            apis.append(label)
        if translator and translator not in translators:
            translators.append(translator)

    if "ddraw.dll" in names:
        add_api("DirectDraw", "WineD3D")
    if "d3d8.dll" in names:
        add_api("Direct3D 8", "DXVK")
    if "d3d9.dll" in names or any(name.startswith("d3dx9_") for name in names):
        add_api("Direct3D 9", "DXVK")
    if names & {"d3d10.dll", "d3d10_1.dll", "d3d10core.dll"} or any(
        name.startswith("d3dx10_") for name in names
    ):
        add_api("Direct3D 10", "DXVK")
    if "d3d11.dll" in names or any(name.startswith("d3dx11_") for name in names):
        add_api("Direct3D 11", "DXVK")
    if names & {"d3d12.dll", "d3d12core.dll"}:
        add_api("Direct3D 12", "VKD3D-Proton")
    if "d2d1.dll" in names:
        add_api("Direct2D", "WineD3D")
    if "vulkan-1.dll" in names:
        add_api("Vulkan")
    if "opengl32.dll" in names:
        add_api("OpenGL")

    vulkan_recommended = bool({"DXVK", "VKD3D-Proton"} & set(translators))
    vulkan_required = "VKD3D-Proton" in translators or "Vulkan" in apis
    return GraphicsRequirements(
        tuple(apis),
        tuple(translators),
        vulkan_recommended,
        vulkan_required,
    )


def probe_vulkan(executable: str | None = None, *, timeout: int = 10) -> VulkanProbe:
    binary = executable or find_executable("vulkaninfo")
    if binary is None:
        return VulkanProbe(None, error="vulkaninfo is not installed")
    try:
        result = subprocess.run(
            [binary, "--summary"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return VulkanProbe(False, error="vulkaninfo timed out", executable=binary)
    except OSError as error:
        return VulkanProbe(False, error=str(error), executable=binary)

    output = f"{result.stdout}\n{result.stderr}"
    devices = tuple(
        dict.fromkeys(
            match.strip()
            for match in re.findall(r"^\s*deviceName\s*=\s*(.+?)\s*$", output, re.MULTILINE)
            if match.strip()
        )
    )
    versions = re.findall(
        r"(?:Vulkan Instance Version|apiVersion)\s*[:=]\s*([0-9]+(?:\.[0-9]+){1,3})",
        output,
        re.IGNORECASE,
    )
    version = versions[0] if versions else None
    if result.returncode != 0:
        detail = next((line.strip() for line in output.splitlines() if line.strip()), None)
        return VulkanProbe(False, version, devices, detail or "vulkaninfo failed", binary)
    return VulkanProbe(True, version, devices, executable=binary)


def _contains_dxvk_signature(path: Path, *, limit: int = 32 * 1024 * 1024) -> bool:
    try:
        remaining = min(path.stat().st_size, limit)
        carry = b""
        with path.open("rb") as file:
            while remaining > 0:
                chunk = file.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                sample = (carry + chunk).lower()
                if b"dxvk" in sample:
                    return True
                carry = sample[-3:]
                remaining -= len(chunk)
    except OSError:
        return False
    return False


def _prefix_dxvk_components(prefix: Path) -> tuple[str, ...]:
    components: set[str] = set()
    for directory in (
        prefix / "drive_c" / "windows" / "system32",
        prefix / "drive_c" / "windows" / "syswow64",
    ):
        for component in ("d3d8", "d3d9", "d3d10core", "d3d11", "dxgi"):
            candidate = directory / f"{component}.dll"
            if candidate.is_file() and _contains_dxvk_signature(candidate):
                components.add(component)
    return tuple(sorted(components))


def _proton_dxvk_components(proton_script: Path) -> tuple[str, ...]:
    install_dir = proton_script.expanduser().resolve().parent
    directories = (
        install_dir / "files" / "lib64" / "wine" / "dxvk",
        install_dir / "files" / "lib" / "wine" / "dxvk",
        install_dir / "dist" / "lib64" / "wine" / "dxvk",
        install_dir / "dist" / "lib" / "wine" / "dxvk",
        install_dir / "files" / "share" / "default_pfx" / "drive_c" / "windows" / "system32",
        install_dir / "dist" / "share" / "default_pfx" / "drive_c" / "windows" / "system32",
    )
    components: set[str] = set()
    for directory in directories:
        if not directory.is_dir():
            continue
        for component in ("d3d8", "d3d9", "d3d10core", "d3d11", "dxgi"):
            if (directory / f"{component}.dll").is_file():
                components.add(component)
    return tuple(sorted(components))


def detect_dxvk(
    prefix: Path,
    *,
    backend: str,
    proton_script: Path | None = None,
) -> DXVKStatus:
    """Detect DXVK without changing a prefix or starting Wine."""

    prefix_components = _prefix_dxvk_components(prefix)
    if prefix_components:
        return DXVKStatus(True, "environment DLLs", prefix_components)
    if backend == "proton" and proton_script is not None and proton_script.is_file():
        proton_components = _proton_dxvk_components(proton_script)
        if proton_components:
            return DXVKStatus(True, "Proton runtime", proton_components)
        return DXVKStatus(False, "Proton runtime")
    if backend == "wine":
        return DXVKStatus(False, "Wine prefix")
    return DXVKStatus(None, "runtime unavailable")
