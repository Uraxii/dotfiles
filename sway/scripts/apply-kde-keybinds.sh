#!/bin/bash
# Apply Sway-like keyboard shortcuts to KDE Plasma 6.
#
# Replicates the Sway keybindings from ~/.config/sway/modules/keybinds
# as close as KDE allows. Idempotent — safe to run repeatedly.
#
# Usage:
#   ./apply-kde-keybinds.sh
#
# Called from .zprofile on KDE login (alongside apply-plasma-theme.sh).
#
# Sway → KDE mapping:
#   $mod (Super)      ↔ Meta (same key)
#   $mod+Return       ↔ Meta+Return      → ghostty
#   $mod+d            ↔ Meta+d           → wofi (toggle via .desktop entry)
#   $mod+Space        ↔ Meta+Space       → wofi (Spotlight-style alias)
#   (KRunner moves off Meta+d to Alt+Space, kept as a fallback)
#   $mod+h/j/k/l      ↔ Meta+h/j/k/l     → focus window left/down/up/right
#   $mod+arrows       ↔ Meta+arrows      → focus window (same direction)
#   $mod+Shift+h/j/k/l↔ Meta+Shift+h/j/k/l → move window left/down/up/right
#   $mod+Shift+arrows ↔ Meta+Shift+arrows  → move window (same direction)
#   $mod+1-9,0        ↔ Meta+1-9,0       → switch to desktop 1-10
#   $mod+Shift+1-9,0  ↔ Meta+Shift+1-9,0 → window to desktop 1-10
#   $mod+f            ↔ Meta+f           → fullscreen
#   $mod+r            ↔ Meta+r           → resize mode
#   $mod+Ctrl+v       ↔ Meta+Ctrl+v      → clipboard history
#   $mod+L            ↔ Meta+L           → lock (already KDE default)
#   $mod+Shift+End    → no KDE equivalent (swaylock-specific)
#   $mod+minus/scratchpad → no KDE equivalent
#
# Mac-style global/window additions (Meta = Cmd-position key; vim-style kept):
#   Meta+Tab / Meta+Shift+Tab → walk through windows / reverse (⌘Tab)
#   Meta+`                     → cycle windows of current app   (⌘`)
#   Meta+m                     → minimize window                (⌘M)
#   Meta+q                     → close window                   (⌘Q)
#   Meta+o                     → Overview / Exposé (alongside Meta+W)
#
# Conflicts resolved:
#   Meta+1-9 was task manager entries → moved to Meta+Ctrl+1-9
#   Meta+d  was Show Desktop peek     → moved to Meta+Shift+d
#   Meta+arrows was Quick Tile        → moved to Meta+Ctrl+arrows
#   Meta+q  was Activity Switcher     → moved to Meta+Shift+q
#   Meta+m  was Krohnkite monocle     → moved to Meta+Shift+m (if installed)
#   Meta+L remains Lock (already correct)
#
# Deferred to Krohnkite (KWin tiling script), if installed:
#   Meta+h/j/k/l, Meta+Shift+h/j/k/l → tiling focus / move (NOT overridden)
#
# NOTE (Wayland): KWin is the global-shortcut server and reads this config only
# at login, so file edits need a logout/login. To apply live without relogin,
# push each bind via the kglobalaccel D-Bus API (setForeignShortcut).

set -euo pipefail

KDE_GLOBALS="${XDG_CONFIG_HOME:-$HOME/.config}/kglobalshortcutsrc"
TAB=$'\t'
SEP="${TAB}"  # INI tab separator for multi-key shortcuts

# ── Backup ──────────────────────────────────────────────────────────────
if [ -f "$KDE_GLOBALS" ]; then
    BKUP="${KDE_GLOBALS}.bak.$(date +%s)"
    cp "$KDE_GLOBALS" "$BKUP"
    echo "Backed up to $BKUP"
fi

# ── Helpers ─────────────────────────────────────────────────────────────
# Set a KWin shortcut with 1+ key combinations
kwin_sc() {
    local action="$1"; shift
    local default=""
    local current=""
    local sep=""
    for s in "$@"; do
        default="${default}${sep}${s}"
        current="${current}${sep}${s}"
        sep="$SEP"
    done
    # Strip leading separator
    default="${default#$SEP}"
    current="${current#$SEP}"
    kwriteconfig6 --file kglobalshortcutsrc --group kwin \
        --key "$action" "${default},${current},"
}

