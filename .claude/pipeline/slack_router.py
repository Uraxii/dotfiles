#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "slack-bolt>=1.18",
# ]
# ///
"""slack_router — host-bound Slack Socket Mode router daemon.

Single process per host. Routes inbound Slack thread replies to per-session
inbox dirs based on a binding table built from
~/.claude/sessions/*/slack.json.

Usage (detached, via session_bind.py activate — do not run directly):
    uv run --script ~/.claude/pipeline/slack_router.py

Environment (auto-loaded from ~/.claude/pipeline/slack.env.local):
    SLACK_BOT_TOKEN           xoxb-...
    SLACK_APP_TOKEN           xapp-...
    SLACK_ALLOWED_USERS       comma-separated Slack user IDs (empty = any)
    SLACK_ROUTER_IDLE_TIMEOUT seconds before idle exit (default 1800 = 30min)

State (host-level, not stowed):
    ~/.claude/slack-router/router.pid     — held flock + PID number
    ~/.claude/slack-router/router.log     — daemon log
    ~/.claude/slack-router/unrouted/      — unmatched events (audit)
    ~/.claude/slack-router/run-index/     — per-run context for button routing
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import logging
import os
import re
import signal
import sys
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any

_PIPELINE_DIR = Path(__file__).parent
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

from _slack_env import atomic_write_text, default_env_path, load_env_file  # noqa: E402
from session_slack import all_active_bindings, inbox_dir as _inbox_dir  # noqa: E402

try:
    from slack_bolt import App
    from slack_bolt.adapter.socket_mode import SocketModeHandler
except ImportError:
    sys.stderr.write("slack_bolt missing. Install: pip install --user slack-bolt\n")
    sys.exit(2)

__all__ = ["main"]

log = logging.getLogger("slack_router")

# ---------------------------------------------------------------------------
# Top-level constants
# ---------------------------------------------------------------------------

ROUTER_ROOT = Path("~/.claude/slack-router").expanduser()
PID_PATH = ROUTER_ROOT / "router.pid"
LOG_PATH = ROUTER_ROOT / "router.log"
UNROUTED_DIR = ROUTER_ROOT / "unrouted"
RUN_INDEX_DIR = ROUTER_ROOT / "run-index"

POLL_INTERVAL_S = 3.0
IDLE_TIMEOUT_S = int(os.environ.get("SLACK_ROUTER_IDLE_TIMEOUT", "1800"))
RUN_INDEX_MAX_AGE_S = 14 * 86400
BUTTON_LETTERS = ("A", "B", "C", "D")

ORPHAN_TMP_MAX_AGE_S = 60

# Regex guards for button-payload fields (H3).
_RUN_ID_RE = re.compile(r"^[a-z]+(?:-[a-z]+){2}-[a-f0-9]{6}$")
_QD_ID_RE = re.compile(r"^[qd][0-9]{1,4}$")


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Route:
    """Active binding for one session: maps thread_ts → inbox dir."""

    sid: str
    channel_id: str
    thread_ts: str
    inbox_dir: Path


@dataclass(frozen=True, slots=True)
class RoutingSnapshot:
    """Immutable point-in-time view of all active session routes."""

    by_thread: Mapping[str, Route]
    by_sid: Mapping[str, Route]
    fingerprint: str


@dataclass(frozen=True, slots=True)
class SlackContext:
    """Per-run Slack context written to .slack-context.json by pipeline_notify."""

    project_path: Path
    project_path_hash: str
    run_id: str
    channel: str
    thread_ts: str
    qid: str | None
    did: str | None
    options: tuple[tuple[str, str], ...]
    message_ts: str | None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_yaml_scalar(value: str) -> str:
    """Escape newlines and colons for inline YAML scalar values (C1)."""
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")


def _project_hash(project_path_str: str) -> str:
    return hashlib.sha1(project_path_str.encode()).hexdigest()[:8]


def _cleanup_orphan_tmps(inbox: Path) -> None:
    if not inbox.is_dir():
        return
    now = time.time()
    for tmp in inbox.glob("*.tmp"):
        try:
            if now - tmp.stat().st_mtime > ORPHAN_TMP_MAX_AGE_S:
                tmp.unlink(missing_ok=True)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Inbox / unrouted writers
# ---------------------------------------------------------------------------


def _write_inbox_file(inbox: Path, event: dict[str, Any]) -> bool:
    """Write inbox/<msg_ts>.json atomically. Returns True if written."""
    message_ts: str = event.get("ts", "")
    if not message_ts:
        return False
    inbox.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = inbox / f"{message_ts}.json"
    if target.exists():
        return False
    thread_ts: str = event.get("thread_ts", "")
    sid = inbox.parent.name
    payload = {
        "session_id": sid,
        "thread_ts": thread_ts,
        "message_ts": message_ts,
        "user_id": event.get("user", ""),
        "text": event.get("text", ""),
        "received_at": _now_iso(),
    }
    try:
        atomic_write_text(target, json.dumps(payload, indent=2), mode=0o600)
        log.info("inbox: wrote %s", target)
        return True
    except OSError as exc:
        if exc.errno == 28:  # ENOSPC
            log.error(
                "dropped inbox write: ENOSPC target=%s sid=%s",
                target, sid,
                extra={"event": "inbox_drop_enospc", "target": str(target), "sid": sid},
            )
        else:
            log.error("inbox write failed for %s: %s", target, exc)
        return False


def _write_unrouted_file(event: dict[str, Any]) -> None:
    message_ts: str = event.get("ts", "")
    if not message_ts:
        return
    UNROUTED_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = UNROUTED_DIR / f"{message_ts}.json"
    if target.exists():
        return
    payload = {
        "session_id": None,
        "thread_ts": event.get("thread_ts", ""),
        "message_ts": message_ts,
        "user_id": event.get("user", ""),
        "text": event.get("text", ""),
        "received_at": _now_iso(),
        "event_channel": event.get("channel", ""),
    }
    try:
        atomic_write_text(target, json.dumps(payload, indent=2), mode=0o600)
        log.debug("unrouted: wrote %s", target)
    except OSError as exc:
        log.error("unrouted write failed for %s: %s", target, exc)


# ---------------------------------------------------------------------------
# Run-index helpers
# ---------------------------------------------------------------------------


def _write_run_index_entry(run_id: str, run_dir: Path, project_path: Path) -> None:
    RUN_INDEX_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    entry_path = RUN_INDEX_DIR / f"{run_id}.json"
    phash = _project_hash(str(project_path))
    data = {
        "run_dir": str(run_dir),
        "project_path": str(project_path),
        "project_path_hash": phash,
        "updated_at": _now_iso(),
    }
    atomic_write_text(entry_path, json.dumps(data, indent=2), mode=0o600)


def _gc_run_index() -> int:
    """Prune stale run-index entries and old unrouted files. Returns count pruned."""
    now = time.time()
    pruned = 0

    if RUN_INDEX_DIR.is_dir():
        for entry_path in RUN_INDEX_DIR.glob("*.json"):
            try:
                data = json.loads(entry_path.read_text())
                run_dir = Path(data["run_dir"])
                if not run_dir.is_dir():
                    entry_path.unlink(missing_ok=True)
                    pruned += 1
                    continue
                if (now - entry_path.stat().st_mtime) > RUN_INDEX_MAX_AGE_S:
                    entry_path.unlink(missing_ok=True)
                    pruned += 1
            except (OSError, json.JSONDecodeError, KeyError) as exc:
                log.warning("gc_run_index: error processing %s: %s", entry_path, exc)

    if UNROUTED_DIR.is_dir():
        for unrouted_path in UNROUTED_DIR.glob("*.json"):
            try:
                if (now - unrouted_path.stat().st_mtime) > RUN_INDEX_MAX_AGE_S:
                    unrouted_path.unlink(missing_ok=True)
                    pruned += 1
            except OSError as exc:
                log.warning("gc_unrouted: error processing %s: %s", unrouted_path, exc)

    return pruned


def _resolve_route_dir_from_value(
    value: str,
) -> tuple[Path, str] | tuple[None, str]:
    """Parse <phash8>|<run-id>|<qd-id>|<choice>, validate, return (run_dir, qd_id).

    On failure returns ``(None, reason)`` where ``reason`` is a short
    human-readable string the caller can surface to the clicking user via
    ``chat_postEphemeral``. Reasons:

    - ``malformed``      — value did not split into 4 fields
    - ``run_id_format``  — run-id didn't match artifact-slug regex
    - ``qd_id_format``   — qd-id didn't match q/d-prefix regex
    - ``index_missing``  — no run-index entry for this run-id
    - ``index_unreadable`` — run-index entry present but unreadable
    - ``project_mismatch`` — phash8 didn't match the run-index entry
    - ``run_dir_gone``   — run-dir recorded in the index no longer exists
    """
    parts = value.split("|", 3)
    if len(parts) != 4:
        log.warning("malformed button value: %r", value)
        return (None, "malformed")
    phash8, run_id, qd_id, _ = parts
    if not _RUN_ID_RE.match(run_id):
        log.warning("run_id failed validation: %r", run_id)
        return (None, "run_id_format")
    if not _QD_ID_RE.match(qd_id):
        log.warning("qd_id failed validation: %r", qd_id)
        return (None, "qd_id_format")
    entry_path = RUN_INDEX_DIR / f"{run_id}.json"
    if not entry_path.is_file():
        log.warning("run-index missing for run_id=%s", run_id)
        return (None, "index_missing")
    try:
        data = json.loads(entry_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("run-index read error for %s: %s", run_id, exc)
        return (None, "index_unreadable")
    if data.get("project_path_hash") != phash8:
        log.warning(
            "project_path_hash mismatch for run_id=%s: button=%s index=%s",
            run_id, phash8, data.get("project_path_hash"),
        )
        return (None, "project_mismatch")
    run_dir = Path(data["run_dir"])
    if not run_dir.is_dir():
        log.warning("run_dir gone for run_id=%s: %s", run_id, run_dir)
        return (None, "run_dir_gone")
    return run_dir, qd_id


_RESOLVE_REASON_TEXT: dict[str, str] = {
    "malformed": "Button payload malformed; reposting may help.",
    "run_id_format": (
        "Run id rejected by router (expected artifact-slug format "
        "`<adj>-<mid>-<noun>-<hex6>`). Regenerate the question."
    ),
    "qd_id_format": "Question/decision id rejected by router.",
    "index_missing": "This click is stale (router has no record of the run).",
    "index_unreadable": "Router run-index entry is corrupt.",
    "project_mismatch": "Cross-project click rejected by router.",
    "run_dir_gone": "Run directory was deleted; click cannot resolve.",
}


def _load_slack_context(run_dir: Path) -> SlackContext | None:
    ctx_path = run_dir / ".slack-context.json"
    if not ctx_path.is_file():
        return None
    try:
        data = json.loads(ctx_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("failed to read .slack-context.json: %s", exc)
        return None
    opts_raw = data.get("options", [])
    options: tuple[tuple[str, str], ...] = tuple(
        (str(pair[0]), str(pair[1])) for pair in opts_raw if len(pair) == 2
    )
    return SlackContext(
        project_path=Path(data.get("project_path", "")),
        project_path_hash=data.get("project_path_hash", ""),
        run_id=data.get("run_id", ""),
        channel=data.get("channel", ""),
        thread_ts=data.get("thread_ts", ""),
        qid=data.get("qid"),
        did=data.get("did"),
        options=options,
        message_ts=data.get("message_ts"),
    )


# ---------------------------------------------------------------------------
# Answer / decision writers
# ---------------------------------------------------------------------------


def _resolve_choice_label(run_dir: Path, qd_id: str, choice: str) -> str:
    """Resolve label for choice key from question file. Returns choice on fail."""
    n = qd_id.lstrip("q")
    qfile = run_dir / f"question-r{n}.md"
    if not qfile.is_file():
        return choice
    text = qfile.read_text()
    for line in text.splitlines():
        if line.startswith(f"## Option {choice}:"):
            return line[len(f"## Option {choice}:"):].strip()
    return choice


def _write_answer_file(
    run_dir: Path, qid: str, choice: str, label: str, user_id: str
) -> Path:
    n = qid.lstrip("q")
    out = run_dir / f"answer-r{n}.md"
    if out.exists():
        return out
    qfile = run_dir / f"question-r{n}.md"
    opened_at = "null"
    requesting_role = "unknown"
    if qfile.is_file():
        for line in qfile.read_text().splitlines():
            if line.startswith("opened_at:"):
                opened_at = line.split(":", 1)[1].strip()
            elif line.startswith("requesting_role:"):
                requesting_role = line.split(":", 1)[1].strip()
    safe_user_id = _safe_yaml_scalar(user_id)
    body = (
        "---\n"
        f"question_id: {qid}\n"
        "verdict: answered\n"
        f"chosen_key: {choice}\n"
        f"chosen_label: {label}\n"
        "delivery_mode: slack\n"
        f"opened_at: {opened_at}\n"
        f"answered_at: {_now_iso()}\n"
        f"answered_by_slack_user: {safe_user_id}\n"
        f"requesting_role: {requesting_role}\n"
        "---\n\n"
        "## Notes\n"
        "(no notes; chose via Slack button)\n\n"
        "## Source question\n"
        f"- Path: question-r{n}.md\n"
    )
    out.write_text(body)
    log.info("wrote answer file: %s", out)
    return out


def _write_decision_file(
    run_dir: Path, did: str, choice: str, user_id: str
) -> Path:
    n = did.lstrip("d")
    out = run_dir / f"decision-r{n}.md"
    if out.exists():
        return out
    awaiting = run_dir / f"awaiting-decision-r{n}.md"
    opened_at = "null"
    requesting_role = "unknown"
    options_source = "unknown"
    if awaiting.is_file():
        for line in awaiting.read_text().splitlines():
            if line.startswith("opened_at:"):
                opened_at = line.split(":", 1)[1].strip()
            elif line.startswith("requesting_role:"):
                requesting_role = line.split(":", 1)[1].strip()
            elif line.startswith("options_source:"):
                options_source = line.split(":", 1)[1].strip()
    safe_user_id = _safe_yaml_scalar(user_id)
    body = (
        "---\n"
        f"decision_id: {did}\n"
        "verdict: chosen\n"
        f"chosen_option: {choice}\n"
        "delivery_mode: slack\n"
        "issue_url: null\n"
        f"opened_at: {opened_at}\n"
        f"decided_at: {_now_iso()}\n"
        f"decided_by_slack_user: {safe_user_id}\n"
        f"requesting_role: {requesting_role}\n"
        f"options_source: {options_source}\n"
        "---\n\n"
        "## Pick rationale\n"
        "(no notes; chose via Slack button)\n\n"
        "## Source options\n"
        f"- Path: options-r{n}.md\n"
    )
    out.write_text(body)
    log.info("wrote decision file: %s", out)
    if awaiting.is_file():
        awaiting.unlink()
    return out


# ---------------------------------------------------------------------------
# RoutingIndex — snapshot container
# ---------------------------------------------------------------------------


class RoutingIndex:
    """Owns the current RoutingSnapshot + shared lock for idle-counter."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        empty: Mapping[str, Route] = MappingProxyType({})
        self._snapshot = RoutingSnapshot(
            by_thread=empty, by_sid=empty, fingerprint=""
        )
        self._idle_counter: float = 0.0

    def current(self) -> RoutingSnapshot:
        with self._lock:
            return self._snapshot

    def swap_if_changed(
        self, new_snap: RoutingSnapshot, idle_counter_ref: list[float]
    ) -> None:
        """Swap snapshot if fingerprint differs. Resets idle counter on non-empty."""
        with self._lock:
            if new_snap.fingerprint == self._snapshot.fingerprint:
                return
            if len(new_snap.by_sid) > 0:
                self._idle_counter = 0.0
                idle_counter_ref[0] = 0.0
            self._snapshot = new_snap


