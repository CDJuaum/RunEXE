import re
import sys
import tarfile
from pathlib import Path

import pytest

from scripts import frozen_entry, package_linux

ROOT = Path(__file__).resolve().parent.parent


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


def test_python_packages_ship_qml_sources():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    assert '"gui/qml/*.qml"' in pyproject
    assert '"gui/qml/**/*.qml"' in pyproject
    assert '"gui/qml/qmldir"' in pyproject
    assert "recursive-include runexe/gui/qml *.qml qmldir" in manifest


def test_glibc_frozen_build_collects_qt_quick_runtime_while_musl_stays_cli_only():
    script = (ROOT / "scripts/build_linux.sh").read_text(encoding="utf-8")
    assert "--hidden-import PySide6.QtQml" in script
    assert "--hidden-import PySide6.QtQuick" in script
    assert "--hidden-import PySide6.QtQuickControls2" in script
    assert "QtQuick.Controls and QtQuick.Dialogs" in script
    assert 'if [ "$1" = glibc ]; then' in script
    assert "extras='.[dev]'" in script
    assert "extras='.[dev,gui]'" in script
    assert "libpython3.10" in script
    assert "python -m pip install --upgrade 'pip>=24.2' 'setuptools>=77.0.3' wheel" in script
    assert "python -m pip install \"$extras\" 'pyinstaller==6.22.2'" in script


def test_release_workflow_accepts_new_tag_pushes():
    workflow = (ROOT / ".github/workflows/release-linux.yml").read_text(encoding="utf-8")

    assert "github.event_name == 'push' && !github.event.deleted" in workflow
    assert "!github.event.created" not in workflow


def test_deb_package_declares_qt_glib_runtime():
    packaging = (ROOT / "scripts/package_linux.py").read_text(encoding="utf-8")

    assert "libglib2.0-0" in packaging
