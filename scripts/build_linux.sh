#!/bin/sh
# Run inside the workflow's clean glibc or musl build container.
set -eu

case "${1:-}" in
  glibc)
    export DEBIAN_FRONTEND=noninteractive
    apt-get -o Acquire::Retries=3 -o Acquire::http::No-Cache=true update -qq
    apt-get install -y --no-install-recommends \
      python3-pip python-is-python3 binutils dpkg-dev rpm desktop-file-utils \
      libegl1 libgl1 libx11-6 libx11-xcb1 libdbus-1-3 \
      libfontconfig1 libfreetype6 libglib2.0-0 \
      libwayland-client0 libwayland-cursor0 libwayland-egl1 \
      libxcb1 libxcb-cursor0 libxcb-icccm4 libxcb-image0 \
      libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 \
      libxcb-render0 libxcb-shape0 libxcb-shm0 libxcb-sync1 \
      libxcb-xfixes0 libxcb-xkb1 libxkbcommon0 libxkbcommon-x11-0
    python -m pip install '.[dev,gui]' 'pyinstaller==6.22.2'
    ;;
  musl)
    apk add --no-cache build-base binutils zlib-dev libffi-dev
    python -m pip install '.[dev]' 'pyinstaller==6.22.2'
    ;;
  *) echo 'Usage: build_linux.sh glibc|musl' >&2; exit 2 ;;
esac

python -m pytest -q
python -m PyInstaller --noconfirm --clean --onedir --name runexe \
  --collect-data runexe --copy-metadata runexe \
  --distpath build/frozen --workpath build/pyinstaller --specpath build \
  scripts/frozen_entry.py
python -c 'from pathlib import Path; from tests.helpers import make_pe; make_pe(Path("/tmp/runexe-smoke.exe"))'

# Test outside the source checkout so missing frozen modules cannot be masked.
bundle="$(pwd)/build/frozen/runexe"
cd /tmp
unset PYTHONPATH
"$bundle/runexe" version
"$bundle/runexe" --help
"$bundle/runexe" analyze --help
"$bundle/runexe" analyze /tmp/runexe-smoke.exe --no-host --json > /tmp/runexe-analysis.json
python -c 'import json; data=json.load(open("/tmp/runexe-analysis.json")); assert data'
if [ "$1" = glibc ]; then
  set +e
  QT_QPA_PLATFORM=offscreen timeout 8s "$bundle/runexe" gui --platform offscreen \
    > /tmp/runexe-frozen-gui.log 2>&1
  result=$?
  set -e
  cat /tmp/runexe-frozen-gui.log
  test "$result" -eq 124
fi
cd /src
python scripts/package_linux.py "$1"