# ---------------------------------------------------------------------------
# RoutingPoller
# ---------------------------------------------------------------------------


def _build_snapshot() -> RoutingSnapshot:
    try:
        bindings = all_active_bindings()
    except Exception as exc:
        log.warning("all_active_bindings failed: %s", exc)
        bindings = {}

    thread_map: dict[str, Route] = {}
    sid_map: dict[str, Route] = {}

    for sid, data in bindings.items():
        channel_id = data.get("channel_id", "")
        thread_ts = data.get("thread_ts", "")
        if not channel_id or not thread_ts:
            continue
        try:
            inbox = _inbox_dir(sid)
        except ValueError as err:
            log.debug("invalid sid skipped: %s", err)
            continue
        route = Route(
            sid=sid,
            channel_id=channel_id,
            thread_ts=thread_ts,
            inbox_dir=inbox,
        )
        thread_map[thread_ts] = route
        sid_map[sid] = route

    sorted_triples = sorted(
        (sid, r.thread_ts, r.channel_id) for sid, r in sid_map.items()
    )
    fp = hashlib.sha1(str(sorted_triples).encode()).hexdigest()[:16]

    return RoutingSnapshot(
        by_thread=MappingProxyType(thread_map),
        by_sid=MappingProxyType(sid_map),
        fingerprint=fp,
    )


