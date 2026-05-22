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

Defined via SSoT in `.pipeline/_shared/agents/`. Both `.claude/agents/` and
`.config/opencode/agents/` are generated — do NOT hand-edit. See "Pipeline SSoT"
section below.

| Agent | Mode | Purpose |
|-------|------|---------|
| `orchestrator` | primary | Triage direct vs pipeline; route stages |
| `plan` | subagent | Scope and task breakdown (no code) |
| `build` | subagent | Implement production code + tests |
| `architect` | subagent | ADRs, contracts, tradeoffs |
| `skeptic` | subagent | Critical gatekeeper |
| `security-auditor` | subagent | Security gate |
| `tester` | subagent | Test strategy / validation |
| `reviewer` | subagent | Two-axis code review (Standards + Spec) |
| `researcher` | subagent | Pre-plan domain research; webfetch |
| `ui-ux-designer` | subagent | Frontend handoff |
| `friction-reviewer` | subagent | End-of-run doctrine audit |
| `progenitor` | primary | Creates / evolves agent role definitions |
| `content-designer` | subagent | Pre-plan ideation |

### Runtime / ignored dirs

Stow-ignored (see `.stow-local-ignore`):
`opencode.json`, `models.local`, `inbox/`, `plans/`,
`projects/`, `messages.md`.

## Pipeline (Claude + OpenCode)

### Purpose

Agentic pipeline. Agent and skill files at `.claude/agents/*.md` and `.claude/skills/<name>/SKILL.md` are the editable source of truth. `.config/opencode/agents/` and `.config/opencode/skills/` are symlinks to those Claude trees — both platforms read the same files.

Monitor agent has been retired.

Memory subsystem removed (2026-05-13). Lessons live in project doctrine (`CLAUDE.md`, `.claude/rules/`, ADRs, agent spec edits). No per-role memory files; no curation skill.

### Key files

- `.claude/agents/*.md` — agent definitions.
- `.claude/skills/<name>/SKILL.md` — skill definitions.
- `.claude/templates/role-template.md` — authoring template.
- `.config/opencode/tools/` — custom OC tools paired with Claude skills (see Custom tools table).
- `.config/opencode/opencode.json` — OC permissions + agent task allow-list. Hand-edited.
- `.config/opencode/commands/*.md` — slash commands.

### Custom tools

| Tool | Permission |
|------|-----------|
| `artifact-slug` | allow |
| `verdict-parse` | allow |
| `handoff-doc` | allow |
| `test-path-resolve` | allow |
| `prod-diff-sha` | allow |
| `worktree-lifecycle` | allow |

### Skill classification

- **Arg-less SKILL.md** (shared to both trees): `caveman`, `frontend-design`, `agent-brief-format`.
- **Claude SKILL.md + OC custom tool**: `verdict-parse`, `handoff-doc`, `test-path-resolve`, `prod-diff-sha`, `worktree-lifecycle`, `artifact-slug`.

### OPENCODE_DISABLE_CLAUDE_CODE=1 requirement

Set this env var in your shell rc to disable OC's Claude-compat fallback:
```bash
export OPENCODE_DISABLE_CLAUDE_CODE=1
```

**Rationale**: Without this, OC also scans `~/.claude/skills/` and project
`CLAUDE.md` via its Claude-compat discovery path, potentially double-loading
skills and instructions that are already explicitly declared in `opencode.json`
`instructions:` array. Setting the env var makes the explicit `opencode.json`
`instructions:` array the SOLE load path for both CLAUDE.md and skills.

See also: `CLAUDE.md` → "Pipeline SSoT" section.

### E8 empirical findings (bash matcher semantics + env-var)

**E8 sub-task (a) — bash permission matcher semantics**:

