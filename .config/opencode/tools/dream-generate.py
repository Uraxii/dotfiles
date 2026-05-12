#!/usr/bin/env python3
"""Generate memory curation diff artifact. READ-ONLY — never mutates memory files.

Usage:
  python3 dream-generate.py --scope run --run-id <artifact-id>
  python3 dream-generate.py --scope background

Output: path to written diff file under ~/.pipeline/dreams/
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

__all__ = ["main"]

MEMORY_DIR = Path.home() / ".pipeline" / "memory"
DREAMS_DIR = Path.home() / ".pipeline" / "dreams"


def load_memory_files(scope: str, run_id: str | None) -> list[tuple[Path, str]]:
    """Return list of (path, content) for relevant memory files."""
    results = []
    if not MEMORY_DIR.exists():
        return results
    for p in sorted(MEMORY_DIR.glob("*.md")):
        results.append((p, p.read_text()))
    return results


def analyze_duplicates(entries: list[tuple[Path, str]]) -> list[str]:
    """Identify duplicate/similar rules across files."""
    findings = []
    seen: dict[str, str] = {}
    for path, content in entries:
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("- ") and len(line) > 20:
                key = line[:50].lower()
                if key in seen:
                    findings.append(
                        f"DUPLICATE: similar rule in {path.name} and {seen[key]}"
                    )
                else:
                    seen[key] = path.name
    return findings


def build_diff(entries: list[tuple[Path, str]], scope: str) -> str:
    """Build a diff artifact documenting curation recommendations."""
    ts = datetime.now(timezone.utc).isoformat()
    lines = [
        f"# Dream Diff — {scope} scope",
        f"**Generated**: {ts}",
        f"**Files analyzed**: {len(entries)}",
        "",
        "## Summary",
        "",
    ]

    if not entries:
        lines.append("No memory files found. Nothing to curate.")
        return "\n".join(lines)

    duplicates = analyze_duplicates(entries)

    lines.append(f"- Total memory files: {len(entries)}")
    lines.append(f"- Potential duplicates: {len(duplicates)}")
    lines.append("")
    lines.append("## Duplicate candidates (to-merge)")
    lines.append("")
    if duplicates:
        for d in duplicates:
            lines.append(f"- {d}")
    else:
        lines.append("None detected.")
    lines.append("")
    lines.append("## Files analyzed")
    lines.append("")
    for path, content in entries:
        entry_count = sum(
            1 for ln in content.splitlines() if ln.strip().startswith("- ")
        )
        lines.append(f"- `{path.name}`: {entry_count} entries")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        "Apply this diff via `/dream-apply` slash command (USER-ONLY). "
        "Do NOT auto-apply."
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate memory curation diff (read-only)."
    )
    parser.add_argument("--scope", required=True, choices=["run", "background"])
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()

    entries = load_memory_files(args.scope, args.run_id)
    diff_text = build_diff(entries, args.scope)

    DREAMS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = DREAMS_DIR / f"{ts}-{args.scope}.diff.md"
    out_path.write_text(diff_text)
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
