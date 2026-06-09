#!/usr/bin/env bash
# Re-apply Hermes patches after an update that overwrites ~/.hermes/hermes-agent/
# Run: bash ~/dotfiles/.hermes/patches/reapply-after-update.sh
set -euo pipefail

PATCH_DIR="$(cd "$(dirname "$0")" && pwd)"
HERMES_AGENT="$HOME/.hermes/hermes-agent"

echo "→ Re-applying display.py nerd-font icon patch..."
if [ -f "$PATCH_DIR/display-nerd-font-icons.patch" ]; then
    cd "$HERMES_AGENT"
    if git apply --check "$PATCH_DIR/display-nerd-font-icons.patch" 2>/dev/null; then
        git apply "$PATCH_DIR/display-nerd-font-icons.patch"
        echo "  ✓ Patch applied successfully"
    else
        echo "  ⚠ Patch rejected — Hermes source has diverged. Check manually:"
        echo "    diff $HERMES_AGENT/agent/display.py $PATCH_DIR/display-nerd-font-icons.patch"
        exit 1
    fi
else
    echo "  ⚠ Patch file not found at $PATCH_DIR/display-nerd-font-icons.patch"
    exit 1
fi

echo "→ Verifying skin file symlink..."
if [ ! -L "$HOME/.hermes/skins/synthwave-84.yaml" ]; then
    echo "  ⚠ Skin symlink missing — recreate with:"
    echo "    ln -sf ../../dotfiles/.hermes/skins/synthwave-84.yaml ~/.hermes/skins/synthwave-84.yaml"
fi

echo
echo "✓ All patches reapplied. Restart Hermes for changes to take effect."
