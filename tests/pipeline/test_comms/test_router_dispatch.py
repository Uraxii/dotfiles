"""Test InboundConsumerImpl dispatch: R4, R5, R6, R7, R16."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from types import MappingProxyType
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from comms.router import (
    BUTTON_LETTERS,
    InboundConsumerImpl,
    Route,
    RoutingIndex,
    RoutingSnapshot,
    _write_answer_file,
    _write_decision_file,
    _safe_yaml_scalar,
)
from comms.types import InboundEvent, MessageRef, ThreadRef


def _make_thread_ref(channel: str = "C1", thread_ts: str = "1.0") -> ThreadRef:
    return ThreadRef(
        provider="slack",
        provider_data=MappingProxyType({"channel_id": channel, "thread_ts": thread_ts}),
    )


def _make_message_ref(
    channel: str = "C1", thread_ts: str = "1.0", message_ts: str = "1.1"
) -> MessageRef:
    return MessageRef(
        provider="slack",
        provider_data=MappingProxyType(
            {"channel_id": channel, "thread_ts": thread_ts, "message_ts": message_ts}
        ),
    )


def _make_index_with_route(
    thread_ts: str, inbox_dir: Path
) -> RoutingIndex:
    index = RoutingIndex()
    route = Route(
        sid="test-sid",
        thread_ref=_make_thread_ref(thread_ts=thread_ts),
        inbox_dir=inbox_dir,
    )
    snap = RoutingSnapshot(
        by_thread=MappingProxyType({thread_ts: route}),
        by_sid=MappingProxyType({"test-sid": route}),
        fingerprint="fp1",
    )
    index._snapshot = snap
    return index


# --- R4: allowlist drop silently for message ---


def test_message_allowlist_drop_silent(tmp_path: Path) -> None:
    """R4: disallowed user message -> no inbox write, no ephemeral."""
    inbox = tmp_path / "inbox"
    inbox.mkdir(mode=0o700)
    provider = MagicMock()
    index = _make_index_with_route("1.0", inbox)
    stop = threading.Event()

    consumer = InboundConsumerImpl(
        provider=provider,
        index=index,
        allowed_users=frozenset({"UALLOWED"}),
        stop_evt=stop,
    )
    ev = InboundEvent(
        event_role="message",
        run_id=None, qd_id=None, option_index=None,
        thread_ref=_make_thread_ref(),
        message_ref=_make_message_ref(),
        user_id="UDISALLOWED",
        text="hello",
        received_at="2026-05-15T00:00:00Z",
    )
    consumer.dispatch(ev)

    # No inbox files written.
    assert list(inbox.glob("*.json")) == []
    # No ephemeral posted for message path.
    provider.post_ephemeral_error.assert_not_called()


# --- R5: button allowlist drop -> ephemeral, no answer file ---


def test_button_allowlist_drop_ephemeral(tmp_path: Path) -> None:
    """R5: disallowed user button click -> ephemeral posted, no answer file."""
    inbox = tmp_path / "inbox"
    inbox.mkdir(mode=0o700)
    provider = MagicMock()
    index = _make_index_with_route("1.0", inbox)
    stop = threading.Event()

    consumer = InboundConsumerImpl(
        provider=provider,
        index=index,
        allowed_users=frozenset({"UALLOWED"}),
        stop_evt=stop,
    )
    ev = InboundEvent(
        event_role="question_answer",
        run_id="alpha-bravo-charlie-abc123",
        qd_id="q1",
        option_index=0,
        thread_ref=_make_thread_ref(),
        message_ref=_make_message_ref(),
        user_id="UDISALLOWED",
        text=None,
        received_at="2026-05-15T00:00:00Z",
    )
    consumer.dispatch(ev)

    provider.post_ephemeral_error.assert_called_once()
    # No answer file written.
    assert not (tmp_path / "answer-r1.md").exists()


# --- R6: button click -> answer file with delivery_mode: async ---


def test_button_writes_answer_file(tmp_path: Path) -> None:
    """R6: button click -> answer-r<N>.md exists w/ delivery_mode: async (NOT slack)."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    inbox = tmp_path / "inbox"
    inbox.mkdir(mode=0o700)

    # Write a dummy question file.
    (run_dir / "question-r1.md").write_text(
        "---\nquestion_id: q1\nopened_at: 2026-05-15T00:00:00Z\nrequesting_role: build\n---\n\n"
        "## Option A: Go\n## Option B: Stop\n"
    )

    provider = MagicMock()
    index = _make_index_with_route("1.0", inbox)
    stop = threading.Event()

    consumer = InboundConsumerImpl(
        provider=provider,
        index=index,
        allowed_users=frozenset(),
        stop_evt=stop,
    )

    # Write run-index entry so _resolve_route_dir_from_run_id can find the run.
    from comms.router import RUN_INDEX_DIR
    import hashlib

    phash8 = hashlib.sha1(str(run_dir.parent).encode()).hexdigest()[:8]
    with patch("comms.router.RUN_INDEX_DIR", tmp_path / "run-index"):
        (tmp_path / "run-index").mkdir(exist_ok=True)
        (tmp_path / "run-index" / "alpha-bravo-charlie-abc123.json").write_text(
            json.dumps({
                "run_dir": str(run_dir),
                "project_path": str(run_dir.parent),
                "project_path_hash": phash8,
                "updated_at": "2026-05-15T00:00:00Z",
            })
        )

        ev = InboundEvent(
            event_role="question_answer",
            run_id="alpha-bravo-charlie-abc123",
            qd_id="q1",
            option_index=0,  # A
            thread_ref=_make_thread_ref(),
            message_ref=_make_message_ref(),
            user_id="UALLOWED",
            text=None,
            received_at="2026-05-15T00:00:00Z",
        )
        consumer.dispatch(ev)

    answer_file = run_dir / "answer-r1.md"
    assert answer_file.exists()
    content = answer_file.read_text()
    assert "delivery_mode: async" in content
    assert "delivery_mode: slack" not in content


