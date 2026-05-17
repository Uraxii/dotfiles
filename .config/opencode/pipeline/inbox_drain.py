#!/usr/bin/env python3
"""inbox_drain — read / consume inbox files for a session.

Usage:
    inbox_drain.py [--sid <sid>] [--consume] [--json]

Default --sid = env CLAUDE_CODE_SESSION_ID.

Lists files under ~/.config/opencode/sessions/<sid>/inbox/*.json, prints contents.
--consume: moves consumed files to inbox/.consumed/ after reading.
--json: structured output (default: human-friendly).

Stdlib-only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

_PIPELINE_DIR = Path(__file__).parent
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

from comms.env import validate_sid  # noqa: E402

SESSIONS_ROOT = Path("~/.config/opencode/sessions").expanduser()


def _get_sid(sid: str | None) -> str:
    resolved = sid or os.environ.get("CLAUDE_CODE_SESSION_ID", "")
    if not resolved:
        sys.stderr.write(
            "No session id: provide --sid or set CLAUDE_CODE_SESSION_ID.\n"
        )
        sys.exit(1)
    try:
        return validate_sid(resolved)
    except ValueError as exc:
        sys.stderr.write(f"Invalid session id: {exc}\n")
        sys.exit(1)


def _inbox_dir(sid: str) -> Path:
    return SESSIONS_ROOT / sid / "inbox"


def _read_json_file(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        return data
    except (json.JSONDecodeError, OSError):
        return None


def drain(sid: str, consume: bool, as_json: bool) -> int:
    inbox = _inbox_dir(sid)
    if not inbox.is_dir():
        if as_json:
            sys.stdout.write(json.dumps({"sid": sid, "messages": []}) + "\n")
        else:
            sys.stdout.write(f"Inbox empty or not found for session {sid[:8]}...\n")
        return 0

    files = sorted(inbox.glob("*.json"))
    if not files:
        if as_json:
            sys.stdout.write(json.dumps({"sid": sid, "messages": []}) + "\n")
        else:
            sys.stdout.write("No messages.\n")
        return 0

    consumed_dir = inbox / ".consumed"
    if consume:
        consumed_dir.mkdir(parents=True, exist_ok=True)

    messages: list[dict[str, Any]] = []
    errors: list[str] = []

    for f in files:
        data = _read_json_file(f)
        if data is None:
            errors.append(f.name)
            # Malformed files: report but do not consume (do not lose evidence).
            continue
        messages.append({"file": f.name, "content": data})
        if consume:
            dest = consumed_dir / f.name
            try:
                f.rename(dest)
            except OSError as exc:
                sys.stderr.write(f"Failed to consume {f.name}: {exc}\n")

    if as_json:
        # M2: mark all messages as untrusted-slack-user-content.
        for m in messages:
            m["content"]["_provenance"] = "untrusted-slack-user-content"
        out: dict[str, Any] = {"sid": sid, "messages": messages}
        if errors:
            out["errors"] = errors
        sys.stdout.write(json.dumps(out, indent=2) + "\n")
    else:
        for m in messages:
            c = m["content"]
            ts = c.get("message_ts", "?")
            user = c.get("user_id", "?")
            text = c.get("text", "")
            # M2: wrap each message in provenance markers so downstream AI
            # consumers can identify the boundary of untrusted content.
            sys.stdout.write(
                f"<<<UNTRUSTED-SLACK-MESSAGE id={ts} user={user}>>>\n"
                f"{text}\n"
                "<<<END-UNTRUSTED-SLACK-MESSAGE>>>\n"
            )
        if errors:
            sys.stderr.write(f"Malformed files (skipped): {', '.join(errors)}\n")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="inbox_drain.py",
        description="List / consume session inbox files.",
    )
    parser.add_argument(
        "--sid",
        default=None,
        help="Session id (default: env CLAUDE_CODE_SESSION_ID)",
    )
    parser.add_argument(
        "--consume",
        action="store_true",
        default=False,
        help="Move consumed files to inbox/.consumed/ after reading",
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        default=False,
        help="Structured JSON output",
    )
    return parser


def main() -> None:
    # L1: restrict all file creation to owner-only.
    os.umask(0o077)
    parser = build_parser()
    args = parser.parse_args()
    sid = _get_sid(args.sid)
    sys.exit(drain(sid, args.consume, args.as_json))


if __name__ == "__main__":
    main()
