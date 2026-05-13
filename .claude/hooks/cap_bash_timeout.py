#!/usr/bin/env python3
"""cap_bash_timeout — PreToolUse hook gating long Bash timeouts.

Wired in settings.json under `hooks.PreToolUse` w/ matcher "Bash".

Reads tool input JSON from stdin. Denies the call when `tool_input.timeout`
exceeds the default 10-minute cap (600000 ms) and the command does NOT match
the long-timeout allowlist. Allows everything else.

Rationale: `BASH_MAX_TIMEOUT_MS` raises the session ceiling so that hour-/day-
long blocking calls are possible (e.g. `pipeline_ask.py`). Without this hook,
the agent could request 24h on any command including hung loops. This hook
enforces "only allowlisted commands may exceed the default cap."

Hook protocol (Claude Code):
- stdin: JSON envelope w/ tool_name, tool_input, etc.
- stdout: optional JSON `{"decision":"block","reason":"..."}` to deny;
          empty stdout + exit 0 = allow.
- exit code: 0 = success (allow OR rendered block decision); nonzero = hook
  error (ignored by harness, falls back to allow). We always exit 0.

Stdlib only.
"""

from __future__ import annotations

import json
import re
import sys

# Default Bash ceiling before BASH_MAX_TIMEOUT_MS override.
DEFAULT_CAP_MS = 600_000

# Commands permitted to request timeouts beyond DEFAULT_CAP_MS. Match against
# the literal command string. Extend list as needed; regex tested w/ re.search
# so substring presence is sufficient.
LONG_TIMEOUT_ALLOWLIST = [
    re.compile(r"pipeline_ask\.py"),
    # Add future long-blocking tools here. Keep list tight.
]


def emit_block(reason: str) -> None:
    """Print block decision and exit cleanly."""
    sys.stdout.write(json.dumps({"decision": "block", "reason": reason}))
    sys.stdout.write("\n")
    sys.exit(0)


def main() -> int:
    raw = sys.stdin.read()
    if not raw.strip():
        # No payload; nothing to evaluate.
        return 0
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        # Malformed payload — fail open (allow), harness will surface elsewhere.
        return 0

    if payload.get("tool_name") != "Bash":
        return 0

    tool_input = payload.get("tool_input") or {}
    timeout = tool_input.get("timeout")
    command = tool_input.get("command", "")

    if not isinstance(timeout, (int, float)):
        # No timeout specified → harness default applies; nothing to gate.
        return 0
    if timeout <= DEFAULT_CAP_MS:
        # Within standard cap; permitted unconditionally.
        return 0

    for pattern in LONG_TIMEOUT_ALLOWLIST:
        if pattern.search(command):
            return 0

    emit_block(
        f"timeout {int(timeout)}ms exceeds {DEFAULT_CAP_MS}ms default cap; "
        f"command not in long-timeout allowlist. "
        f"Allowlisted patterns: {[p.pattern for p in LONG_TIMEOUT_ALLOWLIST]}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
