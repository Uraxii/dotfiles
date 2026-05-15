# Dotfiles Pipeline

GNU Stow-managed dotfiles with a Claude-Code pipeline subsystem under `.claude/pipeline/`. This glossary covers the pipeline's session/Slack/inbox vocabulary — the surface most subject to terminology drift.

## Language

### Work units

**Campaign**:
A batched run of N **Tasks** across ordered **Phases**. Owned by one **Session**, posts into one Slack **Thread**, optionally backed by a Notion board.
_Avoid_: project, run, batch, sprint

**Task**:
One PR-sized unit of work. Has its own brief, plan, build, review, deliver lifecycle. Produces exactly one PR (or one direct commit). A **Task** is what today's `pipeline.md` calls a "pipeline run."
_Avoid_: ticket, story, step

**Phase**:
An ordered group of **Tasks** within a **Campaign**. **Tasks** inside a **Phase** may execute in parallel; **Phases** execute sequentially. **Phase** boundaries may require a human gate before advancing.
_Avoid_: stage (overloaded with build-stage), milestone

**Codebase Map**:
A pre-flight artifact emitted per **Task** before any planning or building. Names the relevant files, symbols, prior similar work, test conventions, and ADRs that touch the **Task's** scope. Read by every downstream role.
_Avoid_: codebase summary, project digest

**Risk Register**:
A pre-flight artifact emitted per **Task** alongside the **Codebase Map**. Names 3–5 codebase conventions / Global-Do-Nots / rule-file constraints that the **Build** must respect. Compiled from prior verdict files, `.claude/rules/<lang>.md`, `docs/adr/`, `CLAUDE.md` Global-Do-Nots, and recent commit patterns.
_Avoid_: risk list, gotcha doc

**Pre-Flight**:
The first stage of a **Task** lifecycle. Produces the **Codebase Map** + **Risk Register** before plan/build/gate stages run. Designed to cut first-pass-failure rate on the dominant cause (codebase-knowledge gaps). Runs in two tiers: a **Campaign-wide** pass (overview, ADRs, Global-Do-Nots, recent commit patterns) generated once per Campaign, and a **per-Task** pass scoped to the Task's files/symbols that consumes the Campaign overview as input.
_Avoid_: upfront-stage, research-stage

### Verdicts

**Verdict**:
A structured record of a gate outcome (skeptic / reviewer / security-auditor / tester / friction-reviewer). Emitted via the `record-verdict` tool, never hand-written. Has a canonical schema: `verdict ∈ {approved, blocked}`, `findings: [Finding]`, plus role / revision / loops / refs metadata. Persisted to disk as markdown w/ structured YAML frontmatter AND to the SQLite ledger atomically. The tool is the single write-path for all gates.
_Avoid_: review, gate-result, verdict-file (the file is the persistence, not the concept)

**Finding**:
A single issue inside a **Verdict**. Required fields: `id`, `severity ∈ {blocking, major, minor, nit, should-fix}`, `summary`, `status ∈ {open, resolved, wontfix}`. Optional: `rule`, `file`, `line`, `fix_hint`. **Findings** are the unit of cross-Campaign aggregation ("how often does rule X fire?"). **Findings** carry the verdict contract; prose body is optional, post-compressed by `caveman:compress` when present.
_Avoid_: issue, comment, note

### Role-inclusion model

Roles split into **always-run** (Pre-Flight, Plan, Build, Deliver — lifecycle scaffolding) and **conditional**. Each conditional role's `.md` frontmatter declares `applies_when: [predicates]`. Pipeline-cli ships a built-in predicate library (`prod_code_changed`, `ui_changed`, `external_input_added`, `schema_changed`, `tests_present_in_repo`, `diff_lines_gt:<N>`, `card_field_truthy:<name>`, etc.) and evaluates per Task to decide which roles to spawn. Adding a new role = drop a file w/ `applies_when:` declared.

**Card overrides**: `force_roles: [...]` and `skip_roles: [...]` in Card frontmatter override the default decision per Task.

**Default conditional roles** (initial set; extensible):

