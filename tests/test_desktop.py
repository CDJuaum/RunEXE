from pathlib import Path

import pytest

from runexe.desktop import (
    MANAGED_MARKER,
    DesktopIntegrationError,
    install_desktop_entry,
    remove_desktop_entry,
)


def test_desktop_entry_installs_icon_and_opens_one_local_file(tmp_path):
    gui = tmp_path / "bin with spaces" / "runexe-gui"
    gui.parent.mkdir()
    gui.touch(mode=0o755)

    paths = install_desktop_entry(
        gui,
        data_home=tmp_path / "share",
        refresh=False,
        platform_name="linux",
    )

    contents = paths.desktop_file.read_text(encoding="utf-8")
    assert "Name=RunEXE" in contents
    escaped_gui = str(gui.resolve()).replace("\\", "\\\\")
    assert f'Exec="{escaped_gui}" %f' in contents
    assert "Icon=runexe" in contents
    assert "MimeType=" in contents
    assert MANAGED_MARKER in contents
    assert paths.icon_file.read_bytes().startswith(b"\x89PNG")

    _paths, removed = remove_desktop_entry(
        data_home=tmp_path / "share",
        refresh=False,
        platform_name="linux",
    )
    assert removed
    assert not paths.desktop_file.exists()
    assert not paths.icon_file.exists()


def test_desktop_entry_does_not_replace_or_remove_unmanaged_file(tmp_path):
    data_home = tmp_path / "share"
    desktop = data_home / "applications" / "runexe.desktop"
    desktop.parent.mkdir(parents=True)
    desktop.write_text("[Desktop Entry]\nName=Custom\n", encoding="utf-8")
    gui = tmp_path / "runexe-gui"
    gui.touch(mode=0o755)

    with pytest.raises(DesktopIntegrationError, match="unmanaged"):
        install_desktop_entry(
            gui,
            data_home=data_home,
            refresh=False,
            platform_name="linux",
        )
    with pytest.raises(DesktopIntegrationError, match="unmanaged"):
        remove_desktop_entry(
            data_home=data_home,
            refresh=False,
            platform_name="linux",
        )

    assert desktop.read_text(encoding="utf-8") == "[Desktop Entry]\nName=Custom\n"


def test_desktop_integration_rejects_other_operating_systems(tmp_path):
    with pytest.raises(DesktopIntegrationError, match="Linux only"):
        install_desktop_entry(
            Path("runexe-gui"),
            data_home=tmp_path,
            refresh=False,
            platform_name="win32",
        )
