"""Command-line interface for RunEXE."""

from __future__ import annotations

import json
import shlex
from dataclasses import asdict, replace
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer

from runexe import __version__
from runexe.analyzer import analyze_executable
from runexe.backups import (
    BackupError,
    create_environment_backup,
    discover_backups,
    remove_backup,
    restore_backup,
)
from runexe.compatibility import analyze_compatibility
from runexe.configuration import (
    CONFIGURATION_TOOLS,
    ConfigurationError,
    open_environment_configuration,
)
from runexe.desktop import DesktopIntegrationError, install_desktop_entry, remove_desktop_entry
from runexe.diagnostics import collect_diagnostics
from runexe.environments import discover_environments, format_size, remove_managed_environment
from runexe.host import detect_host
from runexe.library import ApplicationLibrary, LaunchPreset
from runexe.platform_support import install_hint
from runexe.profiles import detect_runtime_issue
from runexe.proton import ProtonError, discover_proton_installations, select_proton
from runexe.resources import extract_requested_execution_level
from runexe.runner import LaunchResult, RunnerError, launch
from runexe.ui import (
    console,
    error_console,
    print_banner,
    print_error,
    print_hint,
    print_section,
    print_success,
    print_summary,
    print_table,
    print_warning,
    status_text,
)


class BackendChoice(str, Enum):
    auto = "auto"
    wine = "wine"
    proton = "proton"


class ProtonTuningChoice(str, Enum):
    default = "default"
    diagnostics = "diagnostics"
    wined3d = "wined3d"
    dxvk_hud = "dxvk-hud"
    no_fsync = "no-fsync"
    no_ntsync = "no-ntsync"


app = typer.Typer(
    name="runexe",
    help="Inspect Windows software and launch it through Wine or Proton.",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
    rich_markup_mode="rich",
)
desktop_app = typer.Typer(
    help="Install or remove the per-user Linux desktop-menu entry.",
    no_args_is_help=True,
)
app.add_typer(desktop_app, name="desktop")


def _analysis_as_dict(result, compatibility, host) -> dict:
    data = asdict(result)
    data["path"] = str(result.path)
    data["compatibility"] = asdict(compatibility) if compatibility is not None else None
    data["host"] = asdict(host) if host is not None else None
    return data


def _fail(message: str, code: int = 1) -> None:
    print_error(message)
    raise typer.Exit(code=code)


def _display_name(executable) -> str:
    if executable.package is not None:
        return executable.package.display_name or executable.package.identity_name
    if executable.version_info is not None:
        return executable.version_info.strings.get("ProductName") or executable.path.stem
    return executable.path.stem


def _remember_launch(executable, preset: LaunchPreset) -> ApplicationLibrary | None:
    library = ApplicationLibrary()
    try:
        library.remember_analysis(
            executable.path,
            display_name=_display_name(executable),
            architecture=executable.architecture,
            file_format=executable.format,
            preset=preset,
        )
        library.record_launch(executable.path, preset)
    except OSError as error:
        print_warning(f"Could not update recent applications: {error}")
        return None
    return library


def _runtime_host_with_selector(host, selector: str | None):
    if selector is None:
        return host, None
    selected = select_proton(selector)
    return (
        replace(host, proton_installed=True, proton_versions=[selected.name]),
        selected,
    )


