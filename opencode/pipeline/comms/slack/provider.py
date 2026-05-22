"""SlackProvider — implements CommsProvider for Slack.

Sole module in the codebase that imports slack_bolt or slack_sdk (AC2).
All Slack API calls, channel resolution, and inbound event registration
live here and in comms/slack/inbound.py.
"""
from __future__ import annotations

import hashlib
import logging
import os
import threading
from collections.abc import Sequence
from pathlib import Path
from types import MappingProxyType
from typing import Any

from ..env import default_env_path, load_env_file
from ..provider import CommsProvider  # noqa: F401 — for type annotation
from ..types import (
    AuthCheck,
    DecisionPost,
    InboundConsumer,
    MessageRef,
    OptionSpec,
    QuestionPost,
    ThreadRef,
)
from .blocks import build_decision_blocks, build_question_blocks
from .inbound import SlackInboundStream
from .recovery import recover_message_ts as _recover_message_ts_impl

__all__ = ["SlackProvider", "build_slack_provider"]

log = logging.getLogger(__name__)

# Scopes required for end-to-end session-bound threading.
_REQUIRED_BOT_SCOPES: frozenset[str] = frozenset(
    {"chat:write", "channels:history", "groups:history"}
)

KIND_EMOJI: dict[str, str] = {
    "status": ":information_source:",
    "completion": ":white_check_mark:",
    "friction-summary": ":mag:",
}


def _project_hash(project_path_str: str) -> str:
    return hashlib.sha1(project_path_str.encode()).hexdigest()[:8]


