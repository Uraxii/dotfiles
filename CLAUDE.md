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
├── copilot/skills/               # Curated Copilot CLI skill copies (may diverge from .claude/skills); → ~/.copilot/skills
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

`copilot` (GitHub Copilot CLI) reads `~/.copilot/` (hardcoded, non-XDG). Its dir is full of runtime state (sessions, cache, logs), so only the config subdirs are symlinked into the repo, not the whole dir. Agents point at the parallel `copilot/agents/` tree:
```bash
ln -s ../dotfiles/copilot/agents ~/.copilot/agents   # relative target → ~/dotfiles/copilot/agents
ln -s ../dotfiles/copilot/skills ~/.copilot/skills   # curated skill set (copies of .claude/skills, not symlinks)
```

**zsh + ZDOTDIR**: zsh hardcodes `~/.zshenv` as the one always-loaded file. Create a one-line stub on each machine:
```sh
# ~/.zshenv
export ZDOTDIR="${XDG_CONFIG_HOME:-$HOME/.config}/zsh"
```
After that, zsh loads `.zshrc`, `.zprofile`, etc from `$ZDOTDIR` instead of `$HOME`.

## Stow Ignore

`.stow-local-ignore` controls what stow skips (regex). Ignores: repo meta (`README`, `LICENSE`, `docs`, `CLAUDE.md`, `CONTEXT.md`, `AGENTS.md`, `deps.toml`, `install.py`, `pytest.ini`, `scripts`, `tests`, `home.nix`), VCS files, caches (`__pycache__`, `.ruff_cache`), `.claude/*local*`, `.pipeline`, hermes secrets/runtime, opencode runtime (`memory`, `inbox`, `plans`, `projects`, `models.local`), `tmux/plugins`, `starship.toml` + `.tmpl` (managed by set-theme.sh).

`.stowrc` defines `--target=~/.config` + ignores `.stowrc` itself + `DS_Store`. Stow regex overrides defaults — must re-add defaults manually.
## Agent & Skill Files

`.claude/agents/` and `.claude/skills/` are the Claude Code source of truth.
`.hermes/profiles/` and `.hermes/skills/` are the parallel Hermes source of truth (omerxx-mirrored).
`opencode/agent/`, `opencode/skills/`, `opencode/command/` hold the OpenCode-format copies.
`copilot/agents/*.agent.md` hold the GitHub Copilot CLI copies (symlinked live to `~/.copilot/agents`).
`copilot/skills/` is a curated Copilot skill set — full **copies** of caveman, tdd, handoff, diagnose (with their bundled resources). Skills share Claude's `SKILL.md` format (Copilot reads it natively), so no frontmatter rewrite is needed — but they are copied, not symlinked, because the Copilot versions are expected to diverge from the Claude originals over time. Maintain in parallel like the agent trees. Seed a new one from repo root with `cp -rL .claude/skills/<name> copilot/skills/<name>`, then edit the copy.

`copilot/skills/poc/` is a Copilot-native skill with no Claude original — a thin **launcher** that hands the user's request to the `tech-lead` agent, which orchestrates the specialist fleet. Entry point for the whole multi-agent system: a user types `poc <task>` (or "use the team" / "spin up the tech-lead") and tech-lead triages → phases → delegates → runs the skeptic-gate check. Delegation nests one extra level here (skill → tech-lead → specialist), which Copilot supports.

Frontmatter differs between platforms (Claude Code: `name`/`description`/`model`/`tools`; OpenCode/Hermes: `mode`/`tools: {bash: false}`), so the trees are maintained in parallel rather than symlinked. Edit files directly — no generator.

**Copilot specifics**: filenames are `<name>.agent.md`. Frontmatter drops `model:` — the available model catalog (`claude-haiku-4.5`, `gpt-5-mini`) can't honor the Claude tier intent (opus/sonnet/haiku), so agents inherit the session model; re-pin per-agent once a richer catalog appears. `tools:` uses Copilot's canonical names (`read`, `search`, `edit`, `execute`, `agent`, `web`, `todo` — `Skill` has no equivalent, dropped). Delegation uses the `agent`/`task` tool, not Claude's Agent tool. Tech-lead omits `tools:` so it retains `agent` to spawn specialists.

**Copilot fleet delta**: `codex-implementer`, `codex-skeptic`, and `zakia` are deliberately NOT ported — the codex agents drive a Claude-side Codex bridge, and zakia is the Claude main-thread persona. Copilot's `tech-lead` therefore defaults to `implementation-specialist` and gates on `skeptic-gate` alone. Agent bodies are otherwise byte-for-byte the Claude source below the frontmatter; when a body names a Claude-only affordance (`rotate-agent`, `SendMessage`), the Copilot copy states the behavior in plain prose instead.

## Agent Architecture

