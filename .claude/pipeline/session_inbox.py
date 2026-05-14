#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "slack-bolt>=1.18",
#     "watchdog>=4.0",
# ]
# ///
"""session_inbox — per-session Bolt Socket Mode inbox daemon.

Spawned by session_bind.py activate. Stays alive for the bound session
lifetime. Captures user replies in the bound session thread (and any other
known session threads via cross-listener routing) to inbox files.

Does NOT post decisions/questions, does NOT handle button clicks.
Write-only side: inbox/<msg_ts>.json.

Usage:
    session_inbox.py <CLAUDE_CODE_SESSION_ID>

Environment (auto-loaded from ~/.claude/pipeline/slack.env.local):
    SLACK_BOT_TOKEN
    SLACK_APP_TOKEN
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_PIPELINE_DIR = Path(__file__).parent
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

from _slack_env import (  # noqa: E402
    atomic_write_text,
    default_env_path,
    load_env_file,
    validate_sid,
)
from session_slack import all_active_bindings  # noqa: E402

try:
    from slack_bolt import App
    from slack_bolt.adapter.socket_mode import SocketModeHandler
except ImportError:
    sys.stderr.write(
        "slack_bolt missing. Install: pip install --user slack-bolt watchdog\n"
    )
    sys.exit(2)

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
except ImportError:
    sys.stderr.write(
        "watchdog missing. Install: pip install --user slack-bolt watchdog\n"
    )
    sys.exit(2)

log = logging.getLogger("session_inbox")

SESSIONS_ROOT = Path("~/.claude/sessions").expanduser()
ORPHAN_TMP_MAX_AGE_S = 60
IDLE_TIMEOUT_S = int(os.environ.get("SLACK_LISTENER_IDLE_TIMEOUT", "86400"))


# ---------------------------------------------------------------------------
# Thread-ts → sid routing index
# ---------------------------------------------------------------------------


class RoutingIndex:
    """In-memory map from thread_ts -> sid, rebuilt on watchdog events."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread_to_sid: dict[str, str] = {}
        self._sid_to_inbox: dict[str, Path] = {}

    def rebuild(self) -> None:
        bindings = all_active_bindings()
        new_thread: dict[str, str] = {}
        new_inbox: dict[str, Path] = {}
        for sid, data in bindings.items():
            ts = data.get("thread_ts", "")
            if ts:
                new_thread[ts] = sid
                new_inbox[sid] = SESSIONS_ROOT / sid / "inbox"
        with self._lock:
            self._thread_to_sid = new_thread
            self._sid_to_inbox = new_inbox
        log.debug("routing index rebuilt: %d active sessions", len(new_thread))

    def resolve(self, thread_ts: str) -> Path | None:
        with self._lock:
            sid = self._thread_to_sid.get(thread_ts)
            if sid is None:
                return None
            return self._sid_to_inbox.get(sid)


# ---------------------------------------------------------------------------
# Watchdog: refresh index when slack.json files change
# ---------------------------------------------------------------------------


class SessionsWatcher(FileSystemEventHandler):
    def __init__(self, index: RoutingIndex) -> None:
        self._index = index

    def _maybe_refresh(self, event: Any) -> None:
        path = Path(getattr(event, "src_path", ""))
        if path.name == "slack.json":
            self._index.rebuild()

    def on_created(self, event: Any) -> None:
        self._maybe_refresh(event)

    def on_modified(self, event: Any) -> None:
        self._maybe_refresh(event)

    def on_deleted(self, event: Any) -> None:
        self._maybe_refresh(event)


# ---------------------------------------------------------------------------
# Orphan .tmp cleanup
# ---------------------------------------------------------------------------


def _cleanup_orphan_tmps(inbox: Path) -> None:
    """Remove *.tmp files older than ORPHAN_TMP_MAX_AGE_S seconds."""
    if not inbox.is_dir():
        return
    now = datetime.now(timezone.utc).timestamp()
    for tmp in inbox.glob("*.tmp"):
        try:
            age = now - tmp.stat().st_mtime
            if age > ORPHAN_TMP_MAX_AGE_S:
                tmp.unlink(missing_ok=True)
                log.debug("removed orphan tmp: %s (age=%.0fs)", tmp, age)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Inbox writer
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_inbox_file(
    inbox: Path,
    event: dict[str, Any],
    expected_channel: str = "",
) -> None:
    """Write a single inbox/<message_ts>.json atomically.

    Skips if the target file already exists (exactly-one-writer invariant H3).
    M3/M4: if expected_channel is provided, skips events from other channels.
    """
    # M3/M4: channel verification.
    if expected_channel:
        event_channel = event.get("channel", "")
        if event_channel and event_channel != expected_channel:
            log.debug(
                "inbox drop: event channel %s != expected %s",
                event_channel, expected_channel,
            )
            return

    inbox.mkdir(parents=True, exist_ok=True)
    message_ts: str = event.get("ts", "")
    if not message_ts:
        log.warning("event missing ts; skipping inbox write: %s", event)
        return

    target = inbox / f"{message_ts}.json"
    if target.exists():
        log.debug("inbox file already exists; skipping (H3): %s", target)
        return

    thread_ts: str = event.get("thread_ts", "")
    sid = inbox.parent.name
    payload = {
        "session_id": sid,
        "thread_ts": thread_ts,
        "message_ts": message_ts,
        "user_id": event.get("user", ""),
        "text": event.get("text", ""),
        "received_at": _now_iso(),
    }
    try:
        atomic_write_text(target, json.dumps(payload, indent=2), mode=0o600)
        log.info("inbox: wrote %s", target)
    except OSError as exc:
        # L4: surface ENOSPC explicitly.
        if exc.errno == 28:  # ENOSPC
            log.error(
                "dropped inbox write: ENOSPC target=%s sid=%s",
                target, sid,
                extra={"event": "inbox_drop_enospc", "target": str(target), "sid": sid},
            )
        else:
            log.error("inbox write failed for %s: %s", target, exc)


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="session_inbox.py",
        description="Per-session Slack inbox daemon. Spawned by session_bind.py activate.",
    )
    parser.add_argument("session_id", help="CLAUDE_CODE_SESSION_ID value")
    parser.add_argument("--log-level", default="INFO")
    return parser