| Role | applies_when |
|---|---|
| architect | `schema_changed OR card_field_truthy:design_required` |
| skeptic-design | `architect_ran AND verdict_design_emitted` |
| skeptic-code | `prod_code_changed` |
| reviewer-standards | `prod_code_changed` |
| reviewer-spec | `prod_code_changed OR docs_changed` |
| security-auditor | `external_input_added OR diff_lines_gt:50 OR card_field_truthy:security_critical` |
| tester | `prod_code_changed AND tests_present_in_repo` |
| ui-ux-designer | `ui_changed AND card_field_truthy:design_required` |
| friction-reviewer | on-demand only via `pipeline friction <task>` CLI |

### Token-saving defaults (apply across all roles)

- **Pipeline-context digest**: at intake, pipeline-cli emits `<run>/.pipeline-context.md` (~3-5K tokens) summarizing brief + Pre-Flight + plan. Every role reads digest instead of originals.
- **Diff-only revision prompts**: r2+ revisions receive `verdict-r<N-1>.md` (structured findings) + `git diff r<N-1>..r<N>` only — not brief or design unless prior verdict flagged a section.
- **Findings-only verdicts**: prose body is optional; structured `findings:` are the canonical contract. When body is written, record-verdict tool post-compresses via `caveman:compress`.
- **Surgical Read sets**: each role's spawn template declares ONLY the artifacts it consumes (Spec axis → brief; Standards axis → rules; Security → diff). No "everyone reads everything."
- **Prompt caching**: harness adapters wrap the shared prefix (system + skills preamble + digest) in `cache_control: ephemeral` so parallel gate bursts within 5 min hit cache.

**record-verdict (tool)**:
The pipeline-cli function exposed to verdict-emitting agents in every harness. Validates the verdict payload against schema, INSERTs ledger rows, writes the canonical markdown file, fires any side-effects (PM sync, Comms post, ledger update), then returns success or a structured error. Atomic. Single source of truth for verdict emission semantics. **Delivered via MCP**: pipeline-cli runs an MCP server (stdio / unix-socket transport); each harness connects via standard MCP. Role `.md` frontmatter declares `mcp_servers: [pipeline]`. Cross-harness compatible (Claude Code, Agent SDK, OpenCode).
_Avoid_: emit-verdict, write-verdict, post-verdict

**Pipeline MCP Server**:
Pipeline-cli's MCP server. Exposes pipeline-internal tools to harness sessions: `record-verdict`, `query-ledger`, `update-card`, `mark-task-state`, `read-event-stream`, `request-decision`, `wait-for-decision`, others as needed. ~150 LoC over stdio/unix-socket. Harness connects natively; pipeline-cli stays harness-agnostic.
_Avoid_: pipeline server, internal tools

### Decision-elicitation contract

**request-decision (tool, fire-and-forget)**:
A role agent calls `request-decision(qid, question, options, timeout_hours)` via the **Pipeline MCP Server**. The tool returns IMMEDIATELY with `{"status":"emitted","qid":"<qid>"}`. The agent's role contract requires it to end its turn after receiving `status: emitted`. Pipeline-cli stores the ask in the **Ledger**, marks the **Task** `blocked_on_human`, fan-outs via Comms adapters (Slack push + Dashboard render). On human answer: pipeline-cli records `decision-r<N>.md` + ledger row, then issues a new `--resume` turn for the **Task Session** with the answer injected into the prompt. The harness session's prior context is fully retained; no preamble re-paid. Restart-safe via ledger. Cross-harness symmetric (Claude Code, Agent SDK, OpenCode all see identical flow). The optional `wait-for-decision(qid)` tool is provided for later turns that want to read a prior decision inline; normally not needed because the resume prompt already carries the answer.

### Repo split

The pipeline lives across two repos with explicit coupling:

