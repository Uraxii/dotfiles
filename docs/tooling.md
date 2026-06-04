# Tooling

Editor, AI agents, and user-level systemd units.

## nvim

### Purpose

Neovim configuration (Kickstart-derived). Has its own docs — do not
duplicate here.

### Key files

- `.config/nvim/README.md` — install + dependency notes.
- `.config/nvim/CLAUDE.md` — agent-facing internals.

For dependencies (`node`, `fzf`, `gcc`, `go`, `unzip`) and any
nvim-specific guidance, see the linked files above.

### External dependencies

`neovim`. See `.config/nvim/README.md` for the rest.

## opencode

### Purpose

OpenCode CLI agent stack, now mirrored from
`https://github.com/omerxx/dotfiles/tree/master/opencode`.

### Key files

- `opencode/opencode.json` — upstream OpenCode config.
- `opencode/tui.json` — upstream TUI config.
- `opencode/agent/*.md` — upstream agent prompts.
- `opencode/command/{build,scan}.md` — upstream slash commands.
- `opencode/skills/ship/SKILL.md` — upstream shipping skill.

### Agent roles

| Agent | Mode | Purpose |
|-------|------|---------|
| `tech-lead` | primary | Coordinate complex work and specialist routing |
| `big-pickle-simple-tasks` | primary | Break large work into small concrete steps |
| `architect-designer` | subagent | High-level design and architecture |
| `implementation-specialist` | subagent | Precise implementation within existing patterns |
| `requirements-clarifier` | subagent | Clarify vague requirements into specs |
| `test-automation-engineer` | subagent | Write/run tests and verify correctness |

### External dependencies

`opencode` CLI.

## Hermes Agent

### Purpose

Hermes profile prompts mirror the same upstream OpenCode agent prompts, without
the old local pipeline plugin/skill port.

### Key files

- `.hermes/SOUL.md` — default Hermes prompt, mirrored from upstream `tech-lead.md`.
- `.hermes/profiles/*/SOUL.md` — upstream `opencode/agent/*.md` prompts as Hermes profiles.
- `.hermes/skills/caveman/SKILL.md` — output-style skill.
- `.hermes/skills/software-development/graphify/SKILL.md` — graphify helper skill.
- `.hermes/hooks/graphify_advice.sh` — graphify shell advice hook.

### External dependencies

`hermes-agent` (`hermes` CLI).

## systemd / user

### Purpose

User-level systemd units packaged with the dotfiles.

### Key files

- `.config/systemd/user/sway-low-battery.service` — pairs with
  `.config/sway/scripts/battery_monitor.sh` to alert on low battery.

### External dependencies

`systemd` (user instance).
