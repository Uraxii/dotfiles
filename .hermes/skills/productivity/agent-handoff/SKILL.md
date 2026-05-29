---
name: agent-handoff
description: Use when the user asks to compact the current conversation into a handoff document for another agent to pick up.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [handoff, session-continuity, summarization, temp-files]
    related_skills: [session-search, writing-plans]
argument-hint: "What will the next session be used for?"
---

# Agent Handoff

## Overview

Create a concise handoff document that lets a fresh agent continue the current work without replaying the full conversation. The handoff should preserve only context that is not already captured in durable artifacts such as PRDs, plans, ADRs, issues, commits, diffs, or project docs.

Save the handoff document to the temporary directory of the user's operating system, not the current workspace. On Linux/macOS, prefer `/tmp`. On Windows, use the path from `%TEMP%`/`$env:TEMP`.

## When to Use

Use this skill when:
- The user asks for a handoff, session compact, continuity note, or next-agent brief.
- The user wants another agent/session to pick up current work.
- The user provides or references an existing handoff file to continue from, e.g. `@/tmp/handoff-*.md`.
- Context is too large or fragile to rely on chat history alone.

Do not use this skill to rewrite existing project documents when creating a handoff. Reference those documents by path or URL instead. When consuming a handoff, the handoff is an instruction source: read it, load any suggested relevant skills, inspect the named workspace/artifacts, then execute the immediate next steps rather than creating another handoff unless explicitly asked.

## Inputs

If the user passes arguments, treat them as the focus for the next session and tailor the handoff around that future work.

Example arguments:
- `implement milestone 0`
- `continue debugging camera scaling`
- `prepare PR review`

If no arguments are supplied, infer the likely next-step focus from the current conversation and label it as inferred.

## Procedure: Consuming a Handoff

Use this flow when the user references an existing handoff file and appears to want continuation rather than a new handoff.

1. Read the handoff file first.
   - Treat `@/tmp/handoff-*.md` or a pasted handoff path as the current session brief.
   - Do not ask what to do next if the handoff contains explicit `Immediate Next Steps`.

2. Load suggested skills before acting.
   - Invoke skills listed under `Suggested Skills` when they are relevant to the immediate next step.
   - If a suggested skill governs later work but not the current step, note it mentally and defer loading until needed.

3. Inspect the named workspace and durable artifacts.
   - Verify branch/status before editing or committing.
   - Read the raw files or docs named as sources of truth instead of relying only on the handoff summary.

4. Execute the immediate next steps.
   - Preserve raw handoff-referenced artifacts unless the handoff says otherwise.
   - Update durable project docs with distilled decisions, not duplicated transcripts.
   - Commit/push only when the handoff or user request makes that the expected continuation and the diff is verified.

5. Verify completion.
   - Check git status/log after commit/push when working in a repository.
   - Search for stale/conflicting language when the task was to update decisions or requirements.

## Procedure: Creating a Handoff

1. Identify the active workstream.
   - Summarize the current objective in 1-3 sentences.
   - Include the intended next-session focus from the user arguments, if present.

2. Gather only necessary transient context.
   - Include decisions, constraints, unresolved questions, and immediate next steps that are not already recorded elsewhere.
   - Do not duplicate full PRDs, plans, ADRs, issue bodies, diffs, commits, or generated artifacts.
   - Reference durable artifacts by path, URL, branch, or commit instead.

3. Redact sensitive data.
   - Remove API keys, tokens, passwords, cookies, private credentials, SSH keys, and raw auth headers.
   - Avoid unnecessary personally identifiable information.
   - If a secret is relevant, write `[REDACTED_SECRET]` and explain what kind of credential is needed.

4. Include a Suggested Skills section.
   - List skills the next agent should invoke before acting.
   - Include why each skill is relevant.
   - Prefer exact skill names.

5. Write the handoff to the OS temp directory.
   - Use a timestamped filename such as `/tmp/handoff-YYYYMMDD-HHMMSS.md`.
   - Do not write it into the repo or current workspace unless the user explicitly asks.

6. Report the created file path to the user.
   - Keep the final response short.
   - Mention any assumptions or redactions.

## Recommended Document Structure

```markdown
# Handoff: <short title>

Generated: <ISO-like local timestamp>
Next-session focus: <user argument or inferred focus>

## Active Workstream
<1-3 sentence summary.>

## Current State
- Repo/workspace: <path or URL if relevant>
- Branch/commit/status: <only if needed>
- Durable artifacts to read first:
  - <path or URL>

## Key Decisions / Constraints Not Elsewhere Captured
- <decision or constraint>

## Immediate Next Steps
1. <next action>
2. <next action>

## Open Questions / Risks
- <question or risk>

## Suggested Skills
- `<skill-name>`: <why>

## Sensitive Info Handling
- No secrets included.
- <or describe redactions>
```

## Common Pitfalls

1. Duplicating artifacts instead of referencing them.
   - If content already exists in `docs/requirements.md`, a PRD, a plan, an ADR, a commit, or an issue, reference it by path/URL.

2. Writing into the project workspace.
   - The handoff belongs in the OS temp directory unless explicitly told otherwise.

3. Omitting suggested skills.
   - The next agent may not know which domain skills to load. Always include a `Suggested Skills` section.

4. Including secrets from tool output or env files.
   - Redact aggressively. Never copy tokens, keys, cookies, or passwords into the handoff.

5. Over-summarizing away active blockers.
   - Keep unresolved questions, risks, and immediate next steps explicit.

## Verification Checklist

- [ ] Handoff was written to the OS temp directory, not the current workspace.
- [ ] User arguments, if any, are reflected as next-session focus.
- [ ] Durable artifacts are referenced by path/URL instead of duplicated.
- [ ] Sensitive information is redacted.
- [ ] Document includes `Suggested Skills`.
- [ ] Final response reports the handoff path.
