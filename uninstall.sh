#!/bin/sh
# Remove the user-level RunEXE installation without deleting app data or prefixes.

set -eu

DATA_HOME=${XDG_DATA_HOME:-"$HOME/.local/share"}
INSTALL_ROOT=${RUNEXE_INSTALL_ROOT:-"$DATA_HOME/runexe/app"}
VENV="$INSTALL_ROOT/venv"
BIN_DIR=${RUNEXE_BIN_DIR:-"$HOME/.local/bin"}
MARKER="$INSTALL_ROOT/.runexe-installer"

fail() {
    printf 'RunEXE uninstaller: %s\n' "$*" >&2
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

[ "$(uname -s 2>/dev/null || printf unknown)" = "Linux" ] || \
    fail "RunEXE can only be uninstalled by this script on Linux."
validate_install_root

remove_managed_link() {
    name=$1
    link_path="$BIN_DIR/$name"
    expected="$VENV/bin/$name"
    if [ -L "$link_path" ]; then
        target=$(readlink "$link_path" || true)
        if [ "$target" = "$expected" ]; then
            rm -f "$link_path"
        else
            printf 'Preserved unrelated symlink: %s\n' "$link_path" >&2
        fi
    elif [ -e "$link_path" ]; then
        printf 'Preserved unrelated file: %s\n' "$link_path" >&2
    fi
}

remove_managed_link runexe
remove_managed_link runexe-gui

if [ -x "$VENV/bin/runexe" ]; then
    "$VENV/bin/runexe" desktop remove >/dev/null 2>&1 || true
else
    desktop_file="$DATA_HOME/applications/runexe.desktop"
    icon_file="$DATA_HOME/icons/hicolor/256x256/apps/runexe.png"
    if [ -f "$desktop_file" ] && grep -q '^X-RunEXE-Managed=true$' "$desktop_file"; then
        rm -f "$desktop_file" "$icon_file"
    fi
fi

if [ -e "$INSTALL_ROOT" ]; then
    [ -f "$MARKER" ] || \
        fail "refusing to remove unmarked installation directory: $INSTALL_ROOT"
    [ "$(sed -n '1p' "$MARKER")" = "runexe-user-installer-v1" ] || \
        fail "refusing to remove an installation directory with an unknown marker."
    rm -rf "$INSTALL_ROOT"
fi

printf 'RunEXE application files were removed.\n'
printf 'Application history and Wine/Proton environments were preserved under %s/runexe.\n' "$DATA_HOME"
