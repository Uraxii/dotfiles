"""CommsProvider Protocol — every comms backend implements this surface."""
from __future__ import annotations

import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, runtime_checkable

from .types import (
    AuthCheck,
    DecisionPost,
    InboundConsumer,
    MessageRef,
    OptionSpec,
    QuestionPost,
    ThreadRef,
)

__all__ = ["CommsProvider"]


@runtime_checkable
class CommsProvider(Protocol):
    """All outbound + lifecycle + inbound surface for one chat backend.

    Implementations: SlackProvider (this pass).

    Threading: outbound methods are called from CLI one-shot processes
    (notify/ask) AND from the long-lived router daemon. Implementations
    must NOT cache mutable state on `self` across method calls; treat
    each call as independent. Auth client construction is fine to cache
    per-instance because each process builds its own instance.

    Idempotency: post_question / post_decision callers wrap calls in a
    file-locked run-dir context (`.comms-context.json` + `.comms-posting.lock`).
    Adapter implementations participate via `client_msg_id` round-trip
    (see SlackProvider) — they do NOT own the lock.
    """

    name: str
    """Stable registry key, e.g. "slack". Used by CommsRegistry and
    persisted in slack.json `provider` field."""

    # ------------------------------------------------------------------
    # Lifecycle / auth
    # ------------------------------------------------------------------

    def auth_preflight(self) -> AuthCheck:
        """Verify creds + scopes before binding. Network call permitted.
        MUST NOT mutate any on-disk state.
        """
        ...

    # ------------------------------------------------------------------
    # Outbound — simple notifications
    # ------------------------------------------------------------------

    def post_simple(
        self,
        thread: ThreadRef,
        kind: str,
        text: str,
    ) -> MessageRef:
        """Post status/completion/friction-summary text.

        `kind` is the notification-kind string (e.g. "status", "completion",
        "friction-summary"); adapter MAY decorate (emoji prefix etc.).
        """
        ...

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
        """Post a question with N (2..4) option buttons + optional file attachments.

        Adapter MUST embed `client_msg_id` in provider-side message metadata
        so a crashed-mid-post recovery scan can find the message without
        re-posting.

        Raises: provider-specific transport exceptions (caller catches
        and writes stderr). MUST NOT swallow + return a fake MessageRef.
        """
        ...

    def post_decision(
        self,
        thread: ThreadRef,
        decision_text: str,
        options: Sequence[OptionSpec],
        *,
        client_msg_id: str,
    ) -> DecisionPost:
        """Post a decision-point with N option buttons.

        No attachments in this pass (matches current surface).
        """
        ...

    def recover_message_ts(
        self,
        thread: ThreadRef,
        client_msg_id: str,
    ) -> MessageRef | None:
        """Best-effort scan of recent thread history for a post whose
        adapter-side metadata carries `client_msg_id`.

        Returns the recovered MessageRef on hit, or None if not found in the
        recent-history window.

        Used by the provider-neutral CLI crash-recovery branch in
        pipeline_notify. Provider implementations query their native
        history API.

        MUST be safe to call from one-shot CLI processes (no daemon
        state required). MUST NOT mutate any on-disk state.
        """
        ...

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
        """Replace the body of a previously posted message.

        `lock=True` means strip interactive elements (buttons) so the post
        becomes read-only. `lock=False` permits future edit-but-keep-buttons
        cases (not used this pass; reserved).
        """
        ...

    def post_confirmation(
        self,
        thread: ThreadRef,
        ref: MessageRef,
        answer: str,
    ) -> None:
        """Post a thread-reply confirming an answer was recorded.

        `ref` identifies the original question/decision post being confirmed
        (adapter MAY include it in body).
        """
        ...

    def post_ephemeral_error(
        self,
        thread: ThreadRef,
        user_id: str,
        text: str,
    ) -> None:
        """Post a message visible ONLY to `user_id`.

        Used for allowlist rejection + malformed-button-value toasts.
        If the backend has no ephemeral primitive, adapter MAY DM instead.
        """
        ...

    # ------------------------------------------------------------------
    # Lifecycle — bind / unbind (provider posts the welcome / farewell)
    # ------------------------------------------------------------------

    def open_thread(
        self,
        channel_hint: str,
        opening_text: str,
    ) -> ThreadRef:
        """Create a new thread by posting `opening_text` to `channel_hint`.

        Returns a ThreadRef the router/notify can use.
        `channel_hint` is provider-specific (Slack channel id; future
        Discord channel id). Resolved by registry/config, not here.
        """
        ...

    def close_thread(
        self,
        thread: ThreadRef,
        closing_text: str,
    ) -> None:
        """Post a closing reply. Adapter does NOT delete the thread."""
        ...

    # ------------------------------------------------------------------
    # Inbound — push-side registration (D12)
    # ------------------------------------------------------------------

    def start_inbound(
        self,
        consumer: InboundConsumer,
        stop: threading.Event,
    ) -> None:
        """Start the provider's inbound transport. Returns immediately
        after the worker thread is up.

        Threading contract:
          - Provider owns its internal worker thread (Slack: Bolt's
            SocketModeHandler thread + Bolt worker pool).
          - Per normalized event, provider calls `consumer.dispatch(event)`
            from its internal thread. The consumer is responsible for
            synchronization on shared state.
          - Provider monitors `stop` event; when set, it tears down its
            transport and joins its worker thread.
          - start_inbound MUST be a no-op if already started.
        """
        ...

    def stop_inbound(self) -> None:
        """Idempotent shutdown. Tears down transport if running, joins
        worker thread. Safe to call without a prior start_inbound.
        """
        ...
