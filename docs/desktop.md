# Desktop

Sway-based Wayland desktop with waybar, wofi, swaylock, and
networkmanager-dmenu.

## sway

### Purpose

Tiling Wayland compositor. Repo-managed config split across
`prefs` (user-tunable: `$theme`, `$font_family`, `$mod`), `consts`
(stable identifiers), and `modules/` (per-feature includes).

### Key files

- `.config/sway/config` — entry point; sources `prefs`, `consts`,
  `themes/$theme/*`, `modules/*`, and runs
  `scripts/set-theme.sh "$theme" "$font_family"`.
- `.config/sway/prefs` — user-tunable vars.
- `.config/sway/consts` — stable identifiers.
- `.config/sway/modules/` — `battery`, `display`, `env`, `idle`,
  `keybinds`, `wallpaper`, `waybar`, `windows`.
- `.config/sway/scripts/` — `battery_monitor.sh`, `idle_monitor.sh`,
  `lock_system.sh`, `set-theme.sh`.
- `.config/sway/themes/<name>/` — per-theme `colors`, `window`,
  `images/`, `data/`. See [theming.md](theming.md).

### Keybindings & UX

`$mod` = Mod4 (Super). `$left/$down/$up/$right` = `h/j/k/l`
(vim-style). Source of truth: `.config/sway/modules/keybinds`.

| Bind | Action |
|------|--------|
| `$mod+Return` | Spawn `$term` (ghostty) |
| `$mod+d` | Launch `$menu` (wofi) |
| `$mod+Shift+q` | Kill focused window |
| `$mod+Shift+c` | Reload sway config |
| `$mod+Shift+e` | Exit sway (swaynag confirm) |
| `$mod+h/j/k/l` or arrows | Focus left/down/up/right |
| `$mod+Shift+h/j/k/l` or arrows | Move window |
| `$mod+1..9,0` | Switch to workspace 1..10 |
| `$mod+Shift+1..9,0` | Move container to workspace 1..10 |
| `$mod+v` / `$mod+Shift+v` | splitv / splith |
| `$mod+s` / `$mod+w` / `$mod+e` | stacking / tabbed / toggle split |
| `$mod+f` | Fullscreen |
| `$mod+space` | Focus tiling/floating toggle |
| `$mod+Shift+space` | Floating toggle |
| `$mod+a` | Focus parent |
| `$mod+minus` / `$mod+Shift+minus` | Scratchpad show / move |
| `$mod+r` | Resize mode (hjkl/arrows, 10px) |
| `$mod+b` | Toggle waybar (SIGUSR1) |
| `$mod+Shift+End` | Run `$run_system_lock` |
| `XF86Audio{Mute,Lower,Raise,MicMute}` | pactl sink/source |
| `XF86MonBrightness{Up,Down}` | brightnessctl ±5% |
| `Print` / `Shift+Print` / `Ctrl+Print` | grim full / region / region→clipboard |
| `$mod+Ctrl+V` | Open clipboard history picker (cliphist + wofi) |

Input: `caps:swapescape` xkb option.

### Theming integration

`sway/config` sources `themes/$theme/colors` and `themes/$theme/window`
directly. After include, runs
`scripts/set-theme.sh "$theme" "$font_family"` to fan out non-sway
configs (waybar, wofi, GTK, Qt6ct, oh-my-posh). See
[theming.md](theming.md).

### External dependencies

`sway`, `swayidle`, `swaybg`, `swaylock` (or `swaylock-effects`),
`pulseaudio-utils` (`pactl`), `brightnessctl`, `grim`, `slurp`,
`wl-clipboard` (`wl-paste`, `wl-copy`), `cliphist`.

## waybar

### Purpose

Top status bar. Layout + style sourced from HANCORE-linux/waybar-themes
(vendored under `.config/waybar/themes/`). Active variant selected by
`$waybar_theme` in `sway/prefs`. Colors come from active sway `$theme`
via an Omarchy-compat shim.

### Key files

