"""comms.session — provider-aware session binding reader.

Replaces session_slack.py (C3 — deleted, not re-exported). Reads
~/.claude/sessions/<sid>/slack.json and applies the B8 fix: sets
data["provider"] = "slack" inside _load_slack_json so all callers
can assume the field is present.

Public surface:
    resolve_session_binding(session_id)    -> tuple[str, str] | None
    resolve_session_thread_ref(session_id) -> ThreadRef | None
    session_state_path(session_id)         -> Path
    inbox_dir(session_id)                  -> Path
    is_bound(session_id)                   -> bool
    all_active_bindings()                  -> dict[str, dict]
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from .types import ThreadRef

__all__ = [
    "resolve_session_binding",
    "resolve_session_thread_ref",
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
    """Parse slack.json. Returns None on missing file, JSON error, or unsupported schema.

    B8 fix: applies data.setdefault("provider", "slack") at the LOWEST read
    level. All post-call code MAY assume data["provider"] is set.
    """
    if not path.is_file():
        return None
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("failed to read %s: %s", path, exc)
        return None
    if not isinstance(data, dict):
        log.warning(
            "slack.json top-level is not a dict (got %s); path=%s",
            type(data).__name__, path,
        )
        return None
    version = data.get("schema_version", 1)
    if version > SCHEMA_VERSION_SUPPORTED:
        log.warning(
            "slack.json schema_version=%d unsupported (max=%d); path=%s",
            version, SCHEMA_VERSION_SUPPORTED, path,
        )
        return None
    # B8: default provider at the lowest read level so callers need not repeat it.
    data.setdefault("provider", "slack")
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


def resolve_session_thread_ref(
    session_id: str | None = None,
) -> ThreadRef | None:
    """Provider-aware resolver. Returns ThreadRef or None.

    The 2-tuple resolve_session_binding() is kept as a thin shim that
    unpacks ThreadRef.provider_data for the Slack provider only (legacy
    callers unchanged). New code uses this.
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
    from types import MappingProxyType
    provider = data.get("provider", "slack")
    return ThreadRef(
        provider=provider,
        provider_data=MappingProxyType({"channel_id": channel, "thread_ts": thread_ts}),
    )


def is_bound(session_id: str | None = None) -> bool:
    """True iff resolve_session_binding(...) is not None."""
    return resolve_session_binding(session_id) is not None


def all_active_bindings() -> dict[str, dict[str, Any]]:
    """Glob ~/.claude/sessions/*/slack.json; return {sid: parsed_json} for all active.

    B8: provider field guaranteed present via _load_slack_json.
    Used by comms/router.py to build the thread_ts -> sid routing index.
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
