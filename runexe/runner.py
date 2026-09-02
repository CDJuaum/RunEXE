"""Provision isolated Wine or Proton environments and launch Windows software."""

import hashlib
import os
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .environments import write_environment_metadata
from .models import CompatibilityReport, ExecutableInfo
from .pe_utils import run_with_progress
from .platform_support import find_executable, install_hint
from .proton import (
    ProtonError,
    ProtonInstallation,
    compat_data_path_for,
    proton_environment,
    proton_tuning_preset,
    proton_winetricks_environment,
    select_proton,
)

RUNEXE_DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "runexe"
PREFIXES_DIR = RUNEXE_DATA_DIR / "prefixes"

# Winetricks / wineboot can hang waiting on a dialog that will never
# be answered in a headless run; bound both steps rather than blocking
# forever.
PREFIX_INIT_TIMEOUT = 120
WINETRICKS_TIMEOUT = 600
PROTON_INIT_TIMEOUT = 180


class RunnerError(Exception):
    """Setup failure: missing binaries, blocked launch, bad backend."""


@dataclass
class LaunchResult:
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool = False


@dataclass(frozen=True)
class PreparedEnvironment:
    """A ready-to-use isolated Wine prefix or Proton compat-data directory."""

    backend: str
    path: Path
    runtime_name: str
    launcher: str
    wine_arch: str
    proton_installation: ProtonInstallation | None = None
    proton_tuning: str = "default"


@dataclass(frozen=True)
class LaunchSpec:
    """A fully resolved process invocation suitable for CLI or GUI execution."""

    command: tuple[str, ...]
    cwd: Path
    env: dict[str, str]


def _verbose(enabled: bool, message: str) -> None:
    if enabled:
        print(f"[runexe] {message}")


def _record_environment(
    prepared: PreparedEnvironment,
    executable: Path,
    architecture: str,
    windows_version: str | None,
    verbose: bool,
) -> None:
    ready_path = (
        prepared.path / "pfx" / "drive_c"
        if prepared.backend == "proton"
        else prepared.path / "drive_c"
    )
    if not ready_path.is_dir():
        return
    try:
        write_environment_metadata(
            prepared.path,
            backend=prepared.backend,
            source=executable,
            architecture=architecture,
            runtime=prepared.runtime_name,
            windows_version=windows_version,
            runtime_path=prepared.launcher,
        )
    except OSError as error:
        _verbose(verbose, f"Could not update environment metadata: {error}")


def _require_binary(name: str) -> str:
    path = find_executable(name)
    if path is None:
        variable = f"RUNEXE_{name.upper()}_PATH"
        raise RunnerError(
            f"'{name}' not found. {install_hint(name)}. If it is installed outside PATH, "
            f"set {variable} to its executable."
        )
    return path


def prefix_path_for(executable: ExecutableInfo) -> Path:
    """Return a stable, per-app prefix directory.

    Keyed on the executable's filename plus a short hash of its
    resolved path, so re-running the same file reuses its prefix while
    different files that happen to share a filename don't collide.
    """

    resolved = str(executable.path.resolve())
    digest = hashlib.sha1(resolved.encode("utf-8")).hexdigest()[:10]
    slug = re.sub(r"[^a-z0-9._-]+", "_", executable.path.stem.lower()).strip("._-") or "app"

    return PREFIXES_DIR / f"{slug}-{digest}"


def _installed_verbs_marker(prefix: Path) -> Path:
    return prefix / ".runexe-installed-verbs"


def _wine_env(prefix: Path, wine_arch: str) -> dict:
    env = os.environ.copy()
    env["WINEPREFIX"] = str(prefix)
    env["WINEARCH"] = wine_arch
    # Quiet Wine's own logging; we care about the target app's stderr,
    # not Wine's internal debug channel noise.
    env.setdefault("WINEDEBUG", "-all")
    return env