@app.command()
def analyze(
    file: Annotated[
        Path, typer.Argument(help="PE executable, AppX/MSIX package, or package directory.")
    ],
    imports: Annotated[
        bool, typer.Option("--imports", "-i", help="List functions under every imported DLL.")
    ] = False,
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit only a machine-readable JSON report.")
    ] = False,
    check_host: Annotated[
        bool, typer.Option("--host/--no-host", help="Include local Wine and Proton availability.")
    ] = True,
    backend: Annotated[
        BackendChoice,
        typer.Option("--backend", help="Evaluate compatibility for a specific runtime."),
    ] = BackendChoice.auto,
) -> None:
    """Inspect software without executing it or modifying a prefix."""

    try:
        result = analyze_executable(file)
        if not result.valid:
            if json_output:
                typer.echo(json.dumps(_analysis_as_dict(result, None, None), indent=2, default=str))
                raise typer.Exit(code=1)
            _fail(result.reason or "Invalid Windows executable")

        host = detect_host() if check_host else None
        compatibility = analyze_compatibility(result, host, backend.value)
        if json_output:
            typer.echo(
                json.dumps(_analysis_as_dict(result, compatibility, host), indent=2, default=str)
            )
            return

        print_banner("Static analysis | no compatibility environment will be changed")
        summary_rows: list[tuple[str, object]] = [
            ("File", result.path),
            ("Format", result.format or "unknown"),
            ("Architecture", result.architecture or "unknown"),
            ("Subsystem", result.subsystem or "unknown"),
        ]
        if result.package:
            summary_rows.extend(
                [
                    ("Package", result.package.display_name or result.package.identity_name),
                    ("Package version", result.package.version or "unknown"),
                    ("Package app", result.package.application_id or "default"),
                ]
            )
        if result.version_info:
            summary_rows.extend(
                [
                    ("Product", result.version_info.strings.get("ProductName", "unknown")),
                    ("Publisher", result.version_info.strings.get("CompanyName", "unknown")),
                    (
                        "Version",
                        result.version_info.product_version
                        or result.version_info.file_version
                        or "unknown",
                    ),
                ]
            )
        if result.manifest:
            level = extract_requested_execution_level(result.manifest)
            summary_rows.append(("Manifest", level or "present"))
        print_summary("Executable", summary_rows)

        if result.sections:
            print_table(
                "PE sections",
                (("Name", "left"), ("RVA", "right"), ("Virtual", "right"), ("Raw", "right")),
                (
                    (
                        section.name,
                        f"0x{section.virtual_address:08X}",
                        f"0x{section.virtual_size:X}",
                        f"0x{section.raw_size:X} @ 0x{section.raw_offset:X}",
                    )
                    for section in result.sections
                ),
            )

        if result.imports:
            if imports:
                print_section("Imports")
                for imported in result.imports:
                    console.print(f"[label]{imported.name}[/label]")
                    console.print(
                        "  " + ", ".join(imported.functions)
                        if imported.functions
                        else "  [muted]none[/muted]"
                    )
            else:
                print_table(
                    "Imported libraries",
                    (("DLL", "left"), ("Functions", "right")),
                    ((item.name, len(item.functions)) for item in result.imports),
                )
                print_hint("Add --imports to show individual function names.")

        print_summary(
            "Compatibility",
            [
                ("Application", compatibility.application_type),
                (
                    "Category",
                    f"{compatibility.category} "
                    f"({compatibility.classification_confidence} confidence)",
                ),
                ("Selected runtime", compatibility.recommended_runtime),
                ("Backend", compatibility.backend),
                ("Prefix architecture", compatibility.wine_arch or "N/A"),
                ("Status", status_text(not compatibility.blocking_issues)),
            ],
        )
        if compatibility.blocking_issues:
            print_section("Blocking issues")
            for issue in compatibility.blocking_issues:
                print_error(issue)
        for warning in compatibility.warnings:
            print_warning(warning)

        if compatibility.dependencies:
            print_table(
                "Detected dependencies",
                (
                    ("Component", "left"),
                    ("Category", "left"),
                    ("Confidence", "left"),
                    ("Verb", "left"),
                ),
                (
                    (
                        item.name,
                        item.category,
                        item.confidence,
                        item.winetricks_verb or "built in / manual",
                    )
                    for item in compatibility.dependencies
                ),
            )
        if compatibility.notes:
            print_section("Notes")
            for note in compatibility.notes:
                console.print(f"[muted]-[/muted] {note}")

    except typer.Exit:
        raise
    except (OSError, ValueError, ProtonError) as error:
        _fail(str(error))


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def run(
    ctx: typer.Context,
    file: Annotated[
        Path, typer.Argument(help="PE executable, AppX/MSIX package, or package directory.")
    ],
    backend: Annotated[
        BackendChoice,
        typer.Option("--backend", help="Runtime selection: auto, wine, or proton."),
    ] = BackendChoice.auto,
    proton: Annotated[
        str | None,
        typer.Option("--proton", help="Proton build name, installation directory, or script path."),
    ] = None,
    tuning: Annotated[
        ProtonTuningChoice,
        typer.Option(
            "--tuning",
            help="Temporary Proton troubleshooting preset; does not modify the prefix.",
        ),
    ] = ProtonTuningChoice.default,
    prefix: Annotated[
        Path | None,
        typer.Option(
            "--prefix",
            help="Custom Wine prefix, or Proton compat-data directory when using Proton.",
        ),
    ] = None,
    dependencies: Annotated[
        bool | None,
        typer.Option(
            "--deps/--no-deps",
            help="Force dependency provisioning on or off (auto: Wine on, Proton off).",
        ),
    ] = None,
    winver: Annotated[
        str | None,
        typer.Option("--winver", help="Reported Windows version: 7, 8, 8.1, 10, or 11."),
    ] = None,
    timeout: Annotated[
        int | None, typer.Option("--timeout", min=1, help="Maximum runtime in seconds.")
    ] = None,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Show runtime commands.")
    ] = False,
) -> None:
    """Analyze, prepare, and launch software through Wine or Proton.

    Put application arguments after ``--``: ``runexe run app.exe -- --portable``.
    """

    try:
        if proton is not None and backend is BackendChoice.wine:
            raise RunnerError("--proton cannot be combined with --backend wine.")

        result = analyze_executable(file)
        if not result.valid:
            raise RunnerError(result.reason or "Invalid Windows executable")

        host = detect_host()
        host, selected_proton = _runtime_host_with_selector(host, proton)
        preference = BackendChoice.proton if proton and backend is BackendChoice.auto else backend
        compatibility = analyze_compatibility(result, host, preference.value)
        install_dependencies = (
            dependencies if dependencies is not None else compatibility.backend == "wine"
        )
        effective_winver = winver or (
            compatibility.profile.recommended_windows_version
            if compatibility.profile is not None
            else None
        )
        preset = LaunchPreset(
            backend=preference.value,
            proton=proton,
            proton_tuning=tuning.value,
            windows_version=effective_winver,
            dependencies=(
                "auto" if dependencies is None else "install" if dependencies else "skip"
            ),
            prefix=str(prefix.expanduser()) if prefix is not None else None,
            arguments=shlex.join(list(ctx.args)),
        )

        print_banner(f"Launch | {result.path.name}")
        plan_rows: list[tuple[str, object]] = [
            ("Backend", compatibility.backend.upper()),
            (
                "Runtime",
                selected_proton.name if selected_proton else compatibility.recommended_runtime,
            ),
            ("Architecture", compatibility.architecture),
            (
                "Environment",
                prefix
                or (
                    "isolated per-app compat data"
                    if compatibility.backend == "proton"
                    else "isolated per-app prefix"
                ),
            ),
            ("Dependencies", ", ".join(compatibility.required_verbs) or "none detected"),
            ("Provisioning", "enabled" if install_dependencies else "skipped"),
            ("Windows version", effective_winver or "runtime default"),
        ]
        print_summary("Launch plan", plan_rows)
        for warning in compatibility.warnings:
            print_warning(warning)
        if compatibility.blocking_issues:
            for issue in compatibility.blocking_issues:
                print_error(issue)
            raise typer.Exit(code=1)
        if (
            dependencies is None
            and compatibility.backend == "proton"
            and compatibility.required_verbs
        ):
            print_hint(
                "Proton dependency changes are skipped by default to protect its prefix; "
                "use --deps to opt in."
            )

        application_library = _remember_launch(result, preset)
        launch_result: LaunchResult = launch(
            result,
            compatibility,
            extra_args=list(ctx.args),
            timeout=timeout,
            verbose=verbose,
            winver=effective_winver,
            prefix=prefix,
            install_dependencies=install_dependencies,
            proton=selected_proton.script if selected_proton else proton,
            proton_tuning=tuning.value,
        )
        if application_library is not None and launch_result.exit_code is not None:
            try:
                application_library.record_exit(result.path, launch_result.exit_code)
            except OSError as error:
                print_warning(f"Could not save the launch result: {error}")

        if launch_result.stdout:
            console.print(
                launch_result.stdout,
                end="" if launch_result.stdout.endswith("\n") else "\n",
                markup=False,
            )
        if launch_result.stderr:
            error_console.print(
                launch_result.stderr,
                end="" if launch_result.stderr.endswith("\n") else "\n",
                markup=False,
            )
        if launch_result.timed_out:
            _fail(f"Process exceeded the {timeout}-second timeout.", 124)
        if launch_result.exit_code != 0:
            diagnostic = detect_runtime_issue(
                f"{launch_result.stdout}\n{launch_result.stderr}",
                launch_result.exit_code,
                compatibility.profile,
            )
            if diagnostic is not None:
                print_warning(diagnostic.message)
            code = launch_result.exit_code or 1
            _fail(
                f"Process exited with code {launch_result.exit_code}.",
                code if 1 <= code <= 255 else 1,
            )
        print_success("Process exited normally.")

    except typer.Exit:
        raise
    except (OSError, ValueError, ProtonError, RunnerError) as error:
        _fail(str(error))


