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

Top status bar. Layout + style sourced from a vendored upstream theme
under `.config/waybar/themes/<name>/`. Active theme selected by
`$waybar_theme` in `sway/prefs`. Colors come from active sway `$theme`
via the palette pipeline (`.config/waybar/colors.css`).

Waybar runs on the top layer without an exclusive zone, so showing/hiding it
does not resize application windows. This approximates KDE-style dodge behavior
with the existing `$mod+b` toggle: windows can sit underneath the bar, and the
bar draws above them when visible.

The bar background is transparent with semi-transparent module pills. Stock
sway does not support compositor blur behind Waybar; blur would require a
different compositor/fork, so the portable config uses alpha transparency only.

### Key files

- `.config/waybar/themes/minimal/` — ashish-kus/waybar-minimal (current
  only vendored theme). Ships `config.jsonc`, `style.css`, `style2.css`,
  `scripts/` (helper scripts for custom modules).
- `.config/waybar/config` — runtime config (generated; selected theme's
  `config.jsonc` post-stripped).
- `.config/waybar/style.css` — runtime CSS (generated; selected theme's
  `style.css` + appended user-overrides).
- `.config/waybar/colors.css` — runtime palette (generated from
  `sway/themes/<theme>/data/waybar-colors.css`).
- `.config/waybar/scripts/` — runtime copy of selected theme's
  `scripts/` dir (referenced by custom modules at
  `~/.config/waybar/scripts/<name>.sh`).
- `.config/waybar/user-overrides.css` — persistent style overlay
  (font size, padding, etc.). Appended to runtime `style.css` on every
  theme switch. Tracked. Edit this, not the runtime file.
- `.config/sway/scripts/waybar-strip-omarchy.py` — pre-launch sanitizer.
  Drops `custom/*` modules whose `exec` command doesn't resolve on this
  system (Omarchy-only commands, missing scripts, missing binaries).
  Without it, waybar SEGVs in glib when `return-type: json` modules
  receive non-JSON from a failed exec.

### Theming integration

Two-axis: `$theme` (palette) and `$waybar_theme` (layout). Both live in
`sway/prefs`. `set-theme.sh` writes:

1. `~/.config/waybar/colors.css` ← `themes/<theme>/data/waybar-colors.css`.
2. `~/.config/waybar/{config, style.css, scripts/}` ← chosen waybar theme
   (full dir copy; old siblings purged first).
3. Runs `waybar-strip-omarchy.py` over the new config to drop broken
   `custom/*` modules.
4. Appends `user-overrides.css` to runtime `style.css`.

To swap layout: edit `$waybar_theme` in `sway/prefs`, reload sway.
To swap palette: edit `$theme`, reload sway.

### Adding a new waybar theme

1. Drop the upstream theme dir at `.config/waybar/themes/<name>/`
   (must contain `config.jsonc` and `style.css`; optionally `scripts/`).
2. Set `set $waybar_theme <name>` in `.config/sway/prefs`.
3. Reload sway. The stripper runs automatically — modules referencing
   missing commands are removed.

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
- `.config/sway/scripts/toggle-wofi.sh` — toggles the app launcher
  open/closed.

### Keybindings & UX

Bound to `$mod+d` via sway `$menu`; pressing it again closes an existing
`wofi` instance instead of spawning another one.

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
