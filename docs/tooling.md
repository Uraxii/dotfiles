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

OpenCode CLI agent stack. Generates a runtime `opencode.json` from a
template + model defaults so model assignments can vary per machine
without dirtying the tracked config.

### Key files

- `.config/opencode/gen-config.py` — Python renderer. Loads
  `models.defaults`, then `models.local` (optional override), then
  substitutes `##MODEL_*##` placeholders in `opencode.json.tmpl` and
  writes `opencode.json`.
- `.config/opencode/opencode.json.tmpl` — tracked template.
- `.config/opencode/models.defaults` — tracked default model
  assignments (shell-style `KEY="value"`).
- `.config/opencode/models.local` — optional per-machine override
  (stow-ignored).
- `.config/opencode/opencode.json` — runtime, generated, stow-ignored.
- `.config/opencode/prompts/` — per-agent system prompts.
- `.config/opencode/skills/` — invocable skill definitions
  (incl. `caveman/SKILL.md` instruction file).
- `.config/opencode/rules/` — language and process rule snippets.
- `.config/opencode/templates/` — reusable artifact templates.
- `.config/opencode/themes/` — opencode UI themes.

### Agent roles

Defined in `opencode.json.tmpl`:

| Agent | Mode | Purpose |
|-------|------|---------|
| `orchestrator` | primary | Triage direct vs pipeline; route stages |
| `plan` | all | Scope and task breakdown (no code) |
| `build` | all | Implement production code + tests |
| `researcher` | all | Pre-plan domain research; webfetch |
| `architect` | subagent | ADRs, contracts, tradeoffs |
| `skeptic` | subagent | Critical gatekeeper |
| `reviewer` | subagent | Code-quality review |
| `security-auditor` | subagent | Security gate |
| `tester` | subagent | Test strategy / validation |
| `friction-reviewer` | subagent | Pipeline-process review |
| `monitor` | subagent | Memory hygiene + cross-cutting patterns |
| `progenitor` | primary | Creates / evolves agent role definitions |
| `code-reviewer` | subagent | Manual code-review helper |

### Runtime / ignored dirs

Stow-ignored (see `.stow-local-ignore`):
`opencode.json`, `models.local`, `memory/`, `inbox/`, `plans/`,
`projects/`, `messages.md`. The repo also retains `agents_old/` as a
legacy snapshot — not part of the runtime config.

### External dependencies

`opencode` CLI, `python3` (for `gen-config.py`), and the model
providers configured in `models.defaults`.

## systemd / user

### Purpose

User-level systemd units packaged with the dotfiles.

### Key files

- `.config/systemd/user/sway-low-battery.service` — pairs with
  `.config/sway/scripts/battery_monitor.sh` to alert on low battery.

### External dependencies

`systemd` (user instance).