- **dotfiles** (this repo): prompts (`.claude/agents/`, `.claude/skills/`, `.claude/rules/`), `CLAUDE.md`, `docs/adr/`, plus a portable interactive **local pipeline** for laptop co-coding via Claude Code CLI. Everything `stow`-managed; clone + stow + go on any new machine.
- **pipeline-orchestrator** (new repo, planned): the autonomous daemon. Contains pipeline-cli (Python), web dashboard (SvelteKit), all adapters, ledger DDL, Dockerfile. Mounts the dotfiles `.claude/` dir as its config volume. Deployable to a VM via Docker.

Coupling: dotfiles is the single source of prompts + role/skill definitions. Both surfaces (interactive local pipeline + autonomous daemon) read from dotfiles `.claude/`. Editing a role updates both.

### Adapter families

pipeline-cli has four pluggable adapter families. Each is a capability-declared Protocol with one or more implementations. Adding a new tool = adding one adapter; pipeline-cli is otherwise tool-agnostic.

| Family | Contract | First impl |
|---|---|---|
| **Harness Adapter** | Runs LLM work. Methods: `invoke(prompt, continuation) -> InvokeResult`. Capabilities: `RESUME, TOOLS, HOOKS, SKILLS, STREAMING`. | claude-code (CLI subprocess); agent-sdk planned post-June-15 |
| **PM Adapter** | Card lifecycle + spec source-of-truth. Methods: `create_card, update_status, add_comment, attach_artifact, watch_for_changes`. Capabilities: `KANBAN, COMMENTS, ATTACHMENTS, BIDIRECTIONAL, OFFLINE`. | obsidian (vault files) |
| **Comms Adapter** | Human-facing notification + decision channel. Methods: `notify_status, notify_artifact, request_decision`. Capabilities: `PUSH, BUTTONS, ASK, ATTACHMENTS, STATUS_WRITE`. Multiple adapters can be subscribed concurrently; pipeline-cli fans out each call to adapters whose capabilities match the request. **No thread state** — Slack adapter sends DMs; thread/conversation continuity lives in the Dashboard adapter. `wait_for_ambient` deferred to v2. | slack (PUSH/NOTIFY only — DMs operator w/ magic-link to dashboard; no threads) + dashboard (BUTTONS, ASK — renders the actual decision UI) |
| **Agent View Adapter** | Unidirectional observability. Methods: `subscribe() -> AsyncIterator[Event], render(event)`. **Read-only — no back-channel.** Capabilities: `LIVE_STREAM, HISTORICAL, REMOTE_ACCESS, AUTH`. | tui (`pipeline watch`) + obsidian-publish (read-only web) |

### Dashboard tech stack

The web dashboard (Agent View Adapter implementation) uses:
- **Backend**: FastAPI (Python; same asyncio loop as the daemon). SSE for live event push.
- **Frontend**: SvelteKit + shadcn-svelte + Tailwind. SPA w/ SSR. EventSource subscription to backend SSE.
- **Auth + exposure**: Cloudflare Tunnel + Cloudflare Access. No open ports on the host VM.
- **State**: Reads ledger + subscribes to **Event Stream**. No own persistence.

### Event Stream

**Event Stream**:
Append-only `events.jsonl` emitted by pipeline-cli on every state transition + relayed harness tool-call event. Canonical observability source. Every **Agent View Adapter** subscribes. Every state change has a typed event (campaign_started, phase_advanced, task_state_changed, role_started, role_ended, tool_called, verdict_recorded, comms_ask_sent, comms_ask_answered, ...). Schema versioned.
_Avoid_: log file (overloaded), audit log

### Harness runtime

**Harness Adapter**:
Runtime-specific shim that invokes a chosen LLM CLI or SDK (Claude Code, Agent SDK, OpenCode, ...) and reports back exit + continuation token. Declares a **Capability** set (`RESUME`, `TOOLS`, `HOOKS`, `SKILLS`, `STREAMING`). pipeline-cli is harness-agnostic; chooses best-supported grain based on capabilities.
_Avoid_: runtime adapter, LLM driver

**Continuation Token**:
Opaque adapter-specific handle that resumes a prior harness session across multiple invocations. Persisted by pipeline-cli in the **Ledger**; interpreted only by the originating adapter. Claude Code adapter encodes `session_id`; Agent SDK adapter encodes `messages array ref`; Aider adapter encodes `history file path`.
_Avoid_: session id (too specific), handle