@app.command()
def gui(
    file: Annotated[
        Path | None,
        typer.Argument(help="Optional EXE, AppX, or MSIX to analyze when the window opens."),
    ] = None,
    qt_platform: Annotated[
        str,
        typer.Option(
            "--platform",
            help="Qt backend: auto, xcb, wayland, offscreen, or minimal.",
        ),
    ] = "auto",
) -> None:
    """Open the scalable RunEXE desktop interface."""

    from runexe.gui import GuiUnavailableError, launch_gui

    try:
        exit_code = launch_gui(file, qt_platform)
    except GuiUnavailableError as error:
        _fail(str(error))
    raise typer.Exit(code=exit_code)


@app.command()
def doctor(
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit only a machine-readable diagnostic report.")
    ] = False,
    check_gui: Annotated[
        bool,
        typer.Option("--gui/--no-gui", help="Include Qt, display-server, and plugin checks."),
    ] = True,
) -> None:
    """Check Linux, runtime, GUI, and package-manager readiness without changing the host."""

    report = collect_diagnostics(include_gui=check_gui)
    if json_output:
        typer.echo(json.dumps(report.as_dict(), indent=2))
    else:
        print_banner("Read-only host diagnostics | no packages or prefixes will be changed")
        print_summary(
            "Linux host",
            [
                ("Distribution", report.distribution.pretty_name),
                ("Architecture", report.architecture),
                ("C library", report.libc),
                ("Package manager", report.package_manager or "not detected"),
                ("Launch ready", status_text(report.ready)),
            ],
        )
        labels = {"ok": "OK", "warning": "WARNING", "error": "ERROR"}
        print_table(
            "Capability checks",
            (("Status", "left"), ("Component", "left"), ("Details", "left")),
            (
                (labels.get(check.status, check.status.upper()), check.name, check.detail)
                for check in report.checks
            ),
        )
        for check in report.checks:
            if check.fix:
                print_hint(f"{check.name}: {check.fix}")
    if not report.ready:
        raise typer.Exit(code=1)


