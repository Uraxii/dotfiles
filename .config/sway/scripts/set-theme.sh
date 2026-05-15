#!/bin/bash
THEME="${1:-makima}"
FONT="${2:-0xProto Nerd Font}"
WAYBAR_THEME="${3:-V1}"
THEME_DIR="$HOME/.config/sway/themes/$THEME/data"
WAYBAR_THEMES_DIR="$HOME/.config/waybar/themes"
[ ! -d "$THEME_DIR" ] && exit 1

# GTK 3 + 4
[ -f "$THEME_DIR/gtk-colors.css" ] && {
    cp "$THEME_DIR/gtk-colors.css" "$HOME/.config/gtk-3.0/colors.css"
    cp "$THEME_DIR/gtk-colors.css" "$HOME/.config/gtk-4.0/colors.css"
}

# Waybar colors — palette per active sway $theme.
[ -f "$THEME_DIR/waybar-colors.css" ] && \
    cp "$THEME_DIR/waybar-colors.css" "$HOME/.config/waybar/colors.css"

# Omarchy-shim — HANCORE themes import "../omarchy/current/theme/waybar.css"
# which resolves from ~/.config/waybar/style.css to ~/.config/omarchy/...
# Deploy the tracked shim there so HANCORE @imports succeed; shim then
# re-imports our colors.css and aliases Omarchy color names to ours.
SHIM_SRC="$HOME/.config/waybar/themes/omarchy/current/theme/waybar.css"
SHIM_DST="$HOME/.config/omarchy/current/theme/waybar.css"
[ -f "$SHIM_SRC" ] && {
    mkdir -p "$(dirname "$SHIM_DST")"
    cp "$SHIM_SRC" "$SHIM_DST"
}

# Waybar layout — pick HANCORE theme by $waybar_theme. Each theme dir ships
# config.jsonc + style.css plus optional sibling palette/scripts
# (rose-pine.css, cava.sh, scrolling-mpris.py, window_pill.py, bob2.svg, ...).
# Some style.css files @import siblings relatively (e.g. ./rose-pine.css)
# which resolve to ~/.config/waybar/ at runtime — so copy the whole dir.
if [ -d "$WAYBAR_THEMES_DIR/$WAYBAR_THEME" ]; then
    # Purge previous theme's sibling files. Preserve: colors.css (palette
    # owned by $theme pipeline), legacy template, dotfiles.
    # -L follows the ~/.config/waybar symlink (stow tree-folded into repo).
    find -L "$HOME/.config/waybar" -maxdepth 1 -type f \
        ! -name 'colors.css' \
        ! -name 'user-overrides.css' \
        ! -name 'style.css.tmpl.legacy' \
        ! -name '.*' \
        -delete 2>/dev/null
    cp -r "$WAYBAR_THEMES_DIR/$WAYBAR_THEME"/. "$HOME/.config/waybar/"
    # Waybar expects "config" at default path, HANCORE ships "config.jsonc".
    [ -f "$HOME/.config/waybar/config.jsonc" ] && \
        mv "$HOME/.config/waybar/config.jsonc" "$HOME/.config/waybar/config"
    # Strip Omarchy-dependent custom modules (omarchy-*, wttrbar,
    # waybar-module-pacman-updates, $OMARCHY_PATH/...). Those exec calls
    # fail on non-Omarchy systems and SEGV waybar when `return-type: json`
    # modules receive non-JSON output.
    STRIPPER="$HOME/.config/sway/scripts/waybar-strip-omarchy.py"
    [ -x "$STRIPPER" ] && python3 "$STRIPPER" "$HOME/.config/waybar/config" 2>/dev/null
    # User overrides — appended at end of style.css (CSS cascade + !important
    # lets us beat per-theme rules without prepending an @import).
    USER_OVERRIDES="$HOME/.config/waybar/user-overrides.css"
    if [ -f "$USER_OVERRIDES" ] && [ -f "$HOME/.config/waybar/style.css" ]; then
        printf '\n/* --- user-overrides.css --- */\n' >> "$HOME/.config/waybar/style.css"
        cat "$USER_OVERRIDES" >> "$HOME/.config/waybar/style.css"
    fi
fi

# Wofi (no @import support — full CSS per theme)
[ -f "$THEME_DIR/wofi.css" ] && {
    sed "s/{{FONT}}/$FONT/g" "$THEME_DIR/wofi.css" > "$HOME/.config/wofi/style.css"
}

# Qt6ct
[ -f "$THEME_DIR/qt-colors.colors" ] && {
    mkdir -p "$HOME/.config/qt6ct/colors"
    cp "$THEME_DIR/qt-colors.colors" "$HOME/.config/qt6ct/colors/theme.colors"
}

# Starship (prompt) — pick palette declared in theme's data/starship-palette
STARSHIP_PALETTE_FILE="$THEME_DIR/starship-palette"
STARSHIP_TMPL="$HOME/.config/starship.toml.tmpl"
[ -f "$STARSHIP_PALETTE_FILE" ] && [ -f "$STARSHIP_TMPL" ] && {
    . "$STARSHIP_PALETTE_FILE"
    sed -e "s/##PALETTE##/${STARSHIP_PALETTE:-catppuccin_mocha}/g" \
        "$STARSHIP_TMPL" > "$HOME/.config/starship.toml"
}

# tmux theme overlay — copy to runtime path + hot-reload running tmux server.
# Runtime path lives under ~/.local/share/ to avoid stow tree-folding the
# .config/tmux/ dir back into the repo via symlink.
[ -f "$THEME_DIR/tmux-theme.conf" ] && {
    mkdir -p "$HOME/.local/share/tmux"
    cp "$THEME_DIR/tmux-theme.conf" "$HOME/.local/share/tmux/theme.conf"
    command -v tmux >/dev/null && tmux info >/dev/null 2>&1 && \
        tmux source-file "$HOME/.local/share/tmux/theme.conf" 2>/dev/null
}

# Icon theme (GTK + Qt)
[ -f "$THEME_DIR/icon-theme" ] && {
    ICON_THEME=$(cat "$THEME_DIR/icon-theme" | tr -d '[:space:]')
    gsettings set org.gnome.desktop.interface icon-theme "$ICON_THEME"
    [ -f "$HOME/.config/qt6ct/qt6ct.conf" ] && \
        sed -i "s/^icon_theme=.*/icon_theme=$ICON_THEME/" "$HOME/.config/qt6ct/qt6ct.conf"
}

# Restart waybar.
#
# Race-safety: on sway reload exec_always re-fires this script while the old
# waybar still holds wlr-layer-shell. `pkill` returns before reap, so a naive
# pkill && exec races (new waybar can't bind, exits silently). Wait for the
# old process to fully die first.
pkill -x waybar 2>/dev/null
for _ in 1 2 3 4 5 6 7 8 9 10; do
    pgrep -x waybar >/dev/null || break
    sleep 0.1
done
pgrep -x waybar >/dev/null && pkill -9 -x waybar 2>/dev/null
swaymsg exec waybar 2>/dev/null