class RoutingPoller:
    def __init__(
        self,
        index: RoutingIndex,
        stop_evt: threading.Event,
        idle_counter_ref: list[float],
    ) -> None:
        self._index = index
        self._stop_evt = stop_evt
        self._idle_counter_ref = idle_counter_ref
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="routing-poller"
        )

    def start(self) -> None:
        self._thread.start()

    def join(self, timeout: float = 1.0) -> None:
        self._thread.join(timeout=timeout)

    def _loop(self) -> None:
        while not self._stop_evt.is_set():
            snap = _build_snapshot()
            self._index.swap_if_changed(snap, self._idle_counter_ref)
            _gc_run_index()
            self._stop_evt.wait(POLL_INTERVAL_S)


# ---------------------------------------------------------------------------
# IdleMonitor
# ---------------------------------------------------------------------------


class IdleMonitor:
    def __init__(
        self,
        index: RoutingIndex,
        stop_evt: threading.Event,
        idle_counter_ref: list[float],
    ) -> None:
        self._index = index
        self._stop_evt = stop_evt
        self._idle_counter_ref = idle_counter_ref
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="idle-monitor"
        )

    def start(self) -> None:
        self._thread.start()

    def join(self, timeout: float = 1.0) -> None:
        self._thread.join(timeout=timeout)

    def _loop(self) -> None:
        while not self._stop_evt.is_set():
            with self._index._lock:
                snap = self._index._snapshot
                if len(snap.by_sid) == 0:
                    self._index._idle_counter += POLL_INTERVAL_S
                    self._idle_counter_ref[0] = self._index._idle_counter
                    if self._index._idle_counter >= IDLE_TIMEOUT_S:
                        fresh = _build_snapshot()
                        if len(fresh.by_sid) > 0:
                            self._index._snapshot = fresh
                            self._index._idle_counter = 0.0
                            self._idle_counter_ref[0] = 0.0
                        else:
                            log.info(
                                "idle exit: %.0fs empty", self._index._idle_counter
                            )
                            self._stop_evt.set()
                            return
                else:
                    self._index._idle_counter = 0.0
                    self._idle_counter_ref[0] = 0.0
            self._stop_evt.wait(POLL_INTERVAL_S)


