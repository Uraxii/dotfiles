"""Slack block builders for question/decision posts.

Owns BUTTON_LETTERS constant (C6 consolidation target). This is the sole
module that encodes the Slack pipe-encoded action_id format
`<phash8>|<run-id>|<qd-id>|<choice>`. Both the encoding producer
(post_question/post_decision) and the inbound decoder (inbound.py) live
in comms/slack/ so the router never sees Slack-shaped strings.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..types import OptionSpec

__all__ = [
    "BUTTON_LETTERS",
    "build_question_blocks",
    "build_decision_blocks",
    "encode_button_value",
    "decode_button_payload",
]

# Canonical button letter ordering. Index = option_index in InboundEvent.
BUTTON_LETTERS: tuple[str, ...] = ("A", "B", "C", "D")


def encode_button_value(
    phash8: str, run_id: str, qd_id: str, choice: str
) -> str:
    """Encode a Slack button value as the pipe-separated payload string."""
    return f"{phash8}|{run_id}|{qd_id}|{choice}"


def decode_button_payload(
    value: str,
) -> tuple[str, str, str, str] | None:
    """Decode pipe-separated button payload. Returns (phash8, run_id, qd_id, choice) or None."""
    parts = value.split("|", 3)
    if len(parts) != 4:
        return None
    return parts[0], parts[1], parts[2], parts[3]


def build_question_blocks(
    run_id: str,
    qid: str,
    header: str,
    prompt: str,
    options: Sequence[OptionSpec],
    phash8: str,
    attachment_links: list[tuple[str, str]],
) -> list[dict[str, Any]]:
    """Build Slack blocks for a question post with option buttons."""
    header_text = f"[{header}] " if header else ""
    blocks: list[dict[str, Any]] = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{header_text}{qid}*\n{prompt}",
            },
        },
    ]
    if attachment_links:
        link_lines = [f"• <{pl}|{nm}>" for pl, nm in attachment_links if pl and nm]
        if link_lines:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Attachments:*\n" + "\n".join(link_lines),
                },
            })
    for opt in options:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{opt.key}*: {opt.title}",
            },
        })
    blocks.append({
        "type": "actions",
        "block_id": f"qpick_{qid}",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": opt.key},
                "value": encode_button_value(phash8, run_id, qid, opt.key),
                "action_id": f"question_pick_{opt.key}",
            }
            for opt in options
        ],
    })
    return blocks


def build_decision_blocks(
    run_id: str,
    did: str,
    topic: str,
    options: Sequence[OptionSpec],
    phash8: str,
) -> list[dict[str, Any]]:
    """Build Slack blocks for a decision post with option buttons."""
    blocks: list[dict[str, Any]] = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Decision {did}*: {topic}",
            },
        },
    ]
    for opt in options:
        tradeoff = opt.tradeoff or ""
        opt_text = f"*Option {opt.key}*: {opt.title}"
        if tradeoff:
            opt_text += f"\n_{tradeoff}_"
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": opt_text},
        })
    blocks.append({
        "type": "actions",
        "block_id": f"pick_{did}",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": f"Option {opt.key}"},
                "value": encode_button_value(phash8, run_id, did, opt.key),
                "action_id": f"decision_pick_{opt.key}",
            }
            for opt in options
        ],
    })
    return blocks
