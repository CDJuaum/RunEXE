import json
import subprocess
from unittest.mock import patch

from runexe.models import CompatibilityReport, ExecutableInfo
from runexe.proton import ProtonInstallation
from runexe.runner import (
    PreparedEnvironment,
    build_launch_spec,
    launch,
    open_runtime_configuration,
    prefix_path_for,
    prepare_environment,
    set_windows_version,
)


def report(**changes):
    values = dict(
        application_type="Native Windows",
        architecture="x86_64",
        category="application",
        backend="wine",
        recommended_runtime="Wine",
        wine_arch="win64",
    )
    values.update(changes)
    return CompatibilityReport(**values)


def test_prefix_name_is_sanitized_and_stable(tmp_path):
    executable = ExecutableInfo(tmp_path / "Odd Name! (x64).exe", True)

    first = prefix_path_for(executable)
    second = prefix_path_for(executable)

    assert first == second
    assert first.name.startswith("odd_name_x64-")


@patch("runexe.runner.subprocess.run")
@patch("runexe.runner.ensure_prefix")
@patch("runexe.runner._require_binary", return_value="/usr/bin/wine")
def test_launch_uses_executable_directory_and_forwards_arguments(require, ensure, run, tmp_path):
    path = tmp_path / "app.exe"
    path.touch()
    run.return_value = subprocess.CompletedProcess([], 0, "output", "")

    result = launch(ExecutableInfo(path, True), report(), extra_args=["--portable", "two words"])

    assert result.stdout == "output"
    assert run.call_args.kwargs["cwd"] == tmp_path
    assert run.call_args.args[0][-2:] == ["--portable", "two words"]


@patch("runexe.runner.run_with_progress")
@patch("runexe.runner._wine_tool_command", return_value=["winecfg"])
def test_winver_accepts_friendly_and_native_forms(tool, run_progress, tmp_path):
    run_progress.return_value = subprocess.CompletedProcess([], 0)

    set_windows_version(tmp_path, "win64", "win10")

    assert run_progress.call_args.args[0] == ["winecfg", "-v", "win10"]


@patch("runexe.runner.subprocess.run")
@patch("runexe.runner.ensure_proton_prefix")
@patch("runexe.runner.select_proton")
def test_launches_with_selected_proton(select, ensure, run, tmp_path):
    proton_dir = tmp_path / "Proton Experimental"
    proton_dir.mkdir()
    script = proton_dir / "proton"
    script.touch()
    installation = ProtonInstallation(
        "Proton Experimental", script, "experimental", tmp_path / "Steam"
    )
    select.return_value = installation
    run.return_value = subprocess.CompletedProcess([], 0, "played", "")
    executable_path = tmp_path / "game" / "game.exe"
    executable_path.parent.mkdir()
    executable_path.touch()
    compatibility = report(
        category="game", backend="proton", recommended_runtime="Proton Experimental"
    )

    result = launch(
        ExecutableInfo(executable_path, True),
        compatibility,
        prefix=tmp_path / "compatdata",
        install_dependencies=False,
        proton="Experimental",
    )

    assert result.stdout == "played"
    assert run.call_args.args[0][:2] == [str(script), "run"]
    assert run.call_args.kwargs["env"]["STEAM_COMPAT_DATA_PATH"] == str(
        (tmp_path / "compatdata").resolve()
    )


@patch("runexe.runner.subprocess.run")
@patch("runexe.runner.ensure_proton_prefix")
@patch("runexe.runner.select_proton")
def test_launch_applies_selected_proton_tuning(select, ensure, run, tmp_path):
    proton_dir = tmp_path / "Proton"
    proton_dir.mkdir()
    script = proton_dir / "proton"
    script.touch()
    select.return_value = ProtonInstallation("Proton", script, "11", tmp_path / "Steam")
    run.return_value = subprocess.CompletedProcess([], 0, "", "")
    executable = tmp_path / "game.exe"
    executable.touch()

    launch(
        ExecutableInfo(executable, True),
        report(backend="proton", recommended_runtime="Proton"),
        prefix=tmp_path / "compat",
        install_dependencies=False,
        proton_tuning="no-fsync",
    )

    assert run.call_args.kwargs["env"]["PROTON_NO_FSYNC"] == "1"


@patch("runexe.runner.ensure_prefix")
@patch("runexe.runner._require_binary", return_value="/usr/bin/wine")
def test_prepares_wine_without_launching(require, ensure, tmp_path):
    path = tmp_path / "app.exe"
    path.touch()
    prefix = tmp_path / "prefix"

    prepared = prepare_environment(
        ExecutableInfo(path, True),
        report(),
        prefix=prefix,
        install_dependencies=False,
    )

    assert prepared.backend == "wine"
    assert prepared.path == prefix.resolve()
    assert prepared.launcher == "/usr/bin/wine"
    ensure.assert_called_once_with(prefix.resolve(), "win64", verbose=False)


@patch("runexe.runner._require_binary", return_value="/usr/bin/wine")
def test_prepared_environment_writes_inventory_metadata(require, tmp_path, monkeypatch):
    path = tmp_path / "Editor.exe"
    path.touch()
    prefix = tmp_path / "prefix"

    def fake_ensure(target, _architecture, verbose=False):
        (target / "drive_c").mkdir(parents=True)

    monkeypatch.setattr("runexe.runner.ensure_prefix", fake_ensure)
    monkeypatch.setattr("runexe.runner.set_windows_version", lambda *_args, **_kwargs: None)

    prepare_environment(
        ExecutableInfo(path, True),
        report(),
        prefix=prefix,
        install_dependencies=False,
        winver="11",
    )

    metadata = json.loads((prefix / ".runexe-environment.json").read_text(encoding="utf-8"))
    assert metadata["application"] == "Editor"
    assert metadata["backend"] == "wine"
    assert metadata["windows_version"] == "11"


def test_builds_launch_spec_for_gui_process(tmp_path):
    path = tmp_path / "app.exe"
    path.touch()
    prepared = PreparedEnvironment("wine", tmp_path / "prefix", "Wine", "wine", "win64")

    spec = build_launch_spec(ExecutableInfo(path, True), prepared, ["--portable"])

    assert spec.command == ("wine", str(path.resolve()), "--portable")
    assert spec.cwd == tmp_path
    assert spec.env["WINEPREFIX"] == str(tmp_path / "prefix")


@patch("runexe.runner.subprocess.Popen")
@patch("runexe.runner._wine_tool_command", return_value=["winecfg"])
@patch("runexe.runner.prepare_environment")
def test_opens_configuration_for_prepared_wine(prepare, tool, popen, tmp_path):
    path = tmp_path / "app.exe"
    path.touch()
    prepared = PreparedEnvironment("wine", tmp_path / "prefix", "Wine", "wine", "win64")
    prepare.return_value = prepared

    result = open_runtime_configuration(ExecutableInfo(path, True), report())

    assert result == prepared
    assert popen.call_args.args[0] == ["winecfg"]
    assert popen.call_args.kwargs["cwd"] == tmp_path
