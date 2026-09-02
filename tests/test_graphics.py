from types import SimpleNamespace

from runexe.graphics import detect_dxvk, detect_graphics_requirements, probe_vulkan
from runexe.models import PEImport


def test_directx_detection_selects_dxvk_and_vkd3d_paths():
    requirements = detect_graphics_requirements(
        [PEImport("d3d9.dll"), PEImport("d3d11.dll"), PEImport("d3d12.dll")]
    )

    assert requirements.apis == ("Direct3D 9", "Direct3D 11", "Direct3D 12")
    assert requirements.translators == ("DXVK", "VKD3D-Proton")
    assert requirements.vulkan_recommended
    assert requirements.vulkan_required


def test_vulkan_probe_parses_summary(monkeypatch):
    output = """Vulkan Instance Version: 1.3.280
GPU0:
    apiVersion = 1.3.275
    deviceName = Example GPU
"""
    monkeypatch.setattr(
        "runexe.graphics.subprocess.run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout=output, stderr=""),
    )

    probe = probe_vulkan("/usr/bin/vulkaninfo")

    assert probe.available
    assert probe.version == "1.3.280"
    assert probe.devices == ("Example GPU",)


def test_dxvk_detection_uses_prefix_signature_and_proton_runtime(tmp_path):
    prefix = tmp_path / "prefix"
    system32 = prefix / "drive_c" / "windows" / "system32"
    system32.mkdir(parents=True)
    (system32 / "d3d11.dll").write_bytes(b"MZ\x00DXVK\x00")

    wine = detect_dxvk(prefix, backend="wine")

    proton_script = tmp_path / "Proton" / "proton"
    proton_script.parent.mkdir()
    proton_script.touch()
    dxvk_dir = proton_script.parent / "files" / "lib64" / "wine" / "dxvk"
    dxvk_dir.mkdir(parents=True)
    (dxvk_dir / "dxgi.dll").touch()
    proton = detect_dxvk(tmp_path / "empty", backend="proton", proton_script=proton_script)

    assert wine.available and wine.components == ("d3d11",)
    assert proton.available and proton.components == ("dxgi",)
