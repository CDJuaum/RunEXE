import io
import tarfile
from pathlib import Path

import pytest

from runexe.proton import (
    ProtonError,
    ProtonInstallation,
    discover_proton_installations,
    install_managed_proton,
    proton_environment,
    select_proton,
)


def make_proton(root: Path, name: str, version: str = "") -> ProtonInstallation:
    install = root / "steamapps" / "common" / name
    install.mkdir(parents=True)
    script = install / "proton"
    script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    script.chmod(0o755)
    if version:
        (install / "version").write_text(version + "\n", encoding="utf-8")
    return ProtonInstallation(name, script.resolve(), version or None, root.resolve())


def test_discovers_and_prefers_experimental(tmp_path, monkeypatch):
    root = tmp_path / "Steam"
    make_proton(root, "Proton 10.0", "10.0-4")
    make_proton(root, "Proton Experimental", "experimental-bleeding-edge")
    monkeypatch.setattr("runexe.proton._common_steam_roots", lambda: [root])

    installations = discover_proton_installations()

    assert [item.name for item in installations] == ["Proton Experimental", "Proton 10.0"]


def test_discovers_proton_in_an_additional_steam_library(tmp_path, monkeypatch):
    root = tmp_path / "Steam"
    library = tmp_path / "Games"
    manifest = root / "steamapps" / "libraryfolders.vdf"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(f'"libraryfolders" {{ "1" {{ "path" "{library}" }} }}', encoding="utf-8")
    expected = make_proton(library, "GE-Proton")
    monkeypatch.setattr("runexe.proton._common_steam_roots", lambda: [root])

    installations = discover_proton_installations()

    assert [item.script for item in installations] == [expected.script]
    assert installations[0].steam_root == root.resolve()


def test_discovers_runexe_managed_proton(tmp_path, monkeypatch):
    managed = tmp_path / "data" / "runexe" / "runtimes" / "proton"
    install = managed / "GE-Proton10-20"
    install.mkdir(parents=True)
    script = install / "proton"
    script.write_text("#!/bin/sh\n", encoding="utf-8")
    script.chmod(0o755)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setattr("runexe.proton._common_steam_roots", lambda: [])

    installations = discover_proton_installations()

    assert [item.name for item in installations] == ["GE-Proton10-20"]
    assert installations[0].steam_root == managed.resolve()


def test_installs_managed_ge_proton_from_mocked_release(tmp_path, monkeypatch):
    archive = tmp_path / "source.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        data = b"#!/bin/sh\n"
        info = tarfile.TarInfo("GE-Proton10-20/proton")
        info.mode = 0o755
        info.size = len(data)
        bundle.addfile(info, io.BytesIO(data))

    monkeypatch.setattr(
        "runexe.proton._latest_ge_proton_asset",
        lambda: ("GE-Proton10-20", "https://example.invalid/ge.tar.gz"),
    )

    def download(_url, destination, **_kwargs):
        destination.write_bytes(archive.read_bytes())

    monkeypatch.setattr("runexe.proton._download_file", download)

    progress = []
    installation = install_managed_proton(
        tmp_path / "managed", progress=lambda label, value: progress.append((label, value))
    )

    assert installation.name == "GE-Proton10-20"
    assert installation.script == (tmp_path / "managed" / "GE-Proton10-20" / "proton").resolve()
    assert installation.script.read_bytes() == b"#!/bin/sh\n"
    assert progress[0][1] == 5
    assert any("Downloading" in label for label, _value in progress)
    assert progress[-1][1] == 100


def test_managed_proton_rejects_archive_path_traversal(tmp_path, monkeypatch):
    archive = tmp_path / "unsafe.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        data = b"bad"
        info = tarfile.TarInfo("../outside")
        info.size = len(data)
        bundle.addfile(info, io.BytesIO(data))

    monkeypatch.setattr(
        "runexe.proton._latest_ge_proton_asset",
        lambda: ("GE-Proton10-20", "https://example.invalid/ge.tar.gz"),
    )
    monkeypatch.setattr(
        "runexe.proton._download_file",
        lambda _url, destination, **_kwargs: destination.write_bytes(archive.read_bytes()),
    )

    with pytest.raises(ProtonError, match="Unsafe path"):
        install_managed_proton(tmp_path / "managed")

    assert not (tmp_path / "outside").exists()


def test_selects_by_name_and_rejects_ambiguous_query(tmp_path):
    root = tmp_path / "Steam"
    stable = make_proton(root, "Proton 10.0")
    experimental = make_proton(root, "Proton Experimental")

    assert select_proton("Proton 10.0", [experimental, stable]) == stable
    with pytest.raises(ProtonError, match="ambiguous"):
        select_proton("Proton", [experimental, stable])


def test_proton_environment_is_isolated_and_complete(tmp_path):
    root = tmp_path / "Steam"
    installation = make_proton(root, "Proton 10.0")
    executable = tmp_path / "game" / "game.exe"
    executable.parent.mkdir()
    executable.touch()
    compat_data = tmp_path / "compat"

    env = proton_environment(installation, compat_data, executable)

    assert env["STEAM_COMPAT_DATA_PATH"] == str(compat_data)
    assert env["STEAM_COMPAT_CLIENT_INSTALL_PATH"] == str(root.resolve())
    assert env["STEAM_COMPAT_INSTALL_PATH"] == str(executable.parent.resolve())
    assert env["STEAM_COMPAT_APP_ID"].isdigit()
    assert "WINEPREFIX" not in env


def test_proton_tuning_presets_are_temporary_environment_overrides(tmp_path, monkeypatch):
    root = tmp_path / "Steam"
    installation = make_proton(root, "Proton 11.0")
    executable = tmp_path / "game.exe"
    executable.touch()
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))

    diagnostics = proton_environment(installation, tmp_path / "compat", executable, "diagnostics")
    fallback = proton_environment(installation, tmp_path / "compat", executable, "wined3d")

    assert diagnostics["PROTON_LOG"] == "1"
    assert diagnostics["DXVK_LOG_LEVEL"] == "info"
    assert diagnostics["PROTON_LOG_DIR"] == str(tmp_path / "state" / "runexe" / "logs")
    assert fallback["PROTON_USE_WINED3D"] == "1"
    assert "PROTON_USE_WINED3D" not in diagnostics
