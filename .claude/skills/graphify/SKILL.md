---
name: graphify
description: Build a queryable knowledge graph of the current project (code + docs + papers + diagrams) for efficient Claude-driven navigation. Use when user says "graph this codebase", "graphify", "build a knowledge graph", "map the project", "what does this project look like", or invokes /graphify. Best for repos large enough that `grep` + manual reads exceed token budget (~10k+ LoC mixed code/docs).
---

# Graphify

Wraps the `graphify` CLI (https://graphify.net). Per-project knowledge graph via Tree-sitter AST + LLM semantic extraction + NetworkX + Leiden clustering. Compression value scales with corpus size — ~71× on ~500k-word corpora.

## Prerequisites

- `graphify --version` returns ok. If missing:
  ```
  pip install graphifyy
  ```
  Python 3.10+ required. Tell user to install + retry. Do NOT auto-install Python packages without explicit user consent.
- API key for the model graphify uses for semantic extraction (uses the user's existing Claude/OpenAI key from `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` env).

## When to invoke

Trigger on user intent:
- "Graph this codebase" / "graphify" / "build a knowledge graph"
- "Map this project" / "what does this project look like"
- "Find god nodes" / "what are the central modules"
- "Show me the surprise edges" / "unexpected dependencies"
- Multi-file exploration where naïve grep exceeds ~5k tokens

Skip when:
- Single-file task. Just Read + Edit.
- Repo < ~3k LoC. Compression doesn't earn the cost.
- User wants a quick one-liner answer.

## Workflow

1. **Verify graph exists.** Check `graphify-out/graph.json` in current cwd. If absent OR stale (older than the most-recent git commit on the project), prompt user before re-indexing — initial build takes minutes + spends LLM tokens.

2. **Build (first run only).**
   ```
   graphify ./
   ```
   Writes `graphify-out/` w/ `graph.html` + `graph.json` + `GRAPH_REPORT.md` + `cache/`.

3. **Query.** Drive via CLI subcommands:
   - `graphify query "<question>"` — semantic question against graph
   - `graphify path <node_a> <node_b>` — shortest path between two nodes
   - `graphify explain <node>` — node's role + neighbors + community

4. **Surface the answer.** Quote `GRAPH_REPORT.md` god-nodes/surprises or the JSON query result. Cite node ids the user can re-query.

## Anti-patterns

- Do NOT auto-build the graph on every session start. Initial build = LLM spend. Only build when user asks OR when a query needs it.
- Do NOT commit `graphify-out/` to the project repo. Add to `.gitignore` if not already present (the dir is per-machine cache + per-machine HTML output).
- Do NOT use graphify for tasks Read + Grep already handle in a few hundred tokens.
- Do NOT install `graphifyy` Python package without user consent. Surface the install command and stop.

## Project gitignore add

If the current project lacks `graphify-out/` in `.gitignore`, suggest adding it. Do not append silently.

## Output discipline

When summarizing graphify results back to the user:
- Cite the report file path: `graphify-out/GRAPH_REPORT.md`
- List ≤5 god nodes (highest-degree)
- List ≤3 surprise edges (cross-domain unexpected connections)
- Token cost: state the query's token count (graphify reports it).

## Notes

- Graphify is MIT-licensed, no telemetry. Semantic extract sends descriptions, not raw source.
- Cache is per-cwd: changing project = new graph. No leakage between projects.
- For Claude Code: graphify ships its own slash-command + PreToolUse hook. This SKILL.md does NOT install those — it just wraps the CLI for ad-hoc invocation via the `Skill` tool. To install graphify's full hook integration globally, run `graphify install` per the upstream docs.
