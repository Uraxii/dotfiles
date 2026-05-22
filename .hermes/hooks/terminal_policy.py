#!/usr/bin/env python3
"""terminal_policy — Hermes pre_tool_call shell hook enforcing allow/deny lists.

Replaces Claude Code's `settings.json.permissions.{allow,deny}` mechanism
which has no direct Hermes equivalent (Doctrine delta #7 / decision 9).

Wired in ~/.hermes/config.yaml under hooks.pre_tool_call w/ matcher "terminal".

Reads ~/.hermes/policy.json (TOML-like JSON):

    {
      "allow": ["regex pattern", ...],
      "deny": ["regex pattern", ...]
    }

Rules:
- deny patterns ALWAYS win (checked first).
- If `allow` is present and non-empty, command MUST match at least one
  allow pattern, else block w/ "not in allowlist".
- If `allow` is absent or empty, anything not denied is allowed.

Stdlib only.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

POLICY_PATH = Path.home() / ".hermes" / "policy.json"


def emit_block(reason: str) -> None:
    sys.stdout.write(json.dumps({"action": "block", "message": reason}))
    sys.stdout.write("\n")
    sys.exit(0)


def load_policy() -> dict[str, list[re.Pattern[str]]]:
    if not POLICY_PATH.is_file():
        return {"allow": [], "deny": []}
    try:
        raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"allow": [], "deny": []}

    return {
        "allow": [re.compile(p) for p in (raw.get("allow") or [])],
        "deny": [re.compile(p) for p in (raw.get("deny") or [])],
    }


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        return 0
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return 0

    if payload.get("tool_name") != "terminal":
        return 0

    command = (payload.get("tool_input") or {}).get("command", "")
    if not isinstance(command, str) or not command:
        return 0

    policy = load_policy()

    for pattern in policy["deny"]:
        if pattern.search(command):
            emit_block(
                f"command matches deny pattern {pattern.pattern!r} "
                f"(terminal_policy)."
            )

    if policy["allow"]:
        matched = any(p.search(command) for p in policy["allow"])
        if not matched:
            emit_block(
                "command not in terminal_policy allowlist. "
                "Add a regex pattern to ~/.hermes/policy.json.allow to permit."
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
