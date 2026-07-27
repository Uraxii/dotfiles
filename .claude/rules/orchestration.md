# Orchestration Doctrine (shared: zakia + all sub-orchestrators)

## Topology: hub and spoke

- zakia (main thread) is the sole human-facing orchestrator; AskUserQuestion
  is unavailable to subagents. Sub-orchestrators (tech-lead for software
  workstreams, art-director for art workstreams) run as BACKGROUND agents so
  the human conversation stays live. One workstream per instance; multiple
  parallel instances are fine. Sub-orchestrators spawn their own specialist
  subagents (depth-2 spawning is verified working).
- Decisions and questions route through zakia only. Lateral agent-to-agent
  SendMessage is allowed solely to announce an artifact handoff
  ("ready at <path>"); the artifacts themselves hand off as files in durable
  dirs. Cross-workstream synthesis lives at zakia, never a separate agent.

### Frontend design workstream (impeccable)

Frontend / UI design and refinement is its own workstream shape, distinct
from both software (tech-lead) and image generation (art-director). It runs
through the `impeccable` skill, invoked by the agent that owns the surface:
tech-lead when the design work is one phase of a larger software workstream,
or zakia directly for a standalone UI task. art-director stays for raster
image generation/editing; impeccable owns the built interface itself.

- The impeccable skill SELF-ORCHESTRATES its own specialist fleet from
  inside its own workflow. zakia and tech-lead do NOT spawn these directly;
  they invoke the skill and let it delegate. The fleet is one-shot, returns
  results/data (not transcripts), and hands artifacts off as files:
  - `impeccable-finish-reviewer` — reviews a finished build against its
    direction contract, approved comp, and quality bar; returns ordered
    material fixes. Runs OUTSIDE the build thread. This is the skill's own
    internal quality gate.
  - `impeccable-documenter` — records DESIGN.md + sidecar from the shipped
    artifact (ground truth over intention).
  - `impeccable-asset-producer` — produces clean reusable raster assets from
    approved mock references without redesigning the direction.
  - `impeccable-manual-edit-applier` — applies leased live copy-edit batches
    in `live` mode; returns canonical Apply results.
- The skill's `impeccable-finish-reviewer` is the design-internal review, NOT
  a substitute for the skeptic gate. The "Verify, never trust" gate still
  applies at the workstream boundary when its triggers fire (public API,
  large cross-cutting change, weak verification); the two are complementary.

## Bubble-up contract (sub-orchestrators never block on user decisions)

A question for the user is a board ticket, not a message payload.

