"""Tests for M3/M4 — channel verification in inbox write path.

Tests the write_inbox_file function from session_inbox.py in isolation.
DEPRECATED: session_inbox.py removed in comms refactor. Tests skipped.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch, MagicMock

import pytest

pytestmark = pytest.mark.skip(reason="session_inbox.py removed in comms refactor")

_PIPELINE_DIR = Path(__file__).parent.parent / ".claude" / "pipeline"
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))


def _import_write_inbox_file():  # type: ignore[return]
    """Import write_inbox_file while mocking out slack_bolt/watchdog."""
    slack_bolt_mock = MagicMock()
    watchdog_mock = MagicMock()
    watchdog_events_mock = MagicMock()
    watchdog_observers_mock = MagicMock()

    modules_to_mock = {
        "slack_bolt": slack_bolt_mock,
        "slack_bolt.adapter": MagicMock(),
        "slack_bolt.adapter.socket_mode": MagicMock(),
        "watchdog": watchdog_mock,
        "watchdog.events": watchdog_events_mock,
        "watchdog.observers": watchdog_observers_mock,
    }
    # Ensure FileSystemEventHandler is a real class that can be subclassed.
    watchdog_events_mock.FileSystemEventHandler = object

    with patch.dict("sys.modules", modules_to_mock):
        import importlib
        if "session_inbox" in sys.modules:
            del sys.modules["session_inbox"]
        mod = importlib.import_module("session_inbox")
        return mod.write_inbox_file


def _make_event(
    ts: str = "100.001",
    thread_ts: str = "100.000",
    channel: str = "C0TEST",
    text: str = "hello",
) -> dict[str, Any]:
    return {
        "ts": ts,
        "thread_ts": thread_ts,
        "channel": channel,
        "user": "U001",
        "text": text,
    }


# ---------------------------------------------------------------------------
# M3/M4 — channel verification: write_inbox_file
# ---------------------------------------------------------------------------


def test_write_inbox_file_matching_channel(tmp_path: Path) -> None:
    """write_inbox_file writes when event channel matches expected_channel."""
    write_inbox_file = _import_write_inbox_file()
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    event = _make_event(ts="200.001", channel="C0TEST")
    write_inbox_file(inbox, event, expected_channel="C0TEST")
    target = inbox / "200.001.json"
    assert target.exists(), "should write file when channel matches"


def test_write_inbox_file_wrong_channel_skips(tmp_path: Path) -> None:
    """write_inbox_file skips write when event channel does not match expected_channel."""
    write_inbox_file = _import_write_inbox_file()
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    event = _make_event(ts="300.001", channel="CWRONG")
    write_inbox_file(inbox, event, expected_channel="C0TEST")
    target = inbox / "300.001.json"
    assert not target.exists(), "should NOT write file when channel mismatches"


def test_write_inbox_file_no_channel_in_event(tmp_path: Path) -> None:
    """Event with no channel field passes verification (backward compat)."""
    write_inbox_file = _import_write_inbox_file()
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    event = _make_event(ts="400.001")
    del event["channel"]  # channel absent
    # No exception should be raised.
    write_inbox_file(inbox, event, expected_channel="C0TEST")


def test_write_inbox_file_no_expected_channel(tmp_path: Path) -> None:
    """If expected_channel is empty string (unbound), all channels pass."""
    write_inbox_file = _import_write_inbox_file()
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    event = _make_event(ts="500.001", channel="CANY")
    write_inbox_file(inbox, event, expected_channel="")
    target = inbox / "500.001.json"
    assert target.exists(), "empty expected_channel should not gate writes"


def test_write_inbox_file_content_is_json(tmp_path: Path) -> None:
    """Written file contains valid JSON with expected fields."""
    write_inbox_file = _import_write_inbox_file()
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    event = _make_event(ts="600.001", channel="C0TEST", text="test message")
    write_inbox_file(inbox, event, expected_channel="C0TEST")
    data = json.loads((inbox / "600.001.json").read_text(encoding="utf-8"))
    assert data["message_ts"] == "600.001"
    assert data["text"] == "test message"


def test_write_inbox_file_idempotent(tmp_path: Path) -> None:
    """Calling write_inbox_file twice for the same ts is a no-op (H3 invariant)."""
    write_inbox_file = _import_write_inbox_file()
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    event = _make_event(ts="700.001", channel="C0TEST", text="original")
    write_inbox_file(inbox, event, expected_channel="C0TEST")
    event2 = _make_event(ts="700.001", channel="C0TEST", text="replacement")
    write_inbox_file(inbox, event2, expected_channel="C0TEST")
    data = json.loads((inbox / "700.001.json").read_text(encoding="utf-8"))
    assert data["text"] == "original", "second write must not overwrite first"