- `.config/waybar/themes/V*` — HANCORE theme variants
  (`config.jsonc` + `style.css` per theme).
- `.config/waybar/themes/omarchy/current/theme/waybar.css` — Omarchy-shim
  source. Maps HANCORE color names (`@foreground`, `@background`,
  `@red`, `@magenta`, `@base`, `@love`, ...) onto our palette
  (`@bg`, `@fg`, `@accent`, `@urgent`, ...). Deployed at theme switch to
  `~/.config/omarchy/current/theme/waybar.css` because waybar resolves
  HANCORE's relative `@import` from the runtime CSS path, not the repo.
- `.config/waybar/config` — runtime (generated, copy of selected
  HANCORE `config.jsonc`).
- `.config/waybar/style.css` — runtime (generated, copy of selected
  HANCORE `style.css`).
- `.config/waybar/colors.css` — runtime palette (generated from
  `sway/themes/<theme>/data/waybar-colors.css`).
- `.config/waybar/style.css.tmpl.legacy` — retired bespoke style
  template (kept for reference; not consumed by anything).

### Keybindings & UX

Modules: defined per HANCORE theme. Each `V*/config.jsonc` ships its own
module list. To preview themes visually, see the HANCORE repo's
`/showcases/` dir on GitHub.

### Theming integration

Two-axis: `$theme` (palette) and `$waybar_theme` (layout). Both live in
`sway/prefs`. `set-theme.sh` writes:

1. `~/.config/waybar/colors.css` ← `themes/<theme>/data/waybar-colors.css`.
2. `~/.config/omarchy/current/theme/waybar.css` ← Omarchy-shim from repo
   (re-imports `colors.css`, aliases HANCORE color names).
3. `~/.config/waybar/{config,style.css}` ← chosen HANCORE theme.

To switch layout: edit `$waybar_theme` in `sway/prefs`, reload sway.
To switch palette: edit `$theme`, reload sway.

### Omarchy caveat

HANCORE themes target the Omarchy distro. Many `V*/config.jsonc` files
reference Omarchy-specific helper commands and scripts:

- `$OMARCHY_PATH/default/waybar/indicators/{idle,notification-silencing,screen-recording}.sh`
- `omarchy-update-available`, `omarchy-voxtype-status`, `omarchy-theme-current`
- `wttrbar` (weather; installable separately)
- `waybar-module-pacman-updates` (Arch-only)

Missing commands log errors in `journalctl --user`; the bar still
renders and other modules work. Either install the equivalent tools,
stub the scripts, or edit the chosen theme's `config.jsonc` to remove
unwanted custom modules.

### External dependencies

`waybar`, `power-profile-daemon`, `bluez` (+ `blueman` for click),
`networkmanager`, `pavucontrol`, `pamixer`, `brightnessctl`,
NetworkManager + `networkmanager-dmenu`, Nerd Font icons.

## wofi

### Purpose

Wayland app launcher. Also dmenu replacement (used by
`networkmanager-dmenu`).

### Key files

- `.config/wofi/config` — tracked.
- `.config/wofi/style.css` — runtime, generated by
  `set-theme.sh` from `themes/<name>/data/wofi.css`.

### Keybindings & UX

Bound to `$mod+d` via sway `$menu`.

### Theming integration

Per-theme `wofi.css` (no `@import` support, full CSS) FONT-substituted
to runtime path.

### External dependencies

`wofi`.

## swaylock

### Purpose

Screen locker invoked by `scripts/lock_system.sh`.

### Key files

- `.swaylock/config` (empty / inherits sway defaults).
- `.config/sway/scripts/lock_system.sh`.

### Keybindings & UX

`$mod+Shift+End` triggers `$run_system_lock`.

### External dependencies

`swaylock` or `swaylock-effects`.

## networkmanager-dmenu

### Purpose

Wofi-backed NetworkManager UI. Click target for waybar `network`
module.

### Key files

- `.config/networkmanager-dmenu/config.ini`.

### External dependencies

`networkmanager-dmenu`, `networkmanager`, `wofi`.
