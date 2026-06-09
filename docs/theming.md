# Theming

One-line: changing `set $theme <name>` in `.config/sway/prefs` and
reloading sway re-skins sway, GTK, Qt6, waybar, wofi, and the starship
prompt in lock-step.

For the full architecture, placeholder-syntax table, theme directory
layout, and the list of generated runtime files, see the root
[`CLAUDE.md`](../CLAUDE.md) "Theming System" section. This file is a
companion howto — it does not duplicate that content.

## Purpose

Practical recipes for extending the theming pipeline.

## Key files

- `.config/sway/prefs` — defines `$theme`, `$font_family`.
- `.config/sway/config` — sources theme + invokes
  `scripts/set-theme.sh "$theme" "$font_family"`.
- `.config/sway/scripts/set-theme.sh` — fan-out script.
- `.config/sway/themes/<name>/` — per-theme assets.

## How to add a theme

1. Copy an existing theme: `cp -r .config/sway/themes/gruvbox
   .config/sway/themes/<new>`.
2. Edit `.config/sway/themes/<new>/colors` (sway color vars) and
   `window` (wallpaper path, border styles).
3. Replace wallpapers in `themes/<new>/images/`.
4. Edit `themes/<new>/data/`:
   - `gtk-colors.css` — `@define-color` overrides.
   - `qt-colors.colors` — Qt6ct INI palette.
   - `waybar-colors.css` — `@define-color` block.
   - `wofi.css` — full CSS (no `@import` support); use `{{FONT}}` for
     font.
   - `starship-palette` — shell-style `STARSHIP_PALETTE="<name>"`
     naming a `[palettes.<name>]` block in
     `.config/starship.toml.tmpl` (see [shell.md](shell.md)). Add the
     matching palette block to the template too.
   - `icon-theme` — bare icon-theme name (e.g. `Papirus-Dark`).
   - `tmux-theme.conf` — full tmux style overrides (status, window
     list, panes, message). Copy from `themes/gruvbox/data/tmux-theme.conf`
     and re-color. `set-theme.sh` copies this to
     `~/.local/share/tmux/theme.conf` and hot-reloads any running
     tmux server.
5. Set `set $theme <new>` in `.config/sway/prefs`, reload sway
   (`$mod+Shift+c`).

## How to add a templated variable

1. Define the variable in `.config/sway/prefs`
   (e.g. `set $cursor_size 24`).
2. Pass it to the theme script in `.config/sway/config` by adding a
   positional arg to the `exec_always` line that calls
   `scripts/set-theme.sh`.
3. Receive it in `set-theme.sh` as a positional arg
   (`VAR="${N:-default}"`).
4. Add a `sed -e "s/{{NAME}}/$VAR/g"` (CSS) or
   `s/##NAME##/$VAR/g` (TOML) substitution in the relevant template
   block.
5. Add the placeholder to the consuming `.tmpl` file.
6. Update the variable table in the root `CLAUDE.md`.

## Generated runtime files

Listed in the root [`CLAUDE.md`](../CLAUDE.md) "Runtime Files"
sub-section. Not duplicated here.

## External dependencies

`bash`, `sed`, `gsettings` (GNOME schemas, for icon theme),
plus all the per-component deps (waybar, wofi, qt6ct, starship).

### KDE Plasma footgun

The theming pipeline was designed for Sway, but KDE Plasma 6 has three separate dark-mode paths that must agree:

1. **Qt/KDE apps** read Plasma colors from `~/.config/kdeglobals` (`[Colors:Window]`, `[Colors:View]`, etc.).
2. **Plasma shell/widgets** read the Plasma desktop theme from `~/.config/plasmarc` (`[Theme] name=...`).
3. **Electron/GTK/libadwaita apps** often read dark-mode preference from GSettings/XDG portals, not from `kdeglobals`.

The footguns:

- `QT_QPA_PLATFORMTHEME=qt6ct` under Plasma overrides KDE's native Qt integration. Qt apps pick up `~/.config/qt6ct/colors/theme.colors` instead of KDE System Settings / `kdeglobals`.
- Fixing only `kdeglobals` is not enough for Electron apps like Notion. They can still see "system light mode" if `org.gnome.desktop.interface color-scheme` or the XDG portal reports light.
- Applications launched before the env/settings fix may keep stale values until restarted. The XDG portal may also need a restart before new Electron apps see the dark preference.

Current intended behavior:

- `.zprofile` must **not** export `QT_QPA_PLATFORMTHEME=qt6ct` in KDE/Plasma sessions.
- `sway/scripts/apply-plasma-theme.sh` applies the dotfiles palette to KDE by writing `kdeglobals` and setting the Plasma desktop theme.
- That script also keeps GTK/XDG portal dark-mode aligned for Electron/GTK apps by setting:
  ```bash
  gsettings set org.gnome.desktop.interface color-scheme prefer-dark
  ```
- For live debugging, restart portals after changing the setting so new Electron apps see it immediately:
  ```bash
  systemctl --user restart xdg-desktop-portal.service xdg-desktop-portal-kde.service
  ```

Diagnostics:

```bash
# Should be unset in KDE
printenv QT_QPA_PLATFORMTHEME
systemctl --user show-environment | grep '^QT_QPA_PLATFORMTHEME='

# KDE/Qt app colors
kreadconfig6 --file ~/.config/kdeglobals --group General --key ColorScheme
grep -A12 '^\[Colors:Window\]' ~/.config/kdeglobals

# Plasma shell theme
grep -A2 '^\[Theme\]' ~/.config/plasmarc

# Electron/GTK/libadwaita dark-mode signal
gsettings get org.gnome.desktop.interface color-scheme
busctl --user call org.freedesktop.portal.Desktop /org/freedesktop/portal/desktop org.freedesktop.portal.Settings Read ss org.freedesktop.appearance color-scheme
```

Portal color-scheme values: `1` means dark, `2` means light. If this reports `2`, apps like Notion will think the system is light even when Plasma itself looks dark.
