"""SlackInboundStream — Bolt App + SocketModeHandler push-side adapter.

Owns the Slack-specific inbound event handling (B2 + B3 + B6):
- B2: push-side start_inbound / stop_inbound (no generator).
- B3: cross-channel guard INSIDE adapter before InboundEvent construction.
- B6: Slack pipe-encoded action_id decoded inside adapter; InboundEvent carries
      structured run_id / qd_id / option_index — no raw Slack strings.

This module is the sole importer of slack_bolt.adapter.socket_mode.
"""
from __future__ import annotations

import logging
import re
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal

from ..types import EventRole, InboundConsumer, InboundEvent, MessageRef, ThreadRef
from .blocks import BUTTON_LETTERS, decode_button_payload

__all__ = ["SlackInboundStream"]

log = logging.getLogger(__name__)

# Regex guards for run_id and qd_id fields decoded from button payload.
_RUN_ID_RE = re.compile(r"^[a-z]+(?:-[a-z]+){2}-[a-f0-9]{6}$")
_QD_ID_RE = re.compile(r"^[qd][0-9]{1,4}$")

# Unrouted audit dir — written by adapter for cross-channel drops (B3).
_COMMS_ROOT = Path("~/.config/opencode/comms-router").expanduser()
_UNROUTED_DIR = _COMMS_ROOT / "unrouted"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_unrouted_slack(event: dict[str, Any], reason: str = "") -> None:
    """Write provider-internal audit file for unrouted/cross-channel events."""
    import json
    from ..env import atomic_write_text

    message_ts: str = event.get("ts", "")
    if not message_ts:
        return
    _UNROUTED_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = _UNROUTED_DIR / f"{message_ts}.json"
    if target.exists():
        return
    payload: dict[str, Any] = {
        "session_id": None,
        "thread_ts": event.get("thread_ts", ""),
        "message_ts": message_ts,
        "user_id": event.get("user", ""),
        "text": event.get("text", ""),
        "received_at": _now_iso(),
        "event_channel": event.get("channel", ""),
    }
    if reason:
        payload["reason"] = reason
    try:
        atomic_write_text(target, json.dumps(payload, indent=2), mode=0o600)
        log.debug("unrouted(slack): wrote %s reason=%s", target, reason)
    except OSError as exc:
        log.error("unrouted(slack) write failed for %s: %s", target, exc)


