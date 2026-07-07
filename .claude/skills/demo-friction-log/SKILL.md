---
name: demo-friction-log
description: Record a nikki-net framework friction hit from demo development (friction, workaround, proposed feature, severity) into the demo GDD's section 11c table and optionally open a roadmap issue. Use when the user says "log friction", "that was painful, note it", "add to the friction report", or whenever demo work required a workaround for something nikki-net should have provided.
---

# demo-friction-log

The friction report is a PRIMARY deliverable of every demo: it decides
what nikki-net builds next. Log at the moment of friction, never
retroactively.

## Procedure

1. Locate the table: demo GDD section 11c (`docs/<GAME>-GDD.md`), or
   `docs/<GAME>-FRICTION.md` if the GDD links one out.
2. Append one row:
   `| <friction hit> | <workaround used> | <proposed nikki-net feature> | <blocked|slowed|annoyed> |`
   - Friction: what you were trying to do, one sentence, concrete.
   - Workaround: what was actually written instead, with file path(s).
   - Proposed feature: named by EFFECT per repo naming rules (what it
     does for a game dev, not the mechanism).
   - Severity: blocked = could not proceed without the workaround;
     slowed = proceeded but materially slower; annoyed = paper cut.
3. If the row's workaround added per-game netcode that feels like
   framework code, also update the boilerplate count line (lines + file
   paths) in 11c.
4. If severity is blocked, or the user asks: open a roadmap issue via
   `gh issue create` on the nikki-net repo, title = proposed feature
   name, body = the row plus links to the workaround code. Label:
   `friction` (create the label if missing). Paste the issue URL back
   into the row.
5. Never editorialize severity upward or generalize the ask beyond what
   the friction actually demonstrated.
