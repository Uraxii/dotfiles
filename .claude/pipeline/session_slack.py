"""session_slack — stdlib-only session binding helper.

Reads ~/.claude/sessions/<sid>/slack.json and exposes the public surface
used by pipeline_ask.py, slack_router.py, and the orchestrator intake step.

No slack-bolt, no PyYAML, no requests. Pure stdlib.

Public surface:
    resolve_session_binding(session_id)  -> tuple[str, str] | None
    session_state_path(session_id)       -> Path
    inbox_dir(session_id)                -> Path
    is_bound(session_id)                 -> bool
    all_active_bindings()                -> dict[str, dict]
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

__all__ = [
    "resolve_session_binding",
    "session_state_path",
    "inbox_dir",
    "is_bound",
    "all_active_bindings",
]

log = logging.getLogger(__name__)

SESSIONS_ROOT = Path("~/.claude/sessions").expanduser()
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

    Used by slack_router.py to build the thread_ts -> sid routing index.
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
