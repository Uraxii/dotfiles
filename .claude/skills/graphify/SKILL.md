---
name: graphify
description: Project-level graphify knowledge-graph workflow. Use when a repository's CLAUDE.md or AGENTS.md instructs graphify usage, the user invokes /graphify, or scoped subgraph queries are preferable to raw grep over the codebase.
---

# Graphify

## Overview

Graphify is a project-level codebase knowledge graph helper. It stores graph output under the current repository, usually `graphify-out/`, and supports scoped queries over code/docs relationships.

This skill explains how to use graphify safely. It does not decide whether graphify applies globally. The active repository's `CLAUDE.md` / `AGENTS.md` / project instructions are the source of truth for when to use it.

## When to Use

Use this skill when:
- User invokes `/graphify`.
- Repo `CLAUDE.md` or `AGENTS.md` says to use graphify for codebase questions.
- You need codebase navigation and `graphify-out/graph.json` exists.
- You need a scoped subgraph instead of broad raw source browsing.

Do not use this skill to force graphify in repositories whose instructions do not mention it.

## Project-Level Rule

Graphify behavior is dictated by the repository being worked on:

1. Read the repo's `CLAUDE.md` / `AGENTS.md` / local instructions first.
2. If those instructions define graphify usage, follow them exactly.
3. If no repo instruction exists, treat graphify as optional; prefer normal file/search tools unless the user asks.
4. Do not bake graphify usage into agent personalities or global role prompts.

## Commands

Scoped question:

```bash
graphify query "<question>"
```

Relationship/path:

```bash
graphify path "<A>" "<B>"
```

Focused concept:

```bash
graphify explain "<concept>"
```

Refresh graph after code changes, only when repo instructions require it:

```bash
graphify update .
```

## Safe Workflow

1. Check current repo instructions.
2. Check whether `graphify-out/graph.json` exists.
3. For codebase questions, prefer `graphify query` / `path` / `explain` over reading full `GRAPH_REPORT.md`.
4. Treat dirty `graphify-out/` files as generated state unless the task is specifically about graph freshness or graph output.
5. Only run `graphify update .` after code changes when the repo instruction says to keep graph current.
6. Do not run `graphify update .` for personality/config/doc-only changes unless the repo instruction explicitly asks for doc graph refresh.

## Common Pitfalls

1. Running graphify because a personality says so. Wrong owner. Repo instructions own graphify policy.
2. Running `graphify update .` after non-code edits. This creates noisy generated diffs.
3. Reading all of `GRAPH_REPORT.md` before trying scoped query/path/explain.
4. Treating dirty graph files as a blocker. Generated graph state is often dirty after hooks/incremental updates.
5. Assuming graphify exists in every repo. Check command availability and repo instructions first.

## Verification Checklist

- [ ] Repo `CLAUDE.md` / `AGENTS.md` checked before using graphify.
- [ ] `graphify-out/graph.json` exists before query/path/explain.
- [ ] Scoped graphify command used before broad source browsing when required.
- [ ] `graphify update .` only run when repo instructions and change type justify it.
- [ ] Generated graph diffs are reported separately from source changes.
