from pathlib import Path
from types import SimpleNamespace

import pytest

from runexe.graphics import VulkanProbe
from runexe.host import detect_host
from runexe.proton import ProtonInstallation


@pytest.mark.parametrize(
    "supplied",
    [
        None,
        [],
        [ProtonInstallation("Example Proton", Path("/example/proton"), "custom", Path("/example"))],
    ],
)
def test_host_reuses_supplied_discovery_including_empty_list(monkeypatch, supplied):
    discovered = [ProtonInstallation("Detected", Path("/detected/proton"), "custom", None)]
    calls = []

    def discover():
        calls.append(True)
        return discovered

    monkeypatch.setattr("runexe.host.find_executable", lambda name: None)
    monkeypatch.setattr("runexe.host.discover_proton_installations", discover)
    monkeypatch.setattr("runexe.host.probe_vulkan", lambda: VulkanProbe(None))
    monkeypatch.setattr(
        "runexe.host.detect_gpu",
        lambda: SimpleNamespace(vulkan_supported=False, gpu_vendors=[]),
    )

    host = detect_host(proton_installations=supplied)
    expected = discovered if supplied is None else supplied
    assert host.proton_versions == [item.name for item in expected]
    assert host.proton_installed == bool(expected)
    assert len(calls) == int(supplied is None)
