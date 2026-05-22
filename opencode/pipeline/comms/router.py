#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "slack-bolt>=1.18",
# ]
# ///
"""comms_router — host-bound provider-neutral router daemon.

Single process per host. Routes inbound thread events to per-session
inbox dirs based on a binding table built from
~/.claude/sessions/*/slack.json.

Usage (detached, via session_bind.py activate — do not run directly):
    uv run --script ~/.claude/pipeline/comms/router.py

Environment (auto-loaded from ~/.claude/pipeline/slack.env.local):
    SLACK_BOT_TOKEN           xoxb-...
    SLACK_APP_TOKEN           xapp-...
    SLACK_ALLOWED_USERS       comma-separated user IDs (empty = any)
    SLACK_ROUTER_IDLE_TIMEOUT seconds before idle exit (default 1800 = 30min)

State (host-level, not stowed):
    ~/.claude/comms-router/router.pid     — held flock + PID number
    ~/.claude/comms-router/router.log     — daemon log
    ~/.claude/comms-router/unrouted/      — unmatched events (audit)
    ~/.claude/comms-router/run-index/     — per-run context for button routing
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

# N3 fix: same sys.path bootstrap as session_bind.py:43-45 so
# `import comms.xxx` works when spawned as a script.
_PIPELINE_DIR = Path(__file__).parent.parent
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

from comms.env import atomic_write_text, default_env_path, load_env_file  # noqa: E402
from comms.session import all_active_bindings, inbox_dir as _inbox_dir  # noqa: E402
from comms.types import InboundConsumer, InboundEvent, ThreadRef  # noqa: E402

__all__ = ["main"]

log = logging.getLogger("comms_router")

# ---------------------------------------------------------------------------
# Top-level constants
# ---------------------------------------------------------------------------

COMMS_ROOT = Path("~/.claude/comms-router").expanduser()
PID_PATH = COMMS_ROOT / "router.pid"
LOG_PATH = COMMS_ROOT / "router.log"
UNROUTED_DIR = COMMS_ROOT / "unrouted"
RUN_INDEX_DIR = COMMS_ROOT / "run-index"

# T9 reap target ONLY — never read/write for new state.
LEGACY_ROOT = Path("~/.claude/slack-router").expanduser()

POLL_INTERVAL_S = 3.0
IDLE_TIMEOUT_S = int(os.environ.get("SLACK_ROUTER_IDLE_TIMEOUT", "1800"))
RUN_INDEX_MAX_AGE_S = 14 * 86400
ORPHAN_TMP_MAX_AGE_S = 60

# Regex guards for button-payload fields (H3). Must match pipeline_ask.py.
_RUN_ID_RE = re.compile(r"^[a-z]+(?:-[a-z]+){2}-[a-f0-9]{6}$")
_QD_ID_RE = re.compile(r"^[qd][0-9]{1,4}$")

BUTTON_LETTERS = ("A", "B", "C", "D")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_yaml_scalar(value: str) -> str:
    """Escape newlines and colons for inline YAML scalar values (C1).

    Location pinned here per design §13.
    """
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
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Route:
    """Active binding for one session: maps thread_ref -> inbox dir."""

    sid: str
    thread_ref: ThreadRef
    inbox_dir: Path


@dataclass(frozen=True, slots=True)
class RoutingSnapshot:
    """Immutable point-in-time view of all active session routes."""

    by_thread: Mapping[str, Route]
    by_sid: Mapping[str, Route]
    fingerprint: str


# ---------------------------------------------------------------------------
# Inbox / unrouted writers
# ---------------------------------------------------------------------------


def _write_inbox_file(inbox: Path, ev: InboundEvent) -> bool:
    """Write inbox/<msg_ts>.json atomically from InboundEvent. Returns True if written."""
    mref = ev.message_ref
    message_ts = mref.provider_data.get("message_ts", "") if mref else ""
    if not message_ts:
        return False
    inbox.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = inbox / f"{message_ts}.json"
    if target.exists():
        return False
    sid = inbox.parent.name
    # Field names retain thread_ts/message_ts keys for inbox-reader compat (§3.6).
    payload = {
        "session_id": sid,
        "thread_ts": ev.thread_ref.provider_data.get("thread_ts", ""),
        "message_ts": message_ts,
        "user_id": ev.user_id,
        "text": ev.text or "",
        "received_at": ev.received_at,
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


def _write_unrouted_file(ev: InboundEvent) -> None:
    """Write unrouted/<msg_ts>.json for events with no route in index."""
    mref = ev.message_ref
    message_ts = mref.provider_data.get("message_ts", "") if mref else ""
    if not message_ts:
        return
    UNROUTED_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = UNROUTED_DIR / f"{message_ts}.json"
    if target.exists():
        return
    payload: dict[str, Any] = {
        "session_id": None,
        "thread_ts": ev.thread_ref.provider_data.get("thread_ts", ""),
        "message_ts": message_ts,
        "user_id": ev.user_id,
        "text": ev.text or "",
        "received_at": ev.received_at,
        "event_channel": ev.thread_ref.provider_data.get("channel_id", ""),
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


def _resolve_route_dir_from_run_id(
    run_id: str,
    phash8: str,
) -> tuple[Path, str] | tuple[None, str]:
    """Look up run-index by run_id + phash8. Returns (run_dir, run_id) or (None, reason)."""
    if not _RUN_ID_RE.match(run_id):
        log.warning("run_id failed validation: %r", run_id)
        return (None, "run_id_format")
    entry_path = RUN_INDEX_DIR / f"{run_id}.json"
    if not entry_path.is_file():
        log.warning("run-index missing for run_id=%s", run_id)
        return (None, "index_missing")
    try:
        data = json.loads(entry_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("run-index read error for %s: %s", run_id, exc)
        return (None, "index_unreadable")
    # phash8 is a security check. If phash8 is empty (comms-context absent/fresh
    # install), skip the check to allow routing. Non-empty phash must match.
    if phash8 and data.get("project_path_hash") != phash8:
        log.warning(
            "project_path_hash mismatch for run_id=%s: button=%s index=%s",
            run_id, phash8, data.get("project_path_hash"),
        )
        return (None, "project_mismatch")
    run_dir = Path(data["run_dir"])
    if not run_dir.is_dir():
        log.warning("run_dir gone for run_id=%s: %s", run_id, run_dir)
        return (None, "run_dir_gone")
    return run_dir, run_id


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


def _load_comms_context(run_dir: Path) -> dict[str, Any]:
    """Read .comms-context.json from run_dir. Returns {} on missing or error."""
    ctx_path = run_dir / ".comms-context.json"
    if not ctx_path.is_file():
        return {}
    try:
        return json.loads(ctx_path.read_text())  # type: ignore[return-value]
    except (OSError, json.JSONDecodeError):
        return {}


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
    # D9: delivery_mode: async (not "slack") — neutralised literal.
    body = (
        "---\n"
        f"question_id: {qid}\n"
        "verdict: answered\n"
        f"chosen_key: {choice}\n"
        f"chosen_label: {label}\n"
        "delivery_mode: async\n"
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
    # D9: delivery_mode: async (not "slack") — neutralised literal.
    body = (
        "---\n"
        f"decision_id: {did}\n"
        "verdict: chosen\n"
        f"chosen_option: {choice}\n"
        "delivery_mode: async\n"
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
        provider = data.get("provider", "slack")
        thread_ref = ThreadRef(
            provider=provider,
            provider_data=MappingProxyType(
                {"channel_id": channel_id, "thread_ts": thread_ts}
            ),
        )
        route = Route(
            sid=sid,
            thread_ref=thread_ref,
            inbox_dir=inbox,
        )
        thread_map[thread_ts] = route
        sid_map[sid] = route

    sorted_triples = sorted(
        (sid, r.thread_ref.provider_data.get("thread_ts", ""),
         r.thread_ref.provider_data.get("channel_id", ""))
        for sid, r in sid_map.items()
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
# InboundConsumerImpl — provider-agnostic dispatcher
# ---------------------------------------------------------------------------


class InboundConsumerImpl:
    """Implements InboundConsumer Protocol.

    Provider's worker thread calls dispatch() synchronously per event.
    Consumer is responsible for synchronization on shared state
    (RoutingIndex is internally thread-safe; writers use atomic
    rename / O_EXCL; allowed_users is immutable frozenset).

    H1 invariant: allowlist enforced HERE before any artefact write.
    """

    def __init__(
        self,
        provider: Any,
        index: RoutingIndex,
        allowed_users: frozenset[str],
        stop_evt: threading.Event,
    ) -> None:
        self._provider = provider
        self._index = index
        self._allowed_users = allowed_users
        self._stop_evt = stop_evt

    def dispatch(self, ev: InboundEvent) -> None:
        """Dispatch one normalized inbound event."""
        if self._stop_evt.is_set():
            return
        # H1: allowlist enforced before any artefact write.
        if self._allowed_users and ev.user_id not in self._allowed_users:
            if ev.event_role in ("question_answer", "decision_pick"):
                snap = self._index.current()
                thread_ref = ev.thread_ref
                self._provider.post_ephemeral_error(
                    thread_ref,
                    ev.user_id,
                    "You are not authorized to respond to this pipeline.",
                )
            # Message path: silent drop (prevents reply-loop).
            return

        if ev.event_role == "message":
            self._handle_message(ev)
        elif ev.event_role == "question_answer":
            self._handle_button(ev, kind="question")
        elif ev.event_role == "decision_pick":
            self._handle_button(ev, kind="decision")

    def _handle_message(self, ev: InboundEvent) -> None:
        thread_ts = ev.thread_ref.provider_data.get("thread_ts", "")
        snap = self._index.current()
        route = snap.by_thread.get(thread_ts)
        if route is None:
            _write_unrouted_file(ev)
            return
        # Router trusts cross-channel guard is already done by adapter (B3).
        _write_inbox_file(route.inbox_dir, ev)

    def _handle_button(self, ev: InboundEvent, kind: str) -> None:
        """Handle button click: resolve run_dir, write answer/decision, confirm."""
        run_id = ev.run_id
        qd_id = ev.qd_id
        option_index = ev.option_index

        if run_id is None or qd_id is None or option_index is None:
            log.warning("button event missing routing fields: %r", ev)
            return

        if not _QD_ID_RE.match(qd_id):
            log.warning("qd_id failed validation: %r", qd_id)
            return

        if not (0 <= option_index < len(BUTTON_LETTERS)):
            log.warning("option_index out of range: %d", option_index)
            return

        choice = BUTTON_LETTERS[option_index]

        # Resolve run dir from run-index. phash8 from context file.
        ctx = _load_comms_context_by_run_id(run_id)
        phash8 = ctx.get("project_path_hash", "")

        result = _resolve_route_dir_from_run_id(run_id, phash8)
        first, second = result
        if first is None:
            reason: str = second  # type: ignore[assignment]
            self._provider.post_ephemeral_error(
                ev.thread_ref,
                ev.user_id,
                _RESOLVE_REASON_TEXT.get(
                    reason, f"Click could not be routed ({reason}).",
                ),
            )
            return

        run_dir = first

        if kind == "decision":
            _write_decision_file(run_dir, qd_id, choice, ev.user_id)
        else:
            label = _resolve_choice_label(run_dir, qd_id, choice)
            _write_answer_file(run_dir, qd_id, choice, label, ev.user_id)

        self._confirm_pick(ev, qd_id, choice, kind)

    def _confirm_pick(
        self,
        ev: InboundEvent,
        qd_id: str,
        choice: str,
        kind: str,
    ) -> None:
        mref = ev.message_ref
        if mref is None:
            return
        message_ts = mref.provider_data.get("message_ts", "")
        if not message_ts:
            return
        label = "Decision" if kind == "decision" else "Question"
        new_body = (
            f":white_check_mark: *{label} {qd_id}* — "
            f"`{choice}` chosen by <@{ev.user_id}>"
        )
        try:
            self._provider.update_message(mref, new_body, lock=True)
        except Exception as exc:
            log.warning("update_message failed: %s", exc)
        try:
            self._provider.post_confirmation(ev.thread_ref, mref, choice)
        except Exception as exc:
            log.warning("post_confirmation failed: %s", exc)


def _load_comms_context_by_run_id(run_id: str) -> dict[str, Any]:
    """Try to find .comms-context.json for a run_id via run-index."""
    entry_path = RUN_INDEX_DIR / f"{run_id}.json"
    if not entry_path.is_file():
        return {}
    try:
        data = json.loads(entry_path.read_text())
        run_dir = Path(data.get("run_dir", ""))
        if run_dir.is_dir():
            return _load_comms_context(run_dir)
    except (OSError, json.JSONDecodeError):
        pass
    return {}


# ---------------------------------------------------------------------------
# Single-instance gate
# ---------------------------------------------------------------------------


def _acquire_pid_or_exit() -> int:
    """Acquire flock on PID_PATH. Winner returns open fd; loser exits 0."""
    COMMS_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
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
    stop_evt: threading.Event,
    provider: Any,
) -> None:
    stop_evt.wait()
    try:
        provider.stop_inbound()
    except Exception:
        log.exception("provider.stop_inbound failed")
    _cleanup_pidfile()
    os._exit(0)


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------


def _run() -> None:
    os.umask(0o077)
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    is_tty = sys.stdout.isatty()
    log_level = os.environ.get("SLACK_ROUTER_LOG_LEVEL", "INFO")

    if not is_tty:
        COMMS_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
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

    allowed_users: frozenset[str] = frozenset(
        u.strip()
        for u in os.environ.get("SLACK_ALLOWED_USERS", "").split(",")
        if u.strip()
    )

    COMMS_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
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

    # Build provider via registry (uses active_provider with cwd as project_path).
    from comms.registry import get_registry  # noqa: PLC0415
    project_path = Path.cwd()
    provider = get_registry().active_provider(project_path)

    # Wire routing_index_ref for cross-channel guard (B3).
    if hasattr(provider, "set_routing_index_ref"):
        provider.set_routing_index_ref(index.current)

    consumer = InboundConsumerImpl(provider, index, allowed_users, stop_evt)

    supervisor_thread = threading.Thread(
        target=_supervisor, args=(stop_evt, provider), daemon=True, name="supervisor"
    )
    supervisor_thread.start()

    log.info(
        "comms_router started: pid=%d idle_timeout=%ds", os.getpid(), IDLE_TIMEOUT_S
    )

    provider.start_inbound(consumer, stop_evt)

    stop_evt.wait()

    poller.join(timeout=1.0)
    idle.join(timeout=1.0)


def main() -> None:
    _run()


if __name__ == "__main__":
    main()
