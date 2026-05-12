#!/usr/bin/env python3
"""Apply dream diff to memory files. USER-ONLY — NEVER called by pipeline agents.

Usage:
  python3 dream-apply.py --diff-path <path>

Output: path to written apply-receipt file.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

__all__ = ["main"]

MEMORY_DIR = Path.home() / ".pipeline" / "memory"
ARCHIVE_DIR = Path.home() / ".pipeline" / "memory" / ".archive"

STUB_NOTE = (
    "WARNING: dream-apply mutation logic is stubbed; receipt-only mode. "
    "Implement before relying on automatic apply."
)

RECEIPT_TEMPLATE = """\
# Dream Apply Receipt

**Applied**: {timestamp}
**Diff**: {diff_path}
**Status**: {status}

## Actions taken
{actions}
"""


def parse_diff(diff_path: Path) -> dict:
    """Parse the diff file sections."""
    text = diff_path.read_text()
    sections: dict = {
        "to_merge": [],
        "to_remove": [],
        "raw": text,
    }
    current = None
    for line in text.splitlines():
        if "## Duplicate candidates" in line or "to-merge" in line.lower():
            current = "to_merge"
        elif line.startswith("- ") and current == "to_merge":
            sections["to_merge"].append(line[2:])
    return sections


def apply_diff_stub(diff_path: Path) -> list[str]:
    """Stub: log diff read; no memory mutations applied.

    Returns list of actions taken.
    Real implementation would remove/merge entries per diff schema.
    """
    print(STUB_NOTE, file=sys.stderr)
    actions: list[str] = []
    diff_data = parse_diff(diff_path)
    actions.append(f"Read diff: {diff_path}")
    actions.append(f"Duplicate candidates identified: {len(diff_data['to_merge'])}")
    actions.append("Memory files unchanged (no auto-mutations applied in this version).")
    actions.append(
        "Review duplicate candidates above and apply manually if confirmed."
    )
    return actions


def write_receipt(diff_path: str, actions: list[str], ts: str) -> Path:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    receipt_path = ARCHIVE_DIR / f"apply-receipt-{ts}.md"
    content = RECEIPT_TEMPLATE.format(
        timestamp=ts,
        diff_path=diff_path,
        status="applied",
        actions="\n".join(f"- {a}" for a in actions),
    )
    receipt_path.write_text(content)
    return receipt_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply dream diff to memory files. USER-ONLY."
    )
    parser.add_argument("--diff-path", required=True)
    args = parser.parse_args()

    diff_path = Path(args.diff_path)
    if not diff_path.exists():
        print(f"ERROR: diff not found: {diff_path}", file=sys.stderr)
        return 1

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    actions = apply_diff_stub(diff_path)
    receipt_path = write_receipt(str(diff_path), actions, ts)
    print(str(receipt_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
