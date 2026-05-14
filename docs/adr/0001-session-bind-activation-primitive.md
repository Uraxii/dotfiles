# ADR-0001 — Session-bind activation primitive: slash-command CLI, not Skill

Date: 2026-05-14
Status: Accepted
Run: merry-spinning-canyon-4359a7
Related design: `.pipeline/runs/merry-spinning-canyon-4359a7/design.md` §4 + §2.Q3

## Context

The session-bound Slack threading feature requires a `/slack-bind` gesture that:

1. Posts a root message to the configured Slack channel.
2. Captures the returned `thread_ts`.
3. Writes a state file at `~/.claude/sessions/<CLAUDE_CODE_SESSION_ID>/slack.json`.
4. Reports the binding back to the caller.

Two activation surfaces were available within the Claude Code harness:

- **Skill** (`Skill(skill: "slack-bind")` model-mediated invocation).
- **Slash command** (`/slack-bind`) backed by a deterministic Python CLI under `~/.claude/pipeline/session_bind.py`.

The user types `/slack-bind` at the moment they want to bind. Activation is a single-shot side effect with zero judgment surface: post message, capture ts, write file.

## Decision

Activation and deactivation are slash commands (`/slack-bind`, `/slack-unbind`, `/slack-status`) that invoke a deterministic Python CLI:

```bash
python3 ~/.claude/pipeline/session_bind.py activate
python3 ~/.claude/pipeline/session_bind.py deactivate
python3 ~/.claude/pipeline/session_bind.py status
```

The slash-command Markdown shim (`~/.claude/commands/slack-bind.md`) instructs the model to invoke the CLI verbatim with no paraphrase. The model is not a decision-maker in the activation path.

## Consequences

### Positive

- **Reliability:** the harness routes slash commands deterministically; activation cannot fail because the model "decided to do something else."
- **Reproducibility:** the CLI is shell-invocable directly from a terminal — useful for debugging and for scripting (`session_bind.py status` can be called from `setup.sh` or friction-reviewer audits).
- **Isolation:** state mutation lives outside the model's tool surface. The bind/unbind primitives can be hardened (atomic writes, retry semantics) without round-tripping through prompt design.
- **Symmetric with `pipeline_ask.py`:** the existing async question/decision flow already uses the "thin CLI invoked by the model" pattern. The session-bind primitive is the same shape, reducing pattern-count.

### Negative

- **Cannot evolve via prompt-only changes.** Skills are editable Markdown; CLI behaviour requires Python edits. For a primitive this stable that is a non-issue, but it forecloses the option to add LLM intelligence (e.g. "bind to channel X but only for design discussions").
- **One more script to maintain.** `session_bind.py` joins `slack_listener.py` and `pipeline_ask.py` as a pipeline-owned script under `~/.claude/pipeline/`.
- **Slash command discoverability requires doc.** Skills appear in the available-skills list automatically; slash commands need user education or autocompletion via the harness.

## Alternatives considered

### Alt-A: Skill (`Skill(skill: "slack-bind")`)

- **Pro:** discoverable via the available-skills mechanism; editable as Markdown; can dynamically request more info from the user.
- **Con:** model-mediated. Model can refuse, paraphrase args, invoke the wrong skill, or hallucinate state. Activation reliability is unacceptable for a gesture that the user expects to "just work" at the instant they type it.
- **Verdict:** rejected. No skill-shaped capability is needed here; the primitive is pure side effect.

### Alt-B: Hook (e.g. `SessionStart` or a `UserInputHook`)

- **Pro:** zero user gesture — automatic on session start.
- **Con:** brief explicitly defers auto-bind to a later phase ("explicit-bind only for this iteration"). Hooks also conflict with the multi-process isolation requirement (every new Claude Code process would auto-bind a thread, flooding the channel).
- **Verdict:** rejected for this iteration; reserved for a Phase 2 follow-up.

### Alt-C: Both (Skill wrapping the CLI)

- **Pro:** discoverability via skills + reliability via CLI underneath.
- **Con:** two surfaces for one primitive; the Skill's model-mediated layer is dead weight. If the model decides to "explain" the bind instead of running it, the user is back to Alt-A's failure mode.
- **Verdict:** rejected. Choose one surface; let the slash-command shim be the documented entry.

## References

- Brief: `/home/nikki/dotfiles/.pipeline/runs/merry-spinning-canyon-4359a7/brief.md` (Open question Q3).
- Existing pattern: `~/.claude/pipeline/pipeline_ask.py` — CLI-driven primitive with thin skill wrapper for documentation only.
- `question-elicitation` skill is documentation-shaped; the load-bearing logic is in the CLI. Same pattern applies here.
