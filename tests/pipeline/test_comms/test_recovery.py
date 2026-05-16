"""Test recover_message_ts: R9, R10."""
from __future__ import annotations

from types import MappingProxyType
from typing import Any
from unittest.mock import MagicMock

import pytest

from comms.slack.recovery import recover_message_ts
from comms.types import ThreadRef


def _make_thread(channel: str = "C1", thread_ts: str = "111.000") -> ThreadRef:
    return ThreadRef(
        provider="slack",
        provider_data=MappingProxyType({"channel_id": channel, "thread_ts": thread_ts}),
    )


def _mock_client(messages: list[dict[str, Any]]) -> MagicMock:
    client = MagicMock()
    client.conversations_replies.return_value = {"messages": messages}
    return client


# --- R9: found ---


def test_recover_finds_by_client_msg_id() -> None:
    """R9: history returns msg with matching metadata -> MessageRef populated."""
    client = _mock_client([
        {"ts": "111.001", "metadata": {"event_payload": {"client_msg_id": "other"}}},
        {"ts": "111.002", "metadata": {"event_payload": {"client_msg_id": "target-id"}}},
    ])
    result = recover_message_ts(client, _make_thread(), "target-id")
    assert result is not None
    assert result.provider == "slack"
    assert result.provider_data["message_ts"] == "111.002"


def test_recover_first_match_returned() -> None:
    """First matching message is returned even if later ones also match."""
    client = _mock_client([
        {"ts": "111.001", "metadata": {"event_payload": {"client_msg_id": "target-id"}}},
        {"ts": "111.002", "metadata": {"event_payload": {"client_msg_id": "target-id"}}},
    ])
    result = recover_message_ts(client, _make_thread(), "target-id")
    assert result is not None
    assert result.provider_data["message_ts"] == "111.001"


# --- R10: not found ---


def test_recover_returns_none_when_absent() -> None:
    """R10: no match in history -> None (caller retries)."""
    client = _mock_client([
        {"ts": "222.001", "metadata": {"event_payload": {"client_msg_id": "wrong-id"}}},
    ])
    result = recover_message_ts(client, _make_thread(), "missing-id")
    assert result is None


def test_recover_returns_none_on_empty_history() -> None:
    """Empty history -> None."""
    client = _mock_client([])
    result = recover_message_ts(client, _make_thread(), "any-id")
    assert result is None


def test_recover_returns_none_when_api_raises() -> None:
    """conversations_replies raises -> None (caller retries)."""
    client = MagicMock()
    client.conversations_replies.side_effect = Exception("network error")
    result = recover_message_ts(client, _make_thread(), "any-id")
    assert result is None


def test_recover_handles_missing_metadata() -> None:
    """Messages without metadata don't crash the scan."""
    client = _mock_client([
        {"ts": "333.001"},  # no metadata
        {"ts": "333.002", "metadata": {"event_payload": {"client_msg_id": "target"}}},
    ])
    result = recover_message_ts(client, _make_thread(), "target")
    assert result is not None
    assert result.provider_data["message_ts"] == "333.002"


def test_recover_multiple_pages_checked() -> None:
    """Recovery scan checks all returned messages (up to _HISTORY_LIMIT)."""
    # 19 non-matching + 1 matching
    messages = [
        {"ts": f"444.{i:03d}", "metadata": {"event_payload": {"client_msg_id": f"id-{i}"}}}
        for i in range(1, 20)
    ]
    messages.append({"ts": "444.020", "metadata": {"event_payload": {"client_msg_id": "id-target"}}})
    client = _mock_client(messages)
    result = recover_message_ts(client, _make_thread(), "id-target")
    assert result is not None
    assert result.provider_data["message_ts"] == "444.020"