class SlackInboundStream:
    """Wraps Bolt App + SocketModeHandler. Push-side: invokes
    consumer.dispatch(event) from Bolt's worker threads.

    Constructor receives:
      - bot_token, app_token
      - routing_index_ref: callable returning current RoutingSnapshot
        (so the cross-channel guard can resolve the bound channel for
        a thread_ts without holding a stale snapshot)
      - provider_ref: the SlackProvider instance (for post_ephemeral_error
        on malformed button payloads)
    """

    def __init__(
        self,
        bot_token: str,
        app_token: str,
        routing_index_ref: Callable[[], Any],
        provider_ref: Any,
    ) -> None:
        self._bot_token = bot_token
        self._app_token = app_token
        self._routing_index_ref = routing_index_ref
        self._provider_ref = provider_ref
        self._started = False
        self._consumer: InboundConsumer | None = None
        self._stop: threading.Event | None = None
        self._app: Any = None
        self._handler: Any = None
        self._worker: threading.Thread | None = None

    def start(
        self,
        consumer: InboundConsumer,
        stop: threading.Event,
    ) -> None:
        """Start Bolt inbound transport. Idempotent (no-op if already started)."""
        if self._started:
            return
        self._started = True
        self._consumer = consumer
        self._stop = stop

        from slack_bolt import App  # noqa: PLC0415
        from slack_bolt.adapter.socket_mode import SocketModeHandler  # noqa: PLC0415

        self._app = App(token=self._bot_token)
        self._app.event("message")(self._on_message)
        for letter in BUTTON_LETTERS:
            self._app.action(f"question_pick_{letter}")(
                self._on_button_factory("question")
            )
            self._app.action(f"decision_pick_{letter}")(
                self._on_button_factory("decision")
            )
        self._handler = SocketModeHandler(self._app, self._app_token)
        self._worker = threading.Thread(
            target=self._handler.start,
            daemon=True,
            name="slack-inbound-worker",
        )
        self._worker.start()
        # Watchdog: when stop fires, close handler + join.
        threading.Thread(
            target=self._watch_stop,
            daemon=True,
            name="slack-inbound-watchdog",
        ).start()

    def stop(self) -> None:
        """Idempotent shutdown."""
        if not self._started:
            return
        try:
            if self._handler is not None:
                self._handler.close()
        except Exception:
            log.exception("slack handler close failed")
        if self._worker is not None and self._worker.is_alive():
            self._worker.join(timeout=5.0)
        self._started = False

    def _watch_stop(self) -> None:
        """Watchdog: close handler when stop event fires."""
        if self._stop is not None:
            self._stop.wait()
        self.stop()

    def _on_message(self, event: dict[str, Any]) -> None:
        if event.get("subtype") is not None:
            return
        if event.get("bot_id") or event.get("bot_profile"):
            return
        thread_ts: str = event.get("thread_ts") or event.get("ts", "")
        if not thread_ts:
            return
        message_ts: str = event.get("ts", "")
        if not message_ts:
            return

        ev_channel: str = event.get("channel", "")

        # B3: cross-channel guard BEFORE constructing InboundEvent.
        snap = self._routing_index_ref()
        route = snap.by_thread.get(thread_ts)
        if route is not None:
            bound_channel: str = route.thread_ref.provider_data.get("channel_id", "")
            if ev_channel and bound_channel and ev_channel != bound_channel:
                log.warning(
                    "cross-channel drop: event=%s bound=%s",
                    ev_channel, bound_channel,
                )
                _write_unrouted_slack(event, reason="cross_channel")
                return

        thread_ref = ThreadRef(
            provider="slack",
            provider_data=MappingProxyType(
                {"channel_id": ev_channel, "thread_ts": thread_ts}
            ),
        )
        message_ref = MessageRef(
            provider="slack",
            provider_data=MappingProxyType(
                {
                    "channel_id": ev_channel,
                    "thread_ts": thread_ts,
                    "message_ts": message_ts,
                }
            ),
        )
        ev = InboundEvent(
            event_role="message",
            run_id=None,
            qd_id=None,
            option_index=None,
            thread_ref=thread_ref,
            message_ref=message_ref,
            user_id=event.get("user", ""),
            text=event.get("text", ""),
            received_at=_now_iso(),
        )
        if self._consumer is not None:
            self._consumer.dispatch(ev)

    def _on_button_factory(
        self, kind: Literal["question", "decision"]
    ) -> Any:
        """Return a Bolt action handler for the given button kind."""
        role: EventRole = (
            "question_answer" if kind == "question" else "decision_pick"
        )

        def handler(ack: Any, body: dict[str, Any], action: dict[str, Any]) -> None:
            ack()
            try:
                self._process_button(body, action, role)
            except Exception:
                log.exception("button handler failed (kind=%s)", kind)

        return handler

    def _process_button(
        self,
        body: dict[str, Any],
        action: dict[str, Any],
        role: EventRole,
    ) -> None:
        """Decode Slack-pipe action_id and emit InboundEvent (B6)."""
        value: str = action.get("value", "")
        decoded = decode_button_payload(value)
        if decoded is None:
            log.warning("malformed button value: %r", value)
            # Malformed button — ephemeral error to user, drop.
            channel_id = (body.get("channel") or {}).get("id", "")
            user_id = body.get("user", {}).get("id", "")
            thread_ref = ThreadRef(
                provider="slack",
                provider_data=MappingProxyType(
                    {"channel_id": channel_id, "thread_ts": ""}
                ),
            )
            self._provider_ref.post_ephemeral_error(
                thread_ref,
                user_id,
                "Button payload malformed; reposting may help.",
            )
            return

        _phash8, run_id, qd_id, choice = decoded

        # Validate fields (mirrors _resolve_route_dir_from_value guards).
        if not _RUN_ID_RE.match(run_id):
            log.warning("run_id failed validation: %r", run_id)
            return
        if not _QD_ID_RE.match(qd_id):
            log.warning("qd_id failed validation: %r", qd_id)
            return

        # Map choice letter to option_index.
        try:
            option_index = list(BUTTON_LETTERS).index(choice)
        except ValueError:
            log.warning("unknown choice letter: %r", choice)
            return

        message = body.get("message") or {}
        message_ts: str = message.get("ts", "")
        ev_thread_ts: str = message.get("thread_ts") or message_ts
        channel_id = (body.get("channel") or {}).get("id", "")
        user_id = body.get("user", {}).get("id", "")

        thread_ref = ThreadRef(
            provider="slack",
            provider_data=MappingProxyType(
                {"channel_id": channel_id, "thread_ts": ev_thread_ts}
            ),
        )
        message_ref = MessageRef(
            provider="slack",
            provider_data=MappingProxyType(
                {
                    "channel_id": channel_id,
                    "thread_ts": ev_thread_ts,
                    "message_ts": message_ts,
                }
            ),
        )
        ev = InboundEvent(
            event_role=role,
            run_id=run_id,
            qd_id=qd_id,
            option_index=option_index,
            thread_ref=thread_ref,
            message_ref=message_ref,
            user_id=user_id,
            text=None,
            received_at=_now_iso(),
        )
        if self._consumer is not None:
            self._consumer.dispatch(ev)
