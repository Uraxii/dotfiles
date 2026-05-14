#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "slack-bolt>=1.18",
# ]
# ///
"""session_bind — activate / deactivate / status CLI for session-bound Slack threading.

Usage:
    session_bind.py activate    # bind current session to a Slack thread
    session_bind.py deactivate  # unbind and post closing message
    session_bind.py status      # print JSON state or "unbound"

Reads CLAUDE_CODE_SESSION_ID from env. Exits non-zero with a clear stderr
message if the var is unset (caller is not inside a Claude Code process).

Environment (auto-loaded from ~/.claude/pipeline/slack.env.local):
    SLACK_BOT_TOKEN     xoxb-...
    SLACK_APP_TOKEN     xapp-...
    SLACK_CHANNEL       fallback channel ID when pipeline.toml absent
    CLAUDE_CODE_SESSION_ID   harness-owned session UUID (inherited)

Per-project channel override: <cwd>/.pipeline/pipeline.toml [slack].channel
"""

from __future__ import annotations

import argparse
import fcntl
import json
import logging
import os
import signal
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# --- stdlib shim for _slack_env ------------------------------------------------
# session_bind.py may be run directly from ~/.claude/pipeline/; add that dir
# to the import path so _slack_env can be imported as a relative sibling.
_PIPELINE_DIR = Path(__file__).parent
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

from _slack_env import (  # noqa: E402
    atomic_write_text,
    default_env_path,
    load_env_file,
    validate_sid,
)

try:
    from slack_bolt import App
except ImportError:
    sys.stderr.write(
        "slack_bolt missing. Install: pip install --user slack-bolt\n"
    )
    sys.exit(2)

log = logging.getLogger("session_bind")

SESSIONS_ROOT = Path("~/.claude/sessions").expanduser()
SESSION_INBOX_SCRIPT = _PIPELINE_DIR / "session_inbox.py"
SCHEMA_VERSION = 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sid_short(sid: str) -> str:
    """Display-only 8-char prefix. Not a recovery key."""
    return sid[:8]


def _require_session_id() -> str:
    """Read + validate CLAUDE_CODE_SESSION_ID. Exits 1 on missing or invalid."""
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID", "").strip()
    if not sid:
        sys.stderr.write(
            "CLAUDE_CODE_SESSION_ID is not set.\n"
            "This CLI must be invoked inside an active Claude Code process.\n"
        )
        sys.exit(1)
    try:
        return validate_sid(sid)
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        sys.exit(1)


def _session_dir(sid: str) -> Path:
    return SESSIONS_ROOT / sid


def _lock_path(sid: str) -> Path:
    return _session_dir(sid) / ".lock"


def _state_path(sid: str) -> Path:
    return _session_dir(sid) / "slack.json"


def _inbox_path(sid: str) -> Path:
    return _session_dir(sid) / "inbox"


def _acquire_lock(sid: str) -> "tuple[int, Path]":
    """Open + flock LOCK_EX|LOCK_NB on the session .lock file.

    Returns (fd, path). Caller must close fd to release.
    Exits non-zero with clear message on contention.
    """
    lock_p = _lock_path(sid)
    _session_dir(sid).mkdir(parents=True, exist_ok=True)
    lock_p.touch(mode=0o600, exist_ok=True)
    fd = os.open(str(lock_p), os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        sys.stderr.write(
            "Another activate/deactivate is in progress for this session.\n"
            "Retry in a moment, or run 'session_bind.py status' to confirm state.\n"
        )
        sys.exit(1)
    return fd, lock_p


def _release_lock(fd: int) -> None:
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:
        pass
    try:
        os.close(fd)
    except OSError:
        pass


def _atomic_write_state(sid: str, state: dict[str, Any]) -> None:
    """Write state atomically with fsync; file mode 600 (H3)."""
    path = _state_path(sid)
    atomic_write_text(path, json.dumps(state, indent=2, default=str), mode=0o600)


def _read_state(sid: str) -> dict[str, Any] | None:
    path = _state_path(sid)
    if not path.is_file():
        return None
    try:
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        sys.stderr.write(f"State file corrupt ({exc}); treating as unbound.\n")
        return None
    version = data.get("schema_version", 1)
    if version > SCHEMA_VERSION:
        sys.stderr.write(
            f"Incompatible slack.json schema_version={version} "
            f"(max supported={SCHEMA_VERSION}).\n"
            "Please upgrade pipeline scripts.\n"
        )
        sys.exit(1)
    return data


def _resolve_channel(project_path: Path) -> str | None:
    """Resolve Slack channel: per-project pipeline.toml -> env SLACK_CHANNEL."""
    toml_path = project_path / ".pipeline" / "pipeline.toml"
    if toml_path.is_file():
        try:
            with toml_path.open("rb") as fh:
                cfg = tomllib.load(fh)
            channel = cfg.get("slack", {}).get("channel")
            if channel:
                return str(channel)
        except Exception as exc:
            log.warning("failed to read pipeline.toml: %s", exc)
    return os.environ.get("SLACK_CHANNEL") or None


def _is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, OSError):
        return False


