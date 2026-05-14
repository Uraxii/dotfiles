# ADR-0002 — Session state directory under `~/.claude/sessions/`, not `~/.pipeline/sessions/`

Date: 2026-05-14
Status: Accepted
Run: merry-spinning-canyon-4359a7
Related design: `.pipeline/runs/merry-spinning-canyon-4359a7/design.md` §3 + §2.Q1

## Context

The session-bound Slack threading feature persists per-session state (`slack.json` + `inbox/`) to disk. The state file key is `CLAUDE_CODE_SESSION_ID`, an opaque harness-owned identifier.

Two candidate root directories existed:

- `~/.claude/sessions/<sid>/` — colocates with other Claude Code harness state (agents, skills, settings, `pipeline/slack.env.local`).
- `~/.pipeline/sessions/<sid>/` — colocates with pipeline runs (`<project>/.pipeline/runs/<id>/`, `~/.pipeline/plans/`).

The state lifetime is the Claude Code process. A single session may drive pipelines across multiple projects. The state has no dependency on any specific pipeline run dir; the inverse is also true (pipeline runs do not know they belong to a session beyond reading the helper).

## Decision

Session state lives under `~/.claude/sessions/<sid>/`:

```
~/.claude/sessions/<sid>/
├── slack.json
└── inbox/
    └── <message_ts>.json
```

Parent dir mode 700; files mode 644.

## Consequences

### Positive

- **Lifetime alignment.** Session state is keyed on a harness identifier with harness-scoped lifetime; co-locating with other harness state (`~/.claude/pipeline/slack.env.local`, `~/.claude/agents/`, `~/.claude/settings.json`) keeps the mental model consistent.
- **Project-orthogonal.** A session that drives pipelines in two different projects produces one binding, in one place. Storing under `~/.pipeline/` would imply a project relationship that does not exist (sessions are not project-scoped; pipelines are).
- **Run-dir contract preserved.** `<project>/.pipeline/runs/<id>/` is an established artifact contract (brief, pipeline.md, verdicts, evidence, etc.). Inserting session-keyed state under `.pipeline/` muddies the run-dir-is-the-pipeline-state-root invariant.
- **Discoverability for cleanup.** When debugging "why is my session bound to a stale thread?", users now have one location to inspect rather than walking project trees.

### Negative

- **No project-grouped view.** A user who wants "all session bindings that ever ran in project P" cannot get it by listing one directory; they would have to grep `slack.json` `cwd` fields across `~/.claude/sessions/`. The audit use case is hypothetical and easily scriptable.
- **`~/.claude/` accumulation.** Adds a new top-level subdir to `~/.claude/`. Manageable; `~/.claude/` already hosts multiple peers.

## Alternatives considered

### Alt-A: `~/.pipeline/sessions/<sid>/`

- **Pro:** keeps pipeline-related state under one root.
- **Con:** misattributes ownership. The session id is not pipeline-scoped; a session may have zero pipeline runs. Pipeline state under `~/.pipeline/` is keyed by `plan-id` / `artifact-id`, not by session id. Mixing key-types under one root invites confusion.
- **Verdict:** rejected.

### Alt-B: `<project>/.pipeline/sessions/<sid>/`

- **Pro:** keeps every artifact within the project tree.
- **Con:** breaks the multi-project session use case (one session driving pipelines in projects A and B would need state in both project trees, with synchronization). Also conflates session lifetime with project context.
- **Verdict:** rejected; multi-project sessions are explicitly supported.

### Alt-C: `$XDG_STATE_HOME/claude/sessions/<sid>/`

- **Pro:** XDG-correct.
- **Con:** `~/.claude/` already exists as the de-facto Claude harness root, and the rest of the harness state does not honour XDG. Introducing XDG just for sessions creates asymmetry with `~/.claude/pipeline/slack.env.local` etc.
- **Verdict:** rejected for consistency with surrounding harness state. Future global XDG migration could move all `~/.claude/` content together.

## References

- Brief: `/home/nikki/dotfiles/.pipeline/runs/merry-spinning-canyon-4359a7/brief.md` (Open question Q1).
- Existing harness state colocation: `~/.claude/pipeline/`, `~/.claude/agents/`, `~/.claude/skills/`, `~/.claude/settings.json`.
- Existing pipeline-state colocation: `<project>/.pipeline/runs/`, `~/.pipeline/plans/<project-slug>/`.