Source analysis of OC binary (v1.14.41, ELF/Bun bundle) shows:
- `permission.bash` is `{[key: string]: "ask"|"allow"|"deny"}` where keys are **raw glob patterns** matched against the full command string.
- Pattern `*` = zero or more chars, `?` = one char (minimatch-style).
- Matching is raw-string-glob on the **full command string** — NOT shell-tokenized before matching.
- Injection risk: pattern `python3 .../foo.py *` would match `python3 .../foo.py arg; touch /tmp/INJ` since `*` matches everything after the prefix.
- **Conclusion**: raw-string-prefix glob matching (NOT shell-tokenized).
- **Per §1.5-S8-gate**: ALL wildcard-bearing `allow` patterns demoted to `ask` as a permanent constraint. This is documented in `opencode.json`.

**E8 sub-task (b) — `OPENCODE_DISABLE_CLAUDE_CODE=1` and explicit `instructions:` array**:

Source analysis of OC binary shows:
```javascript
// OPENCODE_DISABLE_CLAUDE_CODE sets q=true
// q disables: CLAUDE.md auto-discovery (prompt) + ~/.claude/skills/ fallback
// q does NOT disable: explicit instructions: [...] array loading
var wu = ["AGENTS.md",...ee.OPENCODE_DISABLE_CLAUDE_CODE_PROMPT?[]:["CLAUDE.md"],"CONTEXT.md"];
// instructions array is processed separately in systemPaths() regardless of q
if (u.instructions) for (let p of u.instructions) { /* load explicit paths */ }
```
- **Conclusion**: `OPENCODE_DISABLE_CLAUDE_CODE=1` disables Claude-compat auto-discovery
  but does NOT disable explicit `instructions: ["~/dotfiles/CLAUDE.md"]` array loading.
- The explicit `instructions:` array in `opencode.json` loads regardless of env-var state.
- Setting the env-var is SAFE and RECOMMENDED to prevent double-loading.

### External dependencies

`opencode` CLI, `python3` (stdlib only for scripts; for custom tools), `git`, `gh`.

## Hermes Agent (port of pipeline to Nous Research harness)

### Purpose

Parallel port of the multi-role gated pipeline to the **Hermes Agent harness** (Nous Research, `https://hermes-agent.nousresearch.com`). Coexists with the Claude Code branch — same `.pipeline/runs/<artifact-id>/` ledger, different invocation path.

Doctrine deltas vs Claude Code branch:
- Subagent persistence dropped — every `delegate_task` spawn is fresh. Continuity via mandatory `handoff-<role>-r<N>.md` artifact (Hermes constraint R1: `delegate_task` does not return child session_id; no programmatic resume).
- Toolsets coarse only (`file`, `terminal`, `web`, `pipeline`). Per-role fine-grain via `role_policy.py` shell hook + per-spawn role sidecar (R2).
- Decision elicitation: sync via `clarify` tool (root only); async via Discord `send_message` + text-reply sentinel `!decide <run_id>:d<N> <index>`. Hermes native gateway routes user replies back to orchestrator session — no custom decision-router hook (R3 + R5).
- Slack dropped on Hermes side. Discord only.
- `terminal.backend: local` locked — `pipeline-core` plugin guards registration on this.

### Key files

Stow-managed under `~/dotfiles/.hermes/` → symlinked into `~/.hermes/`:

