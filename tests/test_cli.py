from datetime import datetime, timezone

from typer.testing import CliRunner

from runexe import __version__
from runexe.cli import app
from runexe.desktop import DesktopPaths
from runexe.environments import EnvironmentInfo
from runexe.library import ApplicationLibrary, LaunchPreset
from runexe.models import ApplicationProfile, CompatibilityReport, ExecutableInfo, HostInfo
from runexe.runner import LaunchResult

from .helpers import make_pe

runner = CliRunner()


def test_version_comes_from_package_metadata():
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == f"RunEXE {__version__}"


def test_desktop_install_command_reports_created_entry(tmp_path, monkeypatch):
    paths = DesktopPaths(tmp_path / "runexe.desktop", tmp_path / "runexe.png")
    seen = {}

    def install(executable):
        seen["executable"] = executable
        return paths

    monkeypatch.setattr("runexe.cli.install_desktop_entry", install)
    result = runner.invoke(
        app,
        ["desktop", "install", "--executable", str(tmp_path / "runexe-gui")],
    )

    assert result.exit_code == 0
    assert seen["executable"] == tmp_path / "runexe-gui"
    assert paths.desktop_file.name in result.output


def test_desktop_remove_command_is_idempotent(tmp_path, monkeypatch):
    paths = DesktopPaths(tmp_path / "runexe.desktop", tmp_path / "runexe.png")
    monkeypatch.setattr("runexe.cli.remove_desktop_entry", lambda: (paths, False))

    result = runner.invoke(app, ["desktop", "remove"])

    assert result.exit_code == 0
    assert "No RunEXE-managed desktop entry" in result.output


def test_json_analysis_is_machine_readable(tmp_path):
    path = make_pe(tmp_path / "sample.exe")

    result = runner.invoke(app, ["analyze", str(path), "--json", "--no-host"])

    assert result.exit_code == 0
    assert '"architecture": "x86"' in result.stdout
    assert '"compatibility"' in result.stdout


def test_run_forwards_every_argument_after_separator(tmp_path, monkeypatch):
    path = tmp_path / "app.exe"
    path.touch()
    executable = ExecutableInfo(path, True, architecture="x86_64")
    compatibility = CompatibilityReport(
        application_type="Native Windows",
        architecture="x86_64",
        category="application",
        backend="wine",
        recommended_runtime="Wine",
        wine_arch="win64",
    )
    host = HostInfo("x86_64", True, "wine-10", True, True, True)
    seen = {}

    monkeypatch.setattr("runexe.cli.analyze_executable", lambda _: executable)
    monkeypatch.setattr("runexe.cli.detect_host", lambda: host)
    monkeypatch.setattr("runexe.cli.analyze_compatibility", lambda *_: compatibility)
    monkeypatch.setattr("runexe.cli._remember_launch", lambda *_: None)

    def fake_launch(*args, **kwargs):
        seen.update(kwargs)
        return LaunchResult(0, "", "")

    monkeypatch.setattr("runexe.cli.launch", fake_launch)

    result = runner.invoke(
        app,
        ["run", str(path), "--no-deps", "--", "--portable", "two words"],
    )

    assert result.exit_code == 0
    assert seen["extra_args"] == ["--portable", "two words"]


def test_run_rejects_conflicting_runtime_options(tmp_path):
    path = tmp_path / "app.exe"
    path.touch()

    result = runner.invoke(
        app,
        ["run", str(path), "--backend", "wine", "--proton", "Proton Experimental"],
    )

    assert result.exit_code == 1
    assert "cannot be combined" in result.output


def test_gui_command_keeps_desktop_optional(tmp_path, monkeypatch):
    path = tmp_path / "app.exe"
    path.touch()
    seen = {}

    def fake_launch_gui(initial_file, qt_platform):
        seen["file"] = initial_file
        seen["platform"] = qt_platform
        return 0

    monkeypatch.setattr("runexe.gui.launch_gui", fake_launch_gui)

    result = runner.invoke(app, ["gui", str(path)])

    assert result.exit_code == 0
    assert seen["file"] == path
    assert seen["platform"] == "auto"


