#!/usr/bin/env python3
"""build-kb-index.py — (re)build the FTS5 full-text index over docs/kb/*.md.

No LLM involved: this is a pure SQLite FTS5 rebuild, stdlib only (Python's
sqlite3 ships with FTS5 compiled in). Meant to be cheap enough to run on
every commit that touches docs/kb/, via the post-commit hook installed by
scripts/init-agent-workspace.sh.

Rebuild semantics: every run clears and repopulates the whole table from the
current docs/kb/*.md files. The KB is small (distilled entries, not raw
transcripts), so a full rebuild is simpler and cheaper than tracking
incremental diffs.

Usage:
    scripts/build-kb-index.py [--root REPO_ROOT] [--db DB_PATH]

Defaults: root = current working directory, db = <root>/kb.db,
entries = <root>/docs/kb/*.md.
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

# ponytail: full-text over the whole markdown body, no field parser. A
# schema that parses "Question:"/"Summary:"/"Resolution:" sections would be
# fragile against entry drift for no real gain — FTS5 over the full body
# already satisfies exact-token search, which is all the doctrine asks for
# right now (embeddings are the documented later escalation).
SCHEMA = "CREATE VIRTUAL TABLE IF NOT EXISTS kb USING fts5(path UNINDEXED, body);"


def rebuild_index(entries_dir: Path, db_path: Path) -> int:
    """Clear and repopulate the FTS5 index from entries_dir. Returns count."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(SCHEMA)
        conn.execute("DELETE FROM kb;")
        paths = sorted(entries_dir.glob("*.md"))
        for path in paths:
            body = path.read_text(encoding="utf-8")
            conn.execute(
                "INSERT INTO kb (path, body) VALUES (?, ?);",
                (str(path), body),
            )
        conn.commit()
        return len(paths)
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="build-kb-index.py",
        description="Rebuild the FTS5 index over docs/kb/*.md into kb.db.",
    )
    parser.add_argument(
        "--root", default=".", help="repo root (default: cwd)",
    )
    parser.add_argument(
        "--db", default=None, help="db path (default: <root>/kb.db)",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    entries_dir = root / "docs" / "kb"
    db_path = Path(args.db).resolve() if args.db else root / "kb.db"

    if not entries_dir.is_dir():
        print(f"build-kb-index: no {entries_dir}, nothing to index")
        return 0

    count = rebuild_index(entries_dir, db_path)
    print(f"build-kb-index: {count} entries indexed into {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
