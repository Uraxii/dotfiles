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

# Oh My Posh
OMP_COLORS="$THEME_DIR/omp-colors"
OMP_TMPL="$HOME/.config/omp/uraxii_atomic.omp.toml.tmpl"
[ -f "$OMP_COLORS" ] && [ -f "$OMP_TMPL" ] && {
    . "$OMP_COLORS"
    sed -e "s/##PRIMARY##/$OMP_PRIMARY/g" \
        -e "s/##PATH_BG##/$OMP_PATH_BG/g" \
        -e "s/##PATH_FG##/$OMP_PATH_FG/g" \
        -e "s/##GIT_BG##/$OMP_GIT_BG/g" \
        -e "s/##GIT_FG##/$OMP_GIT_FG/g" \
        -e "s/##GIT_DIRTY##/$OMP_GIT_DIRTY/g" \
        -e "s/##GIT_AHEAD##/$OMP_GIT_AHEAD/g" \
        -e "s/##MUTED##/$OMP_MUTED/g" \
        -e "s/##OS_BG##/$OMP_OS_BG/g" \
        -e "s/##FG_DARK##/$OMP_FG_DARK/g" \
        -e "s/##FG##/$OMP_FG/g" \
        -e "s/##ERROR##/$OMP_ERROR/g" \
        "$OMP_TMPL" > "$HOME/.config/omp/uraxii_atomic.omp.toml"
}

# Icon theme (GTK + Qt)
[ -f "$THEME_DIR/icon-theme" ] && {
    ICON_THEME=$(cat "$THEME_DIR/icon-theme" | tr -d '[:space:]')
    gsettings set org.gnome.desktop.interface icon-theme "$ICON_THEME"
    [ -f "$HOME/.config/qt6ct/qt6ct.conf" ] && \
        sed -i "s/^icon_theme=.*/icon_theme=$ICON_THEME/" "$HOME/.config/qt6ct/qt6ct.conf"
}

# Restart waybar
pkill waybar 2>/dev/null
swaymsg exec waybar 2>/dev/null
