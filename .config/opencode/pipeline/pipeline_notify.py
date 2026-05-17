#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "slack-bolt>=1.18",
#     "filelock>=3.13",
# ]
# ///
"""pipeline_notify — one-shot comms notification CLI.

Posts a message to the active session-bound thread (if any).
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

Environment (auto-loaded from ~/.config/opencode/pipeline/slack.env.local):
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

from comms.env import (  # noqa: E402
    atomic_write_text,
    default_env_path,
    load_env_file,
    validate_sid,
)
from comms.registry import get_registry  # noqa: E402
from comms.session import resolve_session_thread_ref  # noqa: E402
from comms.types import OptionSpec  # noqa: E402

try:
    from filelock import FileLock
except ImportError:
    sys.stderr.write(
        "filelock missing. Install: pip install --user filelock\n"
    )
    sys.exit(2)

log = logging.getLogger("pipeline_notify")

RUN_INDEX_DIR = Path("~/.config/opencode/comms-router/run-index").expanduser()

KIND_EMOJI: dict[str, str] = {
    "status": ":information_source:",
    "completion": ":white_check_mark:",
    "friction-summary": ":mag:",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _project_hash(project_path: Path) -> str:
    return hashlib.sha1(str(project_path).encode()).hexdigest()[:8]


# ---------------------------------------------------------------------------
# Simple notification
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

    thread_ref = resolve_session_thread_ref()
    if thread_ref is None:
        log.debug(
            "no active session binding; notification not posted (kind=%s run=%s)",
            kind, run_id,
        )
        sys.stderr.write(
            f"[pipeline_notify] no binding; status not posted (run={run_id} kind={kind})\n"
        )
        return 0

    project_path = Path.cwd()
    provider = get_registry().active_provider(project_path)
    text = _build_text(run_id, kind, message)
    try:
        provider.post_simple(thread_ref, kind, message)
        log.info("posted %s notification for run=%s", kind, run_id)
        if kind == "completion":
            _remove_run_index_entry(run_id)
    except Exception as exc:
        sys.stderr.write(f"Comms post failed: {exc}\n")
        return 1
    return 0


# ---------------------------------------------------------------------------
# Question / decision post helpers
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


def _read_comms_context(run_dir: Path) -> dict[str, Any]:
    ctx_path = run_dir / ".comms-context.json"
    if not ctx_path.is_file():
        return {}
    try:
        return json.loads(ctx_path.read_text())  # type: ignore[return-value]
    except (OSError, json.JSONDecodeError):
        return {}


def _update_comms_context(run_dir: Path, updates: dict[str, Any]) -> None:
    """Read-modify-write .comms-context.json under file lock."""
    ctx_path = run_dir / ".comms-context.json"
    lock_path = run_dir / ".comms-context.json.lock"
    with FileLock(str(lock_path)):
        existing: dict[str, Any] = {}
        if ctx_path.is_file():
            try:
                existing = json.loads(ctx_path.read_text())
            except (OSError, json.JSONDecodeError):
                pass
        existing.update(updates)
        atomic_write_text(ctx_path, json.dumps(existing, indent=2), mode=0o600)


# ---------------------------------------------------------------------------
# Question post
# ---------------------------------------------------------------------------


def notify_question(run_id: str, run_dir: Path, qid: str) -> int:
    """Post question with buttons to bound thread. Returns 0 on success."""
    load_env_file(default_env_path())

    thread_ref = resolve_session_thread_ref()
    if thread_ref is None:
        sys.stderr.write(
            f"[pipeline_notify] no binding; question not posted (run={run_id} qid={qid})\n"
        )
        return 1

    ctx = _read_comms_context(run_dir)
    if ctx.get("message_ts"):
        log.info("question already posted (idempotent): run=%s qid=%s", run_id, qid)
        return 0

    fm, raw_options = _parse_question_file(run_dir, qid)
    if not raw_options:
        sys.stderr.write(f"no options parsed from question-r*.md for qid={qid}\n")
        return 1

    header = str(fm.get("header", ""))
    prompt = str(fm.get("prompt", f"Question {qid}"))
    attachments_raw = fm.get("attachments") or []
    project_path = Path(ctx.get("project_path") or str(run_dir.parent.parent.parent))
    phash8 = _project_hash(project_path)

    options = [OptionSpec(key=o["key"], title=o["title"]) for o in raw_options]
    attachments = [Path(a).expanduser() for a in attachments_raw if isinstance(a, str)]

    lock_path = run_dir / ".comms-posting.lock"
    ctx_lock_path = run_dir / ".comms-context.json.lock"
    client_msg_id = uuid.uuid4().hex

    project_root = project_path
    provider = get_registry().active_provider(project_root)

    with FileLock(str(ctx_lock_path)):
        ctx_fresh = _read_comms_context(run_dir)
        if ctx_fresh.get("message_ts"):
            log.info(
                "question already posted (idempotent, inner): run=%s qid=%s",
                run_id, qid,
            )
            return 0

        # Recover from prior partial crash.
        if lock_path.is_file():
            recovered_id = client_msg_id
            try:
                lock_data = json.loads(lock_path.read_text())
                recovered_id = lock_data.get("client_msg_id", client_msg_id)
            except (OSError, json.JSONDecodeError):
                pass
            recovered_ref = provider.recover_message_ts(thread_ref, recovered_id)
            if recovered_ref is not None:
                ctx_updates = {
                    "channel": thread_ref.provider_data.get("channel_id"),
                    "thread_ts": thread_ref.provider_data.get("thread_ts"),
                    "message_ts": recovered_ref.provider_data.get("message_ts"),
                    "attachment_permalinks": [],
                }
                ctx_fresh.update(ctx_updates)
                atomic_write_text(
                    run_dir / ".comms-context.json",
                    json.dumps(ctx_fresh, indent=2),
                    mode=0o600,
                )
                try:
                    lock_path.unlink(missing_ok=True)
                except OSError:
                    pass
                log.info("recovered question %s for run=%s", qid, run_id)
                return 0
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

        # Use provider-specific full-fidelity post with routing ids.
        try:
            if hasattr(provider, "post_question_with_ids"):
                post = provider.post_question_with_ids(  # type: ignore[union-attr]
                    thread_ref, run_id, qid, prompt, header, options, phash8,
                    client_msg_id, attachments,
                )
            else:
                post = provider.post_question(
                    thread_ref, prompt, options,
                    client_msg_id=client_msg_id,
                    header=header,
                    attachments=attachments,
                )
        except Exception as exc:
            sys.stderr.write(f"Comms post failed: {exc}\n")
            return 1

        posted_ts = post.ref.provider_data.get("message_ts", "")
        ctx_updates_q = {
            "channel": thread_ref.provider_data.get("channel_id"),
            "thread_ts": thread_ref.provider_data.get("thread_ts"),
            "message_ts": posted_ts,
            "attachment_permalinks": [],
        }
        ctx_fresh.update(ctx_updates_q)
        atomic_write_text(
            run_dir / ".comms-context.json",
            json.dumps(ctx_fresh, indent=2),
            mode=0o600,
        )
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass

    log.info("posted question %s for run=%s ts=%s", qid, run_id, posted_ts)
    return 0


# ---------------------------------------------------------------------------
# Decision post
# ---------------------------------------------------------------------------


def notify_decision(run_id: str, run_dir: Path, did: str) -> int:
    """Post decision with buttons to bound thread. Returns 0 on success."""
    load_env_file(default_env_path())

    thread_ref = resolve_session_thread_ref()
    if thread_ref is None:
        sys.stderr.write(
            f"[pipeline_notify] no binding; decision not posted (run={run_id} did={did})\n"
        )
        return 1

    ctx = _read_comms_context(run_dir)
    if ctx.get("message_ts"):
        log.info("decision already posted (idempotent): run=%s did=%s", run_id, did)
        return 0

    fm, raw_options = _parse_awaiting_file(run_dir, did)
    if not raw_options:
        sys.stderr.write(f"no options for did={did} in {run_dir}\n")
        return 1

    topic = str(fm.get("topic", f"Decision {did}"))
    project_path = run_dir.parent.parent.parent
    phash8 = _project_hash(project_path)

    options = [OptionSpec(key=o["key"], title=o["title"], tradeoff=o.get("tradeoff")) for o in raw_options]

    lock_path = run_dir / ".comms-posting.lock"
    ctx_lock_path = run_dir / ".comms-context.json.lock"
    client_msg_id = uuid.uuid4().hex

    provider = get_registry().active_provider(project_path)

    with FileLock(str(ctx_lock_path)):
        ctx_fresh = _read_comms_context(run_dir)
        if ctx_fresh.get("message_ts"):
            log.info(
                "decision already posted (idempotent, inner): run=%s did=%s",
                run_id, did,
            )
            return 0

        # Recover from prior partial crash.
        if lock_path.is_file():
            recovered_id = client_msg_id
            try:
                lock_data = json.loads(lock_path.read_text())
                recovered_id = lock_data.get("client_msg_id", client_msg_id)
            except (OSError, json.JSONDecodeError):
                pass
            recovered_ref = provider.recover_message_ts(thread_ref, recovered_id)
            if recovered_ref is not None:
                ctx_updates = {
                    "channel": thread_ref.provider_data.get("channel_id"),
                    "thread_ts": thread_ref.provider_data.get("thread_ts"),
                    "message_ts": recovered_ref.provider_data.get("message_ts"),
                }
                ctx_fresh.update(ctx_updates)
                atomic_write_text(
                    run_dir / ".comms-context.json",
                    json.dumps(ctx_fresh, indent=2),
                    mode=0o600,
                )
                try:
                    lock_path.unlink(missing_ok=True)
                except OSError:
                    pass
                log.info("recovered decision %s for run=%s", did, run_id)
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

        try:
            if hasattr(provider, "post_decision_with_ids"):
                post = provider.post_decision_with_ids(  # type: ignore[union-attr]
                    thread_ref, run_id, did, topic, options, phash8, client_msg_id,
                )
            else:
                post = provider.post_decision(
                    thread_ref, topic, options, client_msg_id=client_msg_id,
                )
        except Exception as exc:
            sys.stderr.write(f"Comms post failed: {exc}\n")
            return 1

        posted_ts = post.ref.provider_data.get("message_ts", "")
        ctx_updates_d = {
            "channel": thread_ref.provider_data.get("channel_id"),
            "thread_ts": thread_ref.provider_data.get("thread_ts"),
            "message_ts": posted_ts,
        }
        ctx_fresh.update(ctx_updates_d)
        atomic_write_text(
            run_dir / ".comms-context.json",
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
# CLI (arg surface MUST remain identical — R13/R14 enforce)
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
