# Dotfiles

## Dos
- Recommend safety commits/branches for large changes.

GNU Stow-managed dotfiles. Flat/single-package mode — repo root IS the package, target is `$HOME`.

```bash
stow .          # create symlinks (default target = ..)
stow -R .       # restow after changes
stow -n -v .    # dry run
```

## Repo Structure

```
~/dotfiles/
├── .zshrc                        # Zsh config (starship init + bootstrap, keybinds, aliases)
├── .swaylock/                    # Swaylock config
├── .stow-local-ignore            # Stow ignore patterns (regex)
├── .config/
│   ├── ghostty/                  # Ghostty terminal
│   ├── networkmanager-dmenu/     # Network manager dmenu
│   ├── nvim/                     # Neovim (Kickstart-based, has own CLAUDE.md)
│   ├── omp/                      # Oh My Posh prompt themes (inactive, kept for reference)
│   ├── opencode/                 # OpenCode + Claude Code skills
│   ├── qt6ct/                    # Qt6 theming (qt6ct.conf)
│   ├── starship.toml             # Starship prompt — committed default (bootstrap source)
│   ├── starship.toml.tmpl        # Starship template; set-theme.sh substitutes ##PALETTE##
│   ├── sway/                     # Sway WM (config, modules, themes, scripts)
│   ├── waybar/                   # Waybar (themes/<name>/ + user-overrides.css)
│   └── wofi/                     # Wofi launcher (config only, CSS is runtime)
├── .claude/                      # Claude Code project settings
├── home.nix                      # Nix home-manager config
```

## Stow Ignore

`.stow-local-ignore` controls what stow skips (regex). Currently ignores git files, README/LICENSE, `scripts`, `.claude/settings.local.json`, `.config/starship.toml` (tracked default but managed at runtime by `set-theme.sh` / zshrc bootstrap — must not symlink). Overrides stow defaults — must re-add defaults manually.
## Agent & Skill Files

`.claude/agents/` and `.claude/skills/` are the editable source of truth.
`.config/opencode/agents/` and `.config/opencode/skills/` are symlinks to these.
Edit files directly — no generator.



# Theming System

Changing `set $theme <name>` in `sway/prefs` + sway reload switches sway, GTK, Qt, Waybar, and Wofi together.

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
| Starship palette | `themes/*/data/starship-palette` | `##PALETTE##` | `.config/starship.toml.tmpl` → `~/.config/starship.toml` |

Adding new variable: define in `sway/prefs` → pass to `set-theme.sh` in `sway/config` → receive as positional arg → add `sed` substitution → use placeholder in templates.

## Theme Directory Structure

```
themes/<name>/
├── colors              # Sway color vars
├── window              # Wallpaper, borders (sway syntax)
├── images/             # Wallpapers
└── data/               # Non-sway configs (NOT included by sway)
    ├── gtk-colors.css      # GTK @define-color overrides
    ├── qt-colors.colors    # Qt6ct INI color scheme
    ├── waybar-colors.css   # Waybar @define-color block
    ├── wofi.css            # Wofi CSS with {{FONT}} placeholder
    ├── omp-colors          # Shell vars for oh-my-posh ##PLACEHOLDER## substitution
    ├── starship-palette    # Shell var STARSHIP_PALETTE for starship ##PALETTE## sub
    ├── tmux-theme.conf     # Full tmux style overlay (status, window list, panes)
    └── icon-theme          # Icon theme name (e.g. Papirus-Dark)
```

## Runtime Files (generated, NOT tracked)

`set-theme.sh` writes to: `~/.config/gtk-{3,4}.0/colors.css`, `~/.config/waybar/{colors.css,style.css,config,scripts/}`, `~/.config/wofi/style.css`, `~/.config/qt6ct/colors/theme.colors`, `~/.config/omp/uraxii_atomic.omp.toml`, `~/.local/share/tmux/theme.conf`, `~/.config/starship.toml`.

### Starship cross-system bootstrap

Starship is the active prompt (`.zshrc:24`). Runtime config `~/.config/starship.toml` is owned by two paths:

- **Sway systems**: `set-theme.sh:79-83` regenerates it from `.config/starship.toml.tmpl` + `themes/<name>/starship-palette` on every sway theme switch.
- **Non-sway systems** (or first shell before sway runs): `.zshrc` bootstrap stanza copies the committed `dotfiles/.config/starship.toml` to `~/.config/starship.toml` if missing.

The committed `.config/starship.toml` is a frozen snapshot — a portable default. It is explicitly stow-ignored (`\.config/starship\.toml` in `.stow-local-ignore`) so set-theme.sh never writes through a symlink back into the repo. Refresh the snapshot manually when the desired default changes:
```bash
cp ~/.config/starship.toml ~/dotfiles/.config/starship.toml
```

# Docs

Human-facing per-component docs live in `docs/`. Repo-only — the dir is in `.stow-local-ignore`, never symlinked into `$HOME`.

## Doc inventory

| Component | Doc file |
|-----------|----------|
| sway, waybar, wofi, swaylock, networkmanager-dmenu | `docs/desktop.md` |
| zsh, starship, ghostty | `docs/shell.md` |
| nvim, opencode, systemd/user | `docs/tooling.md` |
| theming pipeline (companion to "Theming System" above) | `docs/theming.md` |

## Doc template

Every component section in `docs/*.md` MUST use these sub-headings (in this order):

1. **Purpose** — one paragraph, what it is and why it's here.
2. **Key files** — bullet list of repo paths the component owns.
3. **Keybindings & UX** — omit if N/A.
4. **Theming integration** — omit if N/A.
5. **External dependencies** — packages required outside this repo.

## Update rule

When a component is added, removed, or materially changed (new module, new keybind, new dependency, new theming hook), update its `docs/*.md` file AND the README inventory table in the same change. Stale docs are worse than missing docs.

## No duplication

- Theming pipeline lives in this file's "Theming System" section. `docs/theming.md` links here, then adds howto recipes only.
- Neovim internals live in `.config/nvim/CLAUDE.md` and `.config/nvim/README.md`. `docs/tooling.md` links — never copies.

# NerdFont Glyphs

Tooling strips high-codepoint UTF-8 on write. Never paste raw glyphs. Use `~/dotfiles/scripts/nerd-glyph`:

- `nerd-glyph emit U+F126` — print bytes (for command substitution / pipes).
- `nerd-glyph sub FILE __TOK__=F126 __TOK2__=E0B6` — replace ASCII tokens in FILE w/ glyph bytes.
- `nerd-glyph check U+F126 [FONT]` — verify codepoint exists in font.

In configs, write tokens (`__GIT__`, `__CAP_L__`, …) then run `nerd-glyph sub`. In shell scripts emit via `printf %b '\xHH\xHH\xHH'`.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