def _wine_tool_command(name: str) -> list[str]:
    """Prefer Wine's native helper, with a loader fallback."""

    helper = find_executable(name)
    if helper:
        return [helper]
    return [_require_binary("wine"), name]


def _existing_prefix_arch(prefix: Path) -> str | None:
    marker = prefix / ".runexe-winearch"
    if marker.is_file():
        return marker.read_text(encoding="utf-8", errors="replace").strip() or None
    system_reg = prefix / "system.reg"
    if system_reg.is_file():
        try:
            with system_reg.open(encoding="utf-8", errors="replace") as file:
                first_line = file.readline()
        except OSError:
            return None
        match = re.search(r"#arch=(win32|win64)", first_line)
        return match.group(1) if match else None
    return None


def ensure_prefix(
    prefix: Path,
    wine_arch: str,
    verbose: bool = False,
) -> None:
    """Create and initialize the Wine prefix if needed."""

    prefix_ready = (prefix / "drive_c").is_dir()

    if prefix_ready:
        existing_arch = _existing_prefix_arch(prefix)
        if existing_arch and existing_arch != wine_arch:
            raise RunnerError(
                f"Existing prefix at {prefix} uses {existing_arch}, but this "
                f"executable requires {wine_arch}."
            )
        _verbose(verbose, f"Reusing Wine prefix: {prefix}")
        return

    prefix.mkdir(parents=True, exist_ok=True)

    command = [*_wine_tool_command("wineboot"), "--init"]

    try:
        result = run_with_progress(
            command,
            env=_wine_env(prefix, wine_arch),
            description="Creating Wine prefix",
            timeout=PREFIX_INIT_TIMEOUT,
            verbose=verbose,
        )

    except subprocess.TimeoutExpired as error:
        raise RunnerError(f"Timed out initializing the Wine prefix at {prefix}.") from error

    if result.returncode != 0:
        raise RunnerError(f"Wine prefix initialization failed with exit code {result.returncode}.")

    if not (prefix / "drive_c").is_dir():
        raise RunnerError(
            f"Wine prefix initialization completed, but the prefix appears incomplete: {prefix}"
        )

    (prefix / ".runexe-winearch").write_text(wine_arch + "\n", encoding="utf-8")


def set_windows_version(
    prefix: Path,
    wine_arch: str,
    winver: str,
    verbose: bool = False,
) -> None:
    """Set the Windows version reported by Wine for this prefix."""

    supported_versions = {
        "7": "win7",
        "8": "win8",
        "8.1": "win81",
        "10": "win10",
        "11": "win11",
    }

    normalized = winver.lower().removeprefix("win")
    wine_version = supported_versions.get(normalized)

    if wine_version is None:
        raise RunnerError(
            f"Unsupported Windows version '{winver}'. "
            f"Supported versions: 7, 8, 8.1, 10, 11 (or win10-style names)"
        )

    command = [
        *_wine_tool_command("winecfg"),
        "-v",
        wine_version,
    ]

    _verbose(
        verbose,
        f"Setting Wine Windows version: Windows {winver}",
    )

    try:
        result = run_with_progress(
            command,
            env=_wine_env(prefix, wine_arch),
            description=f"Configuring Wine for Windows {winver}",
            timeout=60,
            verbose=verbose,
        )
    except subprocess.TimeoutExpired as error:
        raise RunnerError(f"Timed out configuring Wine Windows version to {winver}.") from error

    if result.returncode != 0:
        raise RunnerError(
            f"Failed to configure Wine Windows version to {winver} (exit code {result.returncode})."
        )


