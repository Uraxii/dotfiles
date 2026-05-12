#!/usr/bin/env python3
"""Parse pipeline gate verdict files from a run directory.

Usage:
  python3 verdict-parse.py --run-dir <path> --type <type>

Exit codes:
  0  found + parsed successfully
  1  no verdict file found or parse error
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
VERDICT_RE = re.compile(r"^verdict-(?P<type>[^-]+(?:-[^-r][^-]*)*)-r(?P<rev>\d+)\.md$")
FM_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def parse_frontmatter(text: str) -> dict:
    m = FM_RE.match(text)
    if not m:
        return {}
    result: dict = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            result[k.strip()] = v.strip()
    return result


def find_latest(run_dir: Path, verdict_type: str) -> tuple[Path, int] | None:
    best: tuple[Path, int] | None = None
    pattern = re.compile(
        rf"^verdict-{re.escape(verdict_type)}-r(?P<rev>\d+)\.md$"
    )
    for f in run_dir.glob(f"verdict-{verdict_type}-r*.md"):
        m = pattern.match(f.name)
        if not m:
            continue
        rev = int(m.group("rev"))
        if best is None or rev > best[1]:
            best = (f, rev)
    return best


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse pipeline verdict file.")
    parser.add_argument("--run-dir", required=True, help="Pipeline run directory")
    parser.add_argument(
        "--type", required=True,
        choices=sorted(VERDICT_TYPES),
        help="Verdict type",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.is_dir():
        print(json.dumps({"error": f"run-dir not found: {run_dir}"}))
        return 1

    result = find_latest(run_dir, args.type)
    if result is None:
        print(json.dumps({"error": f"no verdict-{args.type}-r*.md found in {run_dir}"}))
        return 1

    path, rev = result
    fm = parse_frontmatter(path.read_text())
    output = {
        "verdict": fm.get("verdict", ""),
        "role": fm.get("role", ""),
        "review_type": fm.get("review_type", ""),
        "loops": fm.get("loops", ""),
        "revision": fm.get("revision", f"r{rev}"),
        "prod_diff_sha": fm.get("prod_diff_sha", ""),
        "path": str(path),
    }
    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
