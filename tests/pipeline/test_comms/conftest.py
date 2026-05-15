"""Fixtures for comms pipeline tests."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

# Ensure pipeline dir on path.
_PIPELINE_DIR = Path(__file__).parent.parent.parent.parent / ".claude" / "pipeline"
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

# Stub slack_bolt before any import that triggers it.
_slack_bolt_stub = MagicMock()
_slack_bolt_stub.App = MagicMock
_socket_mode_stub = MagicMock()
_socket_mode_stub.SocketModeHandler = MagicMock
for _key, _val in [
    ("slack_bolt", _slack_bolt_stub),
    ("slack_bolt.adapter", MagicMock()),
    ("slack_bolt.adapter.socket_mode", _socket_mode_stub),
]:
    if _key not in sys.modules:
        sys.modules[_key] = _val  # type: ignore[assignment]

# Stub filelock.
_filelock_stub = MagicMock()
_filelock_stub.FileLock = MagicMock().__class__
if "filelock" not in sys.modules:
    sys.modules["filelock"] = _filelock_stub  # type: ignore[assignment]


@pytest.fixture()
def comms_root(tmp_path: Path) -> Path:
    """Temporary ~/.claude/comms-router equivalent."""
    root = tmp_path / "comms-router"
    root.mkdir(mode=0o700)
    (root / "unrouted").mkdir(mode=0o700)
    (root / "run-index").mkdir(mode=0o700)
    return root


@pytest.fixture()
def sessions_root(tmp_path: Path) -> Path:
    """Temporary ~/.claude/sessions equivalent."""
    root = tmp_path / "sessions"
    root.mkdir(mode=0o700)
    return root


@pytest.fixture()
def run_dir(tmp_path: Path) -> Path:
    """Fake pipeline run dir."""
    project = tmp_path / "project"
    rd = project / ".pipeline" / "runs" / "test-run-abc123"
    rd.mkdir(parents=True)
    return rd


def make_slack_json(
    session_dir: Path,
    sid: str,
    active: bool = True,
    channel_id: str = "C0TEST123",
    thread_ts: str = "1731628800.000200",
    schema_version: int = 1,
    provider: str | None = "slack",
) -> Path:
    """Write a minimal slack.json. If provider is None, omits the field (legacy)."""
    state: dict[str, Any] = {
        "session_id": sid,
        "channel_id": channel_id,
        "thread_ts": thread_ts,
        "cwd": "/fake/cwd",
        "started_at": "2026-05-14T12:00:00Z",
        "last_bound_at": "2026-05-14T12:00:00Z",
        "ended_at": None,
        "active": active,
        "schema_version": schema_version,
    }
    if provider is not None:
        state["provider"] = provider
    path = session_dir / "slack.json"
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return path
