import re
import sys
import tarfile

import pytest

from scripts import frozen_entry, package_linux


@pytest.mark.parametrize("tag", ["v0.6.0", "release/test", "$(echo nope)", "../", "x" * 200])
def test_release_labels_are_safe_and_bounded(tag):
    label = package_linux.tag_label(tag)
    assert re.fullmatch(r"[A-Za-z0-9._-]+", label)
    assert len(label) <= 89
    assert not label.startswith(".")
    assert package_linux.tag_label("release/test") != package_linux.tag_label("release-test")


@pytest.mark.parametrize("original", [None, "/custom/lib", ""])
def test_frozen_launcher_restores_host_library_search_path(monkeypatch, original):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("LD_LIBRARY_PATH", "/bundle/_internal")
    if original is None:
        monkeypatch.delenv("LD_LIBRARY_PATH_ORIG", raising=False)
    else:
        monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", original)
    frozen_entry.restore_library_path()
    assert frozen_entry.os.environ.get("LD_LIBRARY_PATH") == original


def test_source_launcher_keeps_environment(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setenv("LD_LIBRARY_PATH", "/custom/lib")
    frozen_entry.restore_library_path()
    assert frozen_entry.os.environ["LD_LIBRARY_PATH"] == "/custom/lib"


def test_musl_archive_contains_executable_license_and_provenance(tmp_path, monkeypatch):
    bundle = tmp_path / "build/frozen/runexe"
    bundle.mkdir(parents=True)
    (bundle / "runexe").write_bytes(b"example executable")
    (tmp_path / "LICENSE").write_text("license", encoding="utf-8")
    (tmp_path / "README.md").write_text("instructions", encoding="utf-8")
    monkeypatch.setattr(package_linux, "ROOT", tmp_path)
    monkeypatch.setattr(package_linux, "installed_version", lambda name: "0.6.0")
    monkeypatch.setattr(sys, "argv", ["package_linux.py", "musl"])
    monkeypatch.setenv("RELEASE_TAG", "release/test")
    monkeypatch.setenv("RELEASE_SHA", "abc123")
    package_linux.main()
    archives = list((tmp_path / "dist/linux").glob("*.tar.gz"))
    assert len(archives) == 1
    with tarfile.open(archives[0]) as archive:
        assert "runexe/runexe" in archive.getnames()
        assert "runexe/LICENSE" in archive.getnames()
        assert "runexe/runexe-gui" not in archive.getnames()
        assert b"Commit: abc123" in archive.extractfile("runexe/BUILD-INFO.txt").read()
