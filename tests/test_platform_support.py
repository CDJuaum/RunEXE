import os
from pathlib import Path

import pytest

from runexe.gui.bootstrap import choose_qt_platform
from runexe.platform_support import (
    LinuxDistribution,
    SystemInstallError,
    detect_linux_distribution,
    find_executable,
    install_hint,
    install_system_component,
    package_install_command,
)


def test_reads_quoted_os_release_and_maps_derivative_family(tmp_path):
    release = tmp_path / "os-release"
    release.write_text(
        'NAME="Kali GNU/Linux"\nID=kali\nID_LIKE="debian ubuntu"\n'
        'PRETTY_NAME="Kali GNU/Linux Rolling"\n',
        encoding="utf-8",
    )

    distribution = detect_linux_distribution(release)

    assert distribution.identifier == "kali"
    assert distribution.family == "debian"
    assert distribution.pretty_name == "Kali GNU/Linux Rolling"


@pytest.mark.parametrize(
    ("distribution", "manager", "expected"),
    [
        (LinuxDistribution("ubuntu"), "apt", "sudo apt install wine"),
        (LinuxDistribution("fedora"), "dnf", "sudo dnf install wine"),
        (LinuxDistribution("arch"), "pacman", "sudo pacman -S wine"),
        (LinuxDistribution("opensuse-tumbleweed"), "zypper", "sudo zypper install wine"),
        (LinuxDistribution("alpine"), "apk", "sudo apk add wine"),
        (LinuxDistribution("void"), "xbps-install", "sudo xbps-install -S wine"),
    ],
)
def test_install_hints_follow_distribution_family(distribution, manager, expected, monkeypatch):
    monkeypatch.setattr(
        "runexe.platform_support.shutil.which",
        lambda name: f"/usr/bin/{name}" if name == manager else None,
    )

    assert install_hint("wine", distribution) == expected


def test_vulkan_hint_is_distribution_specific(monkeypatch):
    monkeypatch.setattr(
        "runexe.platform_support.shutil.which",
        lambda name: "/usr/bin/apt" if name == "apt" else None,
    )

    assert install_hint("vulkan", LinuxDistribution("kali")) == "sudo apt install vulkan-tools"


def test_vulkan_install_command_uses_safe_argv_and_pkexec(monkeypatch):
    paths = {"apt": "/usr/bin/apt", "pkexec": "/usr/bin/pkexec"}
    monkeypatch.setattr("runexe.platform_support.shutil.which", paths.get)
    monkeypatch.setattr("runexe.platform_support._privilege_prefix", lambda: ("/usr/bin/pkexec",))

    command = package_install_command("vulkan", LinuxDistribution("ubuntu"))

    assert command == ["/usr/bin/pkexec", "/usr/bin/apt", "install", "-y", "vulkan-tools"]


def test_install_system_component_executes_without_shell(monkeypatch):
    calls = []
    paths = {"pacman": "/usr/bin/pacman", "sudo": "/usr/bin/sudo"}
    monkeypatch.setattr("runexe.platform_support.shutil.which", paths.get)
    monkeypatch.setattr("runexe.platform_support._privilege_prefix", lambda: ("/usr/bin/sudo",))

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return object()

    monkeypatch.setattr("runexe.platform_support.subprocess.run", run)

    progress = []
    install_system_component(
        "vulkan",
        LinuxDistribution("arch"),
        progress=lambda label, value: progress.append((label, value)),
    )

    assert calls[0][0] == [
        "/usr/bin/sudo",
        "/usr/bin/pacman",
        "-S",
        "--noconfirm",
        "--needed",
        "vulkan-tools",
    ]
    assert calls[0][1]["check"] is True
    assert "shell" not in calls[0][1]
    assert progress[0][1] == 10
    assert progress[1][1] is None
    assert progress[-1][1] == 100


def test_automatic_install_is_explicitly_unsupported_on_nixos():
    distribution = LinuxDistribution("nixos", pretty_name="NixOS")

    with pytest.raises(SystemInstallError, match="not supported on NixOS"):
        package_install_command("vulkan", distribution)


def test_automatic_install_is_explicitly_unsupported_on_unknown_distribution(monkeypatch):
    monkeypatch.setattr("runexe.platform_support.shutil.which", lambda _name: None)
    distribution = LinuxDistribution("unknown", pretty_name="Mystery Linux")

    with pytest.raises(SystemInstallError, match="not supported on Mystery Linux"):
        package_install_command("vulkan", distribution)


def test_wine64_is_a_valid_loader_fallback(monkeypatch):
    monkeypatch.delenv("RUNEXE_WINE_PATH", raising=False)
    monkeypatch.setattr(
        "runexe.platform_support.shutil.which",
        lambda name: "/usr/bin/wine64" if name == "wine64" else None,
    )

    assert find_executable("wine") == "/usr/bin/wine64"


def test_custom_wine_path_supports_nonstandard_and_immutable_distros(monkeypatch):
    configured = Path("/nix/store/example-wine/bin/wine")
    monkeypatch.setenv("RUNEXE_WINE_PATH", str(configured))
    monkeypatch.setattr(
        "runexe.platform_support.shutil.which",
        lambda name: str(configured) if name == str(configured) else None,
    )

    assert find_executable("wine") == str(configured)


def test_custom_umu_path_uses_stable_environment_variable(monkeypatch):
    configured = Path("/opt/umu/bin/umu-run")
    monkeypatch.setenv("RUNEXE_UMU_PATH", str(configured))
    monkeypatch.setattr(
        "runexe.platform_support.shutil.which",
        lambda name: str(configured) if name == str(configured) else None,
    )

    assert find_executable("umu-run") == str(configured)


def test_qt_platform_prefers_wayland_with_x11_fallback():
    environment = {"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0"}

    selected = choose_qt_platform(environment=environment, system="Linux")

    assert selected == "wayland;xcb"


def test_qt_platform_preserves_explicit_qpa_override():
    environment = {"QT_QPA_PLATFORM": "xcb", "WAYLAND_DISPLAY": "wayland-0"}

    selected = choose_qt_platform(environment=environment, system="Linux")

    assert selected == "xcb"


def test_qt_platform_reports_headless_session():
    assert choose_qt_platform(environment={}, system="Linux") is None


def test_qt_platform_accepts_explicit_offscreen_in_headless_session():
    assert choose_qt_platform("offscreen", environment={}, system="Linux") == "offscreen"


def test_qt_platform_rejects_unknown_backend():
    with pytest.raises(ValueError, match="Unknown Qt platform"):
        choose_qt_platform("mir", environment=os.environ.copy(), system="Linux")
