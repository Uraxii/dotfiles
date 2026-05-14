"""Shared fixtures for pipeline session tests.

Provides a fake ~/.claude/sessions/<sid>/ layout using tmp_path.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


@pytest.fixture()
def sid() -> str:
    return "test-session-deadbeef-1234-5678-abcd-000000000001"


@pytest.fixture()
def sessions_root(tmp_path: Path) -> Path:
    root = tmp_path / "sessions"
    root.mkdir(parents=True, exist_ok=True)
    root.chmod(0o700)
    return root


@pytest.fixture()
def session_dir(sessions_root: Path, sid: str) -> Path:
    d = sessions_root / sid
    d.mkdir(parents=True, exist_ok=True)
    inbox = d / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture()
def slack_json_path(session_dir: Path) -> Path:
    return session_dir / "slack.json"


def make_slack_json(
    session_dir: Path,
    sid: str,
    active: bool = True,
    channel_id: str = "C0TEST123",
    thread_ts: str = "1731628800.000200",
    schema_version: int = 1,
    inbox_daemon_pid: int | None = None,
) -> Path:
    """Write a minimal slack.json to session_dir. Returns the path."""
    state = {
        "session_id": sid,
        "channel_id": channel_id,
        "thread_ts": thread_ts,
        "cwd": "/fake/cwd",
        "started_at": "2026-05-14T12:00:00Z",
        "last_bound_at": "2026-05-14T12:00:00Z",
        "ended_at": None,
        "active": active,
        "schema_version": schema_version,
        "inbox_daemon_pid": inbox_daemon_pid,
    }
    path = session_dir / "slack.json"
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return path


@pytest.fixture()
def run_dir(tmp_path: Path) -> Path:
    """Fake pipeline run dir with pipeline.md."""
    project = tmp_path / "project"
    run = project / ".pipeline" / "runs" / "test-run-abc123"
    run.mkdir(parents=True, exist_ok=True)
    md = run / "pipeline.md"
    md.write_text(
        "---\nstatus: active\nslack:\n  bound_session: null\n  channel_id: null\n"
        "  thread_ts: null\n  warning: null\n---\n\n# Pipeline test-run-abc123\n",
        encoding="utf-8",
    )
    return run
