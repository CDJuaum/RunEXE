"""Extensible compatibility profiles for applications with known requirements."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import ApplicationProfile, ExecutableInfo

PAINT_NET = ApplicationProfile(
    key="paint-dot-net",
    name="Paint.NET",
    recommended_windows_version="11",
    minimum_windows_build=19044,
    summary=(
        "Paint.NET 5.1+ requires Windows 10 21H2 (build 19044) or newer. "
        "RunEXE will configure this environment to report Windows 11."
    ),
    requirements=(
        "64-bit x64 with AVX2, or ARM64; at least four CPU cores",
        "Windows 10 21H2 / build 19044 or newer",
        "Direct3D 11-capable graphics stack",
    ),
)


@dataclass(frozen=True)
class RuntimeDiagnostic:
    """A recognized launch failure with a concrete remediation."""

    title: str
    message: str
    recommended_windows_version: str | None = None


def _identity_text(executable: ExecutableInfo) -> str:
    """Combine trustworthy local metadata used for conservative profile matching."""

    values = [executable.path.name, executable.path.stem]
    if executable.version_info is not None:
        values.extend(executable.version_info.strings.values())
    if executable.package is not None:
        values.extend(
            value
            for value in (
                executable.package.identity_name,
                executable.package.display_name,
                executable.package.application_id,
            )
            if value
        )
    return "\n".join(values).casefold()


def detect_application_profile(executable: ExecutableInfo) -> ApplicationProfile | None:
    """Return a known application profile when local metadata is a strong match."""

    identity = _identity_text(executable)
    if (
        "paintdotnet" in identity
        or "paint.net" in identity
        or re.search(r"\bpaint[\s._-]*net\b", identity)
    ):
        return PAINT_NET
    return None


def is_paint_net_web_installer(executable: ExecutableInfo) -> bool:
    """Return whether *executable* is Paint.NET's managed web bootstrapper.

    Paint.NET itself ships its modern .NET runtime with the application, but the
    small ``*.install.anycpu.web.exe`` bootstrapper contains a separate managed
    downloader that targets .NET Framework 4.7.2.  Keep this deliberately narrow
    so an installed ``PaintDotNet.exe`` never inherits the bootstrapper runtime.
    """

    profile = detect_application_profile(executable)
    if profile is None or profile.key != PAINT_NET.key:
        return False

    filename = executable.path.name.casefold()
    if not (".install." in filename and ".web." in filename):
        return False

    strings = executable.version_info.strings if executable.version_info is not None else {}
    original_filename = strings.get("OriginalFilename", "").casefold()
    internal_name = strings.get("InternalName", "").casefold()
    description = strings.get("FileDescription", "").casefold()

    return (
        original_filename == "setupsfx.exe" or internal_name == "setupsfx"
    ) and "paint.net" in description


def detect_runtime_issue(
    output: str,
    exit_code: int | None,
    profile: ApplicationProfile | None = None,
) -> RuntimeDiagnostic | None:
    """Recognize actionable failures from process output or well-known exit codes."""

    normalized = " ".join(output.casefold().split())
    missing_clr = "wine mono is not installed" in normalized or (
        "clrruntimeinfo_getruntimehost" in normalized and "mscoree" in normalized
    )
    if missing_clr:
        return RuntimeDiagnostic(
            title="Managed runtime required",
            message=(
                "The application could not start its Windows CLR runtime. Enable automatic "
                "dependencies, prepare the isolated environment again, and retry."
            ),
        )

    old_windows_message = bool(
        re.search(
            r"windows\s+10.*(?:21h2|windows\s+11).*\brequired\b",
            normalized,
        )
    )
    old_windows_exit = exit_code in {1150, 1150 % 256}
    paint_net_exit = profile is not None and profile.key == PAINT_NET.key and old_windows_exit
    if old_windows_message or paint_net_exit:
        application = profile.name if profile is not None else "The application"
        return RuntimeDiagnostic(
            title="Newer Windows version required",
            message=(
                f"{application} rejected the Windows version reported by the runtime. "
                "Select Windows 11, prepare the isolated environment again, and retry."
            ),
            recommended_windows_version="11",
        )
    return None
