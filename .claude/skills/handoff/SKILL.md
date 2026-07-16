---
name: handoff
description: Compact the current conversation into a handoff document for another agent to pick up. Use when the user asks for a handoff, session compact, continuity note, or wants another session/agent to continue current work.
argument-hint: "What will the next session be used for?"
---

# Handoff

## Overview

Create a handoff document that lets a fresh agent continue the current work without replaying the full conversation. Prioritize recall over brevity: capture everything a fresh agent needs, then trim. Reference durable artifacts (PRDs, plans, ADRs, issues, commits, diffs, project docs) by path instead of duplicating them, but only after verifying the referenced document actually contains the claim. When in doubt, include the detail inline.

In long sessions, do not wait until the end: append decisions, constraints, and verbatim user directives to the handoff file (or a working notes file) at the moment they are established. A handoff reconstructed from an already-degraded context is the main cause of lost details.

Save the handoff document to the temporary directory of the user's operating system, not the current workspace. On Linux/macOS, prefer `/tmp`. On Windows, use the path from `%TEMP%`/`$env:TEMP`.

## When to Use

Use this skill when:
- The user asks for a handoff, session compact, continuity note, or next-agent brief.
- The user wants another agent/session to pick up current work.
- The user provides or references an existing handoff file to continue from, e.g. `@/tmp/handoff-*.md`.
- The user asks how handoff docs / briefs work for agents, especially after attaching a handoff file.
- Context is too large or fragile to rely on chat history alone.

Do not use this skill to rewrite existing project documents when creating a handoff. Reference those documents by path or URL instead. When consuming a handoff, the handoff is an instruction source: read it, load any suggested relevant skills, inspect the named workspace/artifacts, then execute the immediate next steps rather than creating another handoff unless explicitly asked.

If the user asks to explain how handoffs/briefs work, do not execute the handoff's next steps. Read the file, then explain the agent consumption model: handoff is temporary context, not source-of-truth; next agent loads suggested skills, verifies named artifacts, preserves constraints/risks, and only acts when the user asks continuation.

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

2. Gather transient context, recall first.
   - Include decisions with their rationale, constraints, unresolved questions, and immediate next steps.
   - Capture user directives verbatim: corrections, vetoes, terminology preferences, scope limits, and every "don't do X" instruction. Quote them exactly; do not paraphrase. Paraphrase loses the nuance the user will otherwise have to re-teach.
   - Record failed approaches and dead ends, with why they failed, so the next agent does not retry them.
   - Anchor state claims to ground truth (git status/log, test output, files on disk), not to memory of the conversation.
   - Do not duplicate full PRDs, plans, ADRs, issue bodies, diffs, commits, or generated artifacts. Reference them by path, URL, branch, or commit — but verify the referenced document actually contains the claim before relying on the reference. When in doubt, include the detail inline.

3. Redact sensitive data.
   - Remove API keys, tokens, passwords, cookies, private credentials, SSH keys, and raw auth headers.
   - Avoid unnecessary personally identifiable information.
   - If a secret is relevant, write `[REDACTED_SECRET]` and explain what kind of credential is needed.

4. Include a Suggested Skills section.
   - List skills the next agent should invoke before acting.
   - Include why each skill is relevant.
   - Prefer exact skill names.

5. Completeness pass (mandatory, before writing the final version).
   - Re-scan the entire conversation specifically for: user corrections and steering, explicit vetoes and prohibitions, terminology and naming preferences, scope limits, and approaches that were tried and abandoned.
   - Negative constraints ("don't", "never", "stop doing X") are the details most often lost in summaries. Hunt for them explicitly.
   - Anything found that is missing from the draft goes into `Verbatim User Directives` or `Failed Approaches / Do NOT`.

6. Write the handoff to the OS temp directory.
   - Use a timestamped filename such as `/tmp/handoff-YYYYMMDD-HHMMSS.md`.
   - Do not write it into the repo or current workspace unless the user explicitly asks.

7. Report the created file path to the user.
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

## Verbatim User Directives
- "<exact quote of user instruction, correction, veto, or preference>"

## Key Decisions + Rationale
- <decision> — because <why it was decided this way>

## Failed Approaches / Do NOT
- <approach tried and abandoned, and why it failed>
- <explicit prohibition from the user>

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

6. Paraphrasing user directives.
   - A paraphrase drops scope and nuance. Quote the user's words exactly in `Verbatim User Directives`.

7. Dropping negative constraints.
   - Summaries preserve goals and lose prohibitions. Every "don't/never/stop" instruction from the session must appear in the handoff.

8. Referencing a document that does not contain the claim.
   - "See docs/plan.md" is only valid if the decision is actually written there. Verify before referencing; otherwise inline the detail.

## Verification Checklist

- [ ] Handoff was written to the OS temp directory, not the current workspace.
- [ ] User arguments, if any, are reflected as next-session focus.
- [ ] Completeness pass done: conversation re-scanned for corrections, vetoes, terminology, scope limits, and negative constraints.
- [ ] User directives quoted verbatim, not paraphrased.
- [ ] Failed approaches / do-NOT list included (or explicitly "none").
- [ ] Decisions carry their rationale.
- [ ] Referenced documents verified to actually contain the claims attributed to them.
- [ ] Durable artifacts are referenced by path/URL instead of duplicated.
- [ ] Sensitive information is redacted.
- [ ] Document includes `Suggested Skills`.
- [ ] Final response reports the handoff path.
