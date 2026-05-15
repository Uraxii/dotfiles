"""Tests for session_slack public surface.

Covers: session_state_path, inbox_dir, resolve_session_binding,
is_bound, all_active_bindings.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add pipeline dir to path so session_slack can import _slack_env.
_PIPELINE_DIR = Path(__file__).parent.parent / ".claude" / "pipeline"
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

from tests.conftest import make_slack_json  # noqa: E402
import comms.session as session_slack  # noqa: E402


# ---------------------------------------------------------------------------
# session_state_path
# ---------------------------------------------------------------------------


def test_session_state_path_uses_arg(tmp_path: Path) -> None:
    with patch.object(session_slack, "SESSIONS_ROOT", tmp_path / "sessions"):
        path = session_slack.session_state_path("my-session-id")
    assert path.parts[-1] == "slack.json"
    assert "my-session-id" in str(path)


def test_session_state_path_uses_env(tmp_path: Path) -> None:
    with (
        patch.object(session_slack, "SESSIONS_ROOT", tmp_path / "sessions"),
        patch.dict(os.environ, {"CLAUDE_CODE_SESSION_ID": "env-sid-xyz"}),
    ):
        path = session_slack.session_state_path()
    assert "env-sid-xyz" in str(path)


def test_session_state_path_raises_when_no_sid() -> None:
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_SESSION_ID"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(ValueError, match="CLAUDE_CODE_SESSION_ID"):
            session_slack.session_state_path()


# ---------------------------------------------------------------------------
# inbox_dir
# ---------------------------------------------------------------------------


def test_inbox_dir_path(tmp_path: Path) -> None:
    with patch.object(session_slack, "SESSIONS_ROOT", tmp_path / "sessions"):
        path = session_slack.inbox_dir("sid-abc")
    assert path.parts[-1] == "inbox"
    assert "sid-abc" in str(path)


# ---------------------------------------------------------------------------
# resolve_session_binding
# ---------------------------------------------------------------------------


def test_resolve_returns_tuple_when_active(
    sessions_root: Path, session_dir: Path, sid: str
) -> None:
    make_slack_json(session_dir, sid, active=True, channel_id="C999", thread_ts="111.222")
    with patch.object(session_slack, "SESSIONS_ROOT", sessions_root):
        result = session_slack.resolve_session_binding(sid)
    assert result == ("C999", "111.222")


def test_resolve_returns_none_when_inactive(
    sessions_root: Path, session_dir: Path, sid: str
) -> None:
    make_slack_json(session_dir, sid, active=False)
    with patch.object(session_slack, "SESSIONS_ROOT", sessions_root):
        result = session_slack.resolve_session_binding(sid)
    assert result is None


def test_resolve_returns_none_when_missing(
    sessions_root: Path, sid: str
) -> None:
    with patch.object(session_slack, "SESSIONS_ROOT", sessions_root):
        result = session_slack.resolve_session_binding(sid)
    assert result is None


def test_resolve_returns_none_when_corrupt(
    sessions_root: Path, session_dir: Path, sid: str
) -> None:
    (session_dir / "slack.json").write_text("NOT JSON", encoding="utf-8")
    with patch.object(session_slack, "SESSIONS_ROOT", sessions_root):
        result = session_slack.resolve_session_binding(sid)
    assert result is None


def test_resolve_returns_none_when_schema_too_new(
    sessions_root: Path, session_dir: Path, sid: str
) -> None:
    make_slack_json(session_dir, sid, active=True, schema_version=99)
    with patch.object(session_slack, "SESSIONS_ROOT", sessions_root):
        result = session_slack.resolve_session_binding(sid)
    assert result is None


def test_resolve_uses_env_sid(
    sessions_root: Path, session_dir: Path, sid: str
) -> None:
    make_slack_json(session_dir, sid, active=True, channel_id="CENV", thread_ts="777.888")
    with (
        patch.object(session_slack, "SESSIONS_ROOT", sessions_root),
        patch.dict(os.environ, {"CLAUDE_CODE_SESSION_ID": sid}),
    ):
        result = session_slack.resolve_session_binding()
    assert result == ("CENV", "777.888")


# ---------------------------------------------------------------------------
# is_bound
# ---------------------------------------------------------------------------


def test_is_bound_true(sessions_root: Path, session_dir: Path, sid: str) -> None:
    make_slack_json(session_dir, sid, active=True)
    with patch.object(session_slack, "SESSIONS_ROOT", sessions_root):
        assert session_slack.is_bound(sid) is True


def test_is_bound_false_inactive(sessions_root: Path, session_dir: Path, sid: str) -> None:
    make_slack_json(session_dir, sid, active=False)
    with patch.object(session_slack, "SESSIONS_ROOT", sessions_root):
        assert session_slack.is_bound(sid) is False


# ---------------------------------------------------------------------------
# all_active_bindings
# ---------------------------------------------------------------------------


def test_all_active_bindings_returns_active_only(tmp_path: Path) -> None:
    root = tmp_path / "sessions"

    sid_a = "aaaa-aaaa"
    sid_b = "bbbb-bbbb"
    sid_c = "cccc-cccc"

    dir_a = root / sid_a
    dir_b = root / sid_b
    dir_c = root / sid_c
    for d in (dir_a, dir_b, dir_c):
        d.mkdir(parents=True)

    make_slack_json(dir_a, sid_a, active=True, channel_id="CA", thread_ts="1.1")
    make_slack_json(dir_b, sid_b, active=False, channel_id="CB", thread_ts="2.2")
    make_slack_json(dir_c, sid_c, active=True, channel_id="CC", thread_ts="3.3")

    with patch.object(session_slack, "SESSIONS_ROOT", root):
        bindings = session_slack.all_active_bindings()

    assert sid_a in bindings
    assert sid_c in bindings
    assert sid_b not in bindings
    assert bindings[sid_a]["channel_id"] == "CA"
    assert bindings[sid_c]["thread_ts"] == "3.3"


def test_all_active_bindings_empty_when_no_sessions(tmp_path: Path) -> None:
    root = tmp_path / "sessions"
    root.mkdir()
    with patch.object(session_slack, "SESSIONS_ROOT", root):
        assert session_slack.all_active_bindings() == {}


def test_all_active_bindings_skips_corrupt(tmp_path: Path) -> None:
    root = tmp_path / "sessions"
    sid = "good-sid"
    bad_sid = "bad-sid"
    (root / sid).mkdir(parents=True)
    (root / bad_sid).mkdir(parents=True)
    make_slack_json(root / sid, sid, active=True)
    (root / bad_sid / "slack.json").write_text("{invalid", encoding="utf-8")
    with patch.object(session_slack, "SESSIONS_ROOT", root):
        bindings = session_slack.all_active_bindings()
    assert sid in bindings
    assert bad_sid not in bindings
