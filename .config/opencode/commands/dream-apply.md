---
description: USER-ONLY apply dream diff to memory. Never invoke from pipeline agents.
agent: primary
subtask: false
---

Apply a dream diff to pipeline memory files. USER-ONLY — pipeline agents must NOT invoke this.

This command invokes `dream-apply.py` via bash. The bash `ask` permission gate will present the command for your approval before execution.

Usage: `/dream-apply ~/.pipeline/dreams/<timestamp>-<scope>.diff.md`

```bash
python3 ~/.config/opencode/tools/dream-apply.py --diff-path $1
```
