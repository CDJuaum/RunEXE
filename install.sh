#!/bin/sh
# Install RunEXE into an isolated, user-owned virtual environment.

set -eu

PROJECT_URL="https://github.com/CDJuaum/RunEXE"
DATA_HOME=${XDG_DATA_HOME:-"$HOME/.local/share"}
INSTALL_ROOT=${RUNEXE_INSTALL_ROOT:-"$DATA_HOME/runexe/app"}
VENV="$INSTALL_ROOT/venv"
BIN_DIR=${RUNEXE_BIN_DIR:-"$HOME/.local/bin"}
PYTHON=${RUNEXE_PYTHON:-python3}
WITH_GUI=1
WITH_DESKTOP=1
SOURCE_CHANNEL=release

usage() {
    printf '%s\n' "Install RunEXE for the current user." "" \
        "Usage: sh install.sh [--cli-only] [--no-desktop] [--main]" "" \
        "  --cli-only    Install the console interface without Qt." \
        "  --no-desktop  Do not create a desktop-menu entry." \
        "  --main        Install the current main branch for testing." \
        "  --help        Show this help." "" \
        "Environment overrides:" \
        "  RUNEXE_INSTALL_SPEC  pip requirement or local project path" \
        "  RUNEXE_INSTALL_ROOT installation root (default: $INSTALL_ROOT)" \
        "  RUNEXE_BIN_DIR      command directory (default: $BIN_DIR)" \
        "  RUNEXE_PYTHON       Python 3.10+ executable (default: python3)"
}

fail() {
    printf 'RunEXE installer: %s\n' "$*" >&2
    exit 1
}

validate_install_root() {
    case "$INSTALL_ROOT" in
        /*) ;;
        *) fail "RUNEXE_INSTALL_ROOT must be an absolute path." ;;
    esac
    case "/$INSTALL_ROOT/" in
        */../*|*/./*) fail "RUNEXE_INSTALL_ROOT cannot contain . or .. path segments." ;;
    esac
    case "$INSTALL_ROOT" in
        /|"$HOME"|"$DATA_HOME"|"$BIN_DIR"|/bin|/boot|/dev|/etc|/home|/lib|/lib64|/opt|/proc|/root|/run|/sbin|/srv|/sys|/tmp|/usr|/var)
            fail "refusing unsafe installation path: $INSTALL_ROOT"
            ;;
    esac
    case "$INSTALL_ROOT" in
        */runexe|*/runexe/*|*/runexe-*) ;;
        *) fail "RUNEXE_INSTALL_ROOT must contain a runexe path component." ;;
    esac
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --cli-only)
            WITH_GUI=0
            WITH_DESKTOP=0
            ;;
        --no-desktop)
            WITH_DESKTOP=0
            ;;
        --main)
            SOURCE_CHANNEL=main
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            fail "unknown option: $1"
            ;;
    esac
    shift
done

[ "$(uname -s 2>/dev/null || printf unknown)" = "Linux" ] || \
    fail "RunEXE can only be installed on Linux."
validate_install_root
command -v "$PYTHON" >/dev/null 2>&1 || \
    fail "$PYTHON was not found. Install Python 3.10 or newer first."
"$PYTHON" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))' || \
    fail "$PYTHON must be Python 3.10 or newer."

if [ -n "${RUNEXE_INSTALL_SPEC:-}" ]; then
    INSTALL_SPEC=$RUNEXE_INSTALL_SPEC
    INSTALL_SOURCE="custom install spec"