**Task Session**:
The harness session lifetime bound to one **Task**. Created on Task start, resumed via the **Continuation Token** for each role within the Task (Pre-Flight → Plan → Build → Gates → Tester → Deliver), terminated on Task completion. Bounded session size to avoid compaction fidelity loss.
_Avoid_: campaign session (rejected — too long for compaction), role session (rejected — too short for token efficiency)

**In-Task Orchestration model**:
Pipeline-cli drives top-level role flow inside a **Task Session** by issuing sequential `--resume` turns. Each turn = one role (Pre-Flight / Plan / Build / Gates / Tester / Deliver). Pipeline-cli sets per-turn `model`, `permission_mode`, `allowed_tools` from the role's `.md` frontmatter. **Gate parallelism**: the Gates turn uses the harness's native Agent tool to fan out skeptic-code + reviewer-standards + reviewer-spec + security-auditor concurrently. Each gate subagent gets bounded fresh context with prompt-cache hits on the shared preamble. Verdicts emitted via the `record-verdict` MCP tool. Preamble paid once per Task; sequential roles share session context cheaply; gate subagents stay isolated.
_Avoid_: orchestrator-agent (rejected — pipeline-cli is non-LLM Python; cheaper + deterministic)

### Project-management integration

**PM Adapter**:
A capability-declared shim that integrates pipeline-cli with a project-management tool (Obsidian, Notion, Linear, GH Projects, ...). Implements `create_card`, `update_status`, `add_comment`, `attach_artifact`, optional `watch_for_changes`. Each adapter encodes its own `CardRef` format; pipeline-cli treats refs as opaque. First concrete adapter: **Obsidian**.
_Avoid_: PM tool, kanban adapter

**Vault**:
The PM tool's primary storage. For the Obsidian adapter this is an Obsidian vault directory. For Notion adapter, a Notion workspace. Authoritative for **Campaign** and **Task** definitions (specs). Pipeline-cli reads new Campaigns + Tasks from the **Vault**, materializes them into the **Ledger**, and writes runtime status back to the **Vault** so PM views render live state.
_Avoid_: workspace, board, project

**Card**:
The PM-side representation of a **Task**. Obsidian: a markdown note. Notion: a database page. Linear: an issue. Pipeline-cli reads spec from the **Card** + writes status to it.
_Avoid_: ticket, page, item

**Card schema** (abstract):

- Required (operator-written): `title`, `body` (prose brief), `acceptance_criteria` (list of testable strings), `out_of_scope` (list).
- Optional (operator-written): `campaign_ref`, `phase`, `depends_on`, `priority`.
- Pipeline-written-back: `task_id` (artifact-slug), `card_status` (derived; see below), `last_verdict_ref`, `pr_url`, `updated_at`.

A **Card** missing any required field is not runnable. pipeline-cli fires a `Comms.ask()` to the operator and parks the **Card** in `blocked` until fields are filled.

**Ledger State** (fine, pipeline-internal, single source of truth):
`new | validated | queued | pre-flight | planning | building | gating | testing | delivering | done | blocked_on_human | blocked_on_dep | failed | skipped | wontfix`. Lives in SQLite **Ledger**. Pipeline-cli's state machine routes on this.

**Card Status** (coarse, externally visible, **derived** from Ledger State):
`ready | in-progress | blocked | passed | failed | skipped | wontfix`. Never stored as canonical truth; always computed at PM-write time from Ledger State via a pure function. Single source of truth ⇒ no drift.

Mapping (canonical):
- `queued | validated` → `ready`
- `pre-flight | planning | building | gating | testing | delivering` → `in-progress`
- `blocked_on_human | blocked_on_dep` → `blocked`
- `done` → `passed`
- `failed` → `failed`
- `skipped` → `skipped`
- `wontfix` → `wontfix`
- `new` (pre-validation) → `ready` w/ a "needs review" hint in Card body