class SlackProvider:
    """Slack implementation of CommsProvider."""

    name: str = "slack"

    def __init__(
        self,
        bot_token: str,
        app_token: str | None,
        channel: str = "",
    ) -> None:
        self._bot_token = bot_token
        self._app_token = app_token
        self._channel = channel
        self._inbound: SlackInboundStream | None = None
        self._routing_index_ref: Any = lambda: _EmptySnapshot()

    def _client(self) -> Any:
        """Build a Slack WebClient (or App) for outbound calls."""
        from slack_bolt import App  # noqa: PLC0415
        return App(token=self._bot_token).client

    # ------------------------------------------------------------------
    # Lifecycle / auth
    # ------------------------------------------------------------------

    def auth_preflight(self) -> AuthCheck:
        """Verify bot token has all _REQUIRED_BOT_SCOPES."""
        try:
            from slack_bolt import App  # noqa: PLC0415
            app = App(token=self._bot_token)
            resp = app.client.auth_test()
        except Exception as exc:
            return AuthCheck(ok=False, message=f"auth.test failed: {exc}")

        headers = getattr(resp, "headers", {}) or {}
        raw = headers.get("x-oauth-scopes") or headers.get("X-OAuth-Scopes") or ""
        granted: set[str] = {s.strip() for s in raw.split(",") if s.strip()}
        missing = sorted(_REQUIRED_BOT_SCOPES - granted)
        if not missing:
            return AuthCheck(ok=True, message="", details=MappingProxyType(
                {"granted_scopes": ", ".join(sorted(granted))}
            ))
        return AuthCheck(
            ok=False,
            message=(
                f"Slack bot token is missing required scopes: {', '.join(missing)}.\n"
                f"Granted scopes: {sorted(granted) or '<none>'}\n"
                "Fix: api.slack.com/apps -> your app -> OAuth & Permissions -> add the "
                "missing scope(s) -> click *Reinstall to Workspace* at the top of the "
                "page -> paste the refreshed xoxb- token into "
                f"{default_env_path()}.\n"
                "Without these scopes Slack will not deliver message events to the "
                "router even though posts succeed."
            ),
            details=MappingProxyType({"missing_scopes": ", ".join(missing)}),
        )

    # ------------------------------------------------------------------
    # Outbound — simple notifications
    # ------------------------------------------------------------------

    def post_simple(
        self,
        thread: ThreadRef,
        kind: str,
        text: str,
    ) -> MessageRef:
        """Post status/completion/friction-summary text."""
        client = self._client()
        channel_id = thread.provider_data["channel_id"]
        thread_ts = thread.provider_data["thread_ts"]
        emoji = KIND_EMOJI.get(kind, ":speech_balloon:")
        full_text = f"{emoji} *{kind}:* {text}"
        resp = client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=full_text,
            unfurl_links=False,
            unfurl_media=False,
        )
        return MessageRef(
            provider="slack",
            provider_data=MappingProxyType({
                "channel_id": channel_id,
                "thread_ts": thread_ts,
                "message_ts": str(resp["ts"]),
            }),
        )

    # ------------------------------------------------------------------
    # Outbound — question / decision with buttons
    # ------------------------------------------------------------------

    def post_question(
        self,
        thread: ThreadRef,
        question_text: str,
        options: Sequence[OptionSpec],
        *,
        client_msg_id: str,
        header: str = "",
        attachments: Sequence[Path] = (),
    ) -> QuestionPost:
        """Post a question with option buttons and optional file attachments."""
        client = self._client()
        channel_id = thread.provider_data["channel_id"]
        thread_ts = thread.provider_data["thread_ts"]
        phash8 = _project_hash(channel_id)  # reuse channel as project differentiator

        attachment_links: list[tuple[str, str]] = []
        if attachments:
            attachment_links = self._upload_attachments(
                client, channel_id, thread_ts, list(attachments)
            )

        # qid is embedded in the question_text for display; extract for block_id.
        # For simplicity, pass question_text as prompt and use client_msg_id as qid.
        blocks = build_question_blocks(
            run_id="",  # will be overridden — see note below
            qid=client_msg_id[:8],
            header=header,
            prompt=question_text,
            options=options,
            phash8=phash8,
            attachment_links=attachment_links,
        )
        resp = client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=f"Question: {question_text[:80]}",
            blocks=blocks,
            metadata={
                "event_type": "question",
                "event_payload": {"client_msg_id": client_msg_id},
            },
            unfurl_links=False,
            unfurl_media=False,
        )
        posted_ts = str(resp["ts"])
        ref = MessageRef(
            provider="slack",
            provider_data=MappingProxyType({
                "channel_id": channel_id,
                "thread_ts": thread_ts,
                "message_ts": posted_ts,
            }),
        )
        return QuestionPost(ref=ref, client_msg_id=client_msg_id)

    def post_question_with_ids(
        self,
        thread: ThreadRef,
        run_id: str,
        qid: str,
        question_text: str,
        header: str,
        options: Sequence[OptionSpec],
        phash8: str,
        client_msg_id: str,
        attachments: Sequence[Path] = (),
    ) -> QuestionPost:
        """Full-fidelity question post with explicit routing ids.

        Used by pipeline_notify which owns the routing ids.
        """
        client = self._client()
        channel_id = thread.provider_data["channel_id"]
        thread_ts = thread.provider_data["thread_ts"]

        attachment_links: list[tuple[str, str]] = []
        if attachments:
            attachment_links = self._upload_attachments(
                client, channel_id, thread_ts, list(attachments)
            )

        blocks = build_question_blocks(
            run_id=run_id,
            qid=qid,
            header=header,
            prompt=question_text,
            options=options,
            phash8=phash8,
            attachment_links=attachment_links,
        )
        resp = client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=f"Question {qid}: {question_text[:80]}",
            blocks=blocks,
            metadata={
                "event_type": "question",
                "event_payload": {"client_msg_id": client_msg_id},
            },
            unfurl_links=False,
            unfurl_media=False,
        )
        posted_ts = str(resp["ts"])
        ref = MessageRef(
            provider="slack",
            provider_data=MappingProxyType({
                "channel_id": channel_id,
                "thread_ts": thread_ts,
                "message_ts": posted_ts,
            }),
        )
        return QuestionPost(ref=ref, client_msg_id=client_msg_id)

    def post_decision(
        self,
        thread: ThreadRef,
        decision_text: str,
        options: Sequence[OptionSpec],
        *,
        client_msg_id: str,
    ) -> DecisionPost:
        """Post a decision-point with option buttons."""
        client = self._client()
        channel_id = thread.provider_data["channel_id"]
        thread_ts = thread.provider_data["thread_ts"]
        phash8 = _project_hash(channel_id)

        blocks = build_decision_blocks(
            run_id="",
            did=client_msg_id[:8],
            topic=decision_text,
            options=options,
            phash8=phash8,
        )
        resp = client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=f"Decision: {decision_text}",
            blocks=blocks,
            metadata={
                "event_type": "decision",
                "event_payload": {"client_msg_id": client_msg_id},
            },
            unfurl_links=False,
            unfurl_media=False,
        )
        posted_ts = str(resp["ts"])
        ref = MessageRef(
            provider="slack",
            provider_data=MappingProxyType({
                "channel_id": channel_id,
                "thread_ts": thread_ts,
                "message_ts": posted_ts,
            }),
        )
        return DecisionPost(ref=ref, client_msg_id=client_msg_id)

    def post_decision_with_ids(
        self,
        thread: ThreadRef,
        run_id: str,
        did: str,
        topic: str,
        options: Sequence[OptionSpec],
        phash8: str,
        client_msg_id: str,
    ) -> DecisionPost:
        """Full-fidelity decision post with explicit routing ids.

        Used by pipeline_notify which owns the routing ids.
        """
        client = self._client()
        channel_id = thread.provider_data["channel_id"]
        thread_ts = thread.provider_data["thread_ts"]

        blocks = build_decision_blocks(
            run_id=run_id,
            did=did,
            topic=topic,
            options=options,
            phash8=phash8,
        )
        resp = client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=f"Decision {did}: {topic}",
            blocks=blocks,
            metadata={
                "event_type": "decision",
                "event_payload": {"client_msg_id": client_msg_id},
            },
            unfurl_links=False,
            unfurl_media=False,
        )
        posted_ts = str(resp["ts"])
        ref = MessageRef(
            provider="slack",
            provider_data=MappingProxyType({
                "channel_id": channel_id,
                "thread_ts": thread_ts,
                "message_ts": posted_ts,
            }),
        )
        return DecisionPost(ref=ref, client_msg_id=client_msg_id)

    def recover_message_ts(
        self,
        thread: ThreadRef,
        client_msg_id: str,
    ) -> MessageRef | None:
        """Scan conversations.replies for post with matching client_msg_id."""
        client = self._client()
        return _recover_message_ts_impl(client, thread, client_msg_id)

    # ------------------------------------------------------------------
    # Outbound — message updates / replies
    # ------------------------------------------------------------------

    def update_message(
        self,
        ref: MessageRef,
        new_body: str,
        *,
        lock: bool = True,
    ) -> None:
        """Replace the body of a previously posted message."""
        client = self._client()
        channel_id = ref.provider_data["channel_id"]
        message_ts = ref.provider_data["message_ts"]
        blocks: list[dict[str, Any]] = []
        if lock:
            # Strip buttons — read-only locked state.
            blocks = [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": new_body},
                }
            ]
        try:
            client.chat_update(
                channel=channel_id,
                ts=message_ts,
                text=new_body,
                blocks=blocks if lock else None,
            )
        except Exception as exc:
            log.warning("chat_update failed (ts=%s): %s", message_ts, exc)

    def post_confirmation(
        self,
        thread: ThreadRef,
        ref: MessageRef,
        answer: str,
    ) -> None:
        """Post a thread-reply confirming an answer was recorded."""
        client = self._client()
        channel_id = thread.provider_data["channel_id"]
        thread_ts = thread.provider_data["thread_ts"]
        try:
            client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text=f"Recorded `{answer}`. Pipeline resuming.",
                unfurl_links=False,
                unfurl_media=False,
            )
        except Exception as exc:
            log.warning("confirm post failed: %s", exc)

    def post_ephemeral_error(
        self,
        thread: ThreadRef,
        user_id: str,
        text: str,
    ) -> None:
        """Post a message visible ONLY to user_id."""
        client = self._client()
        channel_id = thread.provider_data.get("channel_id", "")
        try:
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=text,
            )
        except Exception as exc:
            log.warning("ephemeral post failed: %s", exc)

    # ------------------------------------------------------------------
    # Lifecycle — bind / unbind
    # ------------------------------------------------------------------

    def open_thread(
        self,
        channel_hint: str,
        opening_text: str,
    ) -> ThreadRef:
        """Create a new thread by posting opening_text to channel_hint."""
        client = self._client()
        resp = client.chat_postMessage(
            channel=channel_hint,
            text=opening_text,
            unfurl_links=False,
            unfurl_media=False,
        )
        thread_ts = str(resp["ts"])
        return ThreadRef(
            provider="slack",
            provider_data=MappingProxyType(
                {"channel_id": channel_hint, "thread_ts": thread_ts}
            ),
        )

    def close_thread(
        self,
        thread: ThreadRef,
        closing_text: str,
    ) -> None:
        """Post a closing reply. Does NOT delete the thread."""
        client = self._client()
        channel_id = thread.provider_data["channel_id"]
        thread_ts = thread.provider_data["thread_ts"]
        try:
            client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text=closing_text,
                unfurl_links=False,
                unfurl_media=False,
            )
        except Exception as exc:
            log.warning("close_thread post failed: %s", exc)

    # ------------------------------------------------------------------
    # Inbound — push-side registration (D12)
    # ------------------------------------------------------------------

    def set_routing_index_ref(self, ref: Any) -> None:
        """Set the routing index accessor for cross-channel guard (B3)."""
        self._routing_index_ref = ref
        if self._inbound is not None:
            self._inbound._routing_index_ref = ref

    def start_inbound(
        self,
        consumer: InboundConsumer,
        stop: threading.Event,
    ) -> None:
        """Start Bolt Socket Mode inbound transport. Idempotent."""
        if self._inbound is None:
            self._inbound = SlackInboundStream(
                bot_token=self._bot_token,
                app_token=self._app_token or "",
                routing_index_ref=self._routing_index_ref,
                provider_ref=self,
            )
        self._inbound.start(consumer, stop)

    def stop_inbound(self) -> None:
        """Idempotent shutdown of inbound transport."""
        if self._inbound is not None:
            self._inbound.stop()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _upload_attachments(
        self,
        client: Any,
        channel: str,
        thread_ts: str,
        attachments: list[Path],
    ) -> list[tuple[str, str]]:
        """Upload attachment files. Returns [(permalink, filename)]."""
        links: list[tuple[str, str]] = []
        for path in attachments:
            if not path.is_file():
                log.warning("attachment missing: %s", path)
                continue
            last_err: Exception | None = None
            resp = None
            for attempt in (1, 2):
                try:
                    resp = client.files_upload_v2(
                        channel=channel,
                        thread_ts=thread_ts,
                        file=str(path),
                        filename=path.name,
                        title=path.name,
                    )
                    break
                except Exception as exc:
                    last_err = exc
                    log.warning("upload attempt %d failed for %s: %s", attempt, path, exc)
            if resp is None:
                log.error("upload gave up for %s: %s", path, last_err)
                continue
            file_info: dict[str, Any] = {}
            try:
                file_info = resp.get("file", {}) or {}
            except AttributeError:
                pass
            permalink = file_info.get("permalink", "") or ""
            if permalink:
                links.append((permalink, path.name))
        return links


class _EmptySnapshot:
    """Fallback snapshot when routing index not yet set."""

    by_thread: dict[str, Any] = {}
    by_sid: dict[str, Any] = {}
    fingerprint: str = ""


def build_slack_provider() -> SlackProvider:
    """Zero-arg factory invoked by CommsRegistry. Loads env file once."""
    load_env_file(default_env_path())
    bot_token = os.environ.get("SLACK_BOT_TOKEN", "")
    app_token = os.environ.get("SLACK_APP_TOKEN", "")
    if not bot_token:
        raise RuntimeError(
            f"SLACK_BOT_TOKEN required. Set in {default_env_path()}"
        )
    # app_token may be empty for one-shot CLI use (no Socket Mode needed).
    return SlackProvider(
        bot_token=bot_token,
        app_token=app_token or None,
    )
