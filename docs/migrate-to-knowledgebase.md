# Migrating to the global board + knowledgebase

Two things moved **out of your project repos** and into machine-local homes:

| Old (in each repo) | New (machine-local) | Holds |
|--------------------|---------------------|-------|
| `<repo>/.beads/` | `~/.beads-hub/<project>/.beads` | bd board: statuses, deps, claims |
| `<repo>/docs/kb/` + decision vault | `~/.knowledgebase/<project>/` | durable distilled memory |

Why: boards and knowledge are personal, cross-project, and regenerable. Keeping
them per-repo scattered the state and cluttered every project. Now there is one
board hub and one knowledgebase, each split per project, with a single global
index over the top.

The root is `~/.beads-hub`, **not** `~/.beads`, because bd 1.1.0 refuses to
`bd init` under any `.beads`-named ancestor.

---

## 1. Boards: per-repo `.beads` -> `~/.beads-hub`

For each project that already has an in-repo board:

```bash
# 1. export the old board's issues to interchange JSONL
cd ~/Projects/<project>
bd export --output /tmp/<project>-issues.jsonl      # or: bd list --json > ...

# 2. create + register the project's board under the hub
~/Projects/agent-workbench/.claude/skills/agent-workbench/agent-workbench hub add <project>

# 3. import the old issues into the new board
BEADS_DIR="$(~/Projects/agent-workbench/.claude/skills/agent-workbench/agent-workbench hub path <project>)" \
  bd import /tmp/<project>-issues.jsonl

# 4. verify, then delete the old in-repo board
BEADS_DIR="$(~/Projects/agent-workbench/.claude/skills/agent-workbench/agent-workbench hub path <project>)" bd list
rm -rf ~/Projects/<project>/.beads
```

Aggregate all registered boards into the unified read view:

```bash
~/Projects/agent-workbench/.claude/skills/agent-workbench/agent-workbench hub sync
~/Projects/agent-workbench/.claude/skills/agent-workbench/agent-workbench hub list
```

From now on, **do not** run `bd init` inside a repo. Agents write to a project
board with `BEADS_DIR="$(agent-workbench hub path <project>)" bd ...`.

---

## 2. Knowledge: `docs/kb/` + vault -> `~/.knowledgebase`

```bash
# create the vault + this project's folders
~/Projects/agent-workbench/.claude/skills/agent-workbench/agent-workbench kb add <project>      # -> decisions notes research sources

# move existing distilled notes and decisions in
mv ~/Projects/<project>/docs/kb/*.md        ~/.knowledgebase/<project>/notes/
mv "~/Projects/<project>/vault/20 Permanent/decisions/"*.md \
                                            ~/.knowledgebase/<project>/decisions/

# rebuild the global index
~/Projects/agent-workbench/.claude/skills/agent-workbench/agent-workbench kb index
~/Projects/agent-workbench/.claude/skills/agent-workbench/agent-workbench kb query "<a term>" --project <project>
```

Point `record-decision` at the vault so new decisions land in the right place:

```bash
export KB_DECISIONS_DIR="$HOME/.knowledgebase/<project>/decisions"
```

(Add that to your project's env / direnv, or pass `--decisions-dir` per call.)

From now on, write durable notes into `~/.knowledgebase/<project>/`, **not**
`docs/kb/`.

---

## 3. Web sources: store content, not just links

Two capture paths, both deterministic (no model spend), both writing the same
`type: source` note into `<project>/sources/`:

```bash
# agent / CLI path
~/Projects/agent-workbench/.claude/skills/agent-workbench/agent-workbench kb clip "https://example.com/article" --project <project>
```

```
# human browse path: import the Web Clipper template once
docs/kb-clipper-template.json  ->  Obsidian Web Clipper -> Settings -> Templates -> Import
```

Both fill title / source / author / published / description / tags from Open
Graph + Schema.org + meta tags, and store the cleaned article body. The
`question` and `summary` fields are left empty for a later classifier pass.

---

## Known follow-ups

- `.claude/skills/agent-workbench/agent-workbench init-workspace` still
  scaffolds `docs/kb/` and the old per-repo `build-kb-index.py` still exists;
  both are legacy until retired in favour of `~/.knowledgebase`.
- `kb-clip.py`'s HTML-to-markdown keeps headings / paragraphs / lists but drops
  inline formatting (bold, inline links); the source URL is preserved in
  `## Refs`.
