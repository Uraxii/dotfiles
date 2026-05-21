#!/usr/bin/env python3
"""Write a handoff document for agent session rotation.

Writes <run-dir>/handoff-<role>-<iso8601>.md and prints the path.

Usage:
  python3 handoff-doc.py --role <role> --run-dir <path> --next-focus <text>

Exit codes:
  0  success
  1  error
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

__all__ = ["main"]

TEMPLATE = """\
# Handoff: {role} -> fresh session

**Run**: {run_id}
**Timestamp**: {timestamp}

## Next session focus
{next_focus}

## Referenced artifacts (by path)
- pipeline: {run_dir}/pipeline.md
- brief: {run_dir}/brief.md

## State summary
Session rotated at context threshold. Resume in fresh session using task_id \
if supported by harness; otherwise spawn fresh + read referenced artifacts.
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Write handoff document for agent session rotation."
    )
    parser.add_argument("--role", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--next-focus", required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir).expanduser()
    if not run_dir.is_dir():
        print(f"ERROR: run-dir not found: {run_dir}", file=sys.stderr)
        return 1

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = run_dir.name
    out_path = run_dir / f"handoff-{args.role}-{ts}.md"

    content = TEMPLATE.format(
        role=args.role,
        run_id=run_id,
        timestamp=ts,
        next_focus=args.next_focus,
        run_dir=args.run_dir,
    )
    out_path.write_text(content, encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