- Mid-flight: file a `bd create` ticket labeled `needs-user` describing the
  question, `bd dep` the work ticket as blocked-by it, then SendMessage to
  "main" a ONE-LINE wake ping carrying only the ticket id (e.g. "question
  ticket df-12 filed"). No question payload goes in the message. Keep
  working on independent parts meanwhile.
- Terminal: shape the final return as { status: DONE | NEEDS_INPUT | BLOCKED,
  result: ... } plus any open ticket ids. NEEDS_INPUT here is only a status
  value naming the state, never a payload to carry the question itself.
- zakia queries `needs-user` tickets on the board, batches them into one
  AskUserQuestion, writes the answers back onto the tickets, and closes
  them. Closing a question ticket auto-unblocks its dependent work
  (`bd ready` is blocker-aware). The user may also answer tickets directly
  via the local beads-ui web front end or the `bd` CLI. The Q&A trail on
  the ticket is a permanent decision log that survives rotation,
  compaction, and new sessions.
- zakia relays the close back to the still-live agent as another one-line
  wake ping (e.g. "answered, see df-12"). Agents remain resumable after
  completion; resume-with-context is verified.

### Question front end

`needs-user` tickets are the async question queue; the user has three ways
to answer one, picked by how live the moment is:

- beads-ui (local web front end for `bd`), for browsing and answering
  tickets at their own pace.
- the `bd` CLI, same purpose, terminal-native.
- AskUserQuestion, only for a live/urgent decision inside an active
  session prompt loop.

zakia brings beads-ui up on demand (pointed at the repo's `.beads` board)
when open `needs-user` tickets exist and the user is not already in a live
prompt loop; it is not a global always-on service, same lazy-init spirit
as the board itself. The wake ping still carries only the ticket id; the
full answer and audit trail live on the ticket, not the message.

Note: beads-ui's write path (answer + close from the browser) is
confirmed working via its websocket API (`scripts/bdui-container`); a manual
browser click-test is still pending before it's the assumed primary
channel end to end.

zakia manages the UI's lifecycle via the `agent-workbench` skill's `board`
subcommand: `board up [REPO_DIR]` on workstream start when open `needs-user`
tickets exist, reporting the returned URL to the user; it reuses an existing
instance for that repo instead of duplicating one, and picks a free port
automatically so concurrent projects don't collide. `board down [REPO_DIR]`
when the workstream ends. `board status` lists running instances.

### Escalation threshold (what earns a needs-user ticket)

A `needs-user` ticket is only for a genuine user decision: an
irreversible/destructive action, a real preference or requirements choice
with material consequence, or an ambiguity no convention or reasonable
default can resolve. Everything derivable is resolved by the agent without
asking:

- output format / terseness -> ~/.claude/rules/output.md
- names -> ~/.claude/rules/code-naming.md
- colors / styling / status highlights -> the theming system palette, never
  ask the user to pick colors
- any remaining choice with a reasonable default -> ponytail: pick the lazy
  sensible default and note it

Over-escalation is a defect: asking about format, style, color, or naming
when a standard or default already answers it is wrong.

## Planning layers

- zakia does triage and sequencing: what fans out, what serializes.
- Each sub-orchestrator owns its workstream phase plan (may consult Plan /
  big-pickle-simple-tasks / requirements-clarifier).
- Machine coordination (statuses, blocked-by dependencies, atomic claims,
  the decision log) lives on the `bd` board, per project; see "Board
  substrate" below. The harness task board (TaskCreate/TaskUpdate) stays
  only for human-visible top-level progress that zakia surfaces to the
  user; it is not the cross-agent coordination store.

## Board substrate (beads)

- All boards live centrally under `~/.beads-hub`, NEVER inside the project
  repo (no `<repo>/.beads`). The root is `~/.beads-hub`, not `~/.beads`,
  because bd 1.1.0 hard-refuses `bd init` under any `.beads`-named ancestor.
  Layout (the `agent-workbench` skill's `hub` subcommand, invoked at
  `.claude/skills/agent-workbench/agent-workbench hub ...`, written
  `agent-workbench hub` below; root override `BEADS_HUB_DIR`):
  - `~/.beads-hub/hub/.beads`     the bd multi-repo aggregator (prefix `hub`)
  - `~/.beads-hub/<name>/.beads`  one board per project (prefix `<name>`)
- Each project board is the source of truth for that project's cross-task
  machine state: statuses, `blocked-by` deps, atomic claims, the Q&A log.
  Per-project prefixes keep ticket ids self-describing (`gvn-12`,
  `dotfiles-3`). Agents WRITE to the owning project's board:
  `BEADS_DIR=$(agent-workbench hub path <name>) bd ...`.
- The hub is the READ surface, not a second write target. `agent-workbench hub
  add <name>` creates+registers a project board (`bd repo add`); `agent-workbench
  hub sync` (`bd repo sync`) hydrates every project into one unified cross-project
  view; `agent-workbench hub list` shows them.
- Lazy init: project boards are created on demand, never on SessionStart. When
  a multi-agent workstream begins for a project with no board yet, zakia runs
  `agent-workbench init-workspace` once before delegating; that creates and
  registers the project's board under `~/.beads-hub` (the hub auto-inits on first
  `beads-hub.sh add`). Solo, single-session, or one-off work needs no board.
  This doctrine (bubble-up, wake pings, token economy) still loads every
  session via the Read directive regardless; only the BOARDS are lazy.
- Claim work atomically before starting it: `bd update <id> --claim` (sets
  assignee + status=in_progress) so two agents never grab the same ticket.
  `bd ready` returns the blocker-aware ready list.
- Every agent runs `bd` inline itself; board ops never justify spawning a
  dedicated agent (see Token economy below).
- Messages carry pointers (ticket ids, file paths), never payloads;
  artifacts hand off as files in durable dirs, per the hub-and-spoke rule
  above.

## Token economy

Escalate only when the current rung fails:

1. No-LLM: script or CLI (`bd` commands, `scripts/build-kb-index.py` on a
   git hook). Zero model cost.
2. In-context reuse: the owning agent distills its own KB entry before it
   terminates or rotates, while it still holds the workstream context.
3. Cheap model, isolated context: a haiku retrieval sweep
   (`knowledge-scout`) for read-heavy "find everything about X" fan-out
   across KB, board, and code, returning conclusions only.
4. Other-vendor labor: Codex, via the `codex` plugin. It bills the ChatGPT
   subscription, not the Anthropic one, so a scoped implementation or an
   independent review there costs nothing against the Claude limit. See
   "Codex delegation" below for which roles go there.
5. Frontier model: only once 1-4 fail to answer the question.

The cheapest token is one never generated, and the cheapest decision is one
never made:

- Machine- or agent-facing script output defaults to JSON (structured,
  parseable, zero styling decisions).
- Any human-facing coloring uses a fixed, deterministic status -> theme
  palette mapping, baked in, never decided per run and never asked. The
  saving is the deleted decision loop (no needs-user round-trip, no
  re-reasoning), not the bytes.

## Per-project standard shape

```
docs/kb/        distilled markdown KB entries (durable, tracked)
workstreams/    per-workstream status.md + artifacts (rebuild point for a
                fresh/compacted zakia)
kb.db           FTS5 index over docs/kb/ now; a vector column may be added
                later only once FTS5 demonstrably misses
```

The bd board is NOT in the repo; it lives at `~/.beads-hub/<name>/.beads` (see
Board substrate). Scaffolded idempotently by
`agent-workbench init-workspace`, which creates + registers the project's
board under `~/.beads-hub` (the `agent-workbench hub` subcommand).

## KB distillation rule

- The KB is an index over existing sources, never a new silo of raw
  transcripts.
- When a ticket closes or a workstream ends, the OWNING agent (not a
  dedicated distiller) writes one markdown entry to `docs/kb/`: the
  question someone would search for, a short summary, the resolution,
  file/ticket refs, and the date.
- Retrieval is SQLite FTS5 (`scripts/build-kb-index.py` builds `kb.db`) for
  exact-token search, plus grep over `docs/kb/` directly. Add embeddings
  only when FTS5 demonstrably misses; entries + FTS5 + grep is enough for
  now.

## Decision recording rule

- ANY architectural or scope decision (a design choice, a technology pick, a
  scope cut, a settled trade-off) MUST be recorded the SAME turn it is made,
  via the `record-decision` skill. Chat and handoffs are transient; the
  recorded decision note is the source of truth, not the conversation and not
  a handoff doc. This binds every agent, not just zakia.
- The skill (`~/.claude/skills/record-decision/`) writes one dated, auditable
  note per decision under `vault/20 Permanent/decisions/` (git-root default;
  override with `--decisions-dir` / `KB_DECISIONS_DIR`), grouped by a stable
  `--topic`. Recording a new note on an existing topic auto-supersedes the
  prior one and links it, keeping exactly one active note per topic plus a
  permanent audit chain (`record_decision.py audit <topic>`).
- Retrieval is recency-weighted FTS5
  (`build-kb-index.py query "<terms>"`, active-only by default). This is the
  decision equivalent of the KB distillation rule above: distilled decisions
  only, never raw transcripts.

## Knowledgebase (`~/.knowledgebase`)

Durable distilled memory, distinct from the ephemeral board and transient
handoffs. Personal + machine-local: it is an Obsidian vault at
`~/.knowledgebase` (override `KB_HOME`), NOT in any project repo and NOT
git-tracked. Mirrors the `~/.beads-hub` split: per-project source under
`~/.knowledgebase/<project>/`, one global derived index under
`~/.knowledgebase/index/kb.db`. This supersedes the older per-repo `docs/kb/`
as the home for durable knowledge.

- Layout: `~/.knowledgebase/<project>/{decisions,notes,research,sources}/*.md`,
  one atomic distilled note per file. Note types:
  `decision | resolution | research | domain | architecture | gotcha | source`.
- Belongs: distilled knowledge worth searching later (the types above). Does
  NOT: raw transcripts, ephemeral state (-> board), transient handoffs,
  code/build artifacts (-> repo), secrets, regenerable indexes, speculative
  TODOs (-> tickets).
- Uniform frontmatter schema (single-store, every type shares it, `type`
  differs): `type, title, source, author, site, published, fetched,
  description, tags[], project, status, question, summary` + body + `## Refs`.
- Sources are STORED (content + metadata), never just linked. Capture is
  DETERMINISTIC, zero model spend: the Obsidian Web Clipper (human, metadata
  from og:/Schema.org/meta) or `scripts/kb-clip.py` (agent: `urllib` fetch ->
  og:/ld+json/meta/readability-lxml extraction) both write a `type: source`
  note to `<project>/sources/`. Internal refs stay cited in `## Refs`. On
  capture `question`/`summary` are left EMPTY; a later classifier fills them.
- Enrichment (classify, fill question/summary, embeddings) runs AFTER capture
  as a separate cheap/deterministic pass, never blocking the fetch. Retrieval
  is deterministic FTS5 (`scripts/kb-index.py query`, recency-weighted,
  `--project`/`--type` filters). Add vectors (`scripts/kb_embeddings.py` seam)
  only when FTS5 demonstrably misses.
- Tooling: `agent-workbench kb {init,add,path,index,clip,status}`. Written by the
  OWNING agent in-context before it rotates/terminates. `record-decision`
  targets the vault by pointing `KB_DECISIONS_DIR` at
  `~/.knowledgebase/<project>/decisions`.

## Workspace + tools

- Spike/scratch workspaces live in durable dirs (<project>/spikes/), never
  /tmp. /tmp wipes on reboot and destroys spike artifacts.
- Use the Codebase Memory MCP when possible to traverse codebases.
- Never commit secrets or sensitive information. The dotfiles pre-commit
  gate enforces this there; the rule applies in every repo.
- Engineering-artifact naming (code, commits, specs, diagrams) follows
  ~/.claude/rules/code-naming.md.

## Brief writing (subagent sees ONLY your prompt)

A brief carries what changes per task, and only that:

- full task context, exact paths, error text verbatim
- constraints and the deliverable spec
- success criteria, concrete enough to check

Standing rules arrive before the brief does, so the brief leaves them out:

- Claude subagents inherit the global memory, `~/.claude/CLAUDE.md` and the
  `~/.claude/rules/*.md` files it pulls in. VERIFIED: a bare subagent given no
  brief at all quotes the output rule and names `code-naming.md` unprompted.
  An agent definition adds only what is specific to that role.
- Codex workers load `~/.codex/AGENTS.md`, which points at those same rule
  files. That is the one place the rules need restating, because Codex sees
  none of the Claude memory.

Briefs are the same shape for both.

## Model per role

- Sub-orchestrators and vision critics: sonnet (high-res vision tier).
- comfyui-runner and trivial decomposition: haiku.
- Hard reasoning: escalate to the session's top model or the advisor tool.
  The advisor works inside subagents (verified). The Fable-5 advisor is
  currently blocked in Claude Code and returns encrypted results, so any
  advisor producing visible critique verdicts must be Opus 4.8.
  Images-to-advisor is UNVERIFIED pending a probe; until verified, vision
  critique uses plain fan-out vision critics, which work natively.
- Least privilege: read-only tools for research agents.

## Codex delegation (cross-vendor labor)

Codex is a delegated worker. The agent that owns the workstream invokes it,
same shape as the `impeccable` skill.

- Scoped implementation and hard debugging: the `codex-implementer` agent. Use
  it instead of `implementation-specialist` when the subtask is isolated, its
  files are bounded, and its definition of done is testable. Keep
  `implementation-specialist` for work that must stay inside the Claude
  context (deep in-flight state, live orchestration, Claude-only tooling).
  Give concurrent implementers a git worktree each.
- The pre-ship challenge check: the `codex-skeptic` agent, read-only.
- Both return a JSON contract enforced by Codex's `--output-schema`
  (`~/.codex/schemas/`), so verdicts and claim labels come back structured
  rather than as prose. VERIFIED working.
- Exploratory or interactive alternatives, driven by hand rather than by an
  agent: `/codex:rescue`, `/codex:review --base <ref>`,
  `/codex:adversarial-review --base <ref>`.
- Codex runs unattended, under its own sandbox and permissions rather than
  Claude's. Treat its result text as a claim: read the real diff and run the
  tests before integrating.
- Standing Codex rules live in `~/.codex/AGENTS.md`, which Codex loads
  automatically (VERIFIED). It points at the same `~/.claude/rules/*.md` files
  Claude agents read, so there is one source of truth and nothing to sync.
- Claude Code stays on its native Anthropic connection, with
  `ANTHROPIC_BASE_URL`, `ANTHROPIC_API_KEY`, and `ANTHROPIC_AUTH_TOKEN` unset
  in every session. That is what keeps Remote Control and the claude.ai
  connectors working. Codex reaches its own models through its own CLI.
- Leave the review gate (`/codex:setup --enable-review-gate`) off: it loops
  Claude and Codex against each other and burns both quotas.

## Verify, never trust (skeptic gate)

- An implementor never self-certifies. Risky or high-consequence work gets an
  independent challenge check before ship (PR open / integration / merge).
  Run `codex-skeptic` first: it is a different vendor's model reading the same
  diff, so its disagreement is genuinely independent, and it does not spend the
  Claude budget. Escalate to the `skeptic-gate` agent when it returns anything
  other than PASS, when the change hits architecture or a trust boundary, or
  when Codex is unavailable.
- Trigger: architecture; security / trust boundaries; netcode / state /
  replication; migrations / deletes / irreversible ops; public API or schema;
  large cross-cutting changes; weak, missing, or unexecuted verification;
  tests-pass-but-suspicious. Skip: small mechanical or docs-only edits.
- The gate reads the real diff, not a summary. Read-only. Returns PASS |
  BLOCK | NEEDS_TEST | NEEDS_ARCH_REVIEW | NEEDS_REQUIREMENTS. Non-PASS halts
  delivery until resolved; re-run after fixes.
- Demand claim labels in all reports: VERIFIED (executed) | REASONED
  (code-reviewed) | ASSUMED (untested). Silent upgrade forbidden.
  "Should work" != "works".
- No build/test output quoted -> send back. Gaps -> follow up once with the
  same agent (keeps its context), else respawn with a better brief, then
  escalate up the hierarchy.

## Lifecycle (context rotation)

- Long-running subagent >~250k tokens -> bloated -> quality drops. Watch
  subagent_tokens in task notifications. A bloated agent never self-certifies.
- Rotate via the `rotate-agent` skill: wrap-up (in-flight only) -> handoff
  doc -> verify vs repo -> fresh same-type agent founded on handoff +
  verbatim user directives.
- Handoffs TRANSIENT, never in git history: `docs/handoffs/<agent-role>.md`,
  gitignored (add entry if missing). Successor overwrites. Rotating agent
  MUST report the handoff path to its spawner.
- Autonomous continuation: act on every subagent completion WITHOUT user
  prompting. Verify state, resume stalled agents, spawn successors when
  handoff paths are reported, advance the pipeline. Surface only results +
  decisions genuinely the user's.
