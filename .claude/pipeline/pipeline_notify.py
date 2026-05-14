#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "slack-bolt>=1.18",
# ]
# ///
"""pipeline_notify — one-shot status/completion/friction-summary notification CLI.

Posts a message to the active session-bound Slack thread (if any).
No-op with a debug trace when no binding is active — never falls back to
per-pipeline thread.

Usage:
    pipeline_notify.py --run <artifact-id> --project <path> \\
        --kind {status|completion|friction-summary} \\
        --message "<one-line>"

Environment (auto-loaded from ~/.claude/pipeline/slack.env.local):
    SLACK_BOT_TOKEN
    CLAUDE_CODE_SESSION_ID   (inherited from Claude Code process)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Literal

_PIPELINE_DIR = Path(__file__).parent
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

from _slack_env import default_env_path, load_env_file, validate_sid  # noqa: E402
from session_slack import resolve_session_binding  # noqa: E402

try:
    from slack_bolt import App
except ImportError:
    sys.stderr.write(
        "slack_bolt missing. Install: pip install --user slack-bolt\n"
    )
    sys.exit(2)

log = logging.getLogger("pipeline_notify")

Kind = Literal["status", "completion", "friction-summary"]

KIND_EMOJI: dict[str, str] = {
    "status": ":information_source:",
    "completion": ":white_check_mark:",
    "friction-summary": ":mag:",
}


def _build_text(run_id: str, kind: str, message: str) -> str:
    emoji = KIND_EMOJI.get(kind, ":speech_balloon:")
    return f"[{run_id}] {emoji} *{kind}:* {message}"


def notify(run_id: str, kind: str, message: str) -> int:
    """Post notification. Returns 0 on success or silent no-op."""
    # B7: load env file FIRST so CLAUDE_CODE_SESSION_ID set there is visible
    # to resolve_session_binding() when not already in os.environ.
    load_env_file(default_env_path())

    # H1: validate session id before using it in path construction.
    raw_sid = os.environ.get("CLAUDE_CODE_SESSION_ID", "").strip()
    if raw_sid:
        try:
            validate_sid(raw_sid)
        except ValueError as exc:
            sys.stderr.write(f"[pipeline_notify] invalid session id: {exc}\n")
            return 1

    binding = resolve_session_binding()
    if binding is None:
        log.debug("no active session binding; notification not posted (kind=%s run=%s)", kind, run_id)
        sys.stderr.write(
            f"[pipeline_notify] no binding; status not posted (run={run_id} kind={kind})\n"
        )
        return 0

    channel, thread_ts = binding
    bot_token = os.environ.get("SLACK_BOT_TOKEN", "")
    if not bot_token:
        sys.stderr.write(
            f"SLACK_BOT_TOKEN required. Set in {default_env_path()}\n"
        )
        return 1

    app = App(token=bot_token)
    text = _build_text(run_id, kind, message)
    try:
        app.client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=text,
            unfurl_links=False,
            unfurl_media=False,
        )
        log.info("posted %s notification for run=%s", kind, run_id)
    except Exception as exc:
        sys.stderr.write(f"Slack post failed: {exc}\n")
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pipeline_notify.py",
        description=(
            "Post a one-shot status/completion/friction-summary message to "
            "the active session-bound Slack thread. No-op when no binding active."
        ),
    )
    parser.add_argument("--run", required=True, help="Pipeline run artifact-id")
    parser.add_argument(
        "--project",
        default=str(Path.cwd()),
        help="Project root (default: cwd; currently unused in routing)",
    )
    parser.add_argument(
        "--kind",
        required=True,
        choices=["status", "completion", "friction-summary"],
        help="Notification kind",
    )
    parser.add_argument("--message", required=True, help="One-line notification body")
    parser.add_argument("--log-level", default="WARNING")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    sys.exit(notify(args.run, args.kind, args.message))


if __name__ == "__main__":
    main()
