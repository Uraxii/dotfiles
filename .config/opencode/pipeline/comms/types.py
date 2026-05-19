"""Provider-neutral value types for the comms abstraction.

Stdlib-only. No slack-bolt, no third-party deps. Importable from inside
the host router daemon and one-shot notify CLIs alike.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal, Protocol

__all__ = [
    "ThreadRef",
    "MessageRef",
    "OptionSpec",
    "QuestionPost",
    "DecisionPost",
    "AuthCheck",
    "InboundEvent",
    "InboundConsumer",
    "ProviderName",
    "EventRole",
]

ProviderName = str  # reserved for future Literal["slack", "discord", ...] tightening


@dataclass(frozen=True, slots=True)
class ThreadRef:
    """Opaque handle to a provider thread/channel pairing.

    `provider` identifies the adapter that minted the ref.
    `provider_data` carries adapter-private identifiers (e.g. Slack:
    {"channel_id": "...", "thread_ts": "..."}). Callers MUST NOT
    interpret keys inside provider_data — only the adapter does.
    """

    provider: ProviderName
    provider_data: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class MessageRef:
    """Opaque handle to a single posted message.

    For Slack: provider_data carries
        {"channel_id": "...", "thread_ts": "...", "message_ts": "..."}.
    For future Discord: {"channel_id": "...", "message_id": "..."} etc.
    """

    provider: ProviderName
    provider_data: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class OptionSpec:
    """One choice on a question or decision post."""

    key: str  # "A".."D" by convention; opaque to provider
    title: str  # human-visible label
    tradeoff: str | None = None  # decision-only sub-line; None for questions


@dataclass(frozen=True, slots=True)
class QuestionPost:
    """Outcome of post_question: ref to the post + the client_msg_id used
    for crash-recovery round-trip (idempotency key).
    """

    ref: MessageRef
    client_msg_id: str  # uuid4().hex; persisted in run-dir lock


@dataclass(frozen=True, slots=True)
class DecisionPost:
    """Outcome of post_decision: same shape as QuestionPost, distinct type
    for caller clarity + future divergence headroom.
    """

    ref: MessageRef
    client_msg_id: str


@dataclass(frozen=True, slots=True)
class AuthCheck:
    """Result of provider.auth_preflight().

    `ok=True` means safe to bind. `ok=False` means `message` is a human-readable
    fix instruction (e.g. "Add channels:history scope -> Reinstall to
    Workspace"). `details` carries provider-private diagnostics
    (granted scopes, account id, etc.) for logging only.
    """

    ok: bool
    message: str
    details: Mapping[str, str] = field(default_factory=dict)


EventRole = Literal["question_answer", "decision_pick", "message"]


@dataclass(frozen=True, slots=True)
class InboundEvent:
    """Provider-neutral inbound interaction.

    Emitted by the provider (push-side, see CommsProvider.start_inbound)
    and consumed by InboundConsumer.dispatch. The router decides where
    to write (inbox vs answer vs decision artefact) using the structured
    fields below — it MUST NOT parse any Slack-shaped strings.

    Fields:
      event_role     -- discriminator. "message" = thread reply text;
                        "question_answer" / "decision_pick" = button click.
      run_id         -- populated for button kinds (parsed by adapter from
                        button payload). None for plain messages; the router
                        resolves run via thread_ref -> routing index instead.
      qd_id          -- question/decision id, format "r<N>" (e.g. "r2").
                        None for messages.
      option_index   -- 0..3 (matches BUTTON_LETTERS A..D). None for messages.
      thread_ref     -- provider thread the event belongs to.
                        For Slack messages: provider_data["channel_id"] carries
                        the EVENT channel (NOT the route's bound channel);
                        cross-channel guard is enforced inside SlackProvider
                        before InboundEvent is constructed (see B3).
      message_ref    -- message that was posted/replied/clicked.
                        None only for the rare "reply to root without ts" case.
      user_id        -- provider-native user id (opaque to router).
      text           -- message body for event_role=="message"; None otherwise.
      received_at    -- ISO8601 UTC timestamp set by adapter at ingress.
    """

    event_role: EventRole
    run_id: str | None
    qd_id: str | None
    option_index: int | None
    thread_ref: ThreadRef
    message_ref: MessageRef | None
    user_id: str
    text: str | None
    received_at: str


class InboundConsumer(Protocol):
    """Push-side consumer the provider calls per normalized event.

    Lives on the router daemon side. The provider's internal worker
    thread invokes `consumer.dispatch(event)` synchronously per event;
    consumer is responsible for any synchronization on shared state
    (RoutingIndex snapshot container is already thread-safe; inbox/answer/decision
    writers serialise per-file via O_EXCL/atomic-rename).
    See CommsProvider.start_inbound for threading model + stop semantics.
    """

    def dispatch(self, event: InboundEvent) -> None:
        """Dispatch one normalized inbound event."""
        ...