- Hub and spoke. `zakia` (main thread) is the sole human-facing orchestrator; it spawns background sub-orchestrators: `tech-lead` (one per software workstream) and `art-director` (one per art workstream). art-director drives ComfyUI over HTTP itself via the `comfyui` skill (`.claude/skills/comfyui/comfyui.py`); there is no separate runner agent, because the poll loop lives in the script and produces no transcript worth isolating.
- Frontend/UI design is its own workstream, run through the `impeccable` skill (invoked by `tech-lead` or `zakia`), which SELF-orchestrates its own specialist fleet: `impeccable-finish-reviewer` (design-internal quality gate, runs outside the build thread), `impeccable-documenter` (records DESIGN.md from the shipped artifact), `impeccable-asset-producer` (raster assets from approved mocks), `impeccable-manual-edit-applier` (live copy-edit batches). zakia/tech-lead never spawn these directly; the skill delegates. See `.claude/refs/orchestration.md` ("Frontend design workstream (impeccable)").
- Agent definitions live in `.claude/agents/`; each file carries only its role-specific delta.
- Two context tiers, and the directory decides which:
  - `.claude/rules/` **auto-loads** into every custom subagent at startup (verified on Claude Code 2.1.220). Files with `paths:` frontmatter load on demand when a matching file is touched; files without it load every session. `output.md` is global by design; the language rules are `paths:`-scoped.
  - `.claude/refs/` **never auto-loads**. Agents pull these with an explicit Read. `orchestration.md` (agent roster) and `code-quality.md` live here so they reach only the agents that need them, instead of every agent regardless of role.
- Agent bodies reference `~/.claude/refs/<file>.md` by tilde path and expand `~` themselves; the Read tool needs an absolute path. `@`-imports do NOT expand inside agent definition bodies, so never rely on them there.
- `codex-implementer`'s heredoc must keep a real on-disk path: Codex is a different vendor's model and receives none of Claude Code's auto-loaded context.
- Deployment: stow creates per-file symlinks. A NEW file under `.claude/` needs a restow (`stow .` from repo root) or a matching manual symlink before `~/.claude` sees it.

## Per-project agent workspace (board + knowledge base)

Every project an agent works in gets the same scaffold, so a fresh or compacted orchestrator can rebuild its state from disk instead of from conversation history. Doctrine lives in `.claude/refs/orchestration.md` ("Per-project standard shape", "Board substrate", "KB distillation rule"); this section is the pointer + the tooling that implements it.

```
docs/kb/        distilled markdown KB entries: tracked, durable, human-readable.
workstreams/    per-workstream status.md + artifacts.
kb.db           SQLite FTS5 index over docs/kb/. Local/regenerable, gitignored.
```

Boards live centrally under `~/.beads-hub`, never in the repo (root is `~/.beads-hub`, not `~/.beads`: bd 1.1.0 refuses `bd init` under any `.beads`-named ancestor). Layout: `~/.beads-hub/hub/.beads` is the bd multi-repo aggregator; `~/.beads-hub/<name>/.beads` is one board per project (prefix `<name>`). the `agent-workbench` skill's `hub` subcommand (`agent-workbench hub {init,add,sync,list,path,status}`, invoked at `.claude/skills/agent-workbench/agent-workbench`, root override `BEADS_HUB_DIR`) manages them: `hub add <name>` creates + registers a project board, `hub sync` (`bd repo sync`) hydrates all into the aggregator, `hub list` shows them, `hub path <name>` prints a board's `BEADS_DIR`. Agents write to a project board via `BEADS_DIR=$(agent-workbench hub path <name>) bd ...`; the aggregator is the cross-project READ view. Doctrine: `.claude/refs/orchestration.md` ("Board substrate").

