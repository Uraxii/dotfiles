"""Test comms/types.py dataclass invariants."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
from types import MappingProxyType

import pytest

from comms.types import (
    AuthCheck,
    DecisionPost,
    EventRole,
    InboundConsumer,
    InboundEvent,
    MessageRef,
    OptionSpec,
    QuestionPost,
    ThreadRef,
)


def test_thread_ref_frozen() -> None:
    """ThreadRef is frozen — mutation must raise."""
    ref = ThreadRef(provider="slack", provider_data=MappingProxyType({"channel_id": "C1"}))
    with pytest.raises((FrozenInstanceError, AttributeError)):
        ref.provider = "other"  # type: ignore[misc]


def test_message_ref_frozen() -> None:
    ref = MessageRef(
        provider="slack",
        provider_data=MappingProxyType({"channel_id": "C1", "message_ts": "1.0"}),
    )
    with pytest.raises((FrozenInstanceError, AttributeError)):
        ref.provider = "other"  # type: ignore[misc]


def test_option_spec_tradeoff_default_none() -> None:
    opt = OptionSpec(key="A", title="Alpha")
    assert opt.tradeoff is None


def test_option_spec_with_tradeoff() -> None:
    opt = OptionSpec(key="B", title="Beta", tradeoff="Fast but risky")
    assert opt.tradeoff == "Fast but risky"


def test_question_post_frozen() -> None:
    ref = MessageRef(provider="slack", provider_data=MappingProxyType({"message_ts": "1.0"}))
    post = QuestionPost(ref=ref, client_msg_id="abc123")
    with pytest.raises((FrozenInstanceError, AttributeError)):
        post.client_msg_id = "other"  # type: ignore[misc]


def test_decision_post_distinct_type() -> None:
    ref = MessageRef(provider="slack", provider_data=MappingProxyType({"message_ts": "2.0"}))
    dpost = DecisionPost(ref=ref, client_msg_id="def456")
    assert isinstance(dpost, DecisionPost)
    assert not isinstance(dpost, QuestionPost)


def test_auth_check_details_default_empty() -> None:
    ac = AuthCheck(ok=True, message="")
    assert dict(ac.details) == {}


def test_auth_check_frozen() -> None:
    ac = AuthCheck(ok=False, message="missing scope")
    with pytest.raises((FrozenInstanceError, AttributeError)):
        ac.ok = True  # type: ignore[misc]


def test_inbound_event_frozen() -> None:
    thread_ref = ThreadRef("slack", MappingProxyType({"thread_ts": "1.0"}))
    ev = InboundEvent(
        event_role="message",
        run_id=None,
        qd_id=None,
        option_index=None,
        thread_ref=thread_ref,
        message_ref=None,
        user_id="U123",
        text="hi",
        received_at="2026-05-15T00:00:00Z",
    )
    with pytest.raises((FrozenInstanceError, AttributeError)):
        ev.user_id = "other"  # type: ignore[misc]


def test_inbound_event_has_no_button_value_field() -> None:
    """B6: InboundEvent must not have a button_value field."""
    ev = InboundEvent(
        event_role="question_answer",
        run_id="test-run-abc123",
        qd_id="q1",
        option_index=0,
        thread_ref=ThreadRef("slack", MappingProxyType({})),
        message_ref=None,
        user_id="U1",
        text=None,
        received_at="2026-05-15T00:00:00Z",
    )
    assert not hasattr(ev, "button_value")


def test_event_role_literal_values() -> None:
    """EventRole covers exactly the three expected values."""
    import typing
    args = typing.get_args(EventRole)
    assert set(args) == {"question_answer", "decision_pick", "message"}