def install_verbs(
    prefix: Path,
    verbs: list[str],
    verbose: bool = False,
    wine_arch: str | None = None,
    env_override: dict[str, str] | None = None,
) -> set[str]:
    """Install the given winetricks verbs into prefix.

    Skips verbs already recorded as installed.
    Returns the full set of installed verbs.
    """

    marker = _installed_verbs_marker(prefix)

    already_installed = (
        set(marker.read_text(encoding="utf-8").split()) if marker.exists() else set()
    )

    to_install = [verb for verb in verbs if verb not in already_installed]

    if not to_install:
        if verbose:
            print("[runexe] Required dependencies are already installed.")

        return already_installed

    winetricks_binary = _require_binary("winetricks")

    env = env_override.copy() if env_override is not None else os.environ.copy()
    env["WINEPREFIX"] = str(prefix)
    if wine_arch and env_override is None:
        env["WINEARCH"] = wine_arch
    env.setdefault("WINEDEBUG", "-all")

    command = [
        winetricks_binary,
        "--unattended",
        *to_install,
    ]

    try:
        result = run_with_progress(
            command,
            env=env,
            description=(f"Installing dependencies: {', '.join(to_install)}"),
            timeout=WINETRICKS_TIMEOUT,
            verbose=verbose,
        )

    except subprocess.TimeoutExpired as error:
        raise RunnerError(
            f"Timed out installing winetricks verbs: {', '.join(to_install)}."
        ) from error

    if result.returncode != 0:
        raise RunnerError(f"Winetricks failed with exit code {result.returncode}.")

    updated = already_installed | set(to_install)

    temporary_marker = marker.with_suffix(".tmp")
    temporary_marker.write_text(" ".join(sorted(updated)) + "\n", encoding="utf-8")
    temporary_marker.replace(marker)

    return updated


def ensure_proton_prefix(
    installation: ProtonInstallation,
    compat_data: Path,
    executable: Path,
    verbose: bool = False,
) -> None:
    """Initialize an isolated Proton compat-data directory once."""

    prefix = compat_data / "pfx"
    if (prefix / "drive_c").is_dir():
        _verbose(verbose, f"Reusing Proton compat data: {compat_data}")
        return

    compat_data.mkdir(parents=True, exist_ok=True)
    command = [str(installation.script), "run", "cmd.exe", "/c", "exit"]
    try:
        result = run_with_progress(
            command,
            env=proton_environment(installation, compat_data, executable),
            description=f"Initializing {installation.name}",
            timeout=PROTON_INIT_TIMEOUT,
            verbose=verbose,
        )
    except subprocess.TimeoutExpired as error:
        raise RunnerError(f"Timed out initializing Proton compat data at {compat_data}.") from error

    if result.returncode != 0 or not (prefix / "drive_c").is_dir():
        raise RunnerError(
            f"{installation.name} could not initialize compat data at {compat_data} "
            f"(exit code {result.returncode})."
        )
    (compat_data / ".runexe-proton").write_text(
        f"{installation.script}\n{installation.version or installation.name}\n",
        encoding="utf-8",
    )


def set_proton_windows_version(
    installation: ProtonInstallation,
    compat_data: Path,
    executable: Path,
    winver: str,
    verbose: bool = False,
) -> None:
    supported = {"7": "win7", "8": "win8", "8.1": "win81", "10": "win10", "11": "win11"}
    normalized = winver.lower().removeprefix("win")
    selected = supported.get(normalized)
    if selected is None:
        raise RunnerError(
            f"Unsupported Windows version '{winver}'. Supported versions: 7, 8, 8.1, 10, 11."
        )
    command = [str(installation.script), "runinprefix", "winecfg", "-v", selected]
    try:
        result = run_with_progress(
            command,
            env=proton_environment(installation, compat_data, executable),
            description=f"Configuring Proton for Windows {normalized}",
            timeout=60,
            verbose=verbose,
        )
    except subprocess.TimeoutExpired as error:
        raise RunnerError(f"Timed out configuring Proton for Windows {normalized}.") from error
    if result.returncode != 0:
        raise RunnerError(f"Could not configure Proton for Windows {normalized}.")


