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

OpenCode CLI agent stack. Agent model assignments are updated in-place
from `models.defaults` plus optional `models.local` overrides, so
per-machine model changes do not require hand-editing each role file.

### Key files

- `.config/opencode/update-models.py` — updates `model:` frontmatter
  in `.config/opencode/agents/*.md` from `models.defaults` plus optional
  `models.local` overrides.
- `.config/opencode/agent-model-map.cfg` — explicit mapping of
  `agents/*.md` files to `MODEL_*` keys.
- `.config/opencode/models.defaults` — tracked default model
  assignments (shell-style `KEY="value"`).
- `.config/opencode/models.local` — optional per-machine override
  (stow-ignored).
- `.config/opencode/opencode.json` — runtime, generated, stow-ignored.
- `.config/opencode/tools/artifact-slug.ts` — custom OpenCode tool
  (`artifact-slug`) that returns human-readable artifact IDs in the
  form `<slug>-<hex6>`.
- `.config/opencode/tools/artifact-slug.py` — Python helper invoked by
  `artifact-slug` tool.
- `.claude/sdk/artifact-slug-server.ts` — Claude Code Agent SDK MCP
  server that reuses the same Python helper and exposes
  `mcp__pipeline__artifact_slug`.
- `.claude/sdk/artifact-slug-example.ts` — minimal Claude Code Agent SDK
  query example wiring the MCP server into `allowedTools`.
- `.config/opencode/prompts/` — per-agent system prompts.
- `.config/opencode/skills/` — invocable skill definitions
  (incl. `caveman/SKILL.md` instruction file).
- `.config/opencode/rules/` — language and process rule snippets.
- `.config/opencode/templates/` — reusable artifact templates.
- `.config/opencode/themes/` — opencode UI themes.

### Agent roles

Defined in `.config/opencode/agents/*.md`:

| Agent | Mode | Purpose |
|-------|------|---------|
| `orchestrator` | primary | Triage direct vs pipeline; route stages |
| `plan` | all | Scope and task breakdown (no code) |
| `build` | all | Implement production code + tests |
| `researcher` | all | Pre-plan domain research; webfetch |
| `architect` | subagent | ADRs, contracts, tradeoffs |
| `skeptic` | subagent | Critical gatekeeper (includes code-quality review scope) |
| `security-auditor` | subagent | Security gate |
| `tester` | subagent | Test strategy / validation |
| `progenitor` | primary | Creates / evolves agent role definitions |

### Runtime / ignored dirs

Stow-ignored (see `.stow-local-ignore`):
`opencode.json`, `models.local`, `memory/`, `inbox/`, `plans/`,
`projects/`, `messages.md`. The repo also retains `agents_old/` as a
legacy snapshot — not part of the runtime config.

### External dependencies

`opencode` CLI, `python3` (for `update-models.py` and `artifact-slug`
tool helper), Claude Code Agent SDK runtime for `.claude/sdk/*.ts`, and the model
providers configured in `models.defaults`.

## systemd / user

### Purpose

User-level systemd units packaged with the dotfiles.

### Key files

- `.config/systemd/user/sway-low-battery.service` — pairs with
  `.config/sway/scripts/battery_monitor.sh` to alert on low battery.

### External dependencies

`systemd` (user instance).
