# Dotfiles

## Dos
- Recommend safety commits/branches for large changes.

GNU Stow-managed dotfiles. Omerxx-style XDG layout — repo root contents land in `~/.config/` (target set via `.stowrc`).

```bash
./setup.sh      # runs `stow .`
```

`setup.sh` is near-stock — just `stow .`. All shell configs are XDG-native (`zsh/`, `xonsh/`). Two AI tools (claude-code, hermes) hardcode `~/.foo` paths; they get a one-time manual symlink per machine (see README "First-time setup").

## Repo Structure

```
~/dotfiles/
├── .stowrc                       # --target=~/.config (omerxx model)
├── .stow-local-ignore            # Stow ignore patterns (regex)
├── setup.sh                      # IGNORED — just runs `stow .`
├── ghostty/                      # → ~/.config/ghostty/
├── networkmanager-dmenu/         # → ~/.config/networkmanager-dmenu/
├── nvim/                         # → ~/.config/nvim/   (Kickstart-based, has own CLAUDE.md)
├── omp/                          # → ~/.config/omp/    (inactive, kept for reference)
├── opencode/                     # → ~/.config/opencode/  (+ Claude Code skills)
├── copilot/agents/               # GitHub Copilot CLI agents (*.agent.md); symlinked to ~/.copilot/agents
├── copilot/skills/               # Curated Copilot CLI skill copies (real copies only, no symlinks; diverge from .claude/skills by design); → ~/.copilot/skills
├── qt6ct/                        # → ~/.config/qt6ct/
├── sway/                         # → ~/.config/sway/
├── swaylock/                     # → ~/.config/swaylock/   (XDG-native)
├── systemd/                      # → ~/.config/systemd/
├── tmux/                         # → ~/.config/tmux/
├── waybar/                       # → ~/.config/waybar/
├── wofi/                         # → ~/.config/wofi/
├── xonsh/rc.xsh                  # → ~/.config/xonsh/rc.xsh   (xonsh native XDG path)
├── zsh/.zshrc                    # → ~/.config/zsh/.zshrc     (loaded via $ZDOTDIR; see ~/.zshenv stub)
├── zsh/.zprofile                 # → ~/.config/zsh/.zprofile
├── starship.toml                 # IGNORED — managed at runtime by set-theme.sh
├── starship.toml.tmpl            # IGNORED — template, set-theme.sh substitutes ##PALETTE##
├── .claude/                      # → ~/.config/.claude/   (hardcoded path; one-time symlink ~/.claude → here)
├── .hermes/                      # → ~/.config/.hermes/   (hardcoded path; one-time symlink ~/.hermes → here)
├── home.nix                      # IGNORED (repo meta)
```

**Hardcoded-path tools**: `claude-code` reads `~/.claude/`, `hermes` reads `~/.hermes/`. Neither honors XDG. One-time per-machine symlink:
```bash
ln -s ~/.config/.claude ~/.claude
ln -s ~/.config/.hermes ~/.hermes
```

`copilot` (GitHub Copilot CLI) reads `~/.copilot/` (hardcoded, non-XDG). Its dir is full of runtime state (sessions, cache, logs), so only the config subdirs are symlinked into the repo, not the whole dir. Run `copilot/install.sh` once per machine: it symlinks `agents`, `skills`, `instructions`, `refs`, and `copilot-instructions.md` into `~/.copilot/`, verifying each source exists first and refusing to clobber or silently relink an existing path (see [`docs/agents.md`](docs/agents.md) "Agent & Skill Files" for the full contract).

**zsh + ZDOTDIR**: zsh hardcodes `~/.zshenv` as the one always-loaded file. Create a one-line stub on each machine:
```sh
# ~/.zshenv
export ZDOTDIR="${XDG_CONFIG_HOME:-$HOME/.config}/zsh"
```
After that, zsh loads `.zshrc`, `.zprofile`, etc from `$ZDOTDIR` instead of `$HOME`.

## Stow Ignore