# Set a plasmashell shortcut
plasma_sc() {
    local action="$1"; shift
    local default=""
    local current=""
    local sep=""
    for s in "$@"; do
        default="${default}${sep}${s}"
        current="${current}${sep}${s}"
        sep="$SEP"
    done
    default="${default#$SEP}"
    current="${current#$SEP}"
    kwriteconfig6 --file kglobalshortcutsrc --group plasmashell \
        --key "$action" "${default},${current},"
}

# For KWin shortcuts that have a known description (keep existing desc)
kwin_sc_desc() {
    local action="$1"; shift
    local desc="$1"; shift
    local default=""
    local current=""
    local sep=""
    for s in "$@"; do
        default="${default}${sep}${s}"
        current="${current}${sep}${s}"
        sep="$SEP"
    done
    default="${default#$SEP}"
    current="${current#$SEP}"
    kwriteconfig6 --file kglobalshortcutsrc --group kwin \
        --key "$action" "${default},${current},${desc}"
}

echo "=== Replicating Sway shortcuts in KDE Plasma 6 ==="

# ── Free up Meta+1-9 from task manager ──────────────────────────────────
echo "  Freeing Meta+1-0 from task manager → Meta+Ctrl+1-0"
for i in $(seq 1 9); do
    kwriteconfig6 --file kglobalshortcutsrc --group plasmashell \
        --key "activate task manager entry $i" "Meta+Ctrl+$i,Meta+Ctrl+$i,"
done
kwriteconfig6 --file kglobalshortcutsrc --group plasmashell \
    --key "activate task manager entry 10" "Meta+Ctrl+0,Meta+Ctrl+0,"

# ── Free up Meta+d from Show Desktop ────────────────────────────────────
# The Meta+D holder is KWin's "Show Desktop" (Peek at Desktop) action — not
# the plasmashell dashboard. Move it aside so Meta+d is free for wofi, and
# clear the dashboard binding so it can't re-claim Meta+Shift+D.
echo "  Moving Show Desktop from Meta+d → Meta+Shift+d"
kwin_sc "Show Desktop" "Meta+Shift+D"
plasma_sc "show dashboard" "none"

# ── Free up Meta+arrows from Quick Tile ─────────────────────────────────
echo "  Moving Quick Tile from Meta+arrows → Meta+Ctrl+arrows"
kwin_sc "Window Quick Tile Left"  "Meta+Ctrl+Left"
kwin_sc "Window Quick Tile Right" "Meta+Ctrl+Right"
kwin_sc "Window Quick Tile Top"   "Meta+Ctrl+Up"
kwin_sc "Window Quick Tile Bottom" "Meta+Ctrl+Down"

# ── Focus movement: $mod+hjkl + $mod+arrows ─────────────────────────────
echo "  Setting focus movement: Meta+h/j/k/l and Meta+arrows"
kwin_sc "Switch Window Left"  "Meta+Left"  "Meta+h"
kwin_sc "Switch Window Down"  "Meta+Down"  "Meta+j"
kwin_sc "Switch Window Up"    "Meta+Up"    "Meta+k"
kwin_sc "Switch Window Right" "Meta+Right" "Meta+l"

# ── Move window: $mod+Shift+hjkl + $mod+Shift+arrows ──────────────────
echo "  Setting window move: Meta+Shift+h/j/k/l and Meta+Shift+arrows"
kwin_sc "Window Pack Left"   "Meta+Shift+Left"  "Meta+Shift+h"
kwin_sc "Window Pack Down"   "Meta+Shift+Down"  "Meta+Shift+j"
kwin_sc "Window Pack Up"     "Meta+Shift+Up"    "Meta+Shift+k"
kwin_sc "Window Pack Right"  "Meta+Shift+Right" "Meta+Shift+l"

# ── Desktop switching: $mod+1-9,0 ──────────────────────────────────────
echo "  Setting desktop switching: Meta+1-9,0"
for i in $(seq 1 9); do
    kwin_sc "Switch to Desktop $i" "Meta+$i"
