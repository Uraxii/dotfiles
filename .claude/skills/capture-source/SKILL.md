---
name: capture-source
description: Store a web source's CONTENT (plus metadata + provenance) into the project knowledgebase instead of dropping a bare link. Use WHENEVER you cite, reference, or rely on a web page, article, doc, or blog post in your work or a report, or when the user shares a URL to keep. Deterministic (no model spend): fetches the page and extracts Open Graph / Schema.org / meta + the cleaned article body into `~/.knowledgebase/<project>/sources/`, then indexes it for later search.
---

# capture-source

A cited link rots and carries no content. Store the SOURCE, not the URL: the
cleaned article text plus title/author/published/description/tags land as a
`type: source` note in the project knowledgebase, searchable later.

Deterministic, zero model spend. It fetches + parses the page itself; you do not
read or summarize it into the note.

## Capture a web source

```bash
~/dotfiles/scripts/kb.sh clip "<url>" --project <project>
```

- Writes `~/.knowledgebase/<project>/sources/<slug>.md` with frontmatter
  (`type: source`, title, source url, author, site, published, fetched,
  description, tags) and the cleaned content body, plus the url in `## Refs`.
- `<project>` is the repo/workstream name (e.g. `gvn`). Creates the folder if
  needed.

## Then index + find it

```bash
~/dotfiles/scripts/kb.sh index
~/dotfiles/scripts/kb-index.py query "<terms>" --project <project> --type source
```

## Rules

- Do NOT paste a bare link in a report or the KB when the content matters. Clip
  it, then cite the stored note (and the url in its `## Refs`).
- Internal/code references stay cited (path or ticket id), not clipped.
- `question` / `summary` are left empty on capture; a later classifier fills
  them. Do not spend a model doing it here.
- JS-heavy or auth-gated pages may not extract cleanly; note that and fall back
  to citing the url in `## Refs` if the body comes back empty.

Full knowledgebase doctrine: `~/.claude/rules/orchestration.md`
("Knowledgebase"). Decisions use the separate `record-decision` skill.
