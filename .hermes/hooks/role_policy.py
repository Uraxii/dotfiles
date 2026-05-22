#!/usr/bin/env python3
"""role_policy — Hermes pre_tool_call shell hook for per-role path sandboxing.

Doctrine delta #2 (decision 6): Hermes delegate_task accepts only coarse
toolset buckets. Fine-grain per-role restrictions (e.g. "tester may not
write to non-test paths") enforced here.

Mechanism:
- Orchestrator writes a per-spawn sidecar `<run-dir>/.role-active-<frag>.json`
  before each delegate_task call, recording the role-id + session_id_fragment.
- This hook reads payload.session_id, locates matching sidecar via fragment,
  loads role denylist from ~/.hermes/role-policy.json, blocks if tool target
  path matches denylist.

Best-effort: if sidecar missing, hook fails open (allow).

Sidecar shape:
    {
      "role": "tester",
      "session_fragment": "a1b2c3",
      "run_dir": "/path/to/run-dir",
      "shard_id": "s1"
    }

Role-policy shape (~/.hermes/role-policy.json):
    {
      "tester": {
        "write_deny": ["^(?!.*tests?/)", "^src/.*(?<!_test)\\.py$"],
        "write_allow_prefix": ["tests/", "test/"]
      },
      ...
    }

Hermes shell hook wire protocol:
- stdin: JSON envelope (hook_event_name, tool_name, tool_input, session_id, cwd)
- stdout: optional JSON `{"action":"block","message":"..."}`
- exit 0

Stdlib only.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROLE_POLICY_PATH = Path.home() / ".hermes" / "role-policy.json"

# Sidecar discovery roots. Orchestrator writes under run_dir (project repo).
# Hook does NOT know run_dir without sidecar — fall back to scanning likely
# parents from cwd.
SIDECAR_GLOB = ".pipeline/runs/*/.role-active-*.json"


def emit_block(reason: str) -> None:
    sys.stdout.write(json.dumps({"action": "block", "message": reason}))
    sys.stdout.write("\n")
    sys.exit(0)


def find_sidecar(session_id: str, cwd: str) -> dict | None:
    """Find role sidecar matching session_id's last 6 chars (fragment)."""
    if not session_id:
        return None
    fragment = session_id[-6:]
    start = Path(cwd or ".").resolve()
    # Walk up to repo root looking for .pipeline/runs.
    for parent in [start, *start.parents]:
        runs = parent / ".pipeline" / "runs"
        if not runs.is_dir():
            continue
        for sidecar in runs.glob(f"*/.role-active-{fragment}.json"):
            try:
                return json.loads(sidecar.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
    return None


def load_role_policy(role: str) -> dict:
    if not ROLE_POLICY_PATH.is_file():
        return {}
    try:
        raw = json.loads(ROLE_POLICY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw.get(role) or {}


def extract_write_target(tool_name: str, tool_input: dict) -> str | None:
    """Best-effort: pull the target path from a write-like tool call."""
    if tool_name == "patch":
        return tool_input.get("path") or tool_input.get("file_path")
    if tool_name == "write_file":
        return tool_input.get("path") or tool_input.get("file_path")
    if tool_name == "terminal":
        # Terminal can shell-write; we don't parse free-form commands.
        return None
    return None


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        return 0
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return 0

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    session_id = payload.get("session_id", "")
    cwd = payload.get("cwd", "")

    sidecar = find_sidecar(session_id, cwd)
    if sidecar is None:
        # No role context — root orchestrator session or unrelated call.
        return 0

    role = sidecar.get("role", "")
    policy = load_role_policy(role)
    if not policy:
        return 0

    target = extract_write_target(tool_name, tool_input)
    if target is None:
        return 0

    # Check allow prefixes first.
    allow_prefixes = policy.get("write_allow_prefix") or []
    if allow_prefixes:
        if not any(target.startswith(p) for p in allow_prefixes):
            emit_block(
                f"role={role} attempted write to {target!r}; not in "
                f"write_allow_prefix list {allow_prefixes}."
            )

    # Check deny patterns.
    deny_patterns = policy.get("write_deny") or []
    for pat in deny_patterns:
        try:
            if re.search(pat, target):
                emit_block(
                    f"role={role} write to {target!r} matches deny pattern "
                    f"{pat!r}."
                )
        except re.error:
            continue

    return 0


if __name__ == "__main__":
    sys.exit(main())