def _spawn_inbox_daemon(sid: str) -> int | None:
    """Spawn session_inbox.py detached. Returns PID or None on failure."""
    if not SESSION_INBOX_SCRIPT.is_file():
        log.warning("session_inbox.py not found at %s; inbox daemon not spawned", SESSION_INBOX_SCRIPT)
        return None
    log_path = _session_dir(sid) / "inbox-daemon.log"
    try:
        log_fh = open(log_path, "a")  # noqa: SIM115
        proc = subprocess.Popen(
            ["uv", "run", "--script", str(SESSION_INBOX_SCRIPT), sid],
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            close_fds=True,
        )
        log.info("spawned inbox daemon pid=%d sid=%s", proc.pid, sid)
        return proc.pid
    except OSError as exc:
        log.warning("inbox daemon spawn failed: %s", exc)
        return None


_INBOX_SCRIPT_NAME = "session_inbox.py"


def _verify_pid_is_inbox_daemon(pid: int, sid: str) -> bool:
    """Best-effort: verify pid belongs to our inbox daemon via /proc/<pid>/cmdline.

    Returns True if it looks like our daemon (or if /proc is unavailable).
    Returns False if cmdline reads but does not contain the expected markers.
    Linux-only; non-Linux systems always return True (safe to SIGTERM).
    """
    cmdline_path = Path(f"/proc/{pid}/cmdline")
    try:
        raw = cmdline_path.read_bytes()
    except FileNotFoundError:
        log.debug("pid=%d already gone (no /proc entry)", pid)
        return False
    except OSError:
        # /proc unavailable (non-Linux) — proceed with SIGTERM.
        return True
    cmdline = raw.replace(b"\x00", b" ").decode("utf-8", errors="replace")
    has_script = _INBOX_SCRIPT_NAME in cmdline
    has_sid = sid in cmdline
    if not has_script or not has_sid:
        log.warning(
            "pid=%d cmdline does not match inbox daemon for sid=%s; "
            "skipping SIGTERM (pid may have been recycled). cmdline=%r",
            pid, sid, cmdline[:200],
        )
        return False
    return True