- `agent-workbench init-workspace [TARGET_DIR]` scaffolds the shape idempotently: creates + registers the project's board under `~/.beads-hub` (via `agent-workbench hub add`, using `bd init --stealth --skip-agents --skip-hooks` under the hood, no CLAUDE.md/AGENTS.md/hooksPath side effects), plus `docs/kb/`, `workstreams/`, a first `kb.db` build, and a git `post-commit` hook.
- `scripts/build-kb-index.py [--root DIR] [--db PATH]` is the no-LLM FTS5 indexer (stdlib `sqlite3` only). Full rebuild from `docs/kb/*.md` on every run; safe to call standalone or from the post-commit hook.
- The post-commit hook (installed into the target repo's `.git/hooks/post-commit`, untracked) reindexes `kb.db` only when the commit touched `docs/kb/`; a no-op otherwise. If a post-commit hook already exists there, the installer warns instead of overwriting it.
- Distillation is in-context: the agent that owns a ticket or workstream writes its own KB entry right before it terminates or rotates. No dedicated distiller agent; retrieval sweeps use `knowledge-scout` instead.

## Knowledgebase (`~/.knowledgebase`)

Durable distilled memory, personal + machine-local (Obsidian vault, NOT in any repo, NOT git-tracked), superseding per-repo `docs/kb/` as the home for lasting knowledge. Mirrors the `~/.beads-hub` split: source under `~/.knowledgebase/<project>/{decisions,notes,research,sources}/`, one global index at `~/.knowledgebase/index/kb.db`. Note types: `decision | resolution | research | domain | architecture | gotcha | source`; all share one frontmatter schema (`type,title,source,author,site,published,fetched,description,tags,project,status,question,summary` + body + `## Refs`). Web sources are STORED (content + metadata), captured DETERMINISTICALLY with zero model spend; classifiers/embeddings run afterward. Full doctrine: `.claude/refs/orchestration.md` ("Knowledgebase").

- `agent-workbench kb {init,add,path,index,clip,status}` (root override `KB_HOME`): `init` makes the vault + `index/`; `add <project>` makes the 4 subdirs; `clip <url> [--project P]` deterministically fetches + extracts a `type: source` note; `index` rebuilds the global FTS5 index.
- `scripts/kb-index.py` is the no-LLM global FTS5 indexer (stdlib `sqlite3`) over `~/.knowledgebase/<project>/**`, uniform row schema, `query "<terms>" [--project P] [--type T] [--all]`.
- `scripts/kb-clip.py` is the deterministic web capture: `urllib` fetch -> Open Graph / Schema.org JSON-LD / meta / `readability-lxml` -> `type: source` note (`question`/`summary` left empty for a later classifier). Dep: `readability-lxml` (user-site); stdlib densest-block fallback on any readability error.
- `docs/kb-clipper-template.json` is the importable Obsidian Web Clipper template (same schema; `tags` fed by `{{meta:name:keywords}}`), for the human browse-and-clip path into `<project>/sources/`.

## Path Standard (enforced by pre-commit hook)

- Never commit expanded home paths or usernames. Use `$HOME` in shell scripts, `~` in markdown/JSON.
- Machine-specific or identity-bearing config (tailnet hosts, emails) goes in `.claude/settings.local.json` (gitignored), never in tracked files.

## Commit Gate

- Local pre-commit hook: thin wrapper in `.git/hooks`, logic at `spikes/commit-linter/lint-staged.sh`.
- Runs an identity-leak lint (with auto-fix) plus a fail-closed TruffleHog scan of staged content. `trufflehog` binary required at `~/.local/bin`.
- Hooks not firing: check `git config core.hooksPath` (bd init once hijacked it).
- Emergency bypass: `git commit --no-verify`. Never for secret findings.

## Spikes

- `spikes/<name>/` are durable, committed prototype workspaces with their own READMEs. Current: `advisor-vision`, `commit-linter`. (bdui moved out to `scripts/bdui-container/`; comfyui-driver promoted to `.claude/skills/comfyui/`.)
- Runtime junk (node_modules, testbeds) is gitignored.
- Agents use spikes as scratch/spike workspaces, never `/tmp`.

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
    ├── qt-colors.colors    # Qt6ct INI color scheme (⚠️ KDE Plasma footgun — see docs/theming.md)
    ├── waybar-colors.css   # Waybar @define-color block
    ├── wofi.css            # Wofi CSS with {{FONT}} placeholder
    ├── omp-colors          # Shell vars for oh-my-posh ##PLACEHOLDER## substitution
    ├── starship-palette    # Shell var STARSHIP_PALETTE for starship ##PALETTE## sub
    ├── tmux-theme.conf     # Full tmux style overlay (status, window list, panes)
    └── icon-theme          # Icon theme name (e.g. Papirus-Dark)
```

## Runtime Files (generated, NOT tracked)

`set-theme.sh` writes to: `~/.config/gtk-{3,4}.0/colors.css`, `~/.config/waybar/{colors.css,style.css,config,scripts/}`, `~/.config/wofi/style.css`, `~/.config/qt6ct/colors/theme.colors`, `~/.config/omp/uraxii_atomic.omp.toml`, `~/.local/share/tmux/theme.conf`, `~/.config/starship.toml`.

> ⚠️ **KDE Plasma 6 note**: Under Plasma, qt6ct colors are ignored in favor of `~/.config/kdeglobals`. If `QT_QPA_PLATFORMTHEME=qt6ct` leaks into a Plasma session, Qt app colors break. See [`docs/theming.md`](docs/theming.md) for the full footgun write-up.

### Starship cross-system bootstrap

Starship is the active prompt (`.zshrc:24`). Runtime config `~/.config/starship.toml` is owned by two paths:

- **Sway systems**: `set-theme.sh:79-83` regenerates it from `starship.toml.tmpl` + `themes/<name>/starship-palette` on every sway theme switch.
- **Non-sway systems** (or first shell before sway runs): `.zshrc` bootstrap stanza copies the committed `dotfiles/starship.toml` to `~/.config/starship.toml` if missing.

The committed `starship.toml` is a frozen snapshot — a portable default. It is explicitly stow-ignored (`^/starship\.toml$` in `.stow-local-ignore`) so set-theme.sh never writes through a symlink back into the repo. Refresh the snapshot manually when the desired default changes:
```bash
cp ~/.config/starship.toml ~/dotfiles/starship.toml
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
