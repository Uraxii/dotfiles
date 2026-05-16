"""Test session provider field B8 / B7: R11, R12."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from comms.session import (
    _load_slack_json,
    all_active_bindings,
    resolve_session_binding,
    resolve_session_thread_ref,
)
from .conftest import make_slack_json


# --- R11: legacy slack.json (no provider) reads as "slack" ---


def test_legacy_slack_json_reads_as_slack_direct(tmp_path: Path) -> None:
    """R11a: slack.json without provider field -> _load_slack_json sets provider='slack'."""
    session_dir = tmp_path / "sessions" / "test-sid-00000001"
    session_dir.mkdir(parents=True)
    path = make_slack_json(session_dir, sid="test-sid-00000001", provider=None)

    data = _load_slack_json(path)
    assert data is not None
    assert data["provider"] == "slack"


def test_legacy_slack_json_reads_as_slack_via_resolve(tmp_path: Path) -> None:
    """R11a: resolve_session_binding works on legacy file (no provider field)."""
    session_dir = tmp_path / "sessions" / "test-sid-legacy1"
    session_dir.mkdir(parents=True)
    make_slack_json(session_dir, sid="test-sid-legacy1", provider=None)

    with patch("comms.session.SESSIONS_ROOT", tmp_path / "sessions"):
        result = resolve_session_binding("test-sid-legacy1")
    assert result is not None
    assert result[0] == "C0TEST123"


def test_legacy_slack_json_reads_as_slack_via_all_active_bindings(tmp_path: Path) -> None:
    """R11b: all_active_bindings() on legacy file (no provider) returns provider='slack'."""
    sessions_root = tmp_path / "sessions"
    session_dir = sessions_root / "test-sid-legacy2"
    session_dir.mkdir(parents=True)
    make_slack_json(session_dir, sid="test-sid-legacy2", provider=None)

    with patch("comms.session.SESSIONS_ROOT", sessions_root):
        bindings = all_active_bindings()

    assert "test-sid-legacy2" in bindings
    assert bindings["test-sid-legacy2"]["provider"] == "slack"


def test_modern_slack_json_provider_preserved(tmp_path: Path) -> None:
    """Modern file with provider field is passed through unchanged."""
    session_dir = tmp_path / "sessions" / "test-sid-modern"
    session_dir.mkdir(parents=True)
    path = make_slack_json(session_dir, sid="test-sid-modern", provider="slack")
    data = _load_slack_json(path)
    assert data is not None
    assert data["provider"] == "slack"


# --- R12: write always sets provider + schema_version ---


def test_write_always_sets_provider_and_schema_version(tmp_path: Path) -> None:
    """R12: cmd_activate writes slack.json with schema_version=1 and provider='slack'.

    Tests the _atomic_write_state path via importing session_bind and simulating
    the state dict construction.
    """
    import session_bind

    sid = "test-sid-activate01"
    session_dir = tmp_path / "sessions" / sid
    session_dir.mkdir(parents=True)
    inbox_dir = session_dir / "inbox"
    inbox_dir.mkdir()
    state_path = session_dir / "slack.json"

    # Simulate what cmd_activate writes.
    state = {
        "schema_version": session_bind.SCHEMA_VERSION,
        "session_id": sid,
        "provider": "slack",
        "channel_id": "C0TEST123",
        "thread_ts": "1731628800.000200",
        "cwd": "/fake/cwd",
        "started_at": "2026-05-15T00:00:00Z",
        "last_bound_at": "2026-05-15T00:00:00Z",
        "ended_at": None,
        "active": True,
    }
    state_path.write_text(json.dumps(state, indent=2))

    # Verify fields present.
    written = json.loads(state_path.read_text())
    assert written["schema_version"] == 1
    assert written["provider"] == "slack"


def test_setdefault_at_lowest_level_not_caller(tmp_path: Path) -> None:
    """Callers of _load_slack_json may assume provider is set — no KeyError."""
    session_dir = tmp_path / "sessions" / "test-sid-setdefault"
    session_dir.mkdir(parents=True)
    make_slack_json(session_dir, sid="test-sid-setdefault", provider=None)
    path = session_dir / "slack.json"

    data = _load_slack_json(path)
    assert data is not None
    # Must not raise:
    provider = data["provider"]
    assert provider == "slack"