def _sigterm_daemon(pid: int | None, sid: str = "") -> None:
    """SIGTERM the inbox daemon after verifying pid identity (M1).

    Ignores ESRCH (process already dead).
    sid is used for cmdline verification; pass empty string to skip check.
    """
    if pid is None:
        return
    if sid and not _verify_pid_is_inbox_daemon(pid, sid):
        return
    try:
        os.kill(pid, signal.SIGTERM)
        log.info("sent SIGTERM to inbox daemon pid=%d", pid)
    except ProcessLookupError:
        pass
    except OSError as exc:
        log.warning("SIGTERM to pid=%d failed: %s", pid, exc)


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def cmd_activate(args: argparse.Namespace) -> int:
    """Activate or reactivate session binding."""
    # H3: restrict all new file/dir creation to owner-only.
    os.umask(0o077)
    sid = _require_session_id()
    cwd_full = Path.cwd()
    # H4: strip $HOME prefix from cwd for Slack display.
    cwd_display = str(cwd_full).replace(str(Path.home()), "~", 1)
    project_path = Path(args.project).expanduser().resolve() if args.project else cwd_full

    load_env_file(default_env_path())
    bot_token = os.environ.get("SLACK_BOT_TOKEN", "")
    app_token = os.environ.get("SLACK_APP_TOKEN", "")
    if not bot_token or not app_token:
        sys.stderr.write(
            "SLACK_BOT_TOKEN and SLACK_APP_TOKEN required.\n"
            f"Set them in {default_env_path()}\n"
        )
        return 1

    channel = _resolve_channel(project_path)
    if not channel:
        sys.stderr.write(
            "No Slack channel configured.\n"
            f"Set SLACK_CHANNEL in {default_env_path()} or "
            "[slack].channel in <project>/.pipeline/pipeline.toml\n"
        )
        return 1

    # H3: create session dir with mode 700 before taking lock.
    session_d = _session_dir(sid)
    session_d.mkdir(mode=0o700, parents=True, exist_ok=True)
    session_d.chmod(0o700)

    # --- take lock BEFORE any Slack call ---
    lock_fd, _ = _acquire_lock(sid)
    try:
        existing = _read_state(sid)

        if existing is not None:
            # Already have state — determine reactivation or idempotent return.
            if existing.get("active", False):
                # Idempotent: already active. Update last_bound_at.
                # B4: SIGTERM stale daemon before respawn.
                daemon_pid = existing.get("inbox_daemon_pid")
                if daemon_pid is None or not _is_pid_alive(daemon_pid):
                    _sigterm_daemon(daemon_pid, sid)
                    new_pid = _spawn_inbox_daemon(sid)
                    existing["inbox_daemon_pid"] = new_pid
                existing["last_bound_at"] = now_iso()
                _atomic_write_state(sid, existing)
                result = {
                    "channel": existing["channel_id"],
                    "thread_ts": existing["thread_ts"],
                    "session_id": sid,
                    "daemon_pid": existing.get("inbox_daemon_pid"),
                    "status": "already_active",
                }
                sys.stdout.write(json.dumps(result) + "\n")
                return 0

            # Previously deactivated — reopen the same thread.
            # C3: two-step write — clear pid BEFORE spawn so crash mid-spawn
            # leaves inbox_daemon_pid=None and next activate respawns cleanly.
            # B4: SIGTERM any surviving daemon from previous session.
            _sigterm_daemon(existing.get("inbox_daemon_pid"), sid)
            existing["active"] = True
            existing["ended_at"] = None
            existing["last_bound_at"] = now_iso()
            existing["inbox_daemon_pid"] = None
            _atomic_write_state(sid, existing)

            app = App(token=bot_token)
            thread_ts = existing["thread_ts"]
            reopen_channel = existing["channel_id"]
            app.client.chat_postMessage(
                channel=reopen_channel,
                thread_ts=thread_ts,
                text=f":arrows_counterclockwise: *Session reopened* at {now_iso()}",
                unfurl_links=False,
                unfurl_media=False,
            )

            # Spawn inbox daemon; write second state with new pid.
            new_pid = _spawn_inbox_daemon(sid)
            existing["inbox_daemon_pid"] = new_pid
            _atomic_write_state(sid, existing)
            result = {
                "channel": reopen_channel,
                "thread_ts": thread_ts,
                "session_id": sid,
                "daemon_pid": new_pid,
                "status": "reactivated",
            }
            sys.stdout.write(json.dumps(result) + "\n")
            return 0

        # No existing state — first bind. Post root message.
        app = App(token=bot_token)
        sid_short = _sid_short(sid)
        resp = app.client.chat_postMessage(
            channel=channel,
            text=(
                f":hourglass_flowing_sand: *Session started* `{sid_short}` "
                f"(cwd={cwd_display})"
            ),
            unfurl_links=False,
            unfurl_media=False,
        )
        thread_ts: str = resp["ts"]

        # H3: inbox dir mode 700 (tighter than design's 755 — holds private msg content).
        inbox_p = _inbox_path(sid)
        inbox_p.mkdir(mode=0o700, parents=True, exist_ok=True)
        inbox_p.chmod(0o700)

        state: dict[str, Any] = {
            "session_id": sid,
            "channel_id": channel,
            "thread_ts": thread_ts,
            "cwd": str(cwd_full),
            "started_at": now_iso(),
            "last_bound_at": now_iso(),
            "ended_at": None,
            "active": True,
            "schema_version": SCHEMA_VERSION,
            "inbox_daemon_pid": None,
        }
        _atomic_write_state(sid, state)

        # Spawn inbox daemon; update state with its pid.
        daemon_pid = _spawn_inbox_daemon(sid)
        state["inbox_daemon_pid"] = daemon_pid
        _atomic_write_state(sid, state)

        result = {
            "channel": channel,
            "thread_ts": thread_ts,
            "session_id": sid,
            "daemon_pid": daemon_pid,
            "status": "activated",
        }
        sys.stdout.write(json.dumps(result) + "\n")
        return 0

    finally:
        _release_lock(lock_fd)


