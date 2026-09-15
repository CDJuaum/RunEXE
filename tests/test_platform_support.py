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
    managed_system_component_packages,
    package_install_command,
    package_remove_command,
    system_component_managed,
    uninstall_system_component,
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
    monkeypatch.setattr("runexe.platform_support._query_package_installed", lambda *_args: None)

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


def test_remove_system_component_uses_package_manager_without_shell(monkeypatch):
    calls = []
    paths = {"pacman": "/usr/bin/pacman", "sudo": "/usr/bin/sudo"}
    monkeypatch.setattr("runexe.platform_support.shutil.which", paths.get)
    monkeypatch.setattr("runexe.platform_support._privilege_prefix", lambda: ("/usr/bin/sudo",))

    assert package_remove_command("wine", LinuxDistribution("arch")) == [
        "/usr/bin/sudo",
        "/usr/bin/pacman",
        "-R",
        "--noconfirm",
        "wine",
    ]

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return object()

    monkeypatch.setattr("runexe.platform_support.subprocess.run", run)
    monkeypatch.setattr(
        "runexe.platform_support.managed_system_component_packages",
        lambda *_args: ("vulkan-tools",),
    )
    uninstall_system_component("vulkan", LinuxDistribution("arch"))

    assert calls[0][0][-1] == "vulkan-tools"
    assert calls[0][1]["check"] is True
    assert "shell" not in calls[0][1]


def test_preexisting_system_package_is_not_claimed_or_removed(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    paths = {"pacman": "/usr/bin/pacman", "sudo": "/usr/bin/sudo"}
    monkeypatch.setattr("runexe.platform_support.shutil.which", paths.get)
    monkeypatch.setattr("runexe.platform_support._privilege_prefix", lambda: ("/usr/bin/sudo",))
    monkeypatch.setattr("runexe.platform_support._query_package_installed", lambda *_args: True)
    monkeypatch.setattr(
        "runexe.platform_support.subprocess.run", lambda *_args, **_kwargs: object()
    )

    distribution = LinuxDistribution("arch")
    install_system_component("wine", distribution)

    assert not system_component_managed("wine", distribution)
    with pytest.raises(SystemInstallError, match="installed itself"):
        uninstall_system_component("wine", distribution)


def test_new_system_package_receipt_allows_exact_removal(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    paths = {"pacman": "/usr/bin/pacman", "sudo": "/usr/bin/sudo"}
    monkeypatch.setattr("runexe.platform_support.shutil.which", paths.get)
    monkeypatch.setattr("runexe.platform_support._privilege_prefix", lambda: ("/usr/bin/sudo",))
    installed = {"wine": False}

    def package_state(_manager, package):
        return installed[package]

    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        if "-S" in argv:
            installed["wine"] = True
        elif "-R" in argv:
            installed["wine"] = False
        return object()

    monkeypatch.setattr("runexe.platform_support._query_package_installed", package_state)
    monkeypatch.setattr("runexe.platform_support.subprocess.run", run)

    distribution = LinuxDistribution("arch")
    install_system_component("wine", distribution)

    assert managed_system_component_packages("wine", distribution) == ("wine",)
    assert system_component_managed("wine", distribution)

    uninstall_system_component("wine", distribution)

    assert calls[-1][0][-3:] == ["-R", "--noconfirm", "wine"]
    assert not system_component_managed("wine", distribution)


def test_package_receipt_refuses_manager_mismatch_or_corrupt_state(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    state_file = tmp_path / "state" / "runexe" / "system-packages.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        '{"schema": 1, "components": {"wine": {"manager": "apt", "packages": ["wine"]}}}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "runexe.platform_support.shutil.which",
        lambda name: "/usr/bin/pacman" if name == "pacman" else None,
    )
    monkeypatch.setattr("runexe.platform_support._query_package_installed", lambda *_args: True)

    assert managed_system_component_packages("wine", LinuxDistribution("arch")) == ()

    state_file.write_text("not-json", encoding="utf-8")
    assert managed_system_component_packages("wine", LinuxDistribution("arch")) == ()


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
