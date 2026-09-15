#!/bin/sh
# Build a native Arch Linux package from the tested glibc portable bundle.
set -eu

archive="${1:-}"
output="${2:-dist/arch}"

if [ -z "$archive" ] || [ ! -f "$archive" ]; then
  echo 'Usage: package_arch.sh /path/to/runexe-*-linux-x86_64-glibc.tar.gz [output-dir]' >&2
  exit 2
fi

version="$(python - <<'PY'
import tomllib
from pathlib import Path

print(tomllib.loads(Path('pyproject.toml').read_text(encoding='utf-8'))['project']['version'])
PY
)"

case "$version" in
  *[!0-9.]*|'') echo "Invalid package version: $version" >&2; exit 2 ;;
esac

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT INT TERM
mkdir -p "$work/src" "$output"
tar -xzf "$archive" -C "$work/src"

if [ ! -x "$work/src/runexe/runexe" ] || [ ! -x "$work/src/runexe/runexe-gui" ]; then
  echo 'Portable glibc bundle is missing RunEXE executables' >&2
  exit 1
fi

cp -a "$work/src/runexe" "$work/runexe"
cat > "$work/PKGBUILD" <<EOF
pkgname=runexe-bin
pkgver=$version
pkgrel=1
pkgdesc='Analyze and run Windows software on Linux with Wine or Proton'
arch=('x86_64')
url='https://github.com/CDJuaum/RunEXE'
license=('LGPL-2.1-only')
depends=('glibc>=2.35' 'libglvnd' 'libxkbcommon' 'libxkbcommon-x11' 'dbus' 'fontconfig' 'xcb-util-cursor' 'xcb-util-wm' 'xcb-util-image' 'xcb-util-keysyms' 'xcb-util-renderutil' 'libxcb' 'wayland')
optdepends=('wine: run Windows applications with Wine' 'winetricks: install Windows runtime dependencies')
options=('!strip')

package() {
  install -d "\$pkgdir/opt/runexe" "\$pkgdir/usr/bin" \
    "\$pkgdir/usr/share/applications" "\$pkgdir/usr/share/icons/hicolor/256x256/apps"
  # The prebuilt bundle sits next to PKGBUILD. makepkg --cleanbuild clears its
  # own srcdir before package(), so do not stage this source inside $srcdir.
  cp -a "\$startdir/runexe/." "\$pkgdir/opt/runexe/"
  ln -s /opt/runexe/runexe "\$pkgdir/usr/bin/runexe"
  ln -s /opt/runexe/runexe-gui "\$pkgdir/usr/bin/runexe-gui"
  install -Dm644 /dev/stdin "\$pkgdir/usr/share/applications/runexe.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=RunEXE
Comment=Run Windows applications with Wine or Proton
Exec=/opt/runexe/runexe-gui %f
Icon=runexe
Terminal=false
Categories=Utility;
MimeType=application/x-ms-dos-executable;application/vnd.microsoft.portable-executable;
StartupWMClass=RunEXE
DESKTOP
  install -Dm644 "\$startdir/runexe/runexe-logo.png" \
    "\$pkgdir/usr/share/icons/hicolor/256x256/apps/runexe.png"
}
EOF

# The bundle logo lives under the frozen application tree. Keep a stable source
# path for PKGBUILD so packaging stays independent of PyInstaller internals.
logo="$(find "$work/runexe" -type f -name 'runexe-logo.png' | head -n 1)"
if [ -z "$logo" ]; then
  echo 'RunEXE logo missing from frozen bundle' >&2
  exit 1
fi
cp "$logo" "$work/runexe/runexe-logo.png"

chmod -R a+rX "$work"
chown -R builder:builder "$work"
su builder -s /bin/sh -c "cd '$work' && makepkg --nodeps --noconfirm --cleanbuild"

package="$(find "$work" -maxdepth 1 -type f -name 'runexe-bin-*.pkg.tar.zst' -print -quit)"
if [ -z "$package" ]; then
  echo 'Arch package was not created' >&2
  exit 1
fi
cp "$package" "$output/"