def cmd_deactivate(args: argparse.Namespace) -> int:
    """Deactivate session binding and post closing message."""
    del args  # unused
    sid = _require_session_id()

    load_env_file(default_env_path())
    bot_token = os.environ.get("SLACK_BOT_TOKEN", "")
    app_token = os.environ.get("SLACK_APP_TOKEN", "")
    if not bot_token or not app_token:
        sys.stderr.write(
            "SLACK_BOT_TOKEN and SLACK_APP_TOKEN required.\n"
        )
        return 1

    lock_fd, _ = _acquire_lock(sid)
    try:
        state = _read_state(sid)
        if state is None:
            sys.stderr.write(f"Session {sid[:8]}... is not bound.\n")
            return 1

        daemon_pid = state.get("inbox_daemon_pid")

        if not state.get("active", False):
            # Already inactive; still attempt to SIGTERM stale daemon.
            _sigterm_daemon(daemon_pid, sid)
            sys.stdout.write("already_inactive\n")
            return 0

        # Post closing message.
        app = App(token=bot_token)
        app.client.chat_postMessage(
            channel=state["channel_id"],
            thread_ts=state["thread_ts"],
            text=f":checkered_flag: *Session ended at {now_iso()}*",
            unfurl_links=False,
            unfurl_media=False,
        )

        state["active"] = False
        state["ended_at"] = now_iso()
        state["inbox_daemon_pid"] = None
        _atomic_write_state(sid, state)

        _sigterm_daemon(daemon_pid, sid)

        # Inbox subtree is intentionally preserved (Q4 / M5).
        sys.stdout.write("ok\n")
        return 0

    finally:
        _release_lock(lock_fd)


def cmd_status(args: argparse.Namespace) -> int:
    """Print JSON state or 'unbound'."""
    del args  # unused
    sid = _require_session_id()
    state = _read_state(sid)
    if state is None:
        sys.stdout.write("unbound\n")
        return 0

    # Augment with live daemon pid check.
    daemon_pid = state.get("inbox_daemon_pid")
    out = dict(state)
    out["daemon_pid_alive"] = _is_pid_alive(daemon_pid) if daemon_pid else False
    sys.stdout.write(json.dumps(out, indent=2, default=str) + "\n")
    return 0


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="session_bind.py",
        description=(
            "Activate / deactivate / status for session-bound Slack threading. "
            "Reads CLAUDE_CODE_SESSION_ID from env."
        ),
    )
    parser.add_argument("--log-level", default="WARNING", help="logging level")
    sub = parser.add_subparsers(dest="command", required=True)

    act = sub.add_parser("activate", help="Bind session to a Slack thread")
    act.add_argument(
        "--project",
        default=None,
        help="Project path for pipeline.toml channel lookup (default: cwd)",
    )

    sub.add_parser("deactivate", help="Unbind session and post closing message")
    sub.add_parser("status", help="Print JSON state or 'unbound'")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    dispatch = {
        "activate": cmd_activate,
        "deactivate": cmd_deactivate,
        "status": cmd_status,
    }
    fn = dispatch.get(args.command)
    if fn is None:
        parser.print_help(sys.stderr)
        sys.exit(1)
    sys.exit(fn(args))


if __name__ == "__main__":
    main()
