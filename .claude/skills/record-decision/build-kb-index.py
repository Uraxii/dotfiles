#!/usr/bin/env python3
"""Build and query the recency-weighted FTS5 index over the project KB.

Sources indexed: docs/kb/**/*.md (distilled findings) and
vault/20 Permanent/**/*.md (canon + decisions/, incl. the decisions/
supersession chain written by record_decision.py). Stdlib only: sqlite3's
bundled FTS5 does the full-text search, no external search engine.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import date
from pathlib import Path

# Reuse the frontmatter parser and git-root helper already written for
# decision notes instead of a second hand-rolled copy.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from record_decision import git_root, parse_frontmatter  # noqa: E402

HEADING_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)

# Placeholders; main() resolves the real values from CLI/env before any
# function below reads them.
REPO_ROOT = Path()
DB_PATH = Path()
KB_SOURCE_DIRS: list[Path] = []


def resolve_db_path(cli_value: str | None, root: Path) -> Path:
    """--db > KB_DB env > <gitroot>/kb.db."""
    if cli_value:
        return Path(cli_value)
    env = os.environ.get("KB_DB")
    if env:
        return Path(env)
    return root / "kb.db"


def resolve_scan_dirs(cli_values: list[str] | None, root: Path) -> list[Path]:
    """--scan (repeatable) > KB_SCAN_DIRS env (os.pathsep-sep) > defaults.

    Default is <gitroot>/vault/20 Permanent plus <gitroot>/docs/kb, the
    latter only if it exists.
    """
    if cli_values:
        return [Path(p) for p in cli_values]
    env = os.environ.get("KB_SCAN_DIRS")
    if env:
        return [Path(p) for p in env.split(os.pathsep) if p]
    dirs = [root / "vault" / "20 Permanent"]
    docs_kb = root / "docs" / "kb"
    if docs_kb.exists():
        dirs.append(docs_kb)
    return dirs


# Recency blend: bm25(kb) is negative, more negative = better match, so
# relevance = -bm25 flips it to higher-is-better. day_ordinal / 1e6 turns
# today's toordinal() (~739000) into a small ~0.74 bonus: enough to break
# a near-tie between two notes matching the SAME query about equally well
# (e.g. a decision and the one it superseded) in favor of the newer one,
# without letting a merely-recent note outrank a genuinely stronger match
# elsewhere. Superseded notes are filtered out before this ever matters
# in the default (non --all) case.
# ponytail: a flat constant divisor, not a normalized-per-corpus scale;
# revisit if the corpus grows enough for bm25 spreads to dwarf ~0.7.
RECENCY_DIVISOR = 1_000_000.0


def fallback_title(path: Path, body: str) -> str:
    """Title for a note with no frontmatter: first heading, else filename."""
    heading = HEADING_RE.search(body)
    if heading:
        return heading.group(1).strip()
    return path.stem.replace("_", " ").replace("-", " ")


def display_path(path: Path, root: Path) -> str:
    """Path relative to the repo root when possible, else absolute.

    A --scan/KB_SCAN_DIRS root outside the repo (e.g. a /tmp override)
    has no sensible relative form, so fall back to the absolute path.
    """
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def load_note(path: Path) -> dict[str, str]:
    """Read one markdown file into the row shape the index stores."""
    fields, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    return {
        "path": display_path(path, REPO_ROOT),
        "title": fields.get("title") or fallback_title(path, body),
        "topic": fields.get("topic", ""),
        "date": fields.get("date", ""),
        "status": fields.get("status", ""),
        "body": body,
    }


def find_markdown_files() -> list[Path]:
    """All markdown files under the indexed KB source directories."""
    files: list[Path] = []
    for source_dir in KB_SOURCE_DIRS:
        if source_dir.exists():
            files.extend(source_dir.rglob("*.md"))
    return files


def build_index() -> int:
    """Rebuild kb.db from scratch (drop + recreate is trivially idempotent)."""
    notes = [load_note(path) for path in find_markdown_files()]
    con = sqlite3.connect(DB_PATH)
    with con:
        con.execute("DROP TABLE IF EXISTS kb")
        con.execute(
            "CREATE VIRTUAL TABLE kb USING fts5(path, title, topic, date, status, body)"
        )
        con.executemany(
            "INSERT INTO kb (path, title, topic, date, status, body) "
            "VALUES (:path, :title, :topic, :date, :status, :body)",
            notes,
        )
    con.close()
    print(json.dumps({"indexed": len(notes), "db": str(DB_PATH)}))
    return len(notes)


def day_ordinal(date_str: str) -> int:
    """ISO date -> ordinal day number, 0 for missing/unparseable dates."""
    try:
        return date.fromisoformat(date_str).toordinal()
    except ValueError:
        return 0


def fts5_match_expr(query: str) -> str:
    """Turn free-text user input into a safe FTS5 MATCH expression.

    FTS5's query syntax gives meaning to punctuation (":", "-", quotes,
    "*"), so a raw phrase like "mesh-deformed" is parsed as a column
    filter and errors out. Quoting each word token neutralizes all of
    that syntax; tokens are then implicitly ANDed, same as a plain
    keyword search.
    """
    tokens = re.findall(r"\w+", query)
    return " ".join(f'"{t}"' for t in tokens)


def query_index(query: str, include_superseded: bool) -> list[dict]:
    """Search kb.db, ranked by bm25 relevance blended with recency."""
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT path, title, topic, date, status, "
        "snippet(kb, 5, '[', ']', '...', 12) AS snippet, "
        "bm25(kb) AS bm25_rank "
        "FROM kb WHERE kb MATCH ?",
        (fts5_match_expr(query),),
    ).fetchall()
    con.close()

    results = []
    for row in rows:
        if not include_superseded and row["status"] == "superseded":
            continue
        relevance = -row["bm25_rank"]
        recency_bonus = day_ordinal(row["date"]) / RECENCY_DIVISOR
        results.append(
            {
                "path": row["path"],
                "title": row["title"],
                "date": row["date"],
                "status": row["status"],
                "snippet": row["snippet"],
                "score": relevance + recency_bonus,
            }
        )
    results.sort(key=lambda r: r["score"], reverse=True)
    return results


def build_parser() -> argparse.ArgumentParser:
    """Construct the build/query CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        default=None,
        help="override the index db path (else KB_DB env, else <gitroot>/kb.db)",
    )
    parser.add_argument(
        "--scan",
        action="append",
        default=None,
        metavar="DIR",
        help="override a scan root (repeatable; else KB_SCAN_DIRS env, "
        "os.pathsep-separated; else the gitroot vault/docs defaults)",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("build", help="rebuild kb.db from docs/kb + vault/20 Permanent")

    query_cmd = sub.add_parser("query", help="full-text search the index")
    query_cmd.add_argument("q")
    query_cmd.add_argument(
        "--all", action="store_true", help="include superseded notes"
    )

    return parser


def main(argv: list[str]) -> int:
    """CLI entry point: dispatch to build or query (build is the default)."""
    args = build_parser().parse_args(argv)
    global REPO_ROOT, DB_PATH, KB_SOURCE_DIRS
    REPO_ROOT = git_root()
    DB_PATH = resolve_db_path(args.db, REPO_ROOT)
    KB_SOURCE_DIRS = resolve_scan_dirs(args.scan, REPO_ROOT)
    if args.command == "query":
        print(json.dumps(query_index(args.q, args.all), indent=2))
    else:
        build_index()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