@app.command()
def recent(
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit the application library as JSON.")
    ] = False,
    prune_missing: Annotated[
        bool,
        typer.Option("--prune-missing", help="Forget entries whose source file no longer exists."),
    ] = False,
) -> None:
    """List recently analyzed or launched applications and their saved presets."""

    library = ApplicationLibrary()
    if prune_missing:
        try:
            removed = library.prune_missing()
        except OSError as error:
            _fail(f"Could not update the application library: {error}")
        if not json_output:
            print_success(
                f"Removed {removed} missing application entr{'y' if removed == 1 else 'ies'}."
            )
    records = library.records()
    if json_output:
        typer.echo(json.dumps([asdict(record) for record in records], indent=2))
        return
    print_banner("Recent applications | per-app launch choices are stored locally")
    if not records:
        print_hint("Launch an application from the GUI or CLI to add it here.")
        return
    print_table(
        "Application library",
        (
            ("ID", "left"),
            ("Application", "left"),
            ("Backend", "left"),
            ("Launches", "right"),
            ("Last result", "left"),
            ("Path", "left"),
        ),
        (
            (
                record.identifier,
                record.display_name,
                record.preset.backend,
                record.launch_count,
                "not launched"
                if record.last_exit_code is None
                else f"exit {record.last_exit_code}",
                record.path,
            )
            for record in records
        ),
    )
    print_hint("Relaunch a saved preset with: runexe rerun ID")


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def rerun(
    ctx: typer.Context,
    identifier: Annotated[str, typer.Argument(help="Application ID from runexe recent.")],
    timeout: Annotated[
        int | None, typer.Option("--timeout", min=1, help="Maximum runtime in seconds.")
    ] = None,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Show runtime commands.")
    ] = False,
) -> None:
    """Launch a recent application with its saved per-app preset."""

    record = next(
        (item for item in ApplicationLibrary().records() if item.identifier == identifier),
        None,
    )
    if record is None:
        _fail(f"No recent application matches '{identifier}'.")
    source = Path(record.path)
    if not source.exists():
        _fail(f"Saved application source no longer exists: {source}")
    preset = record.preset
    try:
        saved_arguments = shlex.split(preset.arguments)
    except ValueError as error:
        _fail(f"Saved arguments are invalid: {error}")
    if not ctx.args:
        ctx.args = saved_arguments
    dependencies = {
        "auto": None,
        "install": True,
        "skip": False,
    }[preset.dependencies]
    run(
        ctx=ctx,
        file=source,
        backend=BackendChoice(preset.backend),
        proton=preset.proton,
        tuning=ProtonTuningChoice(preset.proton_tuning),
        prefix=Path(preset.prefix) if preset.prefix else None,
        dependencies=dependencies,
        winver=preset.windows_version,
        timeout=timeout,
        verbose=verbose,
    )


