#!/usr/bin/env python3
"""build-kb-index.py — (re)build the FTS5 full-text index over docs/kb/*.md,
and, when an OpenRouter key is available, the kb_embedding semantic index.

The FTS5 rebuild is a pure SQLite operation, stdlib only (Python's sqlite3
ships with FTS5 compiled in). Meant to be cheap enough to run on every
commit that touches docs/kb/, via the post-commit hook installed by
scripts/init-agent-workspace.sh.

The embedding step calls the OpenRouter embeddings API (see
kb_embeddings.py) once per entry and is best-effort: no OPENROUTER_API_KEY,
or an unreachable API, degrades to "FTS5 only" with one printed line. It
never fails the build.

Rebuild semantics: every run clears and repopulates the FTS5 table from the
current docs/kb/*.md files. The KB is small (distilled entries, not raw
transcripts), so a full rebuild is simpler and cheaper than tracking
incremental diffs. kb_embedding rows are upserted per path instead, so a
failed embedding run leaves the previous run's vectors in place rather than
wiping them.

Usage:
    scripts/build-kb-index.py [--root REPO_ROOT] [--db DB_PATH]

Defaults: root = current working directory, db = <root>/kb.db,
entries = <root>/docs/kb/*.md.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path

import kb_embeddings

# ponytail: full-text over the whole markdown body, no field parser. A
# schema that parses "Question:"/"Summary:"/"Resolution:" sections would be
# fragile against entry drift for no real gain — FTS5 over the full body
# already satisfies exact-token search, which is all the doctrine asks for
# right now (semantic search is the kb_embedding table built below).
SCHEMA = "CREATE VIRTUAL TABLE IF NOT EXISTS kb USING fts5(path UNINDEXED, body);"


def kb_entry_paths(entries_dir: Path) -> list[Path]:
    """List docs/kb/*.md entries in a stable order."""
    return sorted(entries_dir.glob("*.md"))


def rebuild_index(paths: list[Path], db_path: Path) -> int:
    """Clear and repopulate the FTS5 index from paths. Returns count."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(SCHEMA)
        conn.execute("DELETE FROM kb;")
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


def embed_kb_entries(paths: list[Path], db_path: Path, api_key: str) -> int:
    """Embed each entry via OpenRouter and upsert it into kb_embedding.

    Returns the number of entries embedded. Raises one of
    kb_embeddings.EMBEDDING_ERRORS on the first failure; the caller treats
    that as "skip vectors, the FTS5 index still stands."
    """
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(kb_embeddings.EMBEDDING_SCHEMA)
        for path in paths:
            body = path.read_text(encoding="utf-8")
            vector = kb_embeddings.fetch_embedding(body, api_key)
            conn.execute(
                "INSERT OR REPLACE INTO kb_embedding "
                "(path, model, dim, vector) VALUES (?, ?, ?, ?);",
                (
                    str(path),
                    kb_embeddings.EMBEDDING_MODEL,
                    len(vector),
                    kb_embeddings.vector_to_blob(vector),
                ),
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

    paths = kb_entry_paths(entries_dir)
    count = rebuild_index(paths, db_path)
    print(f"build-kb-index: {count} entries indexed into {db_path}")

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print(
            "build-kb-index: OPENROUTER_API_KEY not set, skipping semantic "
            "vectors (FTS5 index still built)"
        )
        return 0

    try:
        embedded = embed_kb_entries(paths, db_path, api_key)
        print(
            f"build-kb-index: {embedded} entries embedded into kb_embedding "
            f"({kb_embeddings.EMBEDDING_MODEL})"
        )
    except kb_embeddings.EMBEDDING_ERRORS as exc:
        print(
            f"build-kb-index: embedding failed ({exc}), skipping semantic "
            "vectors (FTS5 index still built)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
