#!/usr/bin/env python3
"""verdict_read — read verdict-<type>-r<N>.md files.

Usage:
    verdict_read.py --run <id> --project <path> --type <type> \\
        [--revision <int> | --latest] \\
        [--field {verdict|role|revision|body|all}]

Stdlib-only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

VALID_FIELDS = frozenset({"verdict", "role", "revision", "body", "all"})


def _run_dir(project: Path, run_id: str) -> Path:
    return project / ".pipeline" / "runs" / run_id


def _parse_verdict_file(path: Path) -> dict[str, Any]:
    """Parse frontmatter + body. Returns dict with keys: verdict, role, revision, review_type, body."""
    text = path.read_text(encoding="utf-8")
    fm: dict[str, Any] = {}
    body = text

    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end >= 0:
            fm_raw = text[4:end]
            body = text[end + 5:]
            for line in fm_raw.splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    k = k.strip()
                    v = v.strip()
                    # C2: strip surrounding quotes (single or double) so
                    # `verdict: "approved"` parses identically to `verdict: approved`.
                    if len(v) >= 2 and v[0] == v[-1] and v[0] in ('"', "'"):
                        v = v[1:-1]
                    fm[k] = v

    # Coerce revision to int.
    try:
        rev = int(fm.get("revision", 0))
    except (ValueError, TypeError):
        rev = 0

    return {
        "verdict": fm.get("verdict", ""),
        "role": fm.get("role", ""),
        "revision": rev,
        "review_type": fm.get("review_type", ""),
        "written_at": fm.get("written_at", ""),
        "body": body.strip(),
    }


def _find_latest(run_dir: Path, verdict_type: str) -> int | None:
    """Return the highest revision number present, or None."""
    max_n: int | None = None
    for p in run_dir.glob(f"verdict-{verdict_type}-r*.md"):
        stem = p.stem  # e.g. "verdict-design-r3"
        parts = stem.rsplit("-r", 1)
        if len(parts) != 2:
            continue
        try:
            n = int(parts[1])
        except ValueError:
            continue
        if max_n is None or n > max_n:
            max_n = n
    return max_n


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="verdict_read.py",
        description="Read verdict-<type>-r<N>.md files.",
    )
    parser.add_argument("--run", required=True, help="Run artifact-id")
    parser.add_argument(
        "--project",
        default=str(Path.cwd()),
        help="Project root (default: cwd)",
    )
    parser.add_argument("--type", dest="verdict_type", required=True, help="Verdict type")

    rev_group = parser.add_mutually_exclusive_group()
    rev_group.add_argument("--revision", type=int, default=None, help="Specific revision")
    rev_group.add_argument(
        "--latest",
        action="store_true",
        default=False,
        help="Pick max revision from glob",
    )

    parser.add_argument(
        "--field",
        choices=sorted(VALID_FIELDS),
        default="all",
        help="Field to print (default: all as JSON)",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    project = Path(args.project).expanduser().resolve()
    run_dir = _run_dir(project, args.run)
    if not run_dir.is_dir():
        sys.stderr.write(f"run dir not found: {run_dir}\n")
        sys.exit(1)

    if args.latest:
        revision = _find_latest(run_dir, args.verdict_type)
        if revision is None:
            sys.stderr.write(
                f"no verdict-{args.verdict_type}-r*.md found in {run_dir}\n"
            )
            sys.exit(1)
    elif args.revision is not None:
        revision = args.revision
    else:
        # Default: --latest behaviour when neither specified.
        revision = _find_latest(run_dir, args.verdict_type)
        if revision is None:
            sys.stderr.write(
                f"no verdict-{args.verdict_type}-r*.md found in {run_dir}\n"
            )
            sys.exit(1)

    verdict_path = run_dir / f"verdict-{args.verdict_type}-r{revision}.md"
    if not verdict_path.is_file():
        sys.stderr.write(f"verdict file not found: {verdict_path}\n")
        sys.exit(1)

    parsed = _parse_verdict_file(verdict_path)
    field = args.field or "all"

    if field == "all":
        sys.stdout.write(json.dumps(parsed, indent=2) + "\n")
    else:
        val = parsed.get(field, "")
        if isinstance(val, str):
            sys.stdout.write(val + "\n")
        else:
            sys.stdout.write(json.dumps(val) + "\n")


if __name__ == "__main__":
    main()