# ---------------------------------------------------------------------------
# RouterApp — Slack event + action handlers
# ---------------------------------------------------------------------------


class RouterApp:
    def __init__(
        self,
        app: App,
        index: RoutingIndex,
        allowed_users: set[str],
    ) -> None:
        self._app = app
        self._index = index
        self._allowed_users = allowed_users

    def register(self) -> None:
        self._app.event("message")(self._on_message)
        for letter in BUTTON_LETTERS:
            self._app.action(f"decision_pick_{letter}")(self._on_button_factory("decision"))
            self._app.action(f"question_pick_{letter}")(self._on_button_factory("question"))

    def _on_message(self, event: dict[str, Any]) -> None:
        if event.get("subtype") is not None:
            return
        if event.get("bot_id") or event.get("bot_profile"):
            return
        thread_ts: str | None = event.get("thread_ts")
        if not thread_ts:
            return
        message_ts: str | None = event.get("ts")
        if not message_ts:
            return
        # Enforce allowlist symmetrically with _process_button (H1).
        user_id: str = event.get("user", "")
        if self._allowed_users and user_id not in self._allowed_users:
            log.debug(
                "inbox drop: user=%s not in allowlist (message ts=%s)",
                user_id, message_ts,
            )
            return
        snap = self._index.current()
        route = snap.by_thread.get(thread_ts)
        if route is None:
            _write_unrouted_file(event)
            return
        ev_channel: str = event.get("channel", "")
        if ev_channel and ev_channel != route.channel_id:
            log.warning(
                "cross-channel drop: event=%s bound=%s sid=%s",
                ev_channel, route.channel_id, route.sid,
            )
            _write_unrouted_file(event)
            return
        _write_inbox_file(route.inbox_dir, event)

    # type: ignore[return] — factory returns a Bolt event-handler closure, not None
    def _on_button_factory(self, kind: str):  # type: ignore[return]
        def handler(ack: Any, body: dict[str, Any], client: Any) -> None:
            ack()
            try:
                self._process_button(body, client, kind)
            except Exception:
                log.exception("button handler failed (kind=%s)", kind)
        return handler

    def _process_button(
        self, body: dict[str, Any], client: Any, kind: str
    ) -> None:
        user_id: str = body.get("user", {}).get("id", "")
        if self._allowed_users and user_id not in self._allowed_users:
            channel_id = (body.get("channel") or {}).get("id", "")
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text="You are not authorized to respond to this pipeline.",
            )
            return

        actions = body.get("actions", [])
        if not actions:
            log.warning("button body has no actions")
            return
        value: str = actions[0].get("value", "")
        parts = value.split("|", 3)
        if len(parts) != 4:
            log.warning("malformed button value: %r", value)
            channel_id = (body.get("channel") or {}).get("id", "")
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=_RESOLVE_REASON_TEXT["malformed"],
            )
            return
        _phash8, run_id, qd_id, choice = parts

        resolved = _resolve_route_dir_from_value(value)
        first, second = resolved
        if first is None:
            reason: str = second  # type: ignore[assignment]  # narrowed by first is None
            channel_id = (body.get("channel") or {}).get("id", "")
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=_RESOLVE_REASON_TEXT.get(
                    reason, f"Click could not be routed ({reason}).",
                ),
            )
            return
        run_dir = first
        qd_id = second

        if kind == "decision":
            _write_decision_file(run_dir, qd_id, choice, user_id)
        else:
            label = _resolve_choice_label(run_dir, qd_id, choice)
            _write_answer_file(run_dir, qd_id, choice, label, user_id)

        self._confirm_pick(client, body, qd_id, choice, user_id, kind)

    def _confirm_pick(
        self,
        client: Any,
        body: dict[str, Any],
        qd_id: str,
        choice: str,
        user_id: str,
        kind: str,
    ) -> None:
        message = body.get("message") or {}
        message_ts: str = message.get("ts", "")
        thread_ts: str = message.get("thread_ts") or message_ts
        channel_id = (body.get("channel") or {}).get("id", "")
        if not message_ts or not channel_id:
            return
        label = "Decision" if kind == "decision" else "Question"
        try:
            client.chat_update(
                channel=channel_id,
                ts=message_ts,
                text=f"{label} {qd_id}: locked",
                blocks=[{
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f":white_check_mark: *{label} {qd_id}* — "
                            f"`{choice}` chosen by <@{user_id}>"
                        ),
                    },
                }],
            )
        except Exception as exc:
            log.warning("chat_update failed (ts=%s): %s", message_ts, exc)
        try:
            client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                text=f"Recorded `{choice}` for `{qd_id}`. Pipeline resuming.",
                unfurl_links=False,
                unfurl_media=False,
            )
        except Exception as exc:
            log.warning("confirm post failed: %s", exc)


