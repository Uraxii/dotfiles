"""Slack crash-recovery: recover_message_ts via conversations.replies scan."""
from __future__ import annotations

import logging
from types import MappingProxyType
from typing import Any

from ..types import MessageRef, ThreadRef

__all__ = ["recover_message_ts"]

log = logging.getLogger(__name__)

# Scan most-recent N messages in thread during recovery.
_HISTORY_LIMIT = 20


def recover_message_ts(
    client: Any,
    thread: ThreadRef,
    client_msg_id: str,
) -> MessageRef | None:
    """Scan conversations.replies for a bot message matching client_msg_id.

    Design §4.3 / §8.4 primary recovery defense: after a crash between post
    and context update, this locates the already-posted message so we can
    write its ts without re-posting (avoiding duplicates).

    Returns a MessageRef on hit, or None when not found in the recent-history
    window (caller retries with fresh id).

    MUST NOT mutate any on-disk state.
    """
    channel_id = thread.provider_data.get("channel_id", "")
    thread_ts = thread.provider_data.get("thread_ts", "")
    try:
        resp = client.conversations_replies(
            channel=channel_id,
            ts=thread_ts,
            limit=_HISTORY_LIMIT,
        )
    except Exception as exc:
        log.warning("conversations_replies failed during recovery: %s", exc)
        return None

    messages: list[dict[str, Any]] = resp.get("messages") or []
    for msg in messages:
        metadata = msg.get("metadata") or {}
        payload = metadata.get("event_payload") or {}
        if payload.get("client_msg_id") == client_msg_id:
            msg_ts = str(msg.get("ts", ""))
            log.info(
                "recovery: found existing post ts=%s for client_msg_id=%s",
                msg_ts, client_msg_id,
            )
            return MessageRef(
                provider="slack",
                provider_data=MappingProxyType({
                    "channel_id": channel_id,
                    "thread_ts": thread_ts,
                    "message_ts": msg_ts,
                }),
            )
    return None
