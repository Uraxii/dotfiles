# Claude Code skills

User-level skills loaded by Claude Code from `~/.claude/skills/`. Each skill is a directory with a `SKILL.md` (frontmatter + body) plus optional bundled resources.

Tree maintained as the Claude Code source of truth. Hermes-equivalent skills live under `.hermes/skills/` with omerxx-style frontmatter; opencode versions under `opencode/skills/`. Edit files directly — no generator.

## Skills

| Skill | Description |
|-------|-------------|
| [caveman](caveman/SKILL.md) | Terse smart-caveman output style; pin via memory for persistent activation. |
| [handoff](handoff/SKILL.md) | Compact the current conversation into a durable handoff doc in `$TMPDIR` for another session. |
| [diagnose](diagnose/SKILL.md) | Disciplined diagnosis loop for hard bugs / perf regressions. |
| [tdd](tdd/SKILL.md) | Red-green-refactor TDD loop. |
| [prototype](prototype/SKILL.md) | Throwaway prototype to flesh out a design before committing to it. |
| [triage](triage/SKILL.md) | State-machine-driven issue triage. |
| [yeet](yeet/SKILL.md) | Stage + commit + push + open PR in one flow. |
| [improve-codebase-architecture](improve-codebase-architecture/SKILL.md) | Find deepening / refactor opportunities. |
| [write-a-skill](write-a-skill/SKILL.md) | Author new skills with proper structure. |
| [artifact-serve](artifact-serve/SKILL.md) | Serve generated artifacts over HTTP / Tailscale + collect feedback. |
| [zoom-out](zoom-out/SKILL.md) | Broader-context recap for unfamiliar code. |
| [record-decision](record-decision/SKILL.md) | Record an architectural/scope decision the same turn into a dated, auditable vault note; recency-weighted FTS5 retrieval. |

### Matt Pocock engineering set (v1.1.0)

| Skill | Description |
|-------|-------------|
| [ask-matt](ask-matt/SKILL.md) | Router over the engineering skills; asks which skill or flow fits. |
| [wayfinder](wayfinder/SKILL.md) | Chart a huge, multi-session effort as a shared map of investigation tickets. |
| [research](research/SKILL.md) | Background agent investigates a question against primary sources into a cited Markdown file. |
| [domain-modeling](domain-modeling/SKILL.md) | Build / sharpen the project's ubiquitous language; record ADRs. |
| [codebase-design](codebase-design/SKILL.md) | Shared vocabulary for designing deep modules and placing seams. |
| [to-spec](to-spec/SKILL.md) | Turn a sharpened idea thread into a specification document. |
| [to-tickets](to-tickets/SKILL.md) | Split a spec into tracer-bullet tickets with blocking edges. |
| [implement](implement/SKILL.md) | Build one ticket by driving tdd internally, then code-review the diff. |
| [code-review](code-review/SKILL.md) | Two-axis review (Standards + Spec) of a diff or branch. |
| [resolving-merge-conflicts](resolving-merge-conflicts/SKILL.md) | Resolve an in-progress git merge / rebase conflict. |
