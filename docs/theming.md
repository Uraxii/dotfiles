# Theming

One-line: changing `set $theme <name>` in `.config/sway/prefs` and
reloading sway re-skins sway, GTK, Qt6, waybar, wofi, and the starship
prompt in lock-step.

## Architecture

`sway/prefs` → defines `$theme`, `$font_family`
`sway/config` → includes `themes/$theme/*`, runs `set-theme.sh`
`set-theme.sh` → copies/generates runtime configs from theme data

Non-sway files (CSS, INI) live under `themes/<name>/data/` to avoid sway's include glob parsing them.

## Templates

Configurable values MUST use template system. `.tmpl` extension, `set-theme.sh` does `sed` substitution.

Two placeholder syntaxes (to avoid Go template conflicts in TOML):
- `{{PLACEHOLDER}}` — CSS templates (waybar, wofi)
- `##PLACEHOLDER##` — TOML templates (oh-my-posh, starship)

| Variable | Defined in | Placeholder | Used by |
|----------|-----------|-------------|---------|
| `$font_family` | `sway/prefs` | `{{FONT}}` | `themes/*/data/wofi.css` |
| `$theme` | `sway/prefs` | N/A | `sway/config` include path + `set-theme.sh` arg |
| `$waybar_theme` | `sway/prefs` | N/A | `set-theme.sh` picks layout from `waybar/themes/<name>/` (currently `minimal`) |
| OMP colors | `themes/*/data/omp-colors` | `##PRIMARY##`, `##PATH_BG##`, etc. | `omp/uraxii_atomic.omp.toml.tmpl` |
| Starship palette | `themes/*/data/starship-palette` | `##PALETTE##` | `starship.toml.tmpl` → `~/.config/starship.toml` |

Adding new variable: define in `sway/prefs` → pass to `set-theme.sh` in `sway/config` → receive as positional arg → add `sed` substitution → use placeholder in templates.

## Theme Directory Structure

```
themes/<name>/
├── colors              # Sway color vars
├── window              # Wallpaper, borders (sway syntax)
├── images/             # Wallpapers
└── data/               # Non-sway configs (NOT included by sway)
    ├── gtk-colors.css      # GTK @define-color overrides
    ├── qt-colors.colors    # Qt6ct INI color scheme (⚠️ KDE Plasma footgun — see "KDE Plasma footgun" below)
    ├── waybar-colors.css   # Waybar @define-color block
    ├── wofi.css            # Wofi CSS with {{FONT}} placeholder
    ├── omp-colors          # Shell vars for oh-my-posh ##PLACEHOLDER## substitution
    ├── starship-palette    # Shell var STARSHIP_PALETTE for starship ##PALETTE## sub
    ├── tmux-theme.conf     # Full tmux style overlay (status, window list, panes)
    └── icon-theme          # Icon theme name (e.g. Papirus-Dark)
```

## Runtime Files (generated, NOT tracked)

`set-theme.sh` writes to: `~/.config/gtk-{3,4}.0/colors.css`, `~/.config/waybar/{colors.css,style.css,config,scripts/}`, `~/.config/wofi/style.css`, `~/.config/qt6ct/colors/theme.colors`, `~/.config/omp/uraxii_atomic.omp.toml`, `~/.local/share/tmux/theme.conf`, `~/.config/starship.toml`.

> ⚠️ **KDE Plasma 6 note**: Under Plasma, qt6ct colors are ignored in favor of `~/.config/kdeglobals`. If `QT_QPA_PLATFORMTHEME=qt6ct` leaks into a Plasma session, Qt app colors break. See "KDE Plasma footgun" below for the full footgun write-up.

### Starship cross-system bootstrap

Starship is the active prompt (`.zshrc:24`). Runtime config `~/.config/starship.toml` is owned by two paths:

- **Sway systems**: `set-theme.sh:79-83` regenerates it from `starship.toml.tmpl` + `themes/<name>/starship-palette` on every sway theme switch.
- **Non-sway systems** (or first shell before sway runs): `.zshrc` bootstrap stanza copies the committed `dotfiles/starship.toml` to `~/.config/starship.toml` if missing.

The committed `starship.toml` is a frozen snapshot — a portable default. It is explicitly stow-ignored (`^/starship\.toml$` in `.stow-local-ignore`) so set-theme.sh never writes through a symlink back into the repo. Refresh the snapshot manually when the desired default changes:
```bash
cp ~/.config/starship.toml ~/dotfiles/starship.toml
```

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
6. Update the variable table in the "Templates" section above.

## Generated runtime files

Listed in the "Runtime Files" section above. Not duplicated here.

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
- `sway/scripts/apply-plasma-theme.sh` applies the dotfiles palette to KDE by writing `kdeglobals` and setting the Plasma desktop theme. It runs on every KDE login via `zsh/.zprofile`, so it re-asserts the palette each boot.
- **Per-machine opt-out**: to keep KDE's *own* color scheme (e.g. WhiteSur-dark selected in System Settings) instead of the dotfiles palette, create the sentinel `touch ~/.config/dotfiles-keep-kde-colorscheme`. The script then still aligns GTK/XDG-portal dark mode (Electron/GTK stay dark) but leaves the KDE Qt color scheme and Plasma desktop theme untouched. The file lives outside the repo, so it stays machine-local/untracked.
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