done
kwin_sc "Switch to Desktop 10" "Meta+0"

# ── Move window to desktop: $mod+Shift+1-9,0 ───────────────────────────
echo "  Setting window-to-desktop: Meta+Shift+1-9,0"
for i in $(seq 1 9); do
    kwin_sc "Window to Desktop $i" "Meta+Shift+$i"
done
kwin_sc "Window to Desktop 10" "Meta+Shift+0"

# ── Conflict relocations (Plasma defaults + Krohnkite) ──────────────────
# These free the bare Meta+q / Meta+m for the Mac actions below by parking the
# default holders on Meta+Shift+<key>. The Krohnkite line is a no-op (harmless
# dangling entry) on machines without the Krohnkite KWin tiling script.
echo "  Relocating conflicting defaults to Meta+Shift+q / Meta+Shift+m"
plasma_sc "manage activities"     "Meta+Shift+Q"   # was Meta+q
kwin_sc   "KrohnkiteMonocleLayout" "Meta+Shift+M"  # was Meta+m (Krohnkite)

# ── Window actions ──────────────────────────────────────────────────────
echo "  Setting window actions"
# Mac ⌘Q close (Meta+Shift+q now belongs to the Activity Switcher above);
# Alt+F4 retained as a universal fallback.
kwin_sc "Window Close"      "Meta+q" "Alt+F4"
kwin_sc "Window Fullscreen" "Meta+f"
kwin_sc "Window Resize"     "Meta+r"
kwin_sc "Window No Border"  "Meta+Shift+b"
# Mac ⌘M minimize (keep KDE default Meta+PgDown as a second combo).
kwin_sc "Window Minimize"   "Meta+m" "Meta+PgDown"

# ── Window cycling (Mac ⌘Tab / ⌘`) ──────────────────────────────────────
# These match the KDE defaults; written explicitly so the layout reproduces
# on machines where the defaults differ. Alt+Tab fallbacks retained.
echo "  Setting window cycling: Meta+Tab, Meta+\`"
kwin_sc "Walk Through Windows"           "Meta+Tab"       "Alt+Tab"
kwin_sc "Walk Through Windows (Reverse)" "Meta+Shift+Tab" "Alt+Shift+Tab"
# Backtick is single-quoted to avoid bash command substitution.
kwin_sc "Walk Through Windows of Current Application" 'Meta+`' 'Alt+`'

# ── Overview / Exposé (Mac Mission Control) ─────────────────────────────
# KDE default is Meta+W; add a memorable Meta+o alias alongside it.
echo "  Setting Overview: Meta+W and Meta+o"
kwin_sc "Overview" "Meta+W" "Meta+o"

# ── Application launchers ───────────────────────────────────────────────
echo "  Setting application shortcuts"
# Meta+Return → ghostty
kwriteconfig6 --file kglobalshortcutsrc \
    --group "services" --group "com.mitchellh.ghostty.desktop" \
    --key "_launch" "Meta+Return,Meta+Return,Launch terminal"

# KRunner: release Meta+d (wofi takes it, like Sway $menu) but keep KRunner
# reachable on Alt+Space as a fallback (calculator, unit conversions, etc.).
kwriteconfig6 --file kglobalshortcutsrc \
    --group "services" --group "org.kde.krunner.desktop" \
    --key "_launch" "Alt+Space,Alt+Space,Run command"

# ── Wofi launcher on Meta+d and Meta+Space ─────────────────────────────────
# Create a .desktop entry for wofi toggle (so we can bind it via kglobalshortcutsrc)
WOFI_DESKTOP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$WOFI_DESKTOP_DIR"
cat > "${WOFI_DESKTOP_DIR}/wofi-toggle.desktop" << 'WOFIEOF'
[Desktop Entry]
Name=Wofi Launcher (toggle)
Comment=Toggle wofi application launcher open/closed
Exec=sh -c 'if pgrep -x wofi >/dev/null; then pkill -x wofi; else wofi --show drun; fi'
Type=Application
Categories=Utility;
Terminal=false
NoDisplay=true
WOFIEOF