`.stow-local-ignore` controls what stow skips (regex). Ignores: repo meta (`README`, `LICENSE`, `docs`, `CLAUDE.md`, `CONTEXT.md`, `AGENTS.md`, `deps.toml`, `install.py`, `pytest.ini`, `scripts`, `tests`, `home.nix`), VCS files, caches (`__pycache__`, `.ruff_cache`), `.claude/*local*`, `.pipeline`, hermes secrets/runtime, opencode runtime (`memory`, `inbox`, `plans`, `projects`, `models.local`), `tmux/plugins`, `starship.toml` + `.tmpl` (managed by set-theme.sh).

`.stowrc` defines `--target=~/.config` + ignores `.stowrc` itself + `DS_Store`. Stow regex overrides defaults — must re-add defaults manually.
## Agent & Skill Stack

- `.claude/rules/` auto-loads into every subagent; `.claude/refs/` never auto-loads (agents pull it with an explicit Read).
- `.claude/agents/` and `.claude/skills/` are the Claude Code source of truth; `.hermes/`, `opencode/`, and `copilot/` are separate, deliberately-diverging manual copies (no generator, no symlink).
- Boards live under `~/.beads-hub`; the personal knowledgebase lives under `~/.knowledgebase`. Both are driven only through `$HOME/.claude/skills/agent-workbench/agent-workbench`, never written to directly.
- A new file under `.claude/` needs a restow (`stow .` from repo root) before `~/.claude` sees it.

Full doctrine (platform-porting rules, hub-and-spoke orchestration, per-project workspace scaffold, knowledgebase schema): [`docs/agents.md`](docs/agents.md).

## Path Standard (enforced by pre-commit hook)

- Never commit expanded home paths or usernames. Use `$HOME` in shell scripts/JSON, `~` in markdown.
- Machine-specific or identity-bearing config (tailnet hosts, emails) goes in `.claude/settings.local.json` (gitignored), never in tracked files.

## Commit Gate

- Local pre-commit hook: thin wrapper in `.git/hooks`, logic at `scripts/commit-linter/lint_staged.py`.
- Runs an identity-leak lint (with auto-fix) plus a fail-closed TruffleHog scan of staged content. `trufflehog` binary required at `~/.local/bin`.
- Hooks not firing: check `git config core.hooksPath` (bd init once hijacked it).
- Emergency bypass: `git commit --no-verify`. Never for secret findings.

## Spikes

- `spikes/<name>/` are local, untracked scratch/prototype workspaces.
- `spikes/` is gitignored wholesale; nothing under it is committed.
- Agents use spikes for repo-adjacent scratch work instead of `/tmp`.

# Theming System

Changing `set $theme <name>` in `sway/prefs` + sway reload switches sway, GTK, Qt, Waybar, and Wofi together. Configurable values MUST use the `.tmpl` + `sed` template system. Runtime outputs (`~/.config/waybar/*`, `~/.config/starship.toml`, etc) are generated and NOT tracked.

Full architecture, placeholder tables, theme directory layout, and howto recipes: [`docs/theming.md`](docs/theming.md).

# Docs

Component added/removed/materially changed => update its `docs/*.md` file AND the README inventory table in the same change.

Full doc contract (inventory, template, no-duplication rule): [`docs/conventions.md`](docs/conventions.md).

# NerdFont Glyphs

Tooling strips high-codepoint UTF-8 on write. Never paste raw glyphs. Use `~/dotfiles/scripts/nerd-glyph`:

- `nerd-glyph emit U+F126` — print bytes (for command substitution / pipes).
- `nerd-glyph sub FILE __TOK__=F126 __TOK2__=E0B6` — replace ASCII tokens in FILE w/ glyph bytes.
- `nerd-glyph check U+F126 [FONT]` — verify codepoint exists in font.

In configs, write tokens (`__GIT__`, `__CAP_L__`, …) then run `nerd-glyph sub`. In shell scripts emit via `printf %b '\xHH\xHH\xHH'`.
