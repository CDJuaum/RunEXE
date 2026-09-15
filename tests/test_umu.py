import hashlib
import io
import tarfile
from pathlib import Path

import pytest

from runexe.umu import (
    UmuError,
    _download_file,
    ensure_umu_launcher,
    install_managed_umu,
    remove_managed_umu,
)


def make_zipapp_archive(path, member_name="umu/umu-run", payload=b"#!/usr/bin/python3\n"):
    with tarfile.open(path, "w") as bundle:
        info = tarfile.TarInfo(member_name)
        info.mode = 0o755
        info.size = len(payload)
        bundle.addfile(info, io.BytesIO(payload))
    return payload


def test_installs_managed_umu_zipapp_from_official_release_shape(tmp_path, monkeypatch):
    archive = tmp_path / "source.tar"
    payload = make_zipapp_archive(archive)
    digest = "sha256:" + hashlib.sha256(archive.read_bytes()).hexdigest()
    monkeypatch.setattr(
        "runexe.umu._latest_umu_asset",
        lambda: ("1.4.4", "https://example.invalid/umu.tar", digest),
    )

    def download(_url, destination, expected_digest, **_kwargs):
        assert expected_digest == digest
        destination.write_bytes(archive.read_bytes())

    monkeypatch.setattr("runexe.umu._download_file", download)
    progress = []

    executable = install_managed_umu(
        tmp_path / "managed", progress=lambda label, value: progress.append((label, value))
    )

    assert executable == tmp_path / "managed" / "umu-run"
    assert executable.read_bytes() == payload
    assert (tmp_path / "managed" / "VERSION").read_text(encoding="utf-8") == "1.4.4\n"
    assert progress[0][1] == 5
    assert progress[-1][1] == 100


def test_managed_umu_rejects_traversal_named_zipapp(tmp_path, monkeypatch):
    archive = tmp_path / "unsafe.tar"
    make_zipapp_archive(archive, "../umu-run")
    monkeypatch.setattr(
        "runexe.umu._latest_umu_asset",
        lambda: ("1.4.4", "https://example.invalid/umu.tar", None),
    )
    monkeypatch.setattr(
        "runexe.umu._download_file",
        lambda _url, destination, _digest, **_kwargs: destination.write_bytes(archive.read_bytes()),
    )

    with pytest.raises(UmuError, match="Unsafe UMU archive member"):
        install_managed_umu(tmp_path / "managed")

    assert not (tmp_path / "umu-run").exists()


def test_umu_download_rejects_sha256_mismatch(tmp_path, monkeypatch):
    payload = b"official-looking-but-wrong"

    class Response(io.BytesIO):
        headers = {"Content-Length": str(len(payload))}

    monkeypatch.setattr(
        "runexe.umu.urllib.request.urlopen",
        lambda *_args, **_kwargs: Response(payload),
    )

    with pytest.raises(UmuError, match="SHA-256 verification"):
        _download_file(
            "https://example.invalid/umu.tar",
            Path(tmp_path / "umu.tar"),
            "sha256:" + "0" * 64,
        )


def test_ensure_umu_reuses_managed_zipapp_without_network(tmp_path, monkeypatch):
    managed = tmp_path / "data" / "runexe" / "runtimes" / "umu"
    managed.mkdir(parents=True)
    executable = managed / "umu-run"
    executable.write_bytes(b"zipapp")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setattr("runexe.umu.find_executable", lambda _name: None)
    monkeypatch.setattr(
        "runexe.umu.install_managed_umu",
        lambda **_kwargs: pytest.fail("existing managed UMU should be reused"),
    )

    assert ensure_umu_launcher() == str(executable.resolve())


def test_ensure_umu_prefers_system_launcher(monkeypatch):
    monkeypatch.setattr("runexe.umu.find_executable", lambda _name: "/usr/bin/umu-run")

    assert ensure_umu_launcher() == "/usr/bin/umu-run"


def test_remove_managed_umu_only_removes_runexe_owned_launcher(tmp_path, monkeypatch):
    managed = tmp_path / "data" / "runexe" / "runtimes" / "umu"
    managed.mkdir(parents=True)
    (managed / "umu-run").touch()
    system = tmp_path / "usr" / "bin" / "umu-run"
    system.parent.mkdir(parents=True)
    system.touch()
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))

    assert remove_managed_umu() is True
    assert not managed.exists()
    assert system.exists()


def test_remove_managed_umu_preserves_unrelated_files(tmp_path, monkeypatch):
    managed = tmp_path / "data" / "runexe" / "runtimes" / "umu"
    managed.mkdir(parents=True)
    (managed / "umu-run").touch()
    unrelated = managed / "notes.txt"
    unrelated.write_text("keep", encoding="utf-8")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))

    assert remove_managed_umu() is True
    assert unrelated.read_text(encoding="utf-8") == "keep"
    assert managed.exists()


def test_remove_managed_umu_rejects_symlinked_managed_root(tmp_path, monkeypatch):
    data = tmp_path / "data"
    runtime_root = data / "runexe" / "runtimes"
    runtime_root.mkdir(parents=True)
    outside = tmp_path / "outside-umu"
    outside.mkdir()
    (outside / "umu-run").touch()
    managed = runtime_root / "umu"
    try:
        managed.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are unavailable on this host")
    monkeypatch.setenv("XDG_DATA_HOME", str(data))

    with pytest.raises(UmuError, match="symlinked managed runtime"):
        remove_managed_umu()
    assert (outside / "umu-run").exists()