- `.hermes/SOUL.md.example` — root agent identity template. **Not stowed.** User copies once to `~/.hermes/SOUL.md` (stays local + gitignored).
- `.hermes/config.yaml.example` — harness config template. **Not stowed.** User copies once to `~/.hermes/config.yaml` (stays local + gitignored).
- `.hermes/skills/pipeline/<role>/SKILL.md` — 11 role-skills (orchestrator + plan, researcher, architect, build, skeptic, security-auditor, tester, ui-ux-designer, content-designer, progenitor).
- `.hermes/skills/pipeline-{agent-brief-format,handoff-doc,decision-elicitation,agent-preflight}/SKILL.md` — 4 prompt-skills.
- `.hermes/skills/caveman/SKILL.md` — output-style skill (pin via Hermes `memory` tool).
- `.hermes/skill-bundles/pipeline.yaml` — `/pipeline <request>` entry point.
- `.hermes/plugins/pipeline-core/{plugin.yaml,__init__.py,schemas.py,tools.py}` — Python plugin registering 8 deterministic logic tools (artifact_slug, verdict_parse, dep_graph_compose, revision_route, worktree_lifecycle, test_path_resolve, prod_diff_sha, friction_audit).
- `.hermes/hooks/{cap_bash_timeout.py,graphify_advice.sh,terminal_policy.py,role_policy.py}` — shell hooks.
- `.hermes/policy.json` — `terminal_policy` allow/deny patterns (replaces Claude Code's `settings.json permissions`).
- `.hermes/role-policy.json` — per-role write-path denylists for `role_policy.py`.

Stow-ignored runtime / secrets / local-only:
- `.hermes/SOUL.md` — local-only; seed from `SOUL.md.example`.
- `.hermes/config.yaml` — local-only; seed from `config.yaml.example`.
- `.hermes/.env` — `ANTHROPIC_API_KEY`, `DISCORD_BOT_TOKEN`, `DISCORD_CHANNEL_ID`, `DISCORD_GUILD_ID`.
- `.hermes/state.db` — SQLite session store.
- `.hermes/sessions/sessions.json` — gateway routing index.
- `.hermes/memory/` — Hermes memory provider state (provider-dependent).
- `.hermes/pipeline-registry.json` — active-run registry (orchestrator-maintained for cross-pipeline `run_id → run_dir` lookup on Discord replies).

### Setup

1. Install Hermes: `pip install hermes-agent` (or per upstream docs).
2. Stow dotfiles: `cd ~/dotfiles && stow .` — links skills / plugins / hooks / policies into `~/.hermes/`.
3. **Seed local files** (one-time, not stowed):
   ```bash
   mkdir -p ~/.hermes
   cp ~/dotfiles/.hermes/SOUL.md.example ~/.hermes/SOUL.md
   cp ~/dotfiles/.hermes/config.yaml.example ~/.hermes/config.yaml
   ```
   If Hermes already wrote its own defaults, diff + merge the pipeline-specific blocks (hooks, plugins.enabled, terminal.backend lock, delegation limits).
4. Set secrets: `hermes config set DISCORD_BOT_TOKEN <token>`, `hermes config set DISCORD_CHANNEL_ID <id>`, `hermes config set ANTHROPIC_API_KEY <key>`.
5. Enable plugin: `hermes plugins enable pipeline-core` + restart hermes.
6. Verify: `hermes skills list | grep pipeline` (expect 11 role-skills + 4 prompt-skills + caveman).
7. Use: `hermes chat` → `/pipeline <request>`.

### Sentinels

- Resume: `<<resume-pipeline-<artifact-id>>>` or literal `resume <artifact-id>` in user input.
- Plan reuse: `use plan <artifact-id>` in user input.
- Async decision reply: `!decide <run_id>:d<N> <index>` (Discord text).
- Async drift menu reply: `!resolve <run_id>:drift <rebase|abort|proceed>` (Discord text).

### External dependencies

`hermes-agent` (`hermes` CLI), `python3` ≥ 3.9, `git`, `gh`, `pyyaml` (Hermes ships it). Discord bot token + channel for async decision elicitation (optional — sync via `clarify` works without).

### Port plan reference

`~/.claude/plans/port-claude-code-pipline-fizzy-token.md` — full architectural decisions, doctrine deltas, sequencing, verification.

## systemd / user

### Purpose

User-level systemd units packaged with the dotfiles.

### Key files

- `.config/systemd/user/sway-low-battery.service` — pairs with
  `.config/sway/scripts/battery_monitor.sh` to alert on low battery.

### External dependencies

`systemd` (user instance).