@app.command(name="forget-recent")
def forget_recent(
    identifier: Annotated[str, typer.Argument(help="Application ID from runexe recent.")],
) -> None:
    """Forget one recent entry without deleting its source or environment."""

    library = ApplicationLibrary()
    record = next((item for item in library.records() if item.identifier == identifier), None)
    if record is None:
        _fail(f"No recent application matches '{identifier}'.")
    try:
        library.forget(record.path)
    except OSError as error:
        _fail(f"Could not update the application library: {error}")
    print_success(f"Forgot {record.display_name}; no application files were removed.")


@app.command()
def environments(
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit managed environment inventory as JSON.")
    ] = False,
) -> None:
    """List isolated Wine prefixes and Proton compat-data owned by RunEXE."""

    items = discover_environments()
    if json_output:
        typer.echo(json.dumps([item.as_dict() for item in items], indent=2))
        return
    print_banner("Managed environments | only RunEXE-owned locations are listed")
    if not items:
        print_hint("Prepare or launch an application to create an isolated environment.")
        return
    print_table(
        "Isolated environments",
        (
            ("Identifier", "left"),
            ("Application", "left"),
            ("Runtime", "left"),
            ("DXVK", "left"),
            ("Size", "right"),
            ("State", "left"),
            ("Path", "left"),
        ),
        (
            (
                item.identifier,
                item.application,
                item.runtime or item.backend.title(),
                "available"
                if item.dxvk_available
                else "not detected"
                if item.dxvk_available is False
                else "unknown",
                format_size(item.size_bytes),
                "ready" if item.ready else "incomplete",
                item.path,
            )
            for item in items
        ),
    )
    print_hint("Remove one explicitly with: runexe remove-environment IDENTIFIER --yes")


@app.command(name="remove-environment")
def remove_environment(
    identifier: Annotated[
        str, typer.Argument(help="Exact wine:NAME/proton:NAME identifier from runexe environments.")
    ],
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Confirm permanent removal of this managed environment."),
    ] = False,
    backup: Annotated[
        bool,
        typer.Option(
            "--backup/--no-backup",
            help="Create a restorable snapshot before permanent removal.",
        ),
    ] = True,
) -> None:
    """Permanently remove one validated RunEXE-managed environment."""

    matches = [item for item in discover_environments() if item.identifier == identifier]
    if not matches:
        _fail(f"No managed environment matches '{identifier}'.")
    item = matches[0]
    if not yes:
        print_warning(
            f"This permanently removes {item.application}'s {format_size(item.size_bytes)} "
            f"{item.backend} environment at {item.path}."
        )
        if backup:
            print_hint("A restorable backup will be created first (disable with --no-backup).")
        print_hint(f"Repeat with: runexe remove-environment {identifier} --yes")
        raise typer.Exit(code=2)
    try:
        created_backup = create_environment_backup(item) if backup else None
        remove_managed_environment(item.path)
    except (BackupError, OSError, ValueError) as error:
        _fail(str(error))
    if created_backup is not None:
        print_success(f"Backup created: {created_backup.identifier}")
    print_success(f"Removed {identifier}.")


