#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'HELP'
Usage: ./build_binary.sh [--install]

Build a standalone executable at dist/claudefm for the current platform.
Requires uv; the build uses Python 3.12 and PyInstaller 6.22.3.

  --install  Also install the executable to ~/.local/bin/claudefm
  -h, --help Show this help

Set CLAUDEFM_INSTALL_DIR to choose another installation directory.
mpv and yt-dlp remain external audio dependencies.
HELP
}

INSTALL=false
while (($#)); do
    case "$1" in
        --install) INSTALL=true ;;
        -h|--help) usage; exit 0 ;;
        *) printf 'Unknown option: %s\n' "$1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

if ! command -v uv >/dev/null 2>&1; then
    printf 'uv is required to build the binary. Install it from https://docs.astral.sh/uv/\n' >&2
    exit 1
fi

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

printf 'Building standalone claudefm...\n'
uv tool run --python 3.12 --from 'pyinstaller==6.22.3' pyinstaller \
    --onefile --clean --noconfirm --paths "$DIR" --name claudefm \
    --distpath "$DIR/dist" --workpath "$DIR/build/pyinstaller" \
    --specpath "$DIR/build/pyinstaller" "$DIR/bin/claudefm"

BINARY="$DIR/dist/claudefm"
"$BINARY" --version
printf 'Built %s\n' "$BINARY"

if "$INSTALL"; then
    INSTALL_DIR="${CLAUDEFM_INSTALL_DIR:-${HOME}/.local/bin}"
    mkdir -p "$INSTALL_DIR"
    STAGED_BINARY="$(mktemp "$INSTALL_DIR/.claudefm.XXXXXX")"
    trap 'if [[ -f "$STAGED_BINARY" ]]; then unlink "$STAGED_BINARY"; fi' EXIT
    cp "$BINARY" "$STAGED_BINARY"
    chmod 755 "$STAGED_BINARY"
    mv -f "$STAGED_BINARY" "$INSTALL_DIR/claudefm"
    printf 'Installed %s/claudefm\n' "$INSTALL_DIR"
fi
