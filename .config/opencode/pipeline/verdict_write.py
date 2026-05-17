#!/usr/bin/env python3
"""verdict_write — write a verdict-<type>-r<N>.md file atomically.

Usage:
    verdict_write.py --run <id> --project <path> \\
        --type {design|code|ops|review|security|test|friction} \\
        --revision <int> --verdict {approved|blocked|needs-revision} \\
        --role <role> [--review-type <type>] \\
        [--body-file <path> | --body-stdin]

Stdlib-only. Atomic write via tmp + rename.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

_PIPELINE_DIR = Path(__file__).parent
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

from comms.env import atomic_write_text  # noqa: E402

VALID_TYPES = frozenset({
    "design", "code", "ops", "review", "security", "test", "friction"
})
VALID_VERDICTS = frozenset({"approved", "blocked", "needs-revision"})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_dir(project: Path, run_id: str) -> Path:
    return project / ".pipeline" / "runs" / run_id


def _verdict_path(run_dir: Path, verdict_type: str, revision: int) -> Path:
    return run_dir / f"verdict-{verdict_type}-r{revision}.md"


def _compose(
    verdict_type: str,
    revision: int,
    verdict: str,
    role: str,
    review_type: str | None,
    body: str,
) -> str:
    lines = [
        "---",
        f"verdict: {verdict}",
        f"role: {role}",
        f"review_type: {review_type or verdict_type}",
        f"revision: {revision}",
        f"written_at: {_now_iso()}",
        "---",
        "",
    ]
    if body:
        lines.append(body.rstrip())
        lines.append("")
    return "\n".join(lines)


def _atomic_write(path: Path, content: str) -> None:
    atomic_write_text(path, content, mode=0o644)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="verdict_write.py",
        description="Write a verdict-<type>-r<N>.md file atomically.",
    )
    parser.add_argument("--run", required=True, help="Run artifact-id")
    parser.add_argument(
        "--project",
        default=str(Path.cwd()),
        help="Project root (default: cwd)",
    )
    parser.add_argument(
        "--type",
        dest="verdict_type",
        required=True,
        choices=sorted(VALID_TYPES),
        help="Verdict type",
    )
    parser.add_argument(
        "--revision", required=True, type=int, help="Revision integer (e.g. 1)"
    )
    parser.add_argument(
        "--verdict",
        required=True,
        choices=sorted(VALID_VERDICTS),
        help="Verdict value",
    )
    parser.add_argument("--role", required=True, help="Authoring role name")
    parser.add_argument(
        "--review-type", default=None, help="Optional review-type override"
    )
    body_group = parser.add_mutually_exclusive_group()
    body_group.add_argument(
        "--body-file", default=None, help="Path to file containing verdict body"
    )
    body_group.add_argument(
        "--body-stdin",
        action="store_true",
        default=False,
        help="Read verdict body from stdin",
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

    body = ""
    if args.body_stdin:
        body = sys.stdin.read()
    elif args.body_file:
        body_path = Path(args.body_file).expanduser().resolve()
        if not body_path.is_file():
            sys.stderr.write(f"body file not found: {body_path}\n")
            sys.exit(1)
        body = body_path.read_text(encoding="utf-8")

    content = _compose(
        args.verdict_type,
        args.revision,
        args.verdict,
        args.role,
        args.review_type,
        body,
    )
    out_path = _verdict_path(run_dir, args.verdict_type, args.revision)
    _atomic_write(out_path, content)
    sys.stdout.write(f"{out_path}\n")


if __name__ == "__main__":
    main()
