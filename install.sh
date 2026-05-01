#!/usr/bin/env bash
# Install the Eurorack Faceplate plugin and footprint library into KiCad 10.
# Idempotent — re-running replaces existing symlinks.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KICAD_VERSION="${KICAD_VERSION:-10.0}"

case "$(uname -s)" in
    Linux*)
        CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/kicad/${KICAD_VERSION}"
        ;;
    Darwin*)
        CONFIG_DIR="$HOME/Library/Preferences/kicad/${KICAD_VERSION}"
        ;;
    *)
        echo "Unsupported platform: $(uname -s)" >&2
        echo "Manually symlink:" >&2
        echo "  ${REPO_DIR}/faceplate_plugin -> <kicad-config>/scripting/plugins/faceplate_plugin" >&2
        exit 1
        ;;
esac

PLUGIN_DIR="${CONFIG_DIR}/scripting/plugins"
mkdir -p "${PLUGIN_DIR}"

LINK="${PLUGIN_DIR}/faceplate_plugin"
if [ -L "${LINK}" ] || [ -e "${LINK}" ]; then
    rm -rf "${LINK}"
fi
ln -s "${REPO_DIR}/faceplate_plugin" "${LINK}"
echo "Installed plugin: ${LINK}"
echo "  -> ${REPO_DIR}/faceplate_plugin"
echo
echo "Faceplate footprint library lives at:"
echo "  ${REPO_DIR}/Faceplate.pretty"
echo
echo "Register it as a global library in KiCad:"
echo "  1. Open KiCad → Preferences → Manage Footprint Libraries"
echo "  2. Add a row on the 'Global Libraries' tab:"
echo "       Nickname: Faceplate"
echo "       Library Path: ${REPO_DIR}/Faceplate.pretty"
echo "       Plugin Type: KiCad"
echo
echo "Then in pcbnew: Tools → External Plugins → 'Generate Eurorack Faceplate'."
echo "(You may need 'Refresh Plugins' the first time.)"
