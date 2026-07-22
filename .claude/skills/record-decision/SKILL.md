---
name: record-decision
description: Record an architectural or scope decision the moment it is made, into a dated, auditable vault note (vault/20 Permanent/decisions/), so it survives chat/handoff rotation. Use when the user says "record decision", "/record-decision", "log this decision", "we decided", or whenever a design/scope choice is settled in this session.
---

# record-decision

Chat and handoffs are transient; the vault is this project's long-term
memory. A decision recorded only in chat gets forgotten. Record it the
SAME turn it is made.

Scripts live beside this skill (`~/.claude/skills/record-decision/`) and are
path-configurable (CLI flag > env var > git-root default), so they write to
the current project's vault by default with zero setup.

## Record a new decision

```
python3 ~/.claude/skills/record-decision/record_decision.py record \
  --topic <stable-kebab-key> --title "<title>" --text "<decision statement>" \
  [--rationale "<why>"] [--refs "<paths/tickets>"] [--tags "a, b"] \
  [--supersedes <path-to-prior-note>]
```

- `--topic` groups a decision's history (e.g. `base-body-slices`). If an
  `active` note already exists for that topic, it is automatically
  flipped to `status: superseded` and the new note's `supersedes` field
  points at it. Exactly one `active` note per topic, always.
- Writes to `vault/20 Permanent/decisions/<topic-slug>__<date>.md` under the
  current git root (override with `--decisions-dir` or `KB_DECISIONS_DIR`).

## Audit a decision's history

```
python3 ~/.claude/skills/record-decision/record_decision.py audit <topic>
python3 ~/.claude/skills/record-decision/record_decision.py audit <topic> --human
```

Prints the full chain for a topic, oldest first, with date/status/title
and what supersedes what. JSON by default (machine-facing); `--human` for
a readable table.

## Retrieve decisions later

```
python3 ~/.claude/skills/record-decision/build-kb-index.py build
python3 ~/.claude/skills/record-decision/build-kb-index.py query "<search terms>"
```

Recency-weighted full-text search over `docs/kb/` + `vault/20 Permanent/`
(includes `decisions/`). Excludes `superseded` notes by default so the
newest active decision on a topic always wins; add `--all` to see the
full history including superseded notes.
