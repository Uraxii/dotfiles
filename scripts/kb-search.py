#!/usr/bin/env python3
"""kb-search.py — query the per-project KB (kb.db, built by
build-kb-index.py) by keyword, semantic similarity, or both.

Three modes:
    keyword   FTS5 exact-token match over docs/kb/*.md bodies.
    semantic  Embed the query via OpenRouter, cosine-rank against
              kb_embedding vectors (numpy brute force, no index).
    hybrid    Reciprocal rank fusion of keyword + semantic (default).

semantic and hybrid need OPENROUTER_API_KEY in the environment and a
kb_embedding table populated by build-kb-index.py. Either missing, or the
API being unreachable, degrades to a plain keyword search with one printed
line explaining why — this CLI never hard-fails just because the network
embedding path is down.

Usage:
    scripts/kb-search.py QUERY [--mode keyword|semantic|hybrid] [--top-k N]
                          [--root REPO_ROOT] [--db DB_PATH]
"""
from __future__ import annotations

import argparse
import os
import re
import sqlite3
from pathlib import Path

import numpy as np

import kb_embeddings

DEFAULT_TOP_K = 5
# Reciprocal rank fusion damping constant; 60 is the standard default from
# the original RRF paper (Cormack et al.) and needs no per-repo tuning.
RRF_K = 60

_QUERY_WORD_RE = re.compile(r"\w+")


def fts5_query(text: str) -> str:
    """Turn free text into a safe FTS5 MATCH expression.

    FTS5's MATCH argument is itself a tiny query language (AND/OR/NOT,
    column filters, phrase quoting) — a raw CLI query like "bubble-up"
    or "a:b" would be parsed as syntax, not literal words, and error out.
    Quoting each word as a literal token and AND-ing them side-steps that
    and matches the "all these words appear" behavior a search CLI caller
    expects.
    """
    tokens = _QUERY_WORD_RE.findall(text)
    return " AND ".join(f'"{token}"' for token in tokens)


def keyword_search(conn: sqlite3.Connection, query: str, top_k: int) -> list[str]:
    """Return up to top_k KB paths ranked by FTS5 bm25 relevance."""
    match_expr = fts5_query(query)
    if not match_expr:
        return []
    rows = conn.execute(
        "SELECT path FROM kb WHERE kb MATCH ? ORDER BY rank LIMIT ?;",
        (match_expr, top_k),
    ).fetchall()
    return [row[0] for row in rows]


def cosine_rank(query_vector: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Cosine similarity of one query vector against each row of matrix."""
    query_norm = query_vector / np.linalg.norm(query_vector)
    matrix_norm = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix_norm @ query_norm


def semantic_search(
    conn: sqlite3.Connection, query: str, api_key: str, top_k: int,
) -> list[str] | None:
    """Return up to top_k KB paths ranked by cosine similarity.

    Returns None (not an error) if kb_embedding doesn't exist yet, is
    empty, or was built from a different model than the one this process
    would query with — all three mean "no usable vectors right now", and
    the caller falls back to keyword search. Raises
    kb_embeddings.EMBEDDING_ERRORS if the OpenRouter call itself fails.
    """
    # A build that ran without OPENROUTER_API_KEY never creates this table
    # at all, so ensure it exists before querying it (empty result either
    # way, this just avoids "no such table").
    conn.execute(kb_embeddings.EMBEDDING_SCHEMA)
    rows = conn.execute("SELECT path, model, vector FROM kb_embedding;").fetchall()
    if not rows:
        print("kb-search: no kb_embedding rows, run build-kb-index.py with OPENROUTER_API_KEY set")
        return None
    stale = [path for path, model, _vector in rows if model != kb_embeddings.EMBEDDING_MODEL]
    if stale:
        print(
            f"kb-search: kb_embedding has vectors from a different model "
            f"than {kb_embeddings.EMBEDDING_MODEL!r}, rebuild kb.db"
        )
        return None

    query_vector = np.asarray(kb_embeddings.fetch_embedding(query, api_key), dtype=np.float32)
    paths = [path for path, _model, _vector in rows]
    matrix = np.stack([kb_embeddings.blob_to_vector(vector) for _p, _m, vector in rows])
    order = np.argsort(-cosine_rank(query_vector, matrix))[:top_k]
    return [paths[i] for i in order]


def hybrid_search(
    conn: sqlite3.Connection, query: str, api_key: str, top_k: int,
) -> list[str]:
    """Fuse keyword and semantic rankings via reciprocal rank fusion.

    If semantic_search has no usable vectors (returns None), degrades to
    keyword ranking alone rather than failing.
    """
    keyword_ranks = keyword_search(conn, query, top_k * 4)
    semantic_ranks = semantic_search(conn, query, api_key, top_k * 4)
    if semantic_ranks is None:
        return keyword_ranks[:top_k]

    scores: dict[str, float] = {}
    for ranks in (keyword_ranks, semantic_ranks):
        for rank, path in enumerate(ranks):
            scores[path] = scores.get(path, 0.0) + 1.0 / (RRF_K + rank + 1)
    return sorted(scores, key=scores.get, reverse=True)[:top_k]


def resolve_results(
    conn: sqlite3.Connection, mode: str, query: str, api_key: str | None, top_k: int,
) -> list[str]:
    """Run the requested search mode, degrading to keyword on any semantic
    failure (missing key, unreachable API, no/stale vectors)."""
    if mode == "keyword":
        return keyword_search(conn, query, top_k)

    if not api_key:
        print("kb-search: OPENROUTER_API_KEY not set, falling back to keyword search")
        return keyword_search(conn, query, top_k)

    try:
        if mode == "semantic":
            results = semantic_search(conn, query, api_key, top_k)
        else:
            results = hybrid_search(conn, query, api_key, top_k)
    except kb_embeddings.EMBEDDING_ERRORS as exc:
        print(f"kb-search: semantic lookup failed ({exc}), falling back to keyword search")
        return keyword_search(conn, query, top_k)

    return keyword_search(conn, query, top_k) if results is None else results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="kb-search.py",
        description="Query kb.db by keyword, semantic similarity, or both.",
    )
    parser.add_argument("query", help="search text")
    parser.add_argument(
        "--mode", choices=["keyword", "semantic", "hybrid"], default="hybrid",
        help="search mode (default: hybrid)",
    )
    parser.add_argument(
        "--top-k", type=int, default=DEFAULT_TOP_K, help="max results (default: 5)",
    )
    parser.add_argument("--root", default=".", help="repo root (default: cwd)")
    parser.add_argument("--db", default=None, help="db path (default: <root>/kb.db)")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    db_path = Path(args.db).resolve() if args.db else root / "kb.db"
    if not db_path.exists():
        print(f"kb-search: no {db_path}, run build-kb-index.py first")
        return 1

    conn = sqlite3.connect(db_path)
    try:
        api_key = os.environ.get("OPENROUTER_API_KEY")
        results = resolve_results(conn, args.mode, args.query, api_key, args.top_k)
    finally:
        conn.close()

    if not results:
        print("kb-search: no matches")
        return 0
    for rank, path in enumerate(results, start=1):
        print(f"{rank}. {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
