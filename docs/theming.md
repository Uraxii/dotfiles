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

The theming pipeline was designed for Sway. Under **KDE Plasma 6**, `QT_QPA_PLATFORMTHEME=qt6ct` (set by `zsh/.zprofile` and `sway/modules/env`) overrides Plasma's own color scheme management. Qt apps pick up the `qt-colors.colors` palette from qt6ct and ignore whatever you set in KDE System Settings.

If you enable the KDE profile or boot into Plasma:

- Plasma applies its own Qt colors via `~/.config/kdeglobals` — qt6ct interferes with this.
- The `.zprofile` guard (`XDG_CURRENT_DESKTOP != KDE`) prevents qt6ct from being set in Plasma. This guard is already in place.
- Applications launched from an older terminal session or systemd user env that still has the variable cached will still use qt6ct until the session ends.
- To apply a dark KDE color scheme manually:
  ```bash
  plasma-apply-colorscheme BreezeDark
  plasma-apply-desktoptheme breeze-dark
  ```
