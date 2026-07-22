# How does bubble-up work now, and where does agent knowledge live?

## Question

How do sub-orchestrators ask the user a question without blocking, and
where should agents persist knowledge so it survives rotation, compaction,
and new sessions? (Also: what happened to the NEEDS_INPUT message-payload
contract, and what are docs/kb/, kb.db, and workstreams/ for?)

## Summary

Doctrine v2 replaces the v1 NEEDS_INPUT message-payload bubble-up contract
with board tickets, and adds a lightweight per-project knowledge base built
on the `bd` (beads) board.

A question for the user is now a board ticket labeled `needs-user`. The
asking agent's work ticket is marked blocked-by that question ticket.
SendMessage shrinks to a one-line wake ping carrying only the ticket id
(e.g. "question ticket df-12 filed"); no question payload travels in
messages anymore. zakia queries `needs-user` tickets, batches them into one
AskUserQuestion, writes the answers back onto the tickets, and closes them.
Closing a question ticket auto-unblocks the dependent work (`bd ready` is
blocker-aware). The user can also answer tickets directly via the `bd`
CLI. The Q&A trail on each ticket is a permanent decision log.

The harness task board (TaskCreate/TaskUpdate) is now scoped to
human-visible top-level progress only; machine coordination (statuses,
dependencies, atomic claims) moved to the `bd` board per project.

A standard per-project shape was introduced for durable agent knowledge:

```
.beads/         bd board (machine coordination, local/untracked via stealth)
docs/kb/        distilled markdown KB entries (tracked, durable)
workstreams/    per-workstream status.md + artifacts
kb.db           SQLite FTS5 index over docs/kb/ (local/untracked, rebuildable)
```

Distillation is done by the owning agent, in-context, right before it
terminates or rotates: one markdown entry per resolved question or
finished workstream, never a raw transcript. Retrieval is FTS5 over
`kb.db` (exact tokens) plus grep over `docs/kb/`; embeddings are a later
escalation, only once FTS5 demonstrably misses. A dedicated haiku agent,
`knowledge-scout`, exists solely for read-heavy "find everything about X"
sweeps across the KB, the board, and the code, and returns conclusions
only, never file dumps.

## Resolution

- `scripts/init-agent-workspace.sh` scaffolds the standard shape
  idempotently: `bd init` (stealth mode, so `.beads/` stays local and
  never auto-commits itself into the repo), `docs/kb/`, `workstreams/`,
  and a first `kb.db` build, plus a git post-commit hook that reindexes
  `kb.db` only when a commit touches `docs/kb/`.
- `scripts/build-kb-index.py` is the no-LLM FTS5 indexer (stdlib
  `sqlite3` only): a single `CREATE VIRTUAL TABLE ... USING fts5(path
  UNINDEXED, body)` table, full rebuild from `docs/kb/*.md` on every run.
- `.claude/agents/knowledge-scout.md` is the new haiku, read-only
  retrieval-sweep agent.
- Doctrine text lives in `.claude/rules/orchestration.md` (bubble-up
  contract, board substrate, token economy, per-project standard shape, KB
  distillation rule) and was threaded through `.claude/agents/zakia.md`,
  `.claude/agents/tech-lead.md`, and `.claude/agents/art-director.md`.

## Refs

- `.claude/rules/orchestration.md`
- `.claude/agents/zakia.md`
- `.claude/agents/tech-lead.md`
- `.claude/agents/art-director.md`
- `.claude/agents/knowledge-scout.md`
- `scripts/init-agent-workspace.sh`
- `scripts/build-kb-index.py`

## Date

2026-07-21