# --- R7: button click -> decision file with delivery_mode: async ---


def test_button_writes_decision_file(tmp_path: Path) -> None:
    """R7: decision button -> decision-r<N>.md exists w/ delivery_mode: async."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    inbox = tmp_path / "inbox"
    inbox.mkdir(mode=0o700)

    (run_dir / "awaiting-decision-r1.md").write_text(
        "---\ndecision_id: d1\nopened_at: 2026-05-15T00:00:00Z\nrequesting_role: build\n"
        "options_source: options-r1.md\n---\n\n"
    )

    provider = MagicMock()
    index = _make_index_with_route("1.0", inbox)
    stop = threading.Event()

    consumer = InboundConsumerImpl(
        provider=provider,
        index=index,
        allowed_users=frozenset(),
        stop_evt=stop,
    )

    import hashlib
    phash8 = hashlib.sha1(str(run_dir.parent).encode()).hexdigest()[:8]
    with patch("comms.router.RUN_INDEX_DIR", tmp_path / "run-index"):
        (tmp_path / "run-index").mkdir(exist_ok=True)
        (tmp_path / "run-index" / "alpha-bravo-charlie-abc123.json").write_text(
            json.dumps({
                "run_dir": str(run_dir),
                "project_path": str(run_dir.parent),
                "project_path_hash": phash8,
                "updated_at": "2026-05-15T00:00:00Z",
            })
        )

        ev = InboundEvent(
            event_role="decision_pick",
            run_id="alpha-bravo-charlie-abc123",
            qd_id="d1",
            option_index=1,  # B
            thread_ref=_make_thread_ref(),
            message_ref=_make_message_ref(),
            user_id="UALLOWED",
            text=None,
            received_at="2026-05-15T00:00:00Z",
        )
        consumer.dispatch(ev)

    decision_file = run_dir / "decision-r1.md"
    assert decision_file.exists()
    content = decision_file.read_text()
    assert "delivery_mode: async" in content
    assert "delivery_mode: slack" not in content
    assert "chosen_option: B" in content


# --- R16: idempotent reactivate (single thread) ---


def test_idempotent_reactivate(tmp_path: Path) -> None:
    """R16 (subset): second dispatch of same message_ts is ignored (idempotent)."""
    inbox = tmp_path / "inbox"
    inbox.mkdir(mode=0o700)
    provider = MagicMock()
    index = _make_index_with_route("1.0", inbox)
    stop = threading.Event()

    consumer = InboundConsumerImpl(
        provider=provider,
        index=index,
        allowed_users=frozenset(),
        stop_evt=stop,
    )
    ev = InboundEvent(
        event_role="message",
        run_id=None, qd_id=None, option_index=None,
        thread_ref=_make_thread_ref(),
        message_ref=_make_message_ref(message_ts="1716000000.000100"),
        user_id="U1",
        text="hi",
        received_at="2026-05-15T00:00:00Z",
    )
    consumer.dispatch(ev)
    consumer.dispatch(ev)

    files = list(inbox.glob("*.json"))
    assert len(files) == 1


# --- _safe_yaml_scalar (C1) ---


def test_safe_yaml_scalar_newline_escaped() -> None:
    result = _safe_yaml_scalar("value\ninjected_key: evil")
    assert "\n" not in result
    assert "\\n" in result


def test_safe_yaml_scalar_no_injection_via_newline() -> None:
    malicious = "value\ninjected_key: evil"
    escaped = _safe_yaml_scalar(malicious)
    assert "\n" not in escaped