@app.command(name="backup-environment")
def backup_environment(
    identifier: Annotated[str, typer.Argument(help="Environment ID from runexe environments.")],
) -> None:
    """Create a compressed snapshot of one managed environment."""

    item = next(
        (
            environment
            for environment in discover_environments()
            if environment.identifier == identifier
        ),
        None,
    )
    if item is None:
        _fail(f"No managed environment matches '{identifier}'.")
    try:
        backup = create_environment_backup(item)
    except BackupError as error:
        _fail(str(error))
    print_success(f"Created backup {backup.identifier} ({format_size(backup.size_bytes)}).")


@app.command()
def backups(
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit backup inventory as JSON.")
    ] = False,
) -> None:
    """List restorable managed-environment backups."""

    items = discover_backups()
    if json_output:
        typer.echo(json.dumps([item.as_dict() for item in items], indent=2))
        return
    print_banner("Environment backups | stored separately from live prefixes")
    if not items:
        print_hint("Create one with: runexe backup-environment ENVIRONMENT_ID")
        return
    print_table(
        "Restorable backups",
        (
            ("Backup ID", "left"),
            ("Application", "left"),
            ("Backend", "left"),
            ("Size", "right"),
            ("Created", "left"),
        ),
        (
            (
                item.identifier,
                item.application,
                item.backend,
                format_size(item.size_bytes),
                item.created_at,
            )
            for item in items
        ),
    )


@app.command(name="restore-backup")
def restore_environment_backup(
    identifier: Annotated[str, typer.Argument(help="Backup ID from runexe backups.")],
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Confirm restoration into the original managed location."),
    ] = False,
) -> None:
    """Safely restore a backup when its original environment path is absent."""

    backup = next((item for item in discover_backups() if item.identifier == identifier), None)
    if backup is None:
        _fail(f"No backup matches '{identifier}'.")
    if not yes:
        print_warning(f"This restores {backup.application}'s {backup.backend} environment.")
        print_hint(f"Repeat with: runexe restore-backup {identifier} --yes")
        raise typer.Exit(code=2)
    try:
        target = restore_backup(backup)
    except BackupError as error:
        _fail(str(error))
    print_success(f"Restored {identifier} to {target}.")


@app.command(name="remove-backup")
def remove_environment_backup(
    identifier: Annotated[str, typer.Argument(help="Backup ID from runexe backups.")],
    yes: Annotated[bool, typer.Option("--yes", help="Confirm permanent backup removal.")] = False,
) -> None:
    """Permanently remove one backup without touching a live environment."""

    backup = next((item for item in discover_backups() if item.identifier == identifier), None)
    if backup is None:
        _fail(f"No backup matches '{identifier}'.")
    if not yes:
        print_warning(f"This permanently removes backup {identifier}.")
        print_hint(f"Repeat with: runexe remove-backup {identifier} --yes")
        raise typer.Exit(code=2)
    try:
        remove_backup(backup)
    except BackupError as error:
        _fail(str(error))
    print_success(f"Removed backup {identifier}.")


@app.command(name="configure-environment")
def configure_environment(
    identifier: Annotated[str, typer.Argument(help="Environment ID from runexe environments.")],
    tool: Annotated[
        str,
        typer.Option("--tool", help="winecfg, regedit, control, uninstaller, or explorer."),
    ] = "winecfg",
) -> None:
    """Open a native Wine/Proton maintenance tool for a managed environment."""

    if tool not in CONFIGURATION_TOOLS:
        _fail(f"Unknown tool '{tool}'. Choose one of: {', '.join(CONFIGURATION_TOOLS)}.")
    item = next(
        (
            environment
            for environment in discover_environments()
            if environment.identifier == identifier
        ),
        None,
    )
    if item is None:
        _fail(f"No managed environment matches '{identifier}'.")
    try:
        open_environment_configuration(item, tool)
    except ConfigurationError as error:
        _fail(str(error))
    print_success(f"Opened {CONFIGURATION_TOOLS[tool][0]} for {identifier}.")


