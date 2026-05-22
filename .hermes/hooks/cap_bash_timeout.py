#!/usr/bin/env python3
"""cap_bash_timeout — Hermes pre_tool_call shell hook gating long terminal timeouts.

Wired in ~/.hermes/config.yaml under `hooks.pre_tool_call` w/ matcher "terminal".

Reads tool input JSON from stdin. Denies the call when `tool_input.timeout`
exceeds the default 10-minute cap (600 s) and the command does NOT match the
long-timeout allowlist. Allows everything else.

Hermes shell hook wire protocol:
- stdin: JSON envelope w/ hook_event_name, tool_name, tool_input, session_id, cwd
- stdout: optional JSON `{"action":"block","message":"..."}` to deny;
          empty stdout + exit 0 = allow.
- exit code: 0 = success; nonzero = hook error (logged, falls back to allow).

Ported from .claude/hooks/cap_bash_timeout.py. Differences vs Claude Code:
- tool_name match: "terminal" (was "Bash").
- timeout field semantics: Hermes terminal tool reports `timeout` in seconds
  (was milliseconds in Claude Code). Cap in seconds.
- block decision shape: `{"action":"block","message":"..."}` (was
  `{"decision":"block","reason":"..."}`).

Stdlib only.
"""

from __future__ import annotations

import json
import re
import sys

# Default terminal-tool ceiling before allowlist override. Seconds.
DEFAULT_CAP_SEC = 600

# Commands permitted to request timeouts beyond DEFAULT_CAP_SEC. Match against
# the literal command string. Substring presence sufficient.
LONG_TIMEOUT_ALLOWLIST: list[re.Pattern[str]] = [
    # Extend list as long-blocking pipeline tools land. Keep tight.
]


def emit_block(reason: str) -> None:
    """Print block decision and exit cleanly."""
    sys.stdout.write(json.dumps({"action": "block", "message": reason}))
    sys.stdout.write("\n")
    sys.exit(0)


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        return 0
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        # Fail open on malformed input.
        return 0

    if payload.get("tool_name") != "terminal":
        return 0

    tool_input = payload.get("tool_input") or {}
    timeout = tool_input.get("timeout")
    command = tool_input.get("command", "")

    if not isinstance(timeout, (int, float)):
        return 0
    if timeout <= DEFAULT_CAP_SEC:
        return 0

    for pattern in LONG_TIMEOUT_ALLOWLIST:
        if pattern.search(command):
            return 0

    emit_block(
        f"timeout {int(timeout)}s exceeds {DEFAULT_CAP_SEC}s default cap; "
        f"command not in long-timeout allowlist. "
        f"Allowlisted patterns: {[p.pattern for p in LONG_TIMEOUT_ALLOWLIST]}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
