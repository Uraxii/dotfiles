#!/bin/bash
# Apply dotfiles theme colors to KDE Plasma.
# Called by .zprofile on KDE Plasma login. Idempotent — no-op if theme
# hasn't changed since last run.
#
# Reads the current theme's qt-colors.colors and writes the colors
# directly to ~/.config/kdeglobals, then notifies running apps via DBus.

set -euo pipefail

# ── Resolve theme ──────────────────────────────────────────────────────
ACTIVE_THEME="${ACTIVE_THEME:-gruvbox}"
PALETTE_SRC="${XDG_CONFIG_HOME:-$HOME/.config}/sway/themes/$ACTIVE_THEME/data/qt-colors.colors"
PLASMA_SCHEME_NAME="Dotfiles-$ACTIVE_THEME"
COLOR_SCHEMES_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/color-schemes"
OUTPUT="$COLOR_SCHEMES_DIR/$PLASMA_SCHEME_NAME.colors"
STAMP="$COLOR_SCHEMES_DIR/.$PLASMA_SCHEME_NAME.stamp"
KDGLOBALS="${XDG_CONFIG_HOME:-$HOME/.config}/kdeglobals"

mkdir -p "$COLOR_SCHEMES_DIR"

if [ ! -f "$PALETTE_SRC" ]; then
    # No theme palette — fall back to BreezeDark
    plasma-apply-colorscheme BreezeDark 2>/dev/null || true
    plasma-apply-desktoptheme breeze-dark 2>/dev/null || true
    exit 0
fi

# ── Check if theme changed ─────────────────────────────────────────────
PALETTE_HASH=$(sha256sum "$PALETTE_SRC" | cut -d' ' -f1)
if [ -f "$STAMP" ] && [ "$(cat "$STAMP")" = "$PALETTE_HASH" ]; then
    exit 0
fi

# Generate KDE .colors file (correct CamelCase keys)
{
    currently=""
    while IFS= read -r line; do
        case "$line" in
            '['*)
                case "$line" in
                    '[ColorEffects:'*|'[Colors:'*|'[WM]'*)
                        currently="keep"
                        echo "$line"
                        ;;
                    '['*)
                        currently="skip"
                        ;;
                esac
                ;;
            *)
                [ "$currently" = "keep" ] && [ -n "$line" ] && echo "$line"
                ;;
        esac
    done < "$PALETTE_SRC"
    cat <<EOF
[General]
ColorScheme=$PLASMA_SCHEME_NAME
Name=$PLASMA_SCHEME_NAME
shadeSortColumn=true
EOF
} > "$OUTPUT"

# ── Inject colors into kdeglobals ──────────────────────────────────────
python3 -c "
import configparser, os, subprocess, sys

src = '$PALETTE_SRC'
kdg = '$KDGLOBALS'
name = '$PLASMA_SCHEME_NAME'

# Read palette
palette = configparser.ConfigParser(strict=False)
palette.read(src)

# Read existing kdeglobals
existing = configparser.ConfigParser(strict=False)
existing.optionxform = str  # preserve key casing
existing.read(kdg)

# Remove old color sections from our scheme
for s in list(existing.sections()):
    if s.startswith('ColorEffects:') or s.startswith('Colors:') or s == 'WM':
        existing.remove_section(s)

# Inject new color sections from palette (preserves original key casing)
for s in palette.sections():
    if s.startswith('ColorEffects:') or s.startswith('Colors:') or s == 'WM':
        existing.add_section(s)
        for k, v in palette.items(s):
            existing[s][k] = v

# Set scheme name
if not existing.has_section('General'):
    existing.add_section('General')
existing['General']['ColorScheme'] = name

# Remove stale hash so Plasma re-reads the scheme
if existing.has_option('General', 'ColorSchemeHash'):
    existing.remove_option('General', 'ColorSchemeHash')

with open(kdg, 'w') as f:
    existing.write(f)

# Notify running apps via DBus (same signal plasma-apply-colorscheme sends)
try:
    subprocess.run([
        'dbus-send', '--session', '--dest=org.kde.GtkConfig',
        '/GtkConfig', 'org.kde.GtkConfig.setColorScheme',
        'string:' + name
    ], capture_output=True, timeout=5)
except Exception:
    pass

try:
    subprocess.run([
        'dbus-send', '--session', '--dest=org.kde.plasma.GlobalTheme',
        '/ Plasma', 'org.kde.plasma.GlobalTheme.colorSchemeChanged',
        'string:' + name
    ], capture_output=True, timeout=5)
except Exception:
    pass

print('Applied color scheme:', name)
"

# ── Write stamp ────────────────────────────────────────────────────────
echo "$PALETTE_HASH" > "$STAMP"

# ── Apply Plasma desktop theme ─────────────────────────────────────────
plasma-apply-desktoptheme breeze-dark 2>/dev/null || true