**Ledger**:
The pipeline-cli SQLite database holding runtime state for active Campaigns + Tasks: lifecycle states, Phase pointers, session ids, continuation tokens, gate verdict refs, timestamps. Distinct from the **Vault** (spec) and the run dir (artifacts).
_Avoid_: db, state-store, journal

### Delivery flow

- A **Task** terminates by creating + pushing a Git branch and opening a PR via `gh`.
- Daemon **never merges**. Operator merges manually after reviewing the PR.
- Daemon watches `merged: true` (webhook or 30 s poll) and advances **Phase** deps on merge.
- **Phase** boundary advances only when every **Task** in the Phase has its PR merged (not just gate-approved).

## Relationships among storage domains

- **Vault**: source-of-truth for Campaign + Task SPECS (what to do).
- **Ledger** (SQLite): source-of-truth for RUNTIME state (lifecycle, gates passed, session refs).
- **Run dir** (files): source-of-truth for ARTIFACTS (briefs, verdicts, design docs, build evidence).
- **Comms** (Slack today): source-of-truth for human-interaction history.
- pipeline-cli is the only writer crossing domain boundaries. No domain writes into another's home.

### Session + binding

**Session**:
A single Claude Code process lifetime, identified by `CLAUDE_CODE_SESSION_ID`.
_Avoid_: conversation, chat

**Binding**:
The link between a **Session** and a Slack thread, persisted at `~/.claude/sessions/<sid>/slack.json`. A **Session** has at most one active **Binding** at a time.
_Avoid_: subscription, link, attachment

**Thread**:
The Slack-side conversation rooted at the `thread_ts` captured by a **Binding**. All pipeline messages for that **Session** post into this **Thread**.
_Avoid_: channel, conversation

**Router**:
Host-scoped process (`slack_router.py`) that listens on Slack Socket Mode and dispatches inbound events to the correct **Session inbox**. One per host, not per **Session**.
_Avoid_: listener, daemon, dispatcher

### Inbound message kinds

**Elicited Reply**:
A user reply that answers a specific outstanding **Question** posted by the pipeline. Identified by a question id (`qid`). Consumed synchronously by the role that posted the **Question**.
_Avoid_: response, answer (ambiguous), inbox-message

**Ambient Message**:
A user reply that does not answer a pending **Question** — volunteered context. Has no `qid`. Consumed asynchronously by the agent via a lifecycle hook.
_Avoid_: stray-reply, unsolicited, free-text

**Question**:
A structured ask the pipeline posts to Slack, with N≤4 button options or a free-form prompt. Has a `qid`. Spawns an **Elicited Reply** when the user picks.
_Avoid_: prompt, ask (overloaded), poll

## Relationships

- A **Session** owns at most one active **Binding**.
- A **Binding** points to exactly one **Thread**.
- A **Session** runs at most one active **Campaign** at a time.
- A **Campaign** contains N **Tasks** organized into ≥1 **Phases**.
- A **Phase** contains ≥1 **Tasks**. **Tasks** within one **Phase** may run concurrently; **Phases** run strictly in declared order.
- A **Task** produces exactly one PR (or merged commit) and emits its own artifacts.
- The **Router** delivers every inbound Slack event in a known **Thread** to the owning **Session's** inbox.
- Every **Elicited Reply** belongs to exactly one **Question**.
- An **Ambient Message** belongs to no **Question**.
- **Elicited Reply** and **Ambient Message** are mutually exclusive concepts — a given inbound user reply is one or the other, never both.

## Example dialogue

> **Dev:** "If the user types in the **Thread** while we're mid-tool, what happens?"
> **Domain:** "Router writes an inbound file into the **Session's** inbox. If a **Question** is outstanding with a matching `qid`, it's an **Elicited Reply** and the blocked role picks it up. If no **Question** is outstanding, it's an **Ambient Message** — the agent learns about it via a lifecycle hook, not via a sync wait."

## Flagged ambiguities

- "inbox message" was used as a catch-all for both **Elicited Reply** and **Ambient Message** — resolved: these are distinct concepts with separate consumer paths.
