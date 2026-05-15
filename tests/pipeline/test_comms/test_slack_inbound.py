"""Test SlackInboundStream: R17, R18."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from types import MappingProxyType
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

from comms.slack.blocks import BUTTON_LETTERS
from comms.slack.inbound import SlackInboundStream, _write_unrouted_slack
from comms.types import InboundEvent, ThreadRef


def _make_snapshot_with_channel(channel_id: str, thread_ts: str) -> Any:
    """Return a fake routing snapshot stub."""
    snap = MagicMock()
    route = MagicMock()
    route.thread_ref = ThreadRef(
        provider="slack",
        provider_data=MappingProxyType({"channel_id": channel_id, "thread_ts": thread_ts}),
    )
    snap.by_thread = {thread_ts: route}
    return snap


# --- R17: cross-channel drop writes unrouted, no InboundEvent ---


def test_cross_channel_drop_writes_unrouted(tmp_path: Path) -> None:
    """R17: SlackInboundStream receives event whose event.channel != bound channel
    -> writes unrouted/<ts>.json with reason: cross_channel; NO InboundEvent."""
    dispatched: list[InboundEvent] = []

    class FakeConsumer:
        def dispatch(self, ev: InboundEvent) -> None:
            dispatched.append(ev)

    snapshot = _make_snapshot_with_channel("C_BOUND", "1.0")

    stream = SlackInboundStream(
        bot_token="xoxb-test",
        app_token="xapp-test",
        routing_index_ref=lambda: snapshot,
        provider_ref=MagicMock(),
    )

    # Simulate _on_message with a mismatched channel.
    event = {
        "ts": "1716000001.000100",
        "thread_ts": "1.0",
        "channel": "C_WRONG",
        "user": "UTEST",
        "text": "cross-channel message",
    }

    unrouted_dir = tmp_path / "unrouted"
    with patch("comms.slack.inbound._UNROUTED_DIR", unrouted_dir):
        stream._on_message(event)

    # No InboundEvent dispatched.
    assert dispatched == []

    # Unrouted file written with reason.
    unrouted_files = list(unrouted_dir.glob("*.json"))
    assert len(unrouted_files) == 1
    data = json.loads(unrouted_files[0].read_text())
    assert data.get("reason") == "cross_channel"
    assert data.get("event_channel") == "C_WRONG"


def test_cross_channel_no_route_dispatches_normally(tmp_path: Path) -> None:
    """If no route found for thread_ts, no cross-channel check -> dispatch proceeds."""
    dispatched: list[InboundEvent] = []

    class FakeConsumer:
        def dispatch(self, ev: InboundEvent) -> None:
            dispatched.append(ev)

    snap = MagicMock()
    snap.by_thread = {}  # no route

    stream = SlackInboundStream(
        bot_token="xoxb-test",
        app_token="xapp-test",
        routing_index_ref=lambda: snap,
        provider_ref=MagicMock(),
    )
    stream._consumer = FakeConsumer()

    event = {
        "ts": "1716000002.000100",
        "thread_ts": "2.0",
        "channel": "C_ANY",
        "user": "UTEST",
        "text": "unbound message",
    }
    stream._on_message(event)
    assert len(dispatched) == 1


# --- R18: button payload decoded inside adapter ---


def test_button_payload_decoded_inside_adapter() -> None:
    """R18: Slack-pipe action_id parsed inside adapter; InboundEvent has run_id/qd_id/option_index."""
    dispatched: list[InboundEvent] = []

    class FakeConsumer:
        def dispatch(self, ev: InboundEvent) -> None:
            dispatched.append(ev)

    snap = MagicMock()
    snap.by_thread = {}

    stream = SlackInboundStream(
        bot_token="xoxb-test",
        app_token="xapp-test",
        routing_index_ref=lambda: snap,
        provider_ref=MagicMock(),
    )
    stream._consumer = FakeConsumer()

    body = {
        "user": {"id": "UTEST"},
        "message": {"ts": "1716000003.000200", "thread_ts": "1716000003.000001"},
        "channel": {"id": "C1"},
    }
    action = {"value": "abcd1234|alpha-bravo-charlie-abc123|q1|A"}

    stream._process_button(body, action, "question_answer")

    assert len(dispatched) == 1
    ev = dispatched[0]
    assert ev.run_id == "alpha-bravo-charlie-abc123"
    assert ev.qd_id == "q1"
    assert ev.option_index == 0  # A is index 0
    assert ev.event_role == "question_answer"
    # No button_value field.
    assert not hasattr(ev, "button_value")


def test_button_payload_malformed_triggers_ephemeral() -> None:
    """Malformed button value -> ephemeral error posted, no InboundEvent."""
    dispatched: list[InboundEvent] = []

    class FakeConsumer:
        def dispatch(self, ev: InboundEvent) -> None:
            dispatched.append(ev)

    provider = MagicMock()
    snap = MagicMock()
    snap.by_thread = {}

    stream = SlackInboundStream(
        bot_token="xoxb-test",
        app_token="xapp-test",
        routing_index_ref=lambda: snap,
        provider_ref=provider,
    )
    stream._consumer = FakeConsumer()

    body = {
        "user": {"id": "UTEST"},
        "message": {"ts": "1.0"},
        "channel": {"id": "C1"},
    }
    action = {"value": "malformed-no-pipes"}

    stream._process_button(body, action, "question_answer")

    assert dispatched == []
    provider.post_ephemeral_error.assert_called_once()


def test_button_letters_option_index_mapping() -> None:
    """BUTTON_LETTERS[0] == A, [1] == B, etc."""
    assert BUTTON_LETTERS[0] == "A"
    assert BUTTON_LETTERS[1] == "B"
    assert BUTTON_LETTERS[2] == "C"
    assert BUTTON_LETTERS[3] == "D"
