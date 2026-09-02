import json
from pathlib import Path

import pytest

from runexe.gpu import (
    GpuInfo,
    VulkanIcd,
    discover_graphics_adapters,
    discover_vulkan_icds,
)


def make_render_node(drm_root: Path, name: str, vendor: str, driver: str = "amdgpu") -> None:
    node = drm_root / name
    device = node / "device"
    device.mkdir(parents=True)
    (device / "vendor").write_text(f"{vendor}\n", encoding="utf-8")
    driver_target = drm_root / "drivers" / driver
    driver_target.mkdir(parents=True, exist_ok=True)
    try:
        (device / "driver").symlink_to(driver_target)
    except OSError as error:
        if getattr(error, "winerror", None) == 1314 or isinstance(error, PermissionError):
            pytest.skip("symlink creation is not permitted")
        raise


def test_discovers_adapter_vendor_and_bound_driver(tmp_path):
    drm_root = tmp_path / "drm"
    make_render_node(drm_root, "renderD128", "0x1002", driver="amdgpu")

    adapters = discover_graphics_adapters(drm_root)

    assert len(adapters) == 1
    assert adapters[0].vendor == "amd"
    assert adapters[0].driver == "amdgpu"
    assert adapters[0].render_node == Path("/dev/dri/renderD128")


def test_unknown_pci_vendor_id_is_reported_as_unknown(tmp_path):
    drm_root = tmp_path / "drm"
    make_render_node(drm_root, "renderD128", "0xdead", driver="mystery")

    adapters = discover_graphics_adapters(drm_root)

    assert adapters[0].vendor == "unknown"


def test_missing_drm_directory_returns_no_adapters(tmp_path):
    assert discover_graphics_adapters(tmp_path / "does-not-exist") == ()


def test_discovers_vulkan_icds_and_classifies_vendor(tmp_path, monkeypatch):
    icd_dir = tmp_path / "icd.d"
    icd_dir.mkdir()
    (icd_dir / "nvidia_icd.json").write_text(
        json.dumps({"ICD": {"library_path": "libGLX_nvidia.so.0", "api_version": "1.3.277"}}),
        encoding="utf-8",
    )
    (icd_dir / "lvp_icd.x86_64.json").write_text(
        json.dumps({"ICD": {"library_path": "libvulkan_lvp.so", "api_version": "1.3.275"}}),
        encoding="utf-8",
    )
    monkeypatch.setattr("runexe.gpu._default_icd_dirs", lambda: [icd_dir])
    monkeypatch.setattr("runexe.gpu._icd_override_files", lambda: [])

    icds = discover_vulkan_icds()

    vendors = {icd.vendor for icd in icds}
    assert vendors == {"nvidia", "software"}


def test_malformed_icd_manifest_is_skipped(tmp_path, monkeypatch):
    icd_dir = tmp_path / "icd.d"
    icd_dir.mkdir()
    (icd_dir / "broken.json").write_text("not json", encoding="utf-8")
    monkeypatch.setattr("runexe.gpu._default_icd_dirs", lambda: [icd_dir])
    monkeypatch.setattr("runexe.gpu._icd_override_files", lambda: [])

    assert discover_vulkan_icds() == ()


def test_vulkan_supported_requires_loader_and_hardware_icd():
    software_only = GpuInfo(
        vulkan_icds=(VulkanIcd(Path("lvp.json"), "libvulkan_lvp.so", None, "software"),),
        vulkan_loader_installed=True,
    )
    hardware_no_loader = GpuInfo(
        vulkan_icds=(VulkanIcd(Path("amd.json"), "libvulkan_radeon.so", None, "amd"),),
        vulkan_loader_installed=False,
    )
    hardware_ready = GpuInfo(
        vulkan_icds=(VulkanIcd(Path("amd.json"), "libvulkan_radeon.so", None, "amd"),),
        vulkan_loader_installed=True,
    )

    assert software_only.vulkan_supported is False
    assert hardware_no_loader.vulkan_supported is False
    assert hardware_ready.vulkan_supported is True


def test_gpu_vendors_are_deduplicated_and_sorted():
    from runexe.gpu import GraphicsAdapter

    info = GpuInfo(
        adapters=(
            GraphicsAdapter(Path("/dev/dri/renderD128"), "amd"),
            GraphicsAdapter(Path("/dev/dri/renderD129"), "amd"),
            GraphicsAdapter(Path("/dev/dri/renderD130"), "unknown"),
        )
    )

    assert info.gpu_vendors == ("amd",)
