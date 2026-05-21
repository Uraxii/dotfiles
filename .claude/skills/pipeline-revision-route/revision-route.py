#!/usr/bin/env python3
"""revision-route — map a verdict file to its next-action instruction.

Reads a verdict file (with YAML frontmatter), routes to action JSON.
Calls _assert_table_sync() on every invocation (drift guard — C3/C5).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Final

# Canonical routing table keyed on (review_type, role).
# Used for routing AND drift-guard synchronisation with orchestrator.md.
ROUTING_TABLE: Final[dict[tuple[str, str], dict]] = {
    ("design", "architect"): {
        "respawn_target": "architect",
        "loop_cap": 3,
        "filename_slot": "verdict-design-r<N>.md",
    },
    ("code", "skeptic-code"): {
        "respawn_target": "build",
        "loop_cap": 3,
        "filename_slot": "verdict-code-r<N>.md",
    },
    ("ops", "skeptic-ops"): {
        "respawn_target": "build",
        "loop_cap": 1,
        "filename_slot": "verdict-ops-r<N>.md",
    },
    ("review", "reviewer"): {
        "respawn_target": "build",
        "loop_cap": 3,
        "filename_slot": "verdict-review-r<N>.md",
    },
    ("code", "security-auditor"): {
        "respawn_target": "build",
        "loop_cap": 3,
        "filename_slot": "verdict-security-r<N>.md",
    },
    ("design", "security-auditor"): {
        "respawn_target": "architect",
        "loop_cap": 3,
        "filename_slot": "verdict-security-r<N>.md",
    },
    ("test-audit", "tester"): {
        "respawn_target": "tester",
        "loop_cap": 3,
        "filename_slot": "verdict-test-r<N>.md",
    },
}

_VALID_VERDICTS: frozenset[str] = frozenset({"Approved", "Conditional", "Blocked"})


def _die(msg: str) -> None:
    print(f"revision-route: {msg}", file=sys.stderr)
    sys.exit(2)


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Extract scalar key:value pairs from YAML frontmatter block."""
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        _die("no YAML frontmatter found (expected --- ... --- block)")
    block = m.group(1)
    result: dict[str, str] = {}
    for line in block.splitlines():
        kv = re.match(r"^(\w[\w-]*)\s*:\s*(.+)$", line.strip())
        if kv:
            result[kv.group(1)] = kv.group(2).strip()
    return result


def _default_orch_path() -> Path:
    # C5: parents[2] — script at .claude/skills/revision-route/revision-route.py
    # parents[0] = .claude/skills/revision-route/
    # parents[1] = .claude/skills/
    # parents[2] = .claude/
    return Path(__file__).resolve().parents[2] / "agents" / "orchestrator.md"


def _assert_table_sync(orch_path: Path) -> None:
    """Drift guard (C3/C5): compare ROUTING_TABLE against orchestrator.md table."""
    if not orch_path.exists():
        print(
            f"revision-route: orchestrator.md not found at {orch_path}",
            file=sys.stderr,
        )
        sys.exit(2)
    text = orch_path.read_text(encoding="utf-8")
    expected = {
        (v["filename_slot"], v["respawn_target"])
        for v in ROUTING_TABLE.values()
    }
    parsed = set(
        re.findall(
            r"\|\s*(verdict-[a-z-]+-r<N>\.md)\s*[^|]*\|\s*([a-z-]+)",
            text,
        )
    )
    if not parsed.issuperset(expected):
        missing = expected - parsed
        print(
            f"revision-route: orchestrator.md Revision Loop table drift; "
            f"missing rows: {missing}",
            file=sys.stderr,
        )
        sys.exit(2)


def _route(fm: dict[str, str]) -> dict:
    review_type = fm.get("review_type", "")
    role = fm.get("role", "")
    verdict = fm.get("verdict", "")
    revision_str = fm.get("revision", "r1")
    loops_str = fm.get("loops", "1")

    if verdict not in _VALID_VERDICTS:
        _die(
            f"verdict value {verdict!r} not in "
            f"{{{', '.join(sorted(_VALID_VERDICTS))}}}"
        )

    key = (review_type, role)
    if key not in ROUTING_TABLE:
        _die(f"(review_type={review_type!r}, role={role!r}) not in ROUTING_TABLE")

    meta = ROUTING_TABLE[key]
    loop_cap: int = meta["loop_cap"]
    respawn_target: str = meta["respawn_target"]

    revision_n_match = re.search(r"\d+", revision_str)
    revision_n = int(revision_n_match.group()) if revision_n_match else 1

    try:
        current_loops = int(loops_str)
    except ValueError:
        current_loops = 1

    # Loop cap applies only to Blocked verdicts (re-spawn count).
    loop_cap_hit = verdict == "Blocked" and current_loops >= loop_cap

    if loop_cap_hit:
        action = "halt"
        target_role = None
        reason = (
            f"loop cap {loop_cap} reached for ({review_type}, {role})"
        )
    elif verdict == "Blocked":
        action = "respawn"
        target_role = respawn_target
        reason = (
            f"verdict=Blocked, ({review_type}, {role}) → respawn {respawn_target} r{revision_n + 1}"
        )
    else:
        # Approved or Conditional → approved (orchestrator verifies Conditions)
        action = "approved"
        target_role = None
        reason = f"verdict={verdict}, ({review_type}, {role}) → approved"

    return {
        "action": action,
        "target_role": target_role,
        "revision_n": revision_n + 1 if action == "respawn" else revision_n,
        "reason": reason,
        "loop_cap_hit": loop_cap_hit,
        "verdict_summary": {
            "review_type": review_type,
            "role": role,
            "verdict": verdict,
            "current_loops": current_loops,
            "loop_cap": loop_cap,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="revision-route",
        description="Map a verdict file to its next-action instruction.",
    )
    parser.add_argument(
        "--verdict-path",
        required=True,
        metavar="PATH",
        type=Path,
        help="Absolute path to verdict markdown file",
    )
    parser.add_argument(
        "--orch-path",
        metavar="PATH",
        type=Path,
        default=None,
        help="Override orchestrator.md path (for testing)",
    )
    args = parser.parse_args()

    verdict_path: Path = args.verdict_path.expanduser().resolve()
    if not verdict_path.exists():
        print(
            f"revision-route: verdict file not found: {verdict_path}",
            file=sys.stderr,
        )
        return 2

    orch_path: Path = (
        args.orch_path.expanduser().resolve()
        if args.orch_path
        else _default_orch_path()
    )
    _assert_table_sync(orch_path)

    try:
        text = verdict_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"revision-route: cannot read verdict file: {exc}", file=sys.stderr)
        return 2

    fm = _parse_frontmatter(text)
    result = _route(fm)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