@app.command(name="graphics")
def graphics_readiness(
    json_output: Annotated[
        bool, typer.Option("--json", help="Emit Vulkan/GPU and DXVK readiness as JSON.")
    ] = False,
) -> None:
    """Inspect Vulkan/GPU readiness and DXVK in managed environments."""

    host = detect_host()
    environments = discover_environments()
    payload = {
        "vulkan_available": host.vulkan_available,
        "vulkan_version": host.vulkan_version,
        "vulkan_devices": host.vulkan_devices,
        "vulkan_error": host.vulkan_error,
        "environments": [
            {
                "identifier": item.identifier,
                "dxvk_available": item.dxvk_available,
                "dxvk_source": item.dxvk_source,
                "dxvk_components": item.dxvk_components,
            }
            for item in environments
        ],
    }
    if json_output:
        typer.echo(json.dumps(payload, indent=2))
        return
    print_banner("Graphics readiness | read-only Vulkan and DXVK inspection")
    print_summary(
        "Vulkan",
        [
            (
                "Status",
                "ready"
                if host.vulkan_available
                else "unavailable"
                if host.vulkan_available is False
                else "unknown",
            ),
            ("Version", host.vulkan_version or "not reported"),
            ("Devices", ", ".join(host.vulkan_devices) or "none reported"),
            ("Detail", host.vulkan_error or "vulkaninfo completed successfully"),
        ],
    )
    if host.vulkan_available is None:
        print_hint("Install vulkaninfo with: " + install_hint("vulkan"))
    if environments:
        print_table(
            "DXVK inventory",
            (("Environment", "left"), ("DXVK", "left"), ("Source", "left"), ("DLLs", "left")),
            (
                (
                    item.identifier,
                    "available"
                    if item.dxvk_available
                    else "not detected"
                    if item.dxvk_available is False
                    else "unknown",
                    item.dxvk_source,
                    ", ".join(item.dxvk_components) or "-",
                )
                for item in environments
            ),
        )


@desktop_app.command("install")
def desktop_install(
    executable: Annotated[
        Path | None,
        typer.Option(
            "--executable",
            help="runexe-gui executable to place in the desktop entry.",
        ),
    ] = None,
) -> None:
    """Add RunEXE to the current Linux user's desktop application menu."""

    try:
        paths = install_desktop_entry(executable)
    except DesktopIntegrationError as error:
        _fail(str(error))
    print_success(f"Installed desktop entry: {paths.desktop_file}")
    print_hint("RunEXE should now appear in the application menu and Open With list.")


@desktop_app.command("remove")
def desktop_remove() -> None:
    """Remove only the desktop-menu files managed by RunEXE."""

    try:
        paths, removed = remove_desktop_entry()
    except DesktopIntegrationError as error:
        _fail(str(error))
    if removed:
        print_success(f"Removed desktop entry: {paths.desktop_file}")
    else:
        print_hint("No RunEXE-managed desktop entry was installed.")


@app.command(name="backends")
def list_backends() -> None:
    """Show the Wine and Proton runtimes RunEXE can use."""

    host = detect_host()
    installations = discover_proton_installations()
    print_banner("Runtime discovery")
    print_summary(
        "Host",
        [
            ("Architecture", host.architecture),
            ("Wine", status_text(host.wine_installed)),
            ("Wine version", host.wine_version or "not detected"),
            ("Winetricks", status_text(host.winetricks_installed)),
            ("Proton", status_text(bool(installations))),
            ("Vulkan", status_text(host.vulkan_supported)),
            (
                "GPU vendor(s)",
                ", ".join(host.gpu_vendors) if host.gpu_vendors else "not detected",
            ),
        ],
    )
    if installations:
        print_table(
            "Installed Proton builds (selection order)",
            (("Name", "left"), ("Version", "left"), ("Launcher", "left")),
            ((item.name, item.version or "unknown", item.script) for item in installations),
        )
        print_hint("Choose one with --proton NAME or --proton /path/to/proton.")
    else:
        print_hint(
            "Install Proton through Steam, add a custom build to compatibilitytools.d, "
            "or set RUNEXE_PROTON_PATH."
        )
    if not host.vulkan_supported:
        print_hint(
            "No hardware Vulkan driver detected; run 'runexe doctor' for a "
            "distro-specific install command."
        )


@app.command()
def version() -> None:
    """Show the installed RunEXE version."""

    typer.echo(f"RunEXE {__version__}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