def main() -> None:
    # L1: restrict all file creation to owner-only (no world-readable logs).
    os.umask(0o077)

    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # H1: validate session id to prevent path-traversal.
    try:
        sid: str = validate_sid(args.session_id)
    except ValueError as exc:
        sys.stderr.write(f"Invalid session id: {exc}\n")
        sys.exit(1)
    session_dir = SESSIONS_ROOT / sid
    pid_path = session_dir / "inbox-daemon.pid"

    # Write pid file; clean up on exit.
    session_dir.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(f"{os.getpid()}\n", encoding="utf-8")

    import atexit
    atexit.register(lambda: pid_path.unlink(missing_ok=True))

    # C1: Graceful SIGTERM — set an event from the signal handler; a supervisor
    # thread closes the SocketModeHandler so the blocking C-level socket call
    # returns promptly rather than waiting for the next Python bytecode.
    _should_exit = threading.Event()
    _handler_ref: list[Any] = []  # filled after handler is created

    def _on_sigterm(signum: int, frame: Any) -> None:
        log.info("received SIGTERM; setting exit flag")
        _should_exit.set()

    signal.signal(signal.SIGTERM, _on_sigterm)

    def _exit_supervisor() -> None:
        """Wait for exit flag, then disconnect SocketModeHandler."""
        _should_exit.wait()
        h = _handler_ref[0] if _handler_ref else None
        if h is not None:
            try:
                h.close()
            except Exception as exc:
                log.debug("handler close error: %s", exc)
        # Fallback: force exit if close() stalls.
        import time
        time.sleep(2)
        os._exit(0)

    supervisor = threading.Thread(target=_exit_supervisor, daemon=True, name="sigterm-supervisor")
    supervisor.start()

    # Cleanup orphan tmps at boot.
    _cleanup_orphan_tmps(session_dir / "inbox")

    load_env_file(default_env_path())
    bot_token = os.environ.get("SLACK_BOT_TOKEN", "")
    app_token = os.environ.get("SLACK_APP_TOKEN", "")
    if not bot_token or not app_token:
        sys.stderr.write(
            "SLACK_BOT_TOKEN and SLACK_APP_TOKEN required. "
            f"Set in {default_env_path()}\n"
        )
        sys.exit(1)

    # Build routing index.
    index = RoutingIndex()
    index.rebuild()

    # M3/M4: load the bound channel_id for this session so on_thread_message
    # can reject events from other channels.
    from session_slack import resolve_session_binding as _resolve  # noqa: E402
    _binding = _resolve(sid)
    _bound_channel_id: str = _binding[0] if _binding is not None else ""

    app = App(token=bot_token)

    @app.event("message")
    def on_thread_message(event: dict[str, Any], body: dict[str, Any]) -> None:  # noqa: ARG001
        """Capture thread replies to known session threads.

        M3/M4: verify event channel matches binding channel_id before writing inbox.
        """
        if event.get("subtype") is not None:
            return  # skip edits, joins, thread_broadcast, etc.
        thread_ts = event.get("thread_ts")
        if not thread_ts:
            return  # top-level channel message, not a reply
        inbox = index.resolve(thread_ts)
        if inbox is None:
            return  # not a known session thread
        write_inbox_file(inbox, event, expected_channel=_bound_channel_id)

    # Watchdog on ~/.claude/sessions/ to refresh routing index on slack.json changes.
    observer: Observer | None = None
    if SESSIONS_ROOT.is_dir():
        watcher = SessionsWatcher(index)
        observer = Observer()
        observer.schedule(watcher, str(SESSIONS_ROOT), recursive=True)
        observer.start()
        log.info("watching %s for session changes", SESSIONS_ROOT)

    log.info(
        "session_inbox daemon started: sid=%s pid=%d idle_timeout=%ds",
        sid, os.getpid(), IDLE_TIMEOUT_S,
    )

    try:
        handler = SocketModeHandler(app, app_token)
        _handler_ref.append(handler)  # C1: register for SIGTERM supervisor
        handler.start()
    finally:
        if observer is not None:
            observer.stop()
            observer.join()


if __name__ == "__main__":
    main()
