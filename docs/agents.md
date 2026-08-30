# Agents

What runs the agent setup on this machine. No agent file lives in this repo.

## Agents and skills live in `~/dotai`

The `Uraxii/dotai` repo owns every agent and every skill. The checkout on this
machine:

```
~/dotai
```

Layout is `skills/<name>/SKILL.md` for skills and `agents/<name>.md` for agents.
Install for Claude Code:

```
/plugin marketplace add Uraxii/dotai
/plugin install dotai@Uraxii
```

For Copilot CLI, Cursor, and the other targets skills.sh lists, run
`npx skills@latest add Uraxii/dotai`. Hermes takes
`hermes skills tap add Uraxii/dotai`. For opencode, point
`~/.config/opencode/skills` at the repo's `skills/` directory.

Run `/setup-dotai` once after installing. It offers the preamble lines for your
global instructions file and sets the per-role model pins. Full install notes
are in `~/dotai/README.md`.

## Doctrine lives in the `poteto-mode` skill

Installed at:

```
~/.claude/skills/poteto-mode/
```

| File | Holds |
|---|---|
| `SKILL.md` | Trigger list, principle index, autonomy rules, agent roster, spawn-brief contract, role index |
| `models.md` | Per-role model table, rewritten by `/setup-dotai` |
| `references/brief.md` | Required fields for a spawn brief |
| `references/plan.md` | Plan format |
| `roles/*.md` | One file per role, steps copied verbatim into the agent's todolist |

Every agent body's first action is to load this skill. That is how the roster
and the brief contract reach a subagent, since nothing auto-loads into one.

## The fleet is eight files

`~/.claude/agents/` holds `architect.md`, `developer.md`,
`explorer.md`, `orchestrator.md`, `researcher.md`, `reviewer.md`, `tester.md`,
and `zakia.md`.

Seven of them share the same thin body and carry no default skills. The names
exist so the agent graph reads, not because a name changes behaviour. Every
agent except `orchestrator` is a leaf and never spawns. `zakia` is the
main-thread persona, loaded through `settings.json`.

## History: the trees that left

`.claude/agents/`, `.claude/skills/`, `.claude/rules/`, and `.claude/refs/` used
to live in this repo, next to `copilot/`, `opencode/`, and `.hermes/`. Commit
`5a3ac8c` moved all of them into `~/dotai`. `~/.claude/refs/` and
`~/.claude/rules/` survive on disk as empty directories. Nothing reads them, and
no path under either one resolves, so an agent body that says
`cat ~/.claude/refs/orchestration.md` is quoting a dead doc.

Five files stayed behind under `.claude/` after that commit. They are gone now
too:

| File | Where it went |
|---|---|
| `statusline.sh` | `~/dotai/statusline.sh` |
| `themes/synthwave-84.json` | `~/dotai/themes/synthwave-84.json` |
| `hooks/cap_bash_timeout.py` | `~/dotai/hooks/cap_bash_timeout.py` |
| `hooks/handoff-token-flag.py` | Nowhere. `~/.claude/hooks/handoff-token-flag.py` is the only copy, kept out of version control on purpose. |
| `.stow-local-ignore` | Nowhere. It only configured the stow pass that is now deleted. |

`setup.sh` no longer deploys anything to `~/.claude`. It runs two stow passes,
into `~/.config` and `~/.config/autostart`. The machine keeps working because
`~/.claude` now holds real files instead of symlinks into this repo.

## Boards and knowledgebase

`~/.beads-hub` and `~/.knowledgebase` still hold their data. The
`agent-workbench` CLI that created and drove both is gone from this repo, from
`~/dotai`, and from `~/.claude/skills`, and nothing replaced it.

State of that tooling:

- `bd` 1.1.0 still reads a hub board directly with
  `BEADS_DIR=~/.beads-hub/<project>/.beads bd list`.
  `~/.beads-hub/hub/.beads` is the cross-project aggregator. The
  dotai `beads` skill does not know about the hub. It tells agents to run `bd`
  in the project working directory against a local `.beads/`.
- `scripts/kb-index.py` builds and queries the FTS5 index over
  `~/.knowledgebase/<project>/**` into `~/.knowledgebase/index/kb.db`.
- `scripts/build-kb-index.py` rebuilds a per-repo `kb.db` from a repo's
  `docs/kb/*.md`. This repo no longer has that directory, so nothing here
  feeds it.
- `scripts/kb-clip.py` is broken. It imports `lxml` at module level and `lxml`
  is not installed, so every invocation dies on import.
- `docs/kb-clipper-template.json` is the Obsidian Web Clipper template for the
  manual capture path. It writes a `type: source` note into `inbox/sources` with
  `project: inbox`.
