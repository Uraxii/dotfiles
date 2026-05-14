#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "slack-bolt>=1.18",
#     "filelock>=3.13",
# ]
# ///
"""pipeline_notify — one-shot Slack notification CLI.

Posts a message to the active session-bound Slack thread (if any).
Supports status/completion/friction-summary notifications AND
question/decision posts with button blocks.

Usage:
    pipeline_notify.py --run <id> --project <path> \\
        --kind {status|completion|friction-summary} \\
        --message "<one-line>"

    pipeline_notify.py --run <id> --run-dir <path> \\
        --kind question --qid q1

    pipeline_notify.py --run <id> --run-dir <path> \\
        --kind decision --did d1

Environment (auto-loaded from ~/.claude/pipeline/slack.env.local):
    SLACK_BOT_TOKEN
    CLAUDE_CODE_SESSION_ID   (inherited from Claude Code process)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_PIPELINE_DIR = Path(__file__).parent
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

from _slack_env import (  # noqa: E402
    atomic_write_text,
    default_env_path,
    load_env_file,
    validate_sid,
)
from session_slack import resolve_session_binding  # noqa: E402

try:
    from slack_bolt import App
except ImportError:
    sys.stderr.write(
        "slack_bolt missing. Install: pip install --user slack-bolt\n"
    )
    sys.exit(2)

try:
    from filelock import FileLock
except ImportError:
    sys.stderr.write(
        "filelock missing. Install: pip install --user filelock\n"
    )
    sys.exit(2)

log = logging.getLogger("pipeline_notify")

RUN_INDEX_DIR = Path("~/.claude/slack-router/run-index").expanduser()

KIND_EMOJI: dict[str, str] = {
    "status": ":information_source:",
    "completion": ":white_check_mark:",
    "friction-summary": ":mag:",
}

BUTTON_LETTERS = ("A", "B", "C", "D")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _project_hash(project_path: Path) -> str:
    return hashlib.sha1(str(project_path).encode()).hexdigest()[:8]


# ---------------------------------------------------------------------------
# Simple notification (existing behavior — status/completion/friction-summary)
# ---------------------------------------------------------------------------


def _build_text(run_id: str, kind: str, message: str) -> str:
    emoji = KIND_EMOJI.get(kind, ":speech_balloon:")
    return f"[{run_id}] {emoji} *{kind}:* {message}"


def notify_simple(run_id: str, kind: str, message: str) -> int:
    """Post simple notification. Returns 0 on success or silent no-op."""
    load_env_file(default_env_path())

    raw_sid = os.environ.get("CLAUDE_CODE_SESSION_ID", "").strip()
    if raw_sid:
        try:
            validate_sid(raw_sid)
        except ValueError as exc:
            sys.stderr.write(f"[pipeline_notify] invalid session id: {exc}\n")
            return 1

    binding = resolve_session_binding()
    if binding is None:
        log.debug("no active session binding; notification not posted (kind=%s run=%s)", kind, run_id)
        sys.stderr.write(
            f"[pipeline_notify] no binding; status not posted (run={run_id} kind={kind})\n"
        )
        return 0

    channel, thread_ts = binding
    bot_token = os.environ.get("SLACK_BOT_TOKEN", "")
    if not bot_token:
        sys.stderr.write(f"SLACK_BOT_TOKEN required. Set in {default_env_path()}\n")
        return 1

    app = App(token=bot_token)
    text = _build_text(run_id, kind, message)
    try:
        app.client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=text,
            unfurl_links=False,
            unfurl_media=False,
        )
        log.info("posted %s notification for run=%s", kind, run_id)
        if kind == "completion":
            _remove_run_index_entry(run_id)
    except Exception as exc:
        sys.stderr.write(f"Slack post failed: {exc}\n")
        return 1
    return 0


# ---------------------------------------------------------------------------
# Question / decision post
# ---------------------------------------------------------------------------


def _parse_question_file(
    run_dir: Path, qid: str
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Parse question-r<N>.md. Returns (frontmatter, [{key, title}])."""
    n = qid.lstrip("q")
    qfile = run_dir / f"question-r{n}.md"
    if not qfile.is_file():
        return {}, []

    text = qfile.read_text()
    fm: dict[str, Any] = {}
    body = text
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end > 0:
            current_list_key: str | None = None
            for line in text[4:end].splitlines():
                stripped = line.lstrip(" ")
                if current_list_key is not None and line.startswith("  - "):
                    cast_list = fm[current_list_key]
                    if isinstance(cast_list, list):
                        cast_list.append(line[4:].strip())
                    continue
                current_list_key = None
                if ":" not in stripped or line.startswith(" "):
                    continue
                k, _, v = stripped.partition(":")
                k = k.strip()
                v = v.strip()
                if v == "":
                    fm[k] = []
                    current_list_key = k
                else:
                    fm[k] = v
            body = text[end + 5:]

    options: list[dict[str, str]] = []
    for line in body.splitlines():
        if line.startswith("## Option ") and ":" in line:
            rest = line[len("## Option "):]
            key_part, _, title_part = rest.partition(":")
            if key_part.strip():
                options.append({"key": key_part.strip(), "title": title_part.strip()})
    return fm, options


