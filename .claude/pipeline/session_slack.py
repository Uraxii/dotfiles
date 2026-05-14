"""session_slack — stdlib-only session binding helper.

Reads ~/.claude/sessions/<sid>/slack.json and exposes the public surface
used by pipeline_ask.py, slack_listener.py, and the orchestrator intake step.

No slack-bolt, no PyYAML, no requests. Pure stdlib.

Public surface:
    resolve_session_binding(session_id)  -> tuple[str, str] | None
    session_state_path(session_id)       -> Path
    inbox_dir(session_id)                -> Path
    is_bound(session_id)                 -> bool
    all_active_bindings()                -> dict[str, dict]
    spawn_listener(project_path, run_id) -> subprocess.Popen
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

__all__ = [
    "resolve_session_binding",
    "session_state_path",
    "inbox_dir",
    "is_bound",
    "all_active_bindings",
    "spawn_listener",
]

log = logging.getLogger(__name__)

SESSIONS_ROOT = Path("~/.claude/sessions").expanduser()
LISTENER_SCRIPT = Path("~/.claude/pipeline/slack_listener.py").expanduser()
SCHEMA_VERSION_SUPPORTED = 1


def _get_session_id(session_id: str | None) -> str | None:
    """Resolve session_id: arg wins, else env CLAUDE_CODE_SESSION_ID."""
    if session_id is not None:
        return session_id
    return os.environ.get("CLAUDE_CODE_SESSION_ID")


def session_state_path(session_id: str | None = None) -> Path:
    """Return Path to ~/.claude/sessions/<sid>/slack.json. Does not check existence."""
    sid = _get_session_id(session_id)
    if not sid:
        raise ValueError(
            "session_id required: CLAUDE_CODE_SESSION_ID not set in environment"
        )
    return SESSIONS_ROOT / sid / "slack.json"


def inbox_dir(session_id: str | None = None) -> Path:
    """Return Path to ~/.claude/sessions/<sid>/inbox/. Does not create."""
    sid = _get_session_id(session_id)
    if not sid:
        raise ValueError(
            "session_id required: CLAUDE_CODE_SESSION_ID not set in environment"
        )
    return SESSIONS_ROOT / sid / "inbox"


def _load_slack_json(path: Path) -> dict[str, Any] | None:
    """Parse slack.json. Returns None on missing file, JSON error, or unsupported schema."""
    if not path.is_file():
        return None
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("failed to read %s: %s", path, exc)
        return None
    if not isinstance(data, dict):
        log.warning("slack.json top-level is not a dict (got %s); path=%s", type(data).__name__, path)
        return None
    version = data.get("schema_version", 1)
    if version > SCHEMA_VERSION_SUPPORTED:
        log.warning(
            "slack.json schema_version=%d unsupported (max=%d); path=%s",
            version,
            SCHEMA_VERSION_SUPPORTED,
            path,
        )
        return None
    return data


def resolve_session_binding(
    session_id: str | None = None,
) -> tuple[str, str] | None:
    """Return (channel_id, thread_ts) if an *active* binding exists.

    Defaults to env CLAUDE_CODE_SESSION_ID. Returns None when:
    - session_id is absent / env not set
    - state file missing
    - state file corrupt or schema_version > 1
    - active == false
    """
    sid = _get_session_id(session_id)
    if not sid:
        return None
    path = SESSIONS_ROOT / sid / "slack.json"
    data = _load_slack_json(path)
    if data is None:
        return None
    if not data.get("active", False):
        return None
    channel = data.get("channel_id", "")
    thread_ts = data.get("thread_ts", "")
    if not channel or not thread_ts:
        log.warning("slack.json at %s missing channel_id or thread_ts", path)
        return None
    return channel, thread_ts


def is_bound(session_id: str | None = None) -> bool:
    """True iff resolve_session_binding(...) is not None."""
    return resolve_session_binding(session_id) is not None


def all_active_bindings() -> dict[str, dict[str, Any]]:
    """Glob ~/.claude/sessions/*/slack.json; return {sid: parsed_json} for all active.

    Used by listener and inbox-daemon to build the thread_ts -> sid index.
    """
    result: dict[str, dict[str, Any]] = {}
    if not SESSIONS_ROOT.is_dir():
        return result
    for json_path in SESSIONS_ROOT.glob("*/slack.json"):
        data = _load_slack_json(json_path)
        if data is None:
            continue
        if not data.get("active", False):
            continue
        sid = data.get("session_id") or json_path.parent.name
        result[sid] = data
    return result


def spawn_listener(project_path: Path, run_id: str) -> subprocess.Popen:  # type: ignore[type-arg]
    """Spawn the per-run Slack listener as a detached subprocess.

    Constructs the ``--session-thread CHANNEL:TS`` flag when a binding is
    active for the current session. Stdlib-only beyond subprocess.Popen.

    Used by pipeline_ask.py and the decision-elicitation async branch so both
    callers stay in lockstep on flag construction.
    """
    if not LISTENER_SCRIPT.is_file():
        raise FileNotFoundError(f"listener script missing: {LISTENER_SCRIPT}")

    run_dir = project_path / ".pipeline" / "runs" / run_id
    log_path = run_dir / "slack-listener.log"

    cmd = ["uv", "run", "--script", str(LISTENER_SCRIPT), str(project_path), run_id]

    binding = resolve_session_binding()
    if binding is not None:
        channel, thread_ts = binding
        cmd += ["--session-thread", f"{channel}:{thread_ts}"]
        log.debug("spawn_listener: session-bound channel=%s thread_ts=%s", channel, thread_ts)
    else:
        log.debug("spawn_listener: no active binding; legacy per-run thread")

    try:
        log_fh = open(log_path, "a")  # noqa: SIM115 — lifetime must outlast call
    except OSError as exc:
        raise OSError(f"cannot open listener log {log_path}: {exc}") from exc

    proc = subprocess.Popen(
        cmd,
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        close_fds=True,
    )
    log.info("spawned listener pid=%d run=%s", proc.pid, run_id)
    return proc