# ---------------------------------------------------------------------------
# Single-instance gate
# ---------------------------------------------------------------------------


def _acquire_pid_or_exit() -> int:
    """Acquire flock on PID_PATH. Winner returns open fd; loser exits 0."""
    ROUTER_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(str(PID_PATH), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        log.info("router already running (flock held); exiting 0")
        raise SystemExit(0)
    os.ftruncate(fd, 0)
    os.write(fd, f"{os.getpid()}\n".encode())
    os.fsync(fd)
    return fd


def _cleanup_pidfile() -> None:
    try:
        PID_PATH.unlink(missing_ok=True)
    except OSError as exc:
        log.warning("pidfile unlink failed: %s", exc)


# ---------------------------------------------------------------------------
# Signal handling
# ---------------------------------------------------------------------------


def _install_signal_handlers(stop_evt: threading.Event) -> None:
    """Must be called from MainThread before threads start."""
    def _on_term(signum: int, frame: Any) -> None:
        log.info("signal %d received; stopping", signum)
        stop_evt.set()

    signal.signal(signal.SIGTERM, _on_term)
    signal.signal(signal.SIGINT, _on_term)
    signal.signal(signal.SIGHUP, signal.SIG_IGN)


def _supervisor(
    stop_evt: threading.Event, handler: SocketModeHandler
) -> None:
    stop_evt.wait()
    closer = threading.Thread(
        target=_safe_close, args=(handler,), daemon=True, name="handler-closer"
    )
    closer.start()
    closer.join(timeout=2.0)
    if closer.is_alive():
        log.warning("handler.close exceeded 2s; force exit")
    _cleanup_pidfile()
    os._exit(0)


def _safe_close(h: SocketModeHandler) -> None:
    try:
        h.close()
    except Exception:
        log.exception("handler.close failed")


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------


def _run() -> None:
    os.umask(0o077)
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    is_tty = sys.stdout.isatty()
    log_level = os.environ.get("SLACK_ROUTER_LOG_LEVEL", "INFO")

    if not is_tty:
        ROUTER_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
        logging.basicConfig(
            filename=str(LOG_PATH),
            level=log_level,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
    else:
        logging.basicConfig(
            stream=sys.stderr,
            level=log_level,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )

    load_env_file(default_env_path())

    bot_token = os.environ.get("SLACK_BOT_TOKEN", "")
    app_token = os.environ.get("SLACK_APP_TOKEN", "")
    if not bot_token or not app_token:
        log.error("SLACK_BOT_TOKEN and SLACK_APP_TOKEN required")
        raise SystemExit(2)

    allowed_users: set[str] = {
        u.strip()
        for u in os.environ.get("SLACK_ALLOWED_USERS", "").split(",")
        if u.strip()
    }

    ROUTER_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    UNROUTED_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    RUN_INDEX_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)

    _pid_fd = _acquire_pid_or_exit()  # winner path; loser exits above

    import atexit
    atexit.register(_cleanup_pidfile)

    stop_evt = threading.Event()
    _install_signal_handlers(stop_evt)

    idle_counter_ref: list[float] = [0.0]
    index = RoutingIndex()

    prime = _build_snapshot()
    index._snapshot = prime

    poller = RoutingPoller(index, stop_evt, idle_counter_ref)
    idle = IdleMonitor(index, stop_evt, idle_counter_ref)

    poller.start()
    idle.start()

    sessions_root = Path("~/.claude/sessions").expanduser()
    for sessions_sid_inbox in sessions_root.glob("*/inbox"):
        _cleanup_orphan_tmps(sessions_sid_inbox)

    app = App(token=bot_token)
    router_app = RouterApp(app, index, allowed_users)
    router_app.register()

    handler = SocketModeHandler(app, app_token)

    supervisor_thread = threading.Thread(
        target=_supervisor, args=(stop_evt, handler), daemon=True, name="supervisor"
    )
    supervisor_thread.start()

    log.info(
        "slack_router started: pid=%d idle_timeout=%ds", os.getpid(), IDLE_TIMEOUT_S
    )

    handler.start()  # blocks MainThread

    poller.join(timeout=1.0)
    idle.join(timeout=1.0)


def main() -> None:
    _run()


if __name__ == "__main__":
    main()