else
    if [ "$SOURCE_CHANNEL" = main ]; then
        ARCHIVE_URL="$PROJECT_URL/archive/refs/heads/main.tar.gz"
        INSTALL_SOURCE="main branch"
    else
        command -v curl >/dev/null 2>&1 || fail "curl is required to resolve the latest RunEXE release."
        latest_url=$(curl -fsSL -o /dev/null -w '%{url_effective}' "$PROJECT_URL/releases/latest") || \
            fail "could not resolve the latest published RunEXE release."
        RELEASE_TAG=${latest_url##*/}
        case "$RELEASE_TAG" in
            ''|*[!A-Za-z0-9._-]*) fail "invalid release tag: $RELEASE_TAG" ;;
        esac
        ARCHIVE_URL="$PROJECT_URL/archive/refs/tags/$RELEASE_TAG.tar.gz"
        INSTALL_SOURCE="release $RELEASE_TAG"
    fi
    if [ "$WITH_GUI" -eq 1 ]; then
        INSTALL_SPEC="runexe[gui] @ $ARCHIVE_URL"
    else
        INSTALL_SPEC="runexe @ $ARCHIVE_URL"
    fi
fi

for command_name in runexe runexe-gui; do
    [ "$command_name" = runexe-gui ] && [ "$WITH_GUI" -eq 0 ] && continue
    link_path="$BIN_DIR/$command_name"
    if [ -e "$link_path" ] && [ ! -L "$link_path" ]; then
        fail "$link_path already exists and is not a symlink; it was left unchanged."
    fi
done

mkdir -p "$INSTALL_ROOT" "$BIN_DIR"
printf '%s\n' 'runexe-user-installer-v1' > "$INSTALL_ROOT/.runexe-installer"

if ! "$PYTHON" -m venv "$VENV"; then
    fail "could not create a virtual environment. Install your distribution's python3-venv package."
fi

printf 'Installing RunEXE from %s\n' "$INSTALL_SOURCE"
printf 'Source: %s\n' "$INSTALL_SPEC"
if [ "$SOURCE_CHANNEL" = main ] && [ -z "${RUNEXE_INSTALL_SPEC:-}" ]; then
    "$VENV/bin/python" -m pip uninstall -y runexe >/dev/null 2>&1
fi
if ! "$VENV/bin/python" -m pip install --upgrade "$INSTALL_SPEC"; then
    if [ "$WITH_GUI" -eq 1 ]; then
        printf '%s\n' \
            'The GUI dependency may be unavailable for this architecture or musl system.' \
            'Retry with: sh install.sh --cli-only' >&2
    fi
    fail "package installation failed."
fi

ln -sfn "$VENV/bin/runexe" "$BIN_DIR/runexe"
if [ "$WITH_GUI" -eq 1 ]; then
    [ -x "$VENV/bin/runexe-gui" ] || fail "the GUI entry point was not installed."
    ln -sfn "$VENV/bin/runexe-gui" "$BIN_DIR/runexe-gui"
fi

if [ "$WITH_DESKTOP" -eq 1 ]; then
    if ! "$VENV/bin/runexe" desktop install --executable "$BIN_DIR/runexe-gui"; then
        printf '%s\n' \
            'RunEXE was installed, but its desktop-menu entry could not be created.' \
            "Retry with: $BIN_DIR/runexe desktop install --executable $BIN_DIR/runexe-gui" >&2
    fi
fi

printf '\nRunEXE installed successfully.\n'
if [ "$WITH_GUI" -eq 1 ]; then
    printf 'Commands: %s/runexe and %s/runexe-gui\n' "$BIN_DIR" "$BIN_DIR"
else
    printf 'Command: %s/runexe\n' "$BIN_DIR"
fi
case ":${PATH:-}:" in
    *":$BIN_DIR:"*) ;;
    *) printf 'Add %s to PATH, then open a new terminal.\n' "$BIN_DIR" ;;
esac
printf 'Next: %s/runexe doctor\n' "$BIN_DIR"
if [ "$SOURCE_CHANNEL" = main ] && [ -z "${RUNEXE_INSTALL_SPEC:-}" ]; then
    printf 'Update: rerun this installer with --main.\n'
else
    printf 'Update: run this installer again.\n'
fi
printf '%s\n' \
    'Uninstall: curl -fsSL https://raw.githubusercontent.com/CDJuaum/RunEXE/main/uninstall.sh | sh'