def _parse_awaiting_file(
    run_dir: Path, did: str
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Parse awaiting-decision-r<N>.md + options-r<N>.md."""
    n = did.lstrip("d")
    awaiting = run_dir / f"awaiting-decision-r{n}.md"
    fm: dict[str, Any] = {}
    if awaiting.is_file():
        for line in awaiting.read_text().splitlines():
            if ":" in line and not line.startswith(" "):
                k, _, v = line.partition(":")
                fm[k.strip()] = v.strip()

    options_file = run_dir / f"options-r{n}.md"
    options: list[dict[str, str]] = []
    if options_file.is_file():
        for line in options_file.read_text().splitlines():
            if line.startswith("## Option ") and ":" in line:
                rest = line[len("## Option "):]
                key_part, _, title_part = rest.partition(":")
                if key_part.strip():
                    options.append({"key": key_part.strip(), "title": title_part.strip()})
    return fm, options


def _write_run_index_entry(run_id: str, run_dir: Path, project_path: Path) -> None:
    RUN_INDEX_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    entry_path = RUN_INDEX_DIR / f"{run_id}.json"
    phash = _project_hash(project_path)
    data = {
        "run_dir": str(run_dir),
        "project_path": str(project_path),
        "project_path_hash": phash,
        "updated_at": _now_iso(),
    }
    atomic_write_text(entry_path, json.dumps(data, indent=2), mode=0o600)


def _remove_run_index_entry(run_id: str) -> None:
    entry_path = RUN_INDEX_DIR / f"{run_id}.json"
    try:
        entry_path.unlink(missing_ok=True)
    except OSError as exc:
        log.warning("failed to remove run-index entry for %s: %s", run_id, exc)


def _upload_attachments(
    app: App, channel: str, thread_ts: str, attachments: list[str]
) -> list[tuple[str, str]]:
    """Upload attachment files. Returns [(permalink, filename)]."""
    links: list[tuple[str, str]] = []
    for attach_path in attachments:
        path = Path(attach_path).expanduser()
        if not path.is_file():
            log.warning("attachment missing: %s", path)
            continue
        last_err: Exception | None = None
        resp = None
        for attempt in (1, 2):
            try:
                resp = app.client.files_upload_v2(
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


def _build_question_blocks(
    run_id: str,
    qid: str,
    header: str,
    prompt: str,
    options: list[dict[str, str]],
    phash8: str,
    attachment_links: list[tuple[str, str]],
) -> list[dict[str, Any]]:
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
                "text": f"*{opt['key']}*: {opt['title']}",
            },
        })
    blocks.append({
        "type": "actions",
        "block_id": f"qpick_{qid}",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": opt["key"]},
                "value": f"{phash8}|{run_id}|{qid}|{opt['key']}",
                "action_id": f"question_pick_{opt['key']}",
            }
            for opt in options
        ],
    })
    return blocks


def _build_decision_blocks(
    run_id: str,
    did: str,
    topic: str,
    options: list[dict[str, str]],
    phash8: str,
) -> list[dict[str, Any]]:
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
        tradeoff = opt.get("tradeoff", "")
        opt_text = f"*Option {opt['key']}*: {opt['title']}"
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
                "text": {"type": "plain_text", "text": f"Option {opt['key']}"},
                "value": f"{phash8}|{run_id}|{did}|{opt['key']}",
                "action_id": f"decision_pick_{opt['key']}",
            }
            for opt in options
        ],
    })
    return blocks


def _read_slack_context(run_dir: Path) -> dict[str, Any]:
    ctx_path = run_dir / ".slack-context.json"
    if not ctx_path.is_file():
        return {}
    try:
        # type: ignore[return-value] — json.loads returns Any; caller validates dict shape downstream
        return json.loads(ctx_path.read_text())  # type: ignore[return-value]
    except (OSError, json.JSONDecodeError):
        return {}


def _update_slack_context(run_dir: Path, updates: dict[str, Any]) -> None:
    """Read-modify-write .slack-context.json under file lock."""
    ctx_path = run_dir / ".slack-context.json"
    lock_path = run_dir / ".slack-context.json.lock"
    with FileLock(str(lock_path)):
        existing: dict[str, Any] = {}
        if ctx_path.is_file():
            try:
                existing = json.loads(ctx_path.read_text())
            except (OSError, json.JSONDecodeError):
                pass
        existing.update(updates)
        atomic_write_text(ctx_path, json.dumps(existing, indent=2), mode=0o600)


def _recover_message_ts(
    app: App, channel: str, thread_ts: str, client_msg_id: str
) -> str | None:
    """Scan conversations.history for a bot message matching client_msg_id.

    Design §8.4 primary recovery defense: after a crash between post and
    context update, this locates the already-posted message so we can
    write its ts without re-posting (avoiding duplicates).
    Returns the message_ts string if found, else None.
    """
    HISTORY_LIMIT = 20  # scan most-recent messages in thread
    try:
        resp = app.client.conversations_replies(
            channel=channel,
            ts=thread_ts,
            limit=HISTORY_LIMIT,
        )
    except Exception as exc:
        log.warning("conversations_replies failed during recovery: %s", exc)
        return None

    messages = resp.get("messages") or []
    for msg in messages:
        metadata = msg.get("metadata") or {}
        payload = metadata.get("event_payload") or {}
        if payload.get("client_msg_id") == client_msg_id:
            log.info(
                "recovery: found existing post ts=%s for client_msg_id=%s",
                msg.get("ts"), client_msg_id,
            )
            return str(msg.get("ts", ""))
    return None


def notify_question(run_id: str, run_dir: Path, qid: str) -> int:
    """Post question with buttons to bound thread. Returns 0 on success."""
    load_env_file(default_env_path())

    binding = resolve_session_binding()
    if binding is None:
        sys.stderr.write(
            f"[pipeline_notify] no binding; question not posted (run={run_id} qid={qid})\n"
        )
        return 1

    channel, thread_ts = binding
    bot_token = os.environ.get("SLACK_BOT_TOKEN", "")
    if not bot_token:
        sys.stderr.write(f"SLACK_BOT_TOKEN required. Set in {default_env_path()}\n")
        return 1

    ctx = _read_slack_context(run_dir)
    if ctx.get("message_ts"):
        log.info("question already posted (idempotent): run=%s qid=%s", run_id, qid)
        return 0

    fm, options = _parse_question_file(run_dir, qid)
    if not options:
        sys.stderr.write(f"no options parsed from question-r*.md for qid={qid}\n")
        return 1

    header = str(fm.get("header", ""))
    prompt = str(fm.get("prompt", f"Question {qid}"))
    attachments = fm.get("attachments") or []
    project_path = Path(ctx.get("project_path") or str(run_dir.parent.parent.parent))
    phash8 = _project_hash(project_path)

    lock_path = run_dir / ".slack-posting.lock"
    ctx_lock_path = run_dir / ".slack-context.json.lock"
    client_msg_id = uuid.uuid4().hex

    with FileLock(str(ctx_lock_path)):
        ctx_fresh = _read_slack_context(run_dir)
        if ctx_fresh.get("message_ts"):
            log.info("question already posted (idempotent, inner): run=%s qid=%s", run_id, qid)
            return 0

        app = App(token=bot_token)

        # Recover from prior partial crash (design §8.4 primary defense).
        if lock_path.is_file():
            recovered_id = client_msg_id
            try:
                lock_data = json.loads(lock_path.read_text())
                recovered_id = lock_data.get("client_msg_id", client_msg_id)
            except (OSError, json.JSONDecodeError):
                pass
            recovered_ts = _recover_message_ts(app, channel, thread_ts, recovered_id)
            if recovered_ts:
                # Post landed; context update did not. Finish the write.
                perms: list[list[str]] = []
                ctx_updates = {
                    "channel": channel,
                    "thread_ts": thread_ts,
                    "message_ts": recovered_ts,
                    "attachment_permalinks": perms,
                }
                ctx_fresh.update(ctx_updates)
                atomic_write_text(
                    run_dir / ".slack-context.json",
                    json.dumps(ctx_fresh, indent=2),
                    mode=0o600,
                )
                try:
                    lock_path.unlink(missing_ok=True)
                except OSError:
                    pass
                log.info(
                    "recovered question %s for run=%s ts=%s",
                    qid, run_id, recovered_ts,
                )
                return 0
            # Post not found → treat as failed; retry with fresh id.
            log.info(
                "no existing post found for client_msg_id=%s; retrying", recovered_id
            )
            client_msg_id = uuid.uuid4().hex
        else:
            atomic_write_text(
                lock_path,
                json.dumps({"client_msg_id": client_msg_id, "started_at": _now_iso()}),
                mode=0o600,
            )

        _write_run_index_entry(run_id, run_dir, project_path)

        attachment_links: list[tuple[str, str]] = []
        if isinstance(attachments, list):
            attachment_links = _upload_attachments(app, channel, thread_ts, attachments)

        blocks = _build_question_blocks(
            run_id, qid, header, prompt, options, phash8, attachment_links
        )

        try:
            resp = app.client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=f"Question {qid}: {prompt[:80]}",
                blocks=blocks,
                metadata={
                    "event_type": "question",
                    "event_payload": {"client_msg_id": client_msg_id},
                },
                unfurl_links=False,
                unfurl_media=False,
            )
        except Exception as exc:
            sys.stderr.write(f"Slack post failed: {exc}\n")
            return 1

        posted_ts: str = resp["ts"]
        perms_q = [[pl, nm] for pl, nm in attachment_links]
        ctx_updates_q = {
            "channel": channel,
            "thread_ts": thread_ts,
            "message_ts": posted_ts,
            "attachment_permalinks": perms_q,
        }
        ctx_fresh.update(ctx_updates_q)
        atomic_write_text(
            run_dir / ".slack-context.json",
            json.dumps(ctx_fresh, indent=2),
            mode=0o600,
        )
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass

    log.info("posted question %s for run=%s ts=%s", qid, run_id, posted_ts)
    return 0


def notify_decision(run_id: str, run_dir: Path, did: str) -> int:
    """Post decision with buttons to bound thread. Returns 0 on success."""
    load_env_file(default_env_path())

    binding = resolve_session_binding()
    if binding is None:
        sys.stderr.write(
            f"[pipeline_notify] no binding; decision not posted (run={run_id} did={did})\n"
        )
        return 1

    channel, thread_ts = binding
    bot_token = os.environ.get("SLACK_BOT_TOKEN", "")
    if not bot_token:
        sys.stderr.write(f"SLACK_BOT_TOKEN required. Set in {default_env_path()}\n")
        return 1

    ctx = _read_slack_context(run_dir)
    if ctx.get("message_ts"):
        log.info("decision already posted (idempotent): run=%s did=%s", run_id, did)
        return 0

    fm, options = _parse_awaiting_file(run_dir, did)
    if not options:
        sys.stderr.write(f"no options for did={did} in {run_dir}\n")
        return 1

    topic = str(fm.get("topic", f"Decision {did}"))
    project_path = run_dir.parent.parent.parent
    phash8 = _project_hash(project_path)

    lock_path = run_dir / ".slack-posting.lock"
    ctx_lock_path = run_dir / ".slack-context.json.lock"
    client_msg_id = uuid.uuid4().hex

    with FileLock(str(ctx_lock_path)):
        ctx_fresh = _read_slack_context(run_dir)
        if ctx_fresh.get("message_ts"):
            log.info(
                "decision already posted (idempotent, inner): run=%s did=%s",
                run_id, did,
            )
            return 0

        app = App(token=bot_token)

        # Recover from prior partial crash (same pattern as notify_question).
        if lock_path.is_file():
            recovered_id = client_msg_id
            try:
                lock_data = json.loads(lock_path.read_text())
                recovered_id = lock_data.get("client_msg_id", client_msg_id)
            except (OSError, json.JSONDecodeError):
                pass
            recovered_ts = _recover_message_ts(app, channel, thread_ts, recovered_id)
            if recovered_ts:
                ctx_updates = {
                    "channel": channel,
                    "thread_ts": thread_ts,
                    "message_ts": recovered_ts,
                }
                ctx_fresh.update(ctx_updates)
                atomic_write_text(
                    run_dir / ".slack-context.json",
                    json.dumps(ctx_fresh, indent=2),
                    mode=0o600,
                )
                try:
                    lock_path.unlink(missing_ok=True)
                except OSError:
                    pass
                log.info(
                    "recovered decision %s for run=%s ts=%s",
                    did, run_id, recovered_ts,
                )
                return 0
            log.info(
                "no existing decision post found for client_msg_id=%s; retrying",
                recovered_id,
            )
            client_msg_id = uuid.uuid4().hex
        else:
            atomic_write_text(
                lock_path,
                json.dumps({"client_msg_id": client_msg_id, "started_at": _now_iso()}),
                mode=0o600,
            )

        _write_run_index_entry(run_id, run_dir, project_path)

        blocks = _build_decision_blocks(run_id, did, topic, options, phash8)

        try:
            resp = app.client.chat_postMessage(
                channel=channel,
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
        except Exception as exc:
            sys.stderr.write(f"Slack post failed: {exc}\n")
            return 1

        posted_ts: str = resp["ts"]
        ctx_updates_d = {
            "channel": channel,
            "thread_ts": thread_ts,
            "message_ts": posted_ts,
        }
        ctx_fresh.update(ctx_updates_d)
        atomic_write_text(
            run_dir / ".slack-context.json",
            json.dumps(ctx_fresh, indent=2),
            mode=0o600,
        )
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass

    log.info("posted decision %s for run=%s ts=%s", did, run_id, posted_ts)
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pipeline_notify.py",
        description=(
            "Post status/completion/friction-summary OR question/decision "
            "to the active session-bound Slack thread."
        ),
    )
    parser.add_argument("--run", required=True, help="Pipeline run artifact-id")
    parser.add_argument(
        "--project",
        default=str(Path.cwd()),
        help="Project root (default: cwd)",
    )
    parser.add_argument(
        "--run-dir",
        default=None,
        help="Explicit run dir path (required for --kind question/decision)",
    )
    parser.add_argument(
        "--kind",
        required=True,
        choices=["status", "completion", "friction-summary", "question", "decision"],
        help="Notification kind",
    )
    parser.add_argument(
        "--message",
        default=None,
        help="One-line notification body (required for status/completion/friction-summary)",
    )
    parser.add_argument("--qid", default=None, help="Question id (required for --kind question)")
    parser.add_argument("--did", default=None, help="Decision id (required for --kind decision)")
    parser.add_argument("--log-level", default="WARNING")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.kind in ("status", "completion", "friction-summary"):
        if not args.message:
            sys.stderr.write("--message required for status/completion/friction-summary\n")
            sys.exit(1)
        sys.exit(notify_simple(args.run, args.kind, args.message))

    if args.kind == "question":
        if not args.qid:
            sys.stderr.write("--qid required for --kind question\n")
            sys.exit(1)
        run_dir = Path(args.run_dir).expanduser().resolve() if args.run_dir else (
            Path(args.project).expanduser().resolve() / ".pipeline" / "runs" / args.run
        )
        sys.exit(notify_question(args.run, run_dir, args.qid))

    if args.kind == "decision":
        if not args.did:
            sys.stderr.write("--did required for --kind decision\n")
            sys.exit(1)
        run_dir = Path(args.run_dir).expanduser().resolve() if args.run_dir else (
            Path(args.project).expanduser().resolve() / ".pipeline" / "runs" / args.run
        )
        sys.exit(notify_decision(args.run, run_dir, args.did))

    sys.stderr.write(f"unknown kind: {args.kind}\n")
    sys.exit(1)


if __name__ == "__main__":
    main()
