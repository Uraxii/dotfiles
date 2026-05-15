"""Test SlackProvider: R8, R15."""
from __future__ import annotations

import sys
from pathlib import Path
from types import MappingProxyType
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from comms.types import AuthCheck, MessageRef, ThreadRef


def _make_thread_ref(channel: str = "C1", thread_ts: str = "1.0") -> ThreadRef:
    return ThreadRef(
        provider="slack",
        provider_data=MappingProxyType({"channel_id": channel, "thread_ts": thread_ts}),
    )


def _build_provider() -> Any:
    from comms.slack.provider import SlackProvider
    return SlackProvider(bot_token="xoxb-test", app_token=None)


def _patch_app(mock_app: MagicMock) -> Any:
    """Patch slack_bolt.App in sys.modules stub to return mock_app."""
    # slack_bolt is already a MagicMock stub; set App to a callable returning mock_app.
    stub = sys.modules["slack_bolt"]
    return patch.object(stub, "App", return_value=mock_app)


# --- R8: post_question embeds client_msg_id ---


def test_post_question_embeds_client_msg_id() -> None:
    """R8: chat_postMessage mock receives metadata.event_payload.client_msg_id."""
    provider = _build_provider()

    mock_resp = MagicMock()
    mock_resp.__getitem__ = lambda self, key: "111.222" if key == "ts" else None

    mock_client = MagicMock()
    mock_client.chat_postMessage.return_value = mock_resp

    mock_app = MagicMock()
    mock_app.client = mock_client

    from comms.types import OptionSpec
    options = [OptionSpec(key="A", title="Alpha"), OptionSpec(key="B", title="Beta")]
    thread = _make_thread_ref()

    with _patch_app(mock_app):
        post = provider.post_question_with_ids(
            thread,
            "alpha-bravo-charlie-abc123",
            "q1",
            "Pick one",
            "H",
            options,
            "abcd1234",
            "testclientmsgid123",
        )

    call_kwargs = mock_client.chat_postMessage.call_args.kwargs
    metadata = call_kwargs.get("metadata", {})
    payload = metadata.get("event_payload", {})
    assert payload.get("client_msg_id") == "testclientmsgid123"


def test_post_simple_calls_chat_post_message() -> None:
    """post_simple calls chat_postMessage with correct args."""
    provider = _build_provider()
    mock_resp = MagicMock()
    mock_resp.__getitem__ = lambda self, key: "222.333" if key == "ts" else None
    mock_client = MagicMock()
    mock_client.chat_postMessage.return_value = mock_resp
    mock_app = MagicMock()
    mock_app.client = mock_client

    with _patch_app(mock_app):
        ref = provider.post_simple(_make_thread_ref(), "status", "hello world")

    assert ref.provider == "slack"
    assert "message_ts" in ref.provider_data
    mock_client.chat_postMessage.assert_called_once()


# --- R15: auth_preflight missing scope -> AuthCheck(ok=False) ---


def test_auth_preflight_missing_scope() -> None:
    """R15: mocked auth.test response missing channels:history -> AuthCheck(ok=False)."""
    provider = _build_provider()

    mock_resp = MagicMock()
    mock_resp.headers = {
        "x-oauth-scopes": "chat:write,groups:history"
        # missing channels:history
    }
    mock_client = MagicMock()
    mock_client.auth_test.return_value = mock_resp
    mock_app = MagicMock()
    mock_app.client = mock_client

    with _patch_app(mock_app):
        result = provider.auth_preflight()

    assert isinstance(result, AuthCheck)
    assert result.ok is False
    assert "channels:history" in result.message


def test_auth_preflight_all_scopes_present() -> None:
    """All required scopes present -> AuthCheck(ok=True)."""
    provider = _build_provider()

    mock_resp = MagicMock()
    mock_resp.headers = {
        "x-oauth-scopes": "chat:write,channels:history,groups:history,files:read"
    }
    mock_client = MagicMock()
    mock_client.auth_test.return_value = mock_resp
    mock_app = MagicMock()
    mock_app.client = mock_client

    with _patch_app(mock_app):
        result = provider.auth_preflight()

    assert result.ok is True


def test_auth_preflight_auth_test_failure() -> None:
    """auth.test raises exception -> AuthCheck(ok=False) with message."""
    provider = _build_provider()
    mock_app = MagicMock()
    mock_app.client.auth_test.side_effect = Exception("network error")

    with _patch_app(mock_app):
        result = provider.auth_preflight()

    assert result.ok is False
    assert "network error" in result.message
