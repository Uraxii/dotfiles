#!/usr/bin/env python3
"""Parse pipeline gate verdict files from a run directory.

Globs verdict-<type>-r*.md, picks max revision, parses YAML frontmatter.
Returns JSON: {verdict, role, review_type, loops, revision, prod_diff_sha,
blocker_class, path}.

Usage:
  python3 verdict-parse.py --run-dir <path> --type <type>

Exit codes:
  0  found + parsed successfully
  1  error (not found, parse failure, bad args)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

__all__ = ["main"]

VERDICT_TYPES = frozenset(
    {"design", "code", "ops", "review", "test-audit", "friction"}
)
FM_RE = re.compile(r"\A---\s*\n(.*?)\n---", re.DOTALL)
BLOCKER_SEQ_RE = re.compile(r"^\s*\[([^\]]*)\]\s*$")


def parse_frontmatter(text: str, path: Path) -> dict[str, object]:
    m = FM_RE.match(text)
    if not m:
        raise ValueError(f"frontmatter parse failed: {path}")
    kv: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            kv[k.strip()] = v.strip()
    return kv


def parse_blocker_class(raw: str) -> list[str]:
    """Parse single-line YAML flow-seq '[a, b]' → ['a', 'b']. Empty list for []."""
    seq_m = BLOCKER_SEQ_RE.match(raw)
    if not seq_m:
        return []
    inner = seq_m.group(1).strip()
    if not inner:
        return []
    return [x.strip() for x in inner.split(",") if x.strip()]


def find_latest(run_dir: Path, verdict_type: str) -> tuple[Path, int] | None:
    pattern = re.compile(
        rf"^verdict-{re.escape(verdict_type)}-r(?P<rev>\d+)\.md$"
    )
    best: tuple[Path, int] | None = None
    for f in run_dir.glob(f"verdict-{verdict_type}-r*.md"):
        m = pattern.match(f.name)
        if not m:
            continue
        rev = int(m.group("rev"))
        if best is None or rev > best[1]:
            best = (f, rev)
    return best


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parse pipeline verdict file. Returns JSON to stdout."
    )
    parser.add_argument("--run-dir", required=True, help="Pipeline run directory")
    parser.add_argument(
        "--type",
        required=True,
        choices=sorted(VERDICT_TYPES),
        help="Verdict type",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir).expanduser()
    if not run_dir.is_dir():
        print(f"ERROR: run-dir not found: {run_dir}", file=sys.stderr)
        return 1

    result = find_latest(run_dir, args.type)
    if result is None:
        print(
            f"ERROR: no verdict-{args.type}-r*.md in {run_dir}",
            file=sys.stderr,
        )
        return 1

    path, rev = result
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(text, path)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    blocker_raw = fm.get("blocker_class", "")
    blocker_list = parse_blocker_class(blocker_raw) if blocker_raw else []

    output: dict[str, object] = {
        "verdict": fm.get("verdict", ""),
        "role": fm.get("role", ""),
        "review_type": fm.get("review_type", ""),
        "loops": fm.get("loops", ""),
        "revision": fm.get("revision", f"r{rev}"),
        "prod_diff_sha": fm.get("prod_diff_sha", ""),
        "blocker_class": blocker_list,
        "path": str(path),
    }
    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