def _execute_launch(
    command: list[str],
    executable_path: Path,
    env: dict[str, str],
    timeout: int | None,
    verbose: bool,
) -> LaunchResult:
    _verbose(verbose, f"Command: {shlex.join(command)}")
    try:
        completed = subprocess.run(
            command,
            cwd=executable_path.parent,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as error:
        return LaunchResult(
            exit_code=None,
            stdout=(error.stdout or "").decode(errors="replace")
            if isinstance(error.stdout, bytes)
            else (error.stdout or ""),
            stderr=(error.stderr or "").decode(errors="replace")
            if isinstance(error.stderr, bytes)
            else (error.stderr or ""),
            timed_out=True,
        )
    except OSError as error:
        raise RunnerError(f"Could not start compatibility runtime: {error}") from error
    return LaunchResult(completed.returncode, completed.stdout, completed.stderr)


def _validate_environment_request(
    executable: ExecutableInfo,
    compatibility: CompatibilityReport,
) -> None:
    if compatibility.backend == "unsupported":
        raise RunnerError(f"{compatibility.architecture} is not supported by Wine/Proton.")
    if compatibility.backend not in {"wine", "proton"}:
        raise RunnerError(f"Unknown compatibility backend: {compatibility.backend}")
    if compatibility.blocking_issues:
        raise RunnerError("Cannot prepare environment: " + "; ".join(compatibility.blocking_issues))
    if not executable.valid:
        raise RunnerError(executable.reason or "Invalid Windows executable.")
    if not executable.path.exists():
        raise RunnerError(f"Executable not found: {executable.path}")


def prepare_environment(
    executable: ExecutableInfo,
    compatibility: CompatibilityReport,
    *,
    prefix: Path | None = None,
    install_dependencies: bool = True,
    proton: str | Path | None = None,
    winver: str | None = None,
    proton_tuning: str = "default",
    verbose: bool = False,
) -> PreparedEnvironment:
    """Create and configure an isolated environment without launching the app."""

    _validate_environment_request(executable, compatibility)
    executable_path = executable.path.resolve()

    if compatibility.backend == "proton":
        try:
            tuning = proton_tuning_preset(proton_tuning)
        except ProtonError as error:
            raise RunnerError(str(error)) from error
        try:
            installation = select_proton(proton)
        except ProtonError as error:
            raise RunnerError(str(error)) from error

        data_path = (
            prefix.expanduser().resolve()
            if prefix is not None
            else compat_data_path_for(executable_path)
        )
        if install_dependencies and compatibility.required_verbs:
            _require_binary("winetricks")

        _verbose(verbose, f"Backend: Proton ({installation.name})")
        _verbose(verbose, f"Proton tuning: {tuning.label}")
        _verbose(verbose, f"Proton script: {installation.script}")
        _verbose(verbose, f"Compat data: {data_path}")
        ensure_proton_prefix(installation, data_path, executable_path, verbose)

        if install_dependencies and compatibility.required_verbs:
            try:
                proton_wine_env = proton_winetricks_environment(installation, data_path)
            except ProtonError as error:
                raise RunnerError(str(error)) from error
            install_verbs(
                data_path / "pfx",
                compatibility.required_verbs,
                verbose=verbose,
                env_override=proton_wine_env,
            )
        if winver is not None:
            set_proton_windows_version(installation, data_path, executable_path, winver, verbose)

        prepared = PreparedEnvironment(
            backend="proton",
            path=data_path,
            runtime_name=installation.name,
            launcher=str(installation.script),
            wine_arch="win64",
            proton_installation=installation,
            proton_tuning=tuning.key,
        )
        _record_environment(prepared, executable_path, compatibility.architecture, winver, verbose)
        return prepared

    if proton_tuning != "default":
        raise RunnerError("Proton tuning presets can only be used with the Proton backend.")
    wine_arch = compatibility.wine_arch
    if wine_arch is None:
        raise RunnerError("No compatible Wine prefix architecture was found.")
    wine_prefix = (
        prefix.expanduser().resolve() if prefix is not None else prefix_path_for(executable)
    )

    wine_binary = _require_binary("wine")
    if install_dependencies and compatibility.required_verbs:
        _require_binary("winetricks")

    _verbose(verbose, f"Backend: Wine ({wine_binary})")
    _verbose(verbose, f"Wine architecture: {wine_arch}")
    _verbose(verbose, f"Wine prefix: {wine_prefix}")
    ensure_prefix(wine_prefix, wine_arch, verbose=verbose)

    if install_dependencies and compatibility.required_verbs:
        install_verbs(
            wine_prefix,
            compatibility.required_verbs,
            verbose=verbose,
            wine_arch=wine_arch,
        )
    if winver is not None:
        set_windows_version(wine_prefix, wine_arch, winver, verbose=verbose)

    prepared = PreparedEnvironment(
        backend="wine",
        path=wine_prefix,
        runtime_name="Wine",
        launcher=wine_binary,
        wine_arch=wine_arch,
    )
    _record_environment(prepared, executable_path, compatibility.architecture, winver, verbose)
    return prepared


def open_runtime_configuration(
    executable: ExecutableInfo,
    compatibility: CompatibilityReport,
    *,
    prefix: Path | None = None,
    proton: str | Path | None = None,
    verbose: bool = False,
) -> PreparedEnvironment:
    """Prepare an environment and open its native Wine configuration dialog."""

    prepared = prepare_environment(
        executable,
        compatibility,
        prefix=prefix,
        install_dependencies=False,
        proton=proton,
        verbose=verbose,
    )
    executable_path = executable.path.resolve()

    if prepared.proton_installation is not None:
        installation = prepared.proton_installation
        command = [str(installation.script), "runinprefix", "winecfg"]
        env = proton_environment(installation, prepared.path, executable_path)
    else:
        command = _wine_tool_command("winecfg")
        env = _wine_env(prepared.path, prepared.wine_arch)

    try:
        subprocess.Popen(command, cwd=executable_path.parent, env=env)
    except OSError as error:
        raise RunnerError(f"Could not open runtime configuration: {error}") from error
    return prepared


def build_launch_spec(
    executable: ExecutableInfo,
    prepared: PreparedEnvironment,
    extra_args: list[str] | None = None,
) -> LaunchSpec:
    """Build the process command for a previously prepared environment."""

    executable_path = executable.path.resolve()
    if prepared.proton_installation is not None:
        installation = prepared.proton_installation
        command = [str(installation.script), "run", str(executable_path), *(extra_args or [])]
        env = proton_environment(
            installation,
            prepared.path,
            executable_path,
            prepared.proton_tuning,
        )
    else:
        command = [prepared.launcher, str(executable_path), *(extra_args or [])]
        env = _wine_env(prepared.path, prepared.wine_arch)

    return LaunchSpec(tuple(command), executable_path.parent, env)


def _launch_prepared(
    executable: ExecutableInfo,
    prepared: PreparedEnvironment,
    extra_args: list[str] | None,
    timeout: int | None,
    verbose: bool,
) -> LaunchResult:
    spec = build_launch_spec(executable, prepared, extra_args)

    return _execute_launch(
        list(spec.command), executable.path.resolve(), spec.env, timeout, verbose
    )


def launch(
    executable: ExecutableInfo,
    compatibility: CompatibilityReport,
    extra_args: list[str] | None = None,
    timeout: int | None = None,
    verbose: bool = False,
    winver: str | None = None,
    prefix: Path | None = None,
    install_dependencies: bool = True,
    proton: str | Path | None = None,
    proton_tuning: str = "default",
) -> LaunchResult:
    """Provision an isolated Wine/Proton environment and launch the executable."""

    if timeout is not None and timeout <= 0:
        raise RunnerError("Timeout must be greater than zero seconds.")
    prepared = prepare_environment(
        executable,
        compatibility,
        prefix=prefix,
        install_dependencies=install_dependencies,
        proton=proton,
        proton_tuning=proton_tuning,
        winver=winver,
        verbose=verbose,
    )
    _verbose(verbose, f"Launch timeout: {timeout if timeout is not None else 'none'}")
    return _launch_prepared(executable, prepared, extra_args, timeout, verbose)
