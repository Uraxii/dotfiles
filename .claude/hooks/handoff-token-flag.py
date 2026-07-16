#!/usr/bin/env python3
"""handoff-token-flag — UserPromptSubmit hook flagging context past 200k.

Wired in settings.json under `hooks.UserPromptSubmit`.

Reads the session transcript path from stdin JSON, sums the last recorded
`message.usage` input/cache token counts as a proxy for current context
size, and injects an instruction into the agent's context the first time
that size crosses the 200k soft limit (and again every +50k band after,
so the nag does not repeat every turn within the same band).

Rationale: the agent cannot self-measure its own context size. This hook
measures it externally from the transcript and injects a instruction to
offer a handoff at the next natural stopping point.

Hook protocol (Claude Code):
- stdin: JSON envelope w/ transcript_path, session_id, hook_event_name.
- stdout: printed text (if any) is injected into agent context this turn;
          print nothing to inject nothing.
- exit code: always 0. Any error/missing data -> exit 0, print nothing.
  Never crash the session.

Stdlib only.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

THRESHOLD = 200_000
BAND = 50_000


def _last_usage_tokens(transcript_path: Path) -> int | None:
    """Sum input+cache tokens from the last transcript line w/ usage."""
    last_usage: dict[str, int] | None = None
    with transcript_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            usage = obj.get("message", {}).get("usage")
            if usage:
                last_usage = usage

    if last_usage is None:
        return None
    return (
        last_usage.get("input_tokens", 0)
        + last_usage.get("cache_read_input_tokens", 0)
        + last_usage.get("cache_creation_input_tokens", 0)
    )


def _state_file(session_id: str) -> Path:
    """Per-session band tracker in the OS temp dir."""
    # ponytail: minimal sanitize, only used as a filename fragment
    safe_id = "".join(c for c in session_id if c.isalnum() or c in "-_")
    safe_id = safe_id or "unknown"
    return Path(tempfile.gettempdir()) / f"claude-handoff-flag-{safe_id}.txt"


def _read_last_band(state_file: Path) -> int:
    """Last-flagged band, or -1 if no valid state recorded yet."""
    if not state_file.exists():
        return -1
    try:
        return int(state_file.read_text().strip())
    except ValueError:
        return -1


def _build_message(tokens: int) -> str:
    """Injection text for a new band crossing."""
    k = round(tokens / 1000)
    return (
        f"[handoff-token-flag] Main session context ~{k}k tokens, past the "
        "200k soft limit. At the next natural stopping point, ask the user "
        "whether to write a handoff doc (invoke the `handoff` skill) and "
        "close this session; if yes, report the /tmp/handoff-*.md path as "
        "the first line. Do not start major new work. Do not silently rely "
        "on auto-compact."
    )


def main() -> int:
    payload = json.loads(sys.stdin.read())
    transcript_path = Path(payload["transcript_path"])
    session_id = payload.get("session_id") or "unknown"

    tokens = _last_usage_tokens(transcript_path)
    if tokens is None or tokens < THRESHOLD:
        return 0

    band = (tokens - THRESHOLD) // BAND
    state_file = _state_file(session_id)
    if band <= _read_last_band(state_file):
        return 0

    state_file.write_text(str(band))
    print(_build_message(tokens))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # ponytail: fail-safe per hook contract — any error means exit 0,
        # silent. Never crash the session over a token-count nudge.
        sys.exit(0)
