#!/usr/bin/env python3
"""dep-graph-compose — compose ordered role execution graph for a pipeline run.

Reads a JSON payload describing the pipeline context (roles, K, scopes).
Emits an ordered role graph as JSON to stdout.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Required top-level keys in input payload.
_REQUIRED_KEYS: frozenset[str] = frozenset({
    "brief_path",
    "roles_declared",
    "roles_skipped",
    "decision_points",
    "design_handoff",
    "ui_scope",
    "ops_scope",
    "code_change",
    "K",
})

# Per-role metadata: depends_on (roles), loop_cap, revision_loop_kind,
# spawn_when, persistent, verdict_file_glob.
_ROLE_META: dict[str, dict[str, Any]] = {
    "researcher": {
        "depends_on_roles": [],
        "loop_cap": 1,
        "revision_loop_kind": "none",
        "spawn_when": "phase-2-step-1",
        "persistent": False,
        "verdict_file_glob": None,
    },
    "plan": {
        "depends_on_roles": [],
        "loop_cap": 1,
        "revision_loop_kind": "none",
        "spawn_when": "phase-2-step-1",
        "persistent": False,
        "verdict_file_glob": None,
    },
    "architect": {
        "depends_on_roles": ["plan"],
        "loop_cap": 3,
        "revision_loop_kind": "design",
        "spawn_when": "phase-2-step-1",
        "persistent": True,
        "verdict_file_glob": "verdict-design-r*.md",
    },
    "ui-ux-designer": {
        "depends_on_roles": ["architect"],
        "loop_cap": 3,
        "revision_loop_kind": "design",
        "spawn_when": "phase-2-step-1",
        "persistent": True,
        "verdict_file_glob": None,
    },
    "skeptic-design": {
        "depends_on_roles": ["architect"],
        "loop_cap": 3,
        "revision_loop_kind": "design",
        "spawn_when": "phase-2-step-2",
        "persistent": True,
        "verdict_file_glob": "verdict-design-r*.md",
    },
    "build": {
        "depends_on_roles": ["skeptic-design"],
        "loop_cap": 3,
        "revision_loop_kind": "code",
        "spawn_when": "phase-2-step-3",
        "persistent": True,
        "verdict_file_glob": None,
    },
    "skeptic-code": {
        "depends_on_roles": ["build"],
        "loop_cap": 3,
        "revision_loop_kind": "code",
        "spawn_when": "phase-2-step-4",
        "persistent": True,
        "verdict_file_glob": "verdict-code-r*.md",
    },
    "skeptic-ops": {
        "depends_on_roles": ["build"],
        "loop_cap": 1,
        "revision_loop_kind": "ops",
        "spawn_when": "phase-2-step-4",
        "persistent": True,
        "verdict_file_glob": "verdict-ops-r*.md",
    },
    "reviewer": {
        "depends_on_roles": ["build"],
        "loop_cap": 3,
        "revision_loop_kind": "review",
        "spawn_when": "phase-2-step-4",
        "persistent": True,
        "verdict_file_glob": "verdict-review-r*.md",
    },
    "security-auditor": {
        "depends_on_roles": ["build"],
        "loop_cap": 3,
        "revision_loop_kind": "code",
        "spawn_when": "phase-2-step-4",
        "persistent": True,
        "verdict_file_glob": "verdict-security-r*.md",
    },
    "tester": {
        "depends_on_roles": ["skeptic-code", "reviewer", "security-auditor"],
        "loop_cap": 3,
        "revision_loop_kind": "test-audit",
        "spawn_when": "phase-2-step-4",
        "persistent": True,
        "verdict_file_glob": "verdict-test-r*.md",
    },
}


def _die(msg: str) -> None:
    print(f"dep-graph-compose: {msg}", file=sys.stderr)
    sys.exit(2)


def _parse_payload(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        _die(f"payload JSON parse error: {exc}")
    if not isinstance(data, dict):
        _die("payload must be a JSON object")
    missing = _REQUIRED_KEYS - data.keys()
    if missing:
        _die(f"missing required keys: {', '.join(sorted(missing))}")
    k = data["K"]
    if not isinstance(k, int) or k < 1:
        _die(f"K must be a positive integer, got: {k!r}")
    return data


def _topo_sort(declared: list[str]) -> list[str]:
    """Kahn's algorithm over declared roles using _ROLE_META deps."""
    declared_set = set(declared)
    in_degree: dict[str, int] = {r: 0 for r in declared}
    adj: dict[str, list[str]] = {r: [] for r in declared}

    for role in declared:
        meta = _ROLE_META.get(role, {})
        for dep in meta.get("depends_on_roles", []):
            if dep in declared_set:
                adj[dep].append(role)
                in_degree[role] += 1

    queue = sorted(r for r, d in in_degree.items() if d == 0)
    order: list[str] = []
    while queue:
        node = queue.pop(0)
        order.append(node)
        for neighbor in adj.get(node, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
                queue.sort()

    return order


def _build_output(payload: dict[str, Any]) -> dict[str, Any]:
    declared: list[str] = payload["roles_declared"]
    k: int = payload["K"]

    order = _topo_sort(declared)

    ordered_roles = []
    for role in order:
        meta = _ROLE_META.get(role, {})
        ordered_roles.append({
            "role": role,
            "depends_on_roles": [
                d for d in meta.get("depends_on_roles", [])
                if d in set(declared)
            ],
            "loop_cap": meta.get("loop_cap", 1),
            "revision_loop_kind": meta.get("revision_loop_kind", "none"),
            "spawn_when": meta.get("spawn_when", "phase-2-step-1"),
            "persistent": meta.get("persistent", False),
            "verdict_file_glob": meta.get("verdict_file_glob", None),
        })

    decision_inject_points = []
    for d_id, d_cfg in payload.get("decision_points", {}).items():
        decision_inject_points.append({
            "after_role": d_cfg.get("after", ""),
            "decision_id": d_id,
            "delivery": d_cfg.get("delivery", "sync"),
        })

    warnings: list[str] = []
    unlisted = [r for r in declared if r not in _ROLE_META]
    if unlisted:
        warnings.append(f"roles not in meta table (treated as leaf): {unlisted}")

    return {
        "ordered_roles": ordered_roles,
        "decision_inject_points": decision_inject_points,
        "K": k,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="dep-graph-compose",
        description="Compose ordered role execution graph for a pipeline run.",
    )
    parser.add_argument(
        "--payload",
        metavar="JSON",
        help="JSON payload string (pipeline context)",
    )
    parser.add_argument(
        "--payload-file",
        metavar="PATH",
        type=Path,
        help="Path to JSON payload file (escape hatch for long payloads)",
    )
    args = parser.parse_args()

    if args.payload_file is not None:
        try:
            raw = args.payload_file.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"dep-graph-compose: cannot read payload file: {exc}", file=sys.stderr)
            return 2
    elif args.payload is not None:
        raw = args.payload
    else:
        parser.print_help(sys.stderr)
        return 2

    payload = _parse_payload(raw)
    output = _build_output(payload)
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
