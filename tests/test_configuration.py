from datetime import datetime, timezone

from runexe.configuration import open_environment_configuration
from runexe.environments import EnvironmentInfo
from runexe.proton import ProtonInstallation


def environment(path, backend="wine", runtime_path=None):
    ready_path = path / "drive_c" if backend == "wine" else path / "pfx" / "drive_c"
    ready_path.mkdir(parents=True)
    return EnvironmentInfo(
        identifier=f"{backend}:{path.name}",
        backend=backend,
        path=path,
        application="Example",
        source=str(path.parent / "example.exe"),
        architecture="x86_64",
        runtime=backend.title(),
        runtime_path=runtime_path,
        windows_version="11",
        dxvk_available=None,
        dxvk_source="test",
        dxvk_components=(),
        size_bytes=0,
        modified_at=datetime.now(timezone.utc).isoformat(),
        ready=True,
    )


def test_opens_wine_registry_for_exact_managed_prefix(tmp_path, monkeypatch):
    item = environment(tmp_path / "prefix")
    seen = {}
    monkeypatch.setattr(
        "runexe.configuration.find_executable",
        lambda name: "/usr/bin/wine" if name == "wine" else None,
    )
    monkeypatch.setattr(
        "runexe.configuration.subprocess.Popen",
        lambda command, **kwargs: seen.update(command=command, **kwargs),
    )

    open_environment_configuration(item, "regedit")

    assert seen["command"] == ["/usr/bin/wine", "regedit"]
    assert seen["env"]["WINEPREFIX"] == str(item.path)


def test_opens_proton_control_panel_with_recorded_runtime(tmp_path, monkeypatch):
    script = tmp_path / "Proton" / "proton"
    script.parent.mkdir()
    script.touch()
    item = environment(tmp_path / "compat", "proton", str(script))
    installation = ProtonInstallation("Proton", script, "11", tmp_path / "Steam")
    seen = {}
    monkeypatch.setattr("runexe.configuration.select_proton", lambda _path: installation)
    monkeypatch.setattr(
        "runexe.configuration.subprocess.Popen",
        lambda command, **kwargs: seen.update(command=command, **kwargs),
    )

    open_environment_configuration(item, "control")

    assert seen["command"] == [str(script), "runinprefix", "control"]
    assert seen["env"]["STEAM_COMPAT_DATA_PATH"] == str(item.path)