# Meta+d (Sway $menu) and Meta+Space (Spotlight-style) → wofi toggle.
# Multiple combos are tab-separated within each kglobalshortcutsrc field.
kwriteconfig6 --file kglobalshortcutsrc \
    --group "services" --group "wofi-toggle.desktop" \
    --key "_launch" "Meta+d${SEP}Meta+Space,Meta+d${SEP}Meta+Space,Launch wofi launcher"

# ── Clipboard history ──────────────────────────────────────────────────
# Sway: $mod+Ctrl+v → cliphist
# KDE already has Meta+V for clipboard, and Meta+Ctrl+X for action popup
# Meta+Ctrl+v is currently clipboard_action — keep it, it's close enough

# ── Screenshots ─────────────────────────────────────────────────────────
# NOT remapped to Meta+Shift+3/4/5 — those collide head-on with the
# Meta+Shift+1-0 "move window to desktop" binds above. KDE's Spectacle
# defaults (Print / Shift+Print / Meta+Print) are kept as-is.

# ── Media keys ─────────────────────────────────────────────────────────
# KDE already handles XF86Audio*, XF86MonBrightness* via kmix/powerdevil.
# No changes needed.

# ── Lock screen ────────────────────────────────────────────────────────
# Sway: $mod+L → swaylock (via swayidle)
# KDE already locks on Meta+L. Keep KDE default.

# ── Reload shortcuts ───────────────────────────────────────────────────
# How shortcuts get reloaded depends on the session:
#
#   • Wayland (Plasma 6): KWin *is* the global-shortcut server. It owns the
#     org.kde.kglobalaccel bus and reads kglobalshortcutsrc only at startup.
#     There is no separate kglobalacceld to restart and no public "reload
#     shortcuts" call — so component shortcuts (Minimize, Close, focus, etc.)
#     and freshly-added service shortcuts only take effect after KWin restarts,
#     i.e. after a LOG OUT / LOG IN. Restarting plasma-kglobalaccel.service here
#     would be a no-op (and earlier left a misleading "reloaded" message).
#
#   • X11: kglobalacceld is a standalone daemon; restarting it reloads the file.
echo "=== Applying changes ==="
if [ "${XDG_SESSION_TYPE:-}" = "wayland" ]; then
    echo "NOTE: Wayland session — KWin reads global shortcuts only at startup."
    echo "      LOG OUT AND BACK IN for the new keybindings to take effect."
elif systemctl --user restart plasma-kglobalaccel.service 2>/dev/null; then
    echo "Shortcuts reloaded (kglobalacceld restarted)."
else
    echo "NOTE: Log out and back in for shortcuts to take effect."
fi

echo ""
echo "Done. Sway-like shortcuts applied to KDE."
echo "  • Meta+Return  → ghostty"
echo "  • Meta+d       → wofi (toggle)"
echo "  • Meta+Space   → wofi (toggle)"
echo "  • Alt+Space    → KRunner (fallback)"
echo "  • Meta+hjkl    → focus window"
echo "  • Meta+arrows → focus window"
echo "  • Meta+Shift+hjkl → move window"
echo "  • Meta+Shift+arrows → move window"
echo "  • Meta+1-0   → switch desktop"
echo "  • Meta+Shift+1-0 → window to desktop"
echo "  • Meta+f     → fullscreen"
echo "  • Meta+r     → resize mode"
echo "  • Meta+q     → close window (⌘Q)"
echo "  • Meta+Shift+b → toggle window border"
echo "  • Meta+Tab / Meta+Shift+Tab → cycle windows"
echo "  • Meta+\`      → cycle windows of current app"
echo "  • Meta+m     → minimize window"
echo "  • Meta+o / Meta+W → Overview"
echo ""
echo "Conflicts resolved:"
echo "  Task manager moved to Meta+Ctrl+1-9"
echo "  Quick Tile moved to Meta+Ctrl+arrows"
echo "  Show Desktop moved to Meta+Shift+d"
echo "  Activity Switcher moved to Meta+Shift+q"
echo "  Krohnkite monocle moved to Meta+Shift+m (if installed)"
echo ""
echo "NOT replicated (no KDE equivalent):"
echo "  scratchpad, split layouts, focus parent, floating toggle"
echo "  layout toggle (stacking/tabbed/split), exit sway"
echo "  swaylock-specific shortcuts"