def test_run_uses_profile_windows_version_when_not_overridden(tmp_path, monkeypatch):
    path = tmp_path / "PaintDotNet.exe"
    path.touch()
    executable = ExecutableInfo(path, True, architecture="x86_64")
    compatibility = CompatibilityReport(
        application_type=".NET",
        architecture="x86_64",
        category="application",
        backend="wine",
        recommended_runtime="Wine",
        wine_arch="win64",
        profile=ApplicationProfile("paint-dot-net", "Paint.NET", recommended_windows_version="11"),
    )
    host = HostInfo("x86_64", True, "wine-11", True, True, True)
    seen = {}

    monkeypatch.setattr("runexe.cli.analyze_executable", lambda _: executable)
    monkeypatch.setattr("runexe.cli.detect_host", lambda: host)
    monkeypatch.setattr("runexe.cli.analyze_compatibility", lambda *_: compatibility)
    monkeypatch.setattr("runexe.cli._remember_launch", lambda *_: None)

    def fake_launch(*args, **kwargs):
        seen.update(kwargs)
        return LaunchResult(0, "", "")

    monkeypatch.setattr("runexe.cli.launch", fake_launch)

    result = runner.invoke(app, ["run", str(path), "--no-deps"])

    assert result.exit_code == 0
    assert seen["winver"] == "11"


def test_recent_command_emits_saved_presets_as_json(tmp_path, monkeypatch):
    source = tmp_path / "app.exe"
    source.touch()
    library = ApplicationLibrary(tmp_path / "applications.json")
    library.remember_analysis(
        source,
        display_name="Example",
        architecture="x86_64",
        file_format="PE32+",
        preset=LaunchPreset(backend="wine", windows_version="11"),
    )
    monkeypatch.setattr("runexe.cli.ApplicationLibrary", lambda: library)

    result = runner.invoke(app, ["recent", "--json"])

    assert result.exit_code == 0
    assert '"display_name": "Example"' in result.stdout
    assert '"windows_version": "11"' in result.stdout


def test_environment_command_and_removal_confirmation(tmp_path, monkeypatch):
    path = tmp_path / "prefixes" / "example-123"
    path.mkdir(parents=True)
    environment = EnvironmentInfo(
        identifier="wine:example-123",
        backend="wine",
        path=path,
        application="Example",
        source=str(tmp_path / "app.exe"),
        architecture="x86_64",
        runtime="Wine 11",
        runtime_path=None,
        windows_version="11",
        dxvk_available=False,
        dxvk_source="Wine prefix",
        dxvk_components=(),
        size_bytes=2048,
        modified_at=datetime.now(timezone.utc).isoformat(),
        ready=True,
    )
    monkeypatch.setattr("runexe.cli.discover_environments", lambda: [environment])

    listing = runner.invoke(app, ["environments", "--json"])
    removal = runner.invoke(app, ["remove-environment", environment.identifier])

    assert listing.exit_code == 0
    assert '"identifier": "wine:example-123"' in listing.stdout
    assert removal.exit_code == 2
    assert "permanently removes" in removal.stdout
    assert "--yes" in removal.stdout


def test_rerun_restores_saved_cli_preset(tmp_path, monkeypatch):
    source = tmp_path / "app.exe"
    source.touch()
    library = ApplicationLibrary(tmp_path / "applications.json")
    record = library.remember_analysis(
        source,
        display_name="Example",
        architecture="x86_64",
        file_format="PE32+",
        preset=LaunchPreset(
            backend="wine",
            windows_version="11",
            dependencies="skip",
            arguments="--portable 'two words'",
        ),
    )
    seen = {}

    def fake_run(
        ctx,
        file,
        backend,
        proton,
        tuning,
        prefix,
        dependencies,
        winver,
        timeout,
        verbose,
    ):
        seen.update(
            file=file,
            backend=backend,
            tuning=tuning,
            dependencies=dependencies,
            winver=winver,
            arguments=list(ctx.args),
        )

    monkeypatch.setattr("runexe.cli.ApplicationLibrary", lambda: library)
    monkeypatch.setattr("runexe.cli.run", fake_run)

    result = runner.invoke(app, ["rerun", record.identifier])

    assert result.exit_code == 0
    assert seen["file"] == source.resolve()
    assert seen["backend"].value == "wine"
    assert seen["tuning"].value == "default"
    assert seen["dependencies"] is False
    assert seen["winver"] == "11"
    assert seen["arguments"] == ["--portable", "two words"]
