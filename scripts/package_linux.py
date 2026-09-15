"""Package an already frozen x86-64 Linux build into release artifacts."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import tarfile
from importlib.metadata import version as installed_version
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def tag_label(tag: str) -> str:
    """Produce a shell/path-safe artifact label without losing tag uniqueness."""
    label = re.sub(r"[^A-Za-z0-9._-]", "-", tag).strip(".-")[:80] or "tag"
    return f"{label}-{hashlib.sha256(tag.encode()).hexdigest()[:8]}"


def write_file(path: Path, text: str, *, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755 if executable else 0o644)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("libc", choices=("glibc", "musl"))
    args = parser.parse_args()
    version = installed_version("runexe")
    # Package managers need numeric versions; arbitrary Git tags still build.
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Set project.version to a numeric major.minor.patch before packaging")
    tag = os.environ.get("RELEASE_TAG", f"v{version}")
    label = tag_label(tag)
    bundle = ROOT / "build" / "frozen" / "runexe"
    if not (bundle / "runexe").is_file():
        raise FileNotFoundError("Build the frozen executable before packaging")
    if args.libc == "glibc":
        write_file(
            bundle / "runexe-gui",
            '#!/bin/sh\nexec "$(dirname "$(readlink -f "$0")")/runexe" gui "$@"\n',
            executable=True,
        )
    shutil.copy2(ROOT / "LICENSE", bundle / "LICENSE")
    shutil.copy2(ROOT / "README.md", bundle / "README.md")
    write_file(
        bundle / "BUILD-INFO.txt",
        f"Tag: {tag}\nCommit: {os.environ.get('RELEASE_SHA', 'local')}\n"
        f"Application version: {version}\nArchitecture: x86_64\nLibc: {args.libc}\n",
    )
    output = ROOT / "dist" / "linux"
    output.mkdir(parents=True, exist_ok=True)
    stem = f"runexe-{label}-linux-x86_64-{args.libc}"
    with tarfile.open(output / f"{stem}.tar.gz", "w:gz") as archive:
        archive.add(bundle, arcname="runexe")
    if args.libc == "glibc":
        build_native_packages(bundle, output, stem, version)


def build_native_packages(bundle: Path, output: Path, stem: str, version: str) -> None:
    stage = ROOT / "build" / "linux-package"
    # Use a fresh directory; never delete a caller-selected path.
    stage.mkdir(parents=True, exist_ok=False)
    shutil.copytree(bundle, stage / "opt" / "runexe", symlinks=True)
    for command in ("runexe", "runexe-gui"):
        link = stage / "usr" / "bin" / command
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(f"/opt/runexe/{command}")
    desktop = stage / "usr/share/applications/runexe.desktop"
    write_file(
        desktop,
        """[Desktop Entry]
Type=Application
Name=RunEXE
Comment=Run Windows applications with Wine or Proton
Exec=/opt/runexe/runexe-gui %f
Icon=runexe
Terminal=false
Categories=Utility;
MimeType=application/x-ms-dos-executable;application/vnd.microsoft.portable-executable;
StartupWMClass=RunEXE
""",
    )
    subprocess.run(["desktop-file-validate", str(desktop)], check=True)
    icon = stage / "usr/share/icons/hicolor/256x256/apps/runexe.png"
    icon.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "runexe/assets/runexe-logo.png", icon)
    license_path = stage / "usr/share/doc/runexe/copyright"
    license_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "LICENSE", license_path)

    write_file(
        stage / "DEBIAN/control",
        f"""Package: runexe
Version: {version}
Section: utils
Priority: optional
Architecture: amd64
Maintainer: RunEXE contributors <noreply@github.com>
Depends: libc6 (>= 2.35), python3, libglib2.0-0, libgl1, libegl1, libxkbcommon0, libxkbcommon-x11-0,
 libdbus-1-3, libfontconfig1, libxcb-cursor0, libxcb-icccm4, libxcb-image0,
 libxcb-keysyms1, libxcb-render-util0, libxcb-xinerama0, libxcb-xkb1,
 libwayland-client0
Recommends: wine, winetricks
Homepage: https://github.com/CDJuaum/RunEXE
Description: Windows application launcher for Linux
 Includes the RunEXE desktop interface, CLI, Python and Qt.
 Wine or Proton must be installed separately.
""",
    )
    subprocess.run(
        ["dpkg-deb", "--root-owner-group", "--build", str(stage), str(output / f"{stem}.deb")],
        check=True,
    )
    # RPM's explicit manifest excludes Debian control data and application state.
    rpm_root = ROOT / "build" / "rpm"
    rpm_root.mkdir(parents=True, exist_ok=True)
    spec = rpm_root / "runexe.spec"
    write_file(
        spec,
        f"""Name: runexe
Version: {version}
Release: 1
Summary: Windows application launcher for Linux
License: LGPL-2.1-only
URL: https://github.com/CDJuaum/RunEXE
BuildArch: x86_64
AutoReqProv: no
Requires: glibc >= 2.35, libGL.so.1()(64bit), libEGL.so.1()(64bit)
Requires: python3
Requires: libxkbcommon.so.0()(64bit), libxkbcommon-x11.so.0()(64bit)
Requires: libdbus-1.so.3()(64bit), libfontconfig.so.1()(64bit)
Requires: libxcb-cursor.so.0()(64bit), libwayland-client.so.0()(64bit)
Requires: libxcb-icccm.so.4()(64bit), libxcb-image.so.0()(64bit)
Requires: libxcb-keysyms.so.1()(64bit), libxcb-render-util.so.0()(64bit)
Requires: libxcb-xinerama.so.0()(64bit), libxcb-xkb.so.1()(64bit)
%description
RunEXE desktop and CLI with Python and Qt. Install Wine or Proton separately.
%install
mkdir -p %{{buildroot}}
cp -a {stage}/opt {stage}/usr %{{buildroot}}/
%files
/opt/runexe
/usr/bin/runexe
/usr/bin/runexe-gui
/usr/share/applications/runexe.desktop
/usr/share/icons/hicolor/256x256/apps/runexe.png
/usr/share/doc/runexe
""",
    )
    subprocess.run(
        [
            "rpmbuild",
            "-bb",
            "--define",
            f"_topdir {rpm_root}",
            "--define",
            "__os_install_post %{nil}",
            "--define",
            "_build_id_links none",
            str(spec),
        ],
        check=True,
    )
    packages = list((rpm_root / "RPMS").rglob("*.rpm"))
    if len(packages) != 1:
        raise RuntimeError("Expected exactly one built RPM")
    shutil.copy2(packages[0], output / f"{stem}.rpm")


if __name__ == "__main__":
    main()
