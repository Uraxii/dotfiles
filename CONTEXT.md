# Dotfiles Pipeline

GNU Stow-managed dotfiles with a Claude-Code pipeline subsystem under `.claude/pipeline/`. This glossary covers the pipeline's session/Slack/inbox vocabulary — the surface most subject to terminology drift.

## Language

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
- The **Router** delivers every inbound Slack event in a known **Thread** to the owning **Session's** inbox.
- Every **Elicited Reply** belongs to exactly one **Question**.
- An **Ambient Message** belongs to no **Question**.
- **Elicited Reply** and **Ambient Message** are mutually exclusive concepts — a given inbound user reply is one or the other, never both.

## Example dialogue

> **Dev:** "If the user types in the **Thread** while we're mid-tool, what happens?"
> **Domain:** "Router writes an inbound file into the **Session's** inbox. If a **Question** is outstanding with a matching `qid`, it's an **Elicited Reply** and the blocked role picks it up. If no **Question** is outstanding, it's an **Ambient Message** — the agent learns about it via a lifecycle hook, not via a sync wait."

## Flagged ambiguities

- "inbox message" was used as a catch-all for both **Elicited Reply** and **Ambient Message** — resolved: these are distinct concepts with separate consumer paths.
