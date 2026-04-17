#!/bin/bash
THEME="${1:-makima}"
FONT="${2:-0xProto Nerd Font}"
THEME_DIR="$HOME/.config/sway/themes/$THEME/data"
[ ! -d "$THEME_DIR" ] && exit 1

# GTK 3 + 4
[ -f "$THEME_DIR/gtk-colors.css" ] && {
    cp "$THEME_DIR/gtk-colors.css" "$HOME/.config/gtk-3.0/colors.css"
    cp "$THEME_DIR/gtk-colors.css" "$HOME/.config/gtk-4.0/colors.css"
}

# Waybar colors + style
[ -f "$THEME_DIR/waybar-colors.css" ] && \
    cp "$THEME_DIR/waybar-colors.css" "$HOME/.config/waybar/colors.css"
WAYBAR_TMPL="$HOME/.config/waybar/style.css.tmpl"
[ -f "$WAYBAR_TMPL" ] && \
    sed "s/{{FONT}}/$FONT/g" "$WAYBAR_TMPL" > "$HOME/.config/waybar/style.css"

# Wofi (no @import support — full CSS per theme)
[ -f "$THEME_DIR/wofi.css" ] && {
    sed "s/{{FONT}}/$FONT/g" "$THEME_DIR/wofi.css" > "$HOME/.config/wofi/style.css"
}

# Qt6ct
[ -f "$THEME_DIR/qt-colors.colors" ] && {
    mkdir -p "$HOME/.config/qt6ct/colors"
    cp "$THEME_DIR/qt-colors.colors" "$HOME/.config/qt6ct/colors/theme.colors"
}

# Restart waybar
pkill waybar 2>/dev/null
swaymsg exec waybar 2>/dev/null
