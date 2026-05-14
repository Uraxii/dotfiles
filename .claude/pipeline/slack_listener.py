#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "slack-bolt>=1.18",
#     "watchdog>=4.0",
# ]
# ///
"""Pipeline Slack decision listener (Socket Mode).

Per-run daemon. Spawned by the orchestrator when a pipeline run enters the
decision-elicitation stage in async (Slack) mode. Watches a single run dir
for awaiting-decision-r<N>.md files, posts each to Slack as a threaded
message with buttons, and on button click writes decision-r<N>.md back to
the run dir for the pipeline to poll.

Exits cleanly when the run's awaiting set has been empty for IDLE_GRACE
seconds (default 86400 = 24h; override via SLACK_LISTENER_IDLE_TIMEOUT env).
Pipeline re-spawns this process if a later decision point fires in the same
run.

Outbound-only: uses Socket Mode WebSocket. No inbound port. No public URL.

Usage:
    slack_listener.py <project-path> <run-id> [--session-thread CHANNEL:TS]

Environment (auto-loaded from ~/.claude/pipeline/slack.env.local if not in env;
override path via SLACK_ENV_FILE):
    SLACK_BOT_TOKEN            xoxb-... (chat:write, chat:write.public, reactions:write)
    SLACK_APP_TOKEN            xapp-... (connections:write)
    SLACK_ALLOWED_USERS        comma-separated Slack user IDs allowed to click buttons
                               (empty = anyone in channel)
    SLACK_LISTENER_IDLE_TIMEOUT  seconds before idle exit (default 86400 = 24h)

Per-project config: <project>/.pipeline/pipeline.toml
    [slack]
    channel = "C0123ABC"          # required, channel ID (not name)
    project_name = "myproject"    # optional, shown in parent msg

Per-run state: <run-dir>/slack-state.json (thread_ts, posted decision_ids).
Per-run PID:   <run-dir>/slack-listener.pid (written at start, removed at exit).

Session-bound mode (--session-thread CHANNEL:TS):
    When supplied, all outbound posts land in the supplied thread rather than
    a new per-run thread. Each message is prefixed with [<run-id>].  Inbound
    thread replies for any known session are written to that session's inbox.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import threading
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Import shared env helpers + session helper (stdlib-only).
# Both live alongside this script in ~/.claude/pipeline/.
_PIPELINE_DIR = Path(__file__).parent
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

from _slack_env import (  # noqa: E402
    atomic_write_text,
    default_env_path,
    load_env_file,
)
from session_slack import all_active_bindings, inbox_dir as _session_inbox_dir  # noqa: E402

try:
    from slack_bolt import App
    from slack_bolt.adapter.socket_mode import SocketModeHandler
except ImportError:
    sys.stderr.write(
        "slack_bolt missing. Install: pip install --user slack-bolt watchdog\n"
    )
    sys.exit(2)

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
except ImportError:
    sys.stderr.write(
        "watchdog missing. Install: pip install --user slack-bolt watchdog\n"
    )
    sys.exit(2)


log = logging.getLogger("slack_listener")

AWAITING_RE = re.compile(r"^awaiting-decision-r(\d+)\.md$")
QUESTION_RE = re.compile(r"^question-r(\d+)\.md$")
OPTIONS_RE = re.compile(r"^## Option ([A-D]): (.+)$")
TRADEOFF_RE = re.compile(r"^- \*\*Tradeoff:\*\* (.+)$")

_IDLE_TIMEOUT_S = int(os.environ.get("SLACK_LISTENER_IDLE_TIMEOUT", "86400"))

# In-memory cross-listener routing index (populated at boot, refreshed on watchdog events).
# thread_ts -> sid, sid -> inbox_dir
_THREAD_TO_SID: dict[str, str] = {}
_SID_TO_INBOX: dict[str, Path] = {}
_ROUTING_LOCK = threading.Lock()


def _rebuild_routing_index() -> None:
    """Rebuild THREAD_TO_SID + SID_TO_INBOX from all active session bindings."""
    try:
        bindings = all_active_bindings()
    except Exception as exc:
        log.warning("routing index rebuild failed: %s", exc)
        return
    new_thread: dict[str, str] = {}
    new_inbox: dict[str, Path] = {}
    for sid, data in bindings.items():
        ts = data.get("thread_ts", "")
        if ts:
            new_thread[ts] = sid
            try:
                new_inbox[sid] = _session_inbox_dir(sid)
            except ValueError:
                pass
    with _ROUTING_LOCK:
        _THREAD_TO_SID.clear()
        _THREAD_TO_SID.update(new_thread)
        _SID_TO_INBOX.clear()
        _SID_TO_INBOX.update(new_inbox)
    log.debug("routing index rebuilt: %d active sessions", len(new_thread))


def _write_inbox_file(inbox: Path, event: dict[str, Any]) -> None:
    """Atomically write one inbox/<msg_ts>.json. Skip if already exists (H3)."""
    message_ts: str = event.get("ts", "")
    if not message_ts:
        return
    inbox.mkdir(parents=True, exist_ok=True)
    target = inbox / f"{message_ts}.json"
    if target.exists():
        return
    thread_ts: str = event.get("thread_ts", "")
    sid = inbox.parent.name
    payload = {
        "session_id": sid,
        "thread_ts": thread_ts,
        "message_ts": message_ts,
        "user_id": event.get("user", ""),
        "text": event.get("text", ""),
        "received_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        atomic_write_text(target, json.dumps(payload, indent=2), mode=0o600)
        log.info("inbox: wrote %s", target)
    except OSError as exc:
        # L4: surface ENOSPC explicitly so it's auditable.
        if exc.errno == 28:  # ENOSPC
            log.error(
                "dropped inbox write: ENOSPC target=%s sid=%s", target, sid,
                extra={"event": "inbox_drop_enospc", "target": str(target), "sid": sid},
            )
        else:
            log.error("inbox write failed for %s: %s", target, exc)


def _cleanup_orphan_tmps(inbox: Path) -> None:
    """Remove *.tmp files older than 60s at writer startup."""
    if not inbox.is_dir():
        return
    now = datetime.now(timezone.utc).timestamp()
    for tmp in inbox.glob("*.tmp"):
        try:
            if now - tmp.stat().st_mtime > 60:
                tmp.unlink(missing_ok=True)
        except OSError:
            pass


# ----------------------------------------------------------------------------
# Idle monitor (path-activated lifecycle)
# ----------------------------------------------------------------------------


class IdleMonitor:
    """Tracks the run's open decisions; self-exits after GRACE_SECONDS at 0.

    Per-run model: orchestrator spawns one listener per run when async-mode
    decisions are expected. The listener stays alive while any awaiting file
    exists in its run dir, then exits cleanly. The grace window absorbs gaps
    between consecutive decisions in the same run (d1 resolved → d2 about to
    land), avoiding spawn churn.
    """

    @property
    def GRACE_SECONDS(self) -> int:  # type: ignore[override]
        return _IDLE_TIMEOUT_S

    def __init__(self, run_dir: Path, pid_path: Path | None = None) -> None:
        self.run_dir = run_dir
        self.pid_path = pid_path
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None

    def _count_awaiting(self) -> int:
        n = sum(1 for _ in self.run_dir.glob("awaiting-decision-r*.md"))
        # Open questions = question-r<N>.md without matching answer-r<N>.md
        for q in self.run_dir.glob("question-r*.md"):
            m = QUESTION_RE.match(q.name)
            if not m:
                continue
            if not (self.run_dir / f"answer-r{m.group(1)}.md").exists():
                n += 1
        return n

    def tick(self) -> None:
        """Re-evaluate idle state. Call after any awaiting-file lifecycle event."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            n = self._count_awaiting()
            if n == 0:
                log.info(
                    "no open decisions; idle exit scheduled in %ds",
                    self.GRACE_SECONDS,
                )
                self._timer = threading.Timer(self.GRACE_SECONDS, self._fire)
                self._timer.daemon = True
                self._timer.start()
            else:
                log.debug("%d open decision(s); staying alive", n)

    def _fire(self) -> None:
        with self._lock:
            self._timer = None
            if self._count_awaiting() == 0:
                log.info("idle grace elapsed, exiting")
                # os._exit bypasses atexit/thread-join; needed because
                # SocketModeHandler runs a non-daemon background thread.
                # Remove PID file inline since atexit handlers will not fire.
                if self.pid_path is not None:
                    try:
                        self.pid_path.unlink(missing_ok=True)
                    except OSError:
                        pass
                os._exit(0)


# ----------------------------------------------------------------------------
# State persistence
# ----------------------------------------------------------------------------


class State:
    """Per-project persistent state: run_id -> parent thread ts, decision posting."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._data: dict[str, Any] = {"runs": {}, "decisions": {}}
        if path.exists():
            try:
                self._data = json.loads(path.read_text())
            except json.JSONDecodeError:
                log.warning("state file corrupt, starting fresh: %s", path)

    def _flush(self) -> None:
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self._data, indent=2))
        tmp.replace(self.path)

    def get_thread_ts(self, run_id: str) -> str | None:
        with self._lock:
            return self._data["runs"].get(run_id, {}).get("thread_ts")

    def set_thread_ts(self, run_id: str, ts: str, channel: str) -> None:
        with self._lock:
            self._data["runs"][run_id] = {"thread_ts": ts, "channel": channel}
            self._flush()

    def has_posted(self, decision_key: str) -> bool:
        with self._lock:
            return decision_key in self._data["decisions"]

    def mark_posted(self, decision_key: str, ts: str, channel: str) -> None:
        with self._lock:
            self._data["decisions"][decision_key] = {"ts": ts, "channel": channel}
            self._flush()


# ----------------------------------------------------------------------------
# Options parsing
# ----------------------------------------------------------------------------


def parse_options(options_md: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Parse options-r<N>.md → (frontmatter dict, [{key,title,tradeoff}])."""
    text = options_md.read_text()
    frontmatter: dict[str, Any] = {}
    body = text

    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end > 0:
            fm_text = text[4:end]
            body = text[end + 5 :]
            for line in fm_text.splitlines():
                if ":" in line:
                    k, _, v = line.partition(":")
                    frontmatter[k.strip()] = v.strip()

    options: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in body.splitlines():
        m = OPTIONS_RE.match(line)
        if m:
            if current:
                options.append(current)
            current = {"key": m.group(1), "title": m.group(2).strip(), "tradeoff": ""}
            continue
        if current:
            t = TRADEOFF_RE.match(line)
            if t:
                current["tradeoff"] = t.group(1).strip()
    if current:
        options.append(current)

    return frontmatter, options


def parse_awaiting(awaiting_md: Path) -> dict[str, Any]:
    """Parse awaiting-decision-r<N>.md frontmatter."""
    text = awaiting_md.read_text()
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}
    fm: dict[str, Any] = {}
    for line in text[4:end].splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm


def parse_question_file(question_md: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Parse question-r<N>.md → (frontmatter, [{key,title}]). Body uses same
    `## Option <K>: <label>` shape as options-r<N>.md, so OPTIONS_RE is reused.

    Frontmatter `attachments:` may be a YAML block list (two-space indent,
    each line starting with `- <path>`). Those paths are returned under the
    `attachments` key as `list[str]`; everything else is a flat key/value
    string map.
    """
    text = question_md.read_text()
    fm: dict[str, Any] = {}
    body = text
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end > 0:
            fm_text = text[4:end]
            current_list_key: str | None = None
            for line in fm_text.splitlines():
                stripped = line.lstrip(" ")
                # Continuation of a block-list value.
                if current_list_key is not None and line.startswith("  - "):
                    fm[current_list_key].append(line[4:].strip())
                    continue
                current_list_key = None
                if ":" not in stripped or line.startswith(" "):
                    continue
                k, _, v = stripped.partition(":")
                k = k.strip()
                v = v.strip()
                if v == "":
                    # Empty scalar → block list candidate; init container.
                    fm[k] = []
                    current_list_key = k
                else:
                    fm[k] = v
            body = text[end + 5 :]
    options: list[dict[str, str]] = []
    for line in body.splitlines():
        m = OPTIONS_RE.match(line)
        if m:
            options.append({"key": m.group(1), "title": m.group(2).strip()})
    return fm, options


# ----------------------------------------------------------------------------
# Slack post + handlers
# ----------------------------------------------------------------------------


class SlackPoster:
    def __init__(
        self,
        app: App,
        state: State,
        channel: str,
        project_name: str,
        project_path: Path,
        session_thread: tuple[str, str] | None = None,
        project_channel: str | None = None,
        run_dir: Path | None = None,
    ) -> None:
        self.app = app
        self.state = state
        self.channel = channel
        self.project_name = project_name
        self.project_path = project_path
        self.session_thread = session_thread
        self.session_bound: bool = session_thread is not None
        self._project_channel = project_channel or channel
        self._run_dir = run_dir

    def _prefix(self, run_id: str, shard: str | None = None) -> str:
        """Return message prefix for session-bound mode; empty string in legacy mode."""
        if not self.session_bound:
            return ""
        if shard:
            return f"[{run_id} {shard}] "
        return f"[{run_id}] "

    def _post_channel_mismatch_warning(
        self,
        run_id: str,
        project_channel: str,
        session_channel: str,
    ) -> None:
        """Warn about channel mismatch to bound thread (C3 policy)."""
        msg = (
            f":warning: pipeline `{run_id}` cwd-channel `{project_channel}` "
            f"differs from session-bound channel `{session_channel}`; "
            "posting here per session binding."
        )
        try:
            self.app.client.chat_postMessage(
                channel=session_channel,
                thread_ts=self.session_thread[1],  # type: ignore[index]
                text=msg,
                unfurl_links=False,
                unfurl_media=False,
            )
        except Exception as exc:
            log.warning("failed to post channel-mismatch warning: %s", exc)
        log.warning(
            "channel mismatch for run=%s: project_channel=%s session_channel=%s",
            run_id, project_channel, session_channel,
        )
        # Also write to slack-listener.log (already going to stderr/log).
        # Write to pipeline.md if run_dir is known.
        if self._run_dir is not None:
            self._write_pipeline_md_warning(run_id, project_channel, session_channel)

    def _write_pipeline_md_warning(
        self,
        run_id: str,
        project_channel: str,
        session_channel: str,
    ) -> None:
        """Best-effort: write slack.warning to pipeline.md frontmatter via pipeline_state.

        Uses pipeline_state.py set (subprocess) so the write goes through the
        same flock on the sidecar lock file, avoiding the flock-replace race (B2/B3).
        """
        if self._run_dir is None:
            return
        md_path = self._run_dir / "pipeline.md"
        if not md_path.is_file():
            return
        warning = (
            f"channel-mismatch: cwd-channel={project_channel}, "
            f"session-channel={session_channel}; posting to session"
        )
        # Derive project path from run dir layout: <project>/.pipeline/runs/<run_id>
        project_path = self._run_dir.parent.parent.parent
        pipeline_state_script = _PIPELINE_DIR / "pipeline_state.py"
        try:
            import subprocess as _subprocess
            _subprocess.run(
                [
                    "python3", str(pipeline_state_script),
                    "set",
                    "--project", str(project_path),
                    "--run", run_id,
                    "--key", "slack.warning",
                    "--value", warning,
                ],
                check=True,
                capture_output=True,
                timeout=5,
            )
        except Exception as exc:
            log.debug("could not write pipeline.md warning: %s", exc)

    def _header_posted(self, run_id: str) -> bool:
        """True if the run-header was already posted into the session thread."""
        with self.state._lock:  # type: ignore[attr-defined]
            run_data = self.state._data["runs"].get(run_id, {})  # type: ignore[attr-defined]
        return bool(run_data.get("header_posted", False))

    def _mark_header_posted(self, run_id: str, thread_ts: str, channel: str) -> None:
        with self.state._lock:  # type: ignore[attr-defined]
            self.state._data["runs"][run_id] = {  # type: ignore[attr-defined]
                "thread_ts": thread_ts,
                "channel": channel,
                "session_bound": True,
                "header_posted": True,
            }
            self.state._flush()  # type: ignore[attr-defined]

    def _post_run_header(self, run_id: str, brief: str) -> None:
        """Post one [run-id] rocket header reply when first artifact posted in session thread."""
        assert self.session_thread is not None
        channel, thread_ts = self.session_thread
        brief_snippet = brief[:120] if brief else "(no brief)"
        text = (
            f"[{run_id}] :rocket: Pipeline started — brief: {brief_snippet}"
        )
        self.app.client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=text,
            unfurl_links=False,
            unfurl_media=False,
        )
        self._mark_header_posted(run_id, thread_ts, channel)
        log.info("posted session-bound run header for run=%s", run_id)

    def ensure_thread(self, run_id: str, brief: str) -> str:
        """Return thread_ts for run.

        Session-bound mode: return the supplied session thread_ts (no new root
        message).  Post a one-off run header on first artifact for this run.
        Legacy mode: post a per-run parent message as before.
        """
        if self.session_thread is not None:
            session_channel, session_ts = self.session_thread
            # Channel-mismatch policy (r1 C3): prefer session channel, warn, continue.
            if session_channel != self._project_channel:
                self._post_channel_mismatch_warning(
                    run_id, self._project_channel, session_channel
                )
                self.channel = session_channel  # adopt session channel
            if not self._header_posted(run_id):
                self._post_run_header(run_id, brief)
            return session_ts

        # Legacy path.
        ts = self.state.get_thread_ts(run_id)
        if ts:
            return ts
        text = (
            f":hourglass_flowing_sand: *Pipeline started* `{run_id}`\n"
            f"Project: `{self.project_name}`"
        )
        if brief:
            text += f"\nBrief: {brief}"
        resp = self.app.client.chat_postMessage(
            channel=self.channel,
            text=text,
            unfurl_links=False,
            unfurl_media=False,
        )
        ts = resp["ts"]
        self.state.set_thread_ts(run_id, ts, self.channel)
        log.info("posted parent for run=%s ts=%s", run_id, ts)
        return ts

    def post_decision(
        self,
        run_id: str,
        decision_id: str,
        topic: str,
        options: list[dict[str, str]],
        thread_ts: str,
    ) -> str:
        decision_key = f"{run_id}:{decision_id}"
        if self.state.has_posted(decision_key):
            log.info("already posted %s, skipping", decision_key)
            return ""

        pfx = self._prefix(run_id)
        blocks: list[dict[str, Any]] = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{pfx}*Decision {decision_id}*: {topic}",
                },
            },
        ]
        for opt in options:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Option {opt['key']}*: {opt['title']}\n_{opt['tradeoff']}_",
                    },
                }
            )
        blocks.append(
            {
                "type": "actions",
                "block_id": f"pick_{decision_id}",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": f"Option {opt['key']}"},
                        "value": f"{run_id}|{decision_id}|{opt['key']}",
                        "action_id": f"decision_pick_{opt['key']}",
                    }
                    for opt in options
                ],
            }
        )

        resp = self.app.client.chat_postMessage(
            channel=self.channel,
            thread_ts=thread_ts,
            text=f"{pfx}Decision {decision_id}: {topic}",
            blocks=blocks,
            unfurl_links=False,
            unfurl_media=False,
        )
        ts = resp["ts"]
        self.state.mark_posted(decision_key, ts, self.channel)
        log.info("posted decision %s ts=%s", decision_key, ts)
        return ts

    def upload_attachment(
        self,
        run_id: str,
        question_id: str,
        attachment_path: str,
        thread_ts: str,
    ) -> tuple[str, str, str]:
        """Upload a single file into the run's thread, silently.

        Returns (file_id, permalink, filename). Empty tuple on failure
        (logs, doesn't raise — surrounding question post must still go out).

        `initial_comment` is intentionally omitted so the file message has no
        accompanying text post. The caller threads `permalink` into the
        question's button-message blocks as a markdown link, producing the
        compact "link-only in button msg" layout: a small file card in the
        thread + the question msg with a clickable link to it.

        Idempotency: state map key `attach:<run>:<qid>:<path>` records both
        file_id and permalink as a single CSV value (ts column reused) so a
        listener restart can short-circuit without re-uploading AND still
        recover the permalink for the question block.
        """
        key = f"attach:{run_id}:{question_id}:{attachment_path}"
        prior = self._get_attachment_link(key)
        if prior is not None:
            log.info("attachment already uploaded %s, reusing permalink", key)
            file_id, permalink, filename = prior
            return file_id, permalink, filename
        path = Path(attachment_path).expanduser()
        if not path.is_file():
            log.warning("attachment missing on disk: %s", path)
            return "", "", ""
        # files_upload_v2 occasionally times out on slow networks even for
        # small files (multipart upload + getUploadURLExternal + complete are
        # three round-trips). One automatic retry recovers most transient
        # failures without forcing the caller to re-run the whole CLI.
        resp = None
        last_err: Exception | None = None
        for attempt in (1, 2):
            try:
                resp = self.app.client.files_upload_v2(
                    channel=self.channel,
                    thread_ts=thread_ts,
                    file=str(path),
                    filename=path.name,
                    title=path.name,
                    # initial_comment intentionally omitted; link surfaces in
                    # question button message instead.
                )
                break
            except Exception as e:
                last_err = e
                log.warning("file upload attempt %d failed for %s: %s",
                            attempt, path, e)
        if resp is None:
            log.error("file upload gave up after retries for %s: %s",
                      path, last_err)
            return "", "", ""
        file_info: dict[str, Any] = {}
        try:
            file_info = resp.get("file", {}) or {}
        except AttributeError:
            file_info = {}
        file_id = file_info.get("id", "") or ""
        permalink = file_info.get("permalink", "") or ""
        # Encode (file_id, permalink, filename) into the state value channel
        # field so a restart can rehydrate without re-calling Slack.
        composite = f"{file_id}|{permalink}|{path.name}"
        self.state.mark_posted(key, file_id, composite)
        log.info("uploaded attachment %s (file=%s permalink=%s)",
                 key, path.name, permalink)
        return file_id, permalink, path.name

    def _get_attachment_link(
        self, key: str,
    ) -> tuple[str, str, str] | None:
        """Recover (file_id, permalink, filename) from state if already uploaded.

        Returns None if not previously posted, or if the stored entry lacks
        the composite channel value (e.g. written by an older listener
        version that didn't pack permalink). In the latter case caller should
        treat as "posted but no link recoverable" and skip relinking.
        """
        with self.state._lock:  # type: ignore[attr-defined]
            entry = self.state._data["decisions"].get(key)  # type: ignore[attr-defined]
        if not entry:
            return None
        composite = entry.get("channel", "") or ""
        if composite.count("|") != 2:
            # Old-format entry; nothing to relink against.
            return "", "", ""
        file_id, permalink, filename = composite.split("|", 2)
        return file_id, permalink, filename

    def post_question(
        self,
        run_id: str,
        question_id: str,
        header: str,
        prompt: str,
        options: list[dict[str, str]],
        thread_ts: str,
        attachment_links: list[tuple[str, str]] | None = None,
    ) -> str:
        """Post a free-form question with N button options to the run thread.

        Differs from post_decision by namespace key (`q:` prefix) and Slack
        action_id (`question_pick_<K>`). Button value carries
        `<run-id>|<question-id>|<choice>`; the question_pick action handler
        parses and writes answer-r<N>.md.

        attachment_links is `[(permalink, filename), ...]`. When non-empty,
        a markdown section block listing the files as Slack-formatted links
        (`<URL|name>`) is inserted between the prompt and the option blocks.
        """
        key = f"q:{run_id}:{question_id}"
        if self.state.has_posted(key):
            log.info("already posted %s, skipping", key)
            return ""
        pfx = self._prefix(run_id)
        header_text = f"[{header}] " if header else ""
        blocks: list[dict[str, Any]] = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{pfx}*{header_text}{question_id}*\n{prompt}",
                },
            },
        ]
        if attachment_links:
            link_lines = [
                f"• <{pl}|{nm}>" for pl, nm in attachment_links if pl and nm
            ]
            if link_lines:
                blocks.append(
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Attachments:*\n" + "\n".join(link_lines),
                        },
                    }
                )
        for opt in options:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{opt['key']}*: {opt['title']}",
                    },
                }
            )
        blocks.append(
            {
                "type": "actions",
                "block_id": f"qpick_{question_id}",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": opt["key"]},
                        "value": f"{run_id}|{question_id}|{opt['key']}",
                        "action_id": f"question_pick_{opt['key']}",
                    }
                    for opt in options
                ],
            }
        )
        resp = self.app.client.chat_postMessage(
            channel=self.channel,
            thread_ts=thread_ts,
            text=f"{pfx}Question {question_id}: {prompt[:80]}",
            blocks=blocks,
            unfurl_links=False,
            unfurl_media=False,
        )
        ts = resp["ts"]
        self.state.mark_posted(key, ts, self.channel)
        log.info("posted question %s ts=%s", key, ts)
        return ts

    def confirm_pick(
        self,
        run_id: str,
        decision_id: str,
        choice: str,
        user: str,
        message_ts: str,
        thread_ts: str,
    ) -> None:
        # Edit original to lock + show pick
        self.app.client.chat_update(
            channel=self.channel,
            ts=message_ts,
            text=f"Decision {decision_id}: locked",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f":white_check_mark: *Decision {decision_id}* — Option {choice} chosen by <@{user}>",
                    },
                },
            ],
        )
        # Confirmation reply in thread
        self.app.client.chat_postMessage(
            channel=self.channel,
            thread_ts=thread_ts,
            text=f"Recorded *Option {choice}* for `{run_id}` / `{decision_id}`. Pipeline resuming.",
            unfurl_links=False,
            unfurl_media=False,
        )

    def confirm_question_pick(
        self,
        run_id: str,
        question_id: str,
        choice: str,
        user: str,
        message_ts: str,
        thread_ts: str,
    ) -> None:
        """Lock the question message + post thread confirmation."""
        self.app.client.chat_update(
            channel=self.channel,
            ts=message_ts,
            text=f"Question {question_id}: locked",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f":white_check_mark: *Question {question_id}* — `{choice}` chosen by <@{user}>",
                    },
                },
            ],
        )
        self.app.client.chat_postMessage(
            channel=self.channel,
            thread_ts=thread_ts,
            text=f"Recorded *{choice}* for `{run_id}` / `{question_id}`. Caller resuming.",
            unfurl_links=False,
            unfurl_media=False,
        )


# ----------------------------------------------------------------------------
# Decision file writer
# ----------------------------------------------------------------------------


def write_answer_file(
    run_dir: Path,
    question_id: str,
    choice: str,
    chosen_label: str,
    user_id: str,
    rationale: str = "",
) -> Path:
    """Write answer-r<N>.md after question button click.

    Unlike write_decision_file, the source question-r<N>.md is NOT removed —
    the answer file's existence is the satisfied-signal for both the CLI poll
    (pipeline_ask.py) and the listener's IdleMonitor.
    """
    n = question_id.lstrip("q")
    out = run_dir / f"answer-r{n}.md"
    now = datetime.now(timezone.utc).isoformat()
    qfile = run_dir / f"question-r{n}.md"
    qfm: dict[str, Any] = {}
    if qfile.exists():
        qfm, _ = parse_question_file(qfile)
    body = (
        "---\n"
        f"question_id: {question_id}\n"
        "verdict: answered\n"
        f"chosen_key: {choice}\n"
        f"chosen_label: {chosen_label}\n"
        "delivery_mode: slack\n"
        f"opened_at: {qfm.get('opened_at', 'null')}\n"
        f"answered_at: {now}\n"
        f"answered_by_slack_user: {user_id}\n"
        f"requesting_role: {qfm.get('requesting_role', 'unknown')}\n"
        "---\n\n"
        "## Notes\n"
        f"{rationale or '(no notes; chose via Slack button)'}\n\n"
        "## Source question\n"
        f"- Path: question-r{n}.md\n"
    )
    out.write_text(body)
    log.info("wrote answer file: %s", out)
    return out


def write_decision_file(
    run_dir: Path,
    decision_id: str,
    choice: str,
    user_id: str,
    rationale: str = "",
) -> Path:
    """Write decision-r<N>.md after button click."""
    rN = decision_id  # e.g. "d1" → file uses revision N from decision_id index
    # decision_id is d<N>; filename uses same N
    n = decision_id.lstrip("d")
    out = run_dir / f"decision-r{n}.md"
    now = datetime.now(timezone.utc).isoformat()

    awaiting = run_dir / f"awaiting-decision-r{n}.md"
    fm: dict[str, Any] = {}
    if awaiting.exists():
        fm = parse_awaiting(awaiting)

    body = f"""---
decision_id: {decision_id}
verdict: chosen
chosen_option: {choice}
delivery_mode: slack
issue_url: null
opened_at: {fm.get("opened_at", "null")}
decided_at: {now}
decided_by_slack_user: {user_id}
requesting_role: {fm.get("requesting_role", "unknown")}
options_source: {fm.get("options_source", "unknown")}
---

## Pick rationale
{rationale or "(no notes; chose via Slack button)"}

## Source options
- Path: options-r{n}.md
"""
    out.write_text(body)
    log.info("wrote decision file: %s", out)
    # Remove awaiting file to signal pipeline
    if awaiting.exists():
        awaiting.unlink()
    return out


# ----------------------------------------------------------------------------
# Watchdog handler
# ----------------------------------------------------------------------------


class AwaitingHandler(FileSystemEventHandler):
    def __init__(
        self,
        poster: SlackPoster,
        run_dir: Path,
        idle: IdleMonitor,
    ) -> None:
        self.poster = poster
        self.run_dir = run_dir
        self.idle = idle

    def on_created(self, event: Any) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        self._dispatch(path)

    def on_modified(self, event: Any) -> None:
        # Handle atomic-write rename-into-place
        if event.is_directory:
            return
        path = Path(event.src_path)
        self._dispatch(path)

    def on_deleted(self, event: Any) -> None:
        # Any tracked file removed/resolved → re-evaluate idle state.
        if event.is_directory:
            return
        name = Path(event.src_path).name
        if (
            AWAITING_RE.match(name)
            or QUESTION_RE.match(name)
            or name.startswith("answer-r")
        ):
            self.idle.tick()

    def _dispatch(self, path: Path) -> None:
        """Route inotify events by filename to decision or question handler."""
        m_aw = AWAITING_RE.match(path.name)
        if m_aw:
            self.idle.tick()
            self._handle(path, m_aw.group(1))
            return
        m_q = QUESTION_RE.match(path.name)
        if m_q:
            self.idle.tick()
            self._handle_question(path, m_q.group(1))
            return
        # answer-r<N>.md write satisfies a question; just re-tick idle.
        if path.name.startswith("answer-r"):
            self.idle.tick()

    def _handle(self, awaiting_path: Path, n: str) -> None:
        try:
            run_dir = awaiting_path.parent
            run_id = run_dir.name
            decision_id = f"d{n}"
            options_path = run_dir / f"options-r{n}.md"
            if not options_path.exists():
                log.warning("options file missing for %s, skipping", awaiting_path)
                return

            fm, options = parse_options(options_path)
            if not options:
                log.warning("no options parsed from %s", options_path)
                return
            topic = fm.get("topic", f"Decision {decision_id}")
            brief = _read_brief(run_dir)

            thread_ts = self.poster.ensure_thread(run_id, brief)
            self.poster.post_decision(run_id, decision_id, topic, options, thread_ts)
        except Exception:
            log.exception("failed to handle %s", awaiting_path)

    def _handle_question(self, question_path: Path, n: str) -> None:
        """Post a question-r<N>.md as a threaded Slack message with buttons.

        If the frontmatter declares `attachments:` (block list of paths), each
        file is uploaded into the thread *before* the button message so the
        viewer reads context first and then sees the buttons last.
        """
        try:
            run_dir = question_path.parent
            run_id = run_dir.name
            question_id = f"q{n}"
            # Skip if already answered (e.g. listener restarted after resolution).
            if (run_dir / f"answer-r{n}.md").exists():
                return
            fm, options = parse_question_file(question_path)
            if not options:
                log.warning("no options parsed from %s", question_path)
                return
            header = fm.get("header", "")
            prompt = fm.get("prompt", f"Question {question_id}")
            attachments = fm.get("attachments") or []
            brief = _read_brief(run_dir)
            thread_ts = self.poster.ensure_thread(run_id, brief)
            # Upload attachments first; collect permalinks for the link block
            # that goes inside the question button message.
            attachment_links: list[tuple[str, str]] = []
            if isinstance(attachments, list):
                for ap in attachments:
                    _, permalink, filename = self.poster.upload_attachment(
                        run_id, question_id, ap, thread_ts
                    )
                    if permalink and filename:
                        attachment_links.append((permalink, filename))
            self.poster.post_question(
                run_id, question_id, header, prompt, options, thread_ts,
                attachment_links=attachment_links,
            )
        except Exception:
            log.exception("failed to handle %s", question_path)


def _read_brief(run_dir: Path) -> str:
    brief = run_dir / "brief.md"
    if not brief.exists():
        return ""
    for line in brief.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("-"):
            return line[:200]
    return ""


# ----------------------------------------------------------------------------
# Entry
# ----------------------------------------------------------------------------


def load_project_config(project_path: Path) -> dict[str, Any]:
    """Load optional <project>/.pipeline/pipeline.toml. Missing file = empty dict.

    Channel + project_name resolution is handled in main() with precedence:
    pipeline.toml override → env SLACK_CHANNEL default → sync fallback.
    """
    cfg = project_path / ".pipeline" / "pipeline.toml"
    if not cfg.exists():
        return {}
    with cfg.open("rb") as fh:
        return tomllib.load(fh)


# load_env_file imported from _slack_env at top of file.
# Retained as local alias so existing internal references continue to work.
# The canonical implementation lives in _slack_env.py.


def write_pid_file(pid_path: Path) -> None:
    """Write current PID; register atexit removal."""
    pid_path.write_text(f"{os.getpid()}\n")
    import atexit
    atexit.register(lambda: pid_path.unlink(missing_ok=True))


class _SessionsWatcher(FileSystemEventHandler):
    """Watchdog handler: refresh routing index when slack.json files change."""

    def _maybe_refresh(self, event: Any) -> None:
        if Path(getattr(event, "src_path", "")).name == "slack.json":
            _rebuild_routing_index()

    def on_created(self, event: Any) -> None:
        self._maybe_refresh(event)

    def on_modified(self, event: Any) -> None:
        self._maybe_refresh(event)

    def on_deleted(self, event: Any) -> None:
        self._maybe_refresh(event)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pipeline Slack decision listener (Socket Mode)."
    )
    parser.add_argument("project_path", help="Project root containing .pipeline/")
    parser.add_argument(
        "run_id", help="Pipeline run id (artifact-slug; matches run dir name)"
    )
    parser.add_argument(
        "--session-thread",
        default=None,
        metavar="CHANNEL:THREAD_TS",
        help=(
            "When set, override per-run thread routing with the supplied "
            "session-bound channel + thread_ts."
        ),
    )
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    project_path = Path(args.project_path).expanduser().resolve()
    if not project_path.is_dir():
        raise SystemExit(f"not a directory: {project_path}")

    run_dir = project_path / ".pipeline" / "runs" / args.run_id
    if not run_dir.is_dir():
        raise SystemExit(f"run dir missing: {run_dir}")

    # Load tokens from env file if not already injected.
    env_path = default_env_path()
    load_env_file(env_path)

    cfg = load_project_config(project_path)
    slack_cfg = cfg.get("slack", {}) if isinstance(cfg, dict) else {}

    # Channel resolution: per-project override (pipeline.toml) → env default.
    project_channel = slack_cfg.get("channel") or os.environ.get("SLACK_CHANNEL")
    if not project_channel:
        raise SystemExit(
            "no Slack channel configured: set SLACK_CHANNEL in "
            f"{env_path} or [slack].channel in "
            f"{project_path}/.pipeline/pipeline.toml"
        )
    project_name = slack_cfg.get("project_name", project_path.name)

    bot_token = os.environ.get("SLACK_BOT_TOKEN")
    app_token = os.environ.get("SLACK_APP_TOKEN")
    if not bot_token or not app_token:
        raise SystemExit(
            f"SLACK_BOT_TOKEN and SLACK_APP_TOKEN required "
            f"(checked env + {env_path})"
        )
    allowed_users = {
        u.strip()
        for u in os.environ.get("SLACK_ALLOWED_USERS", "").split(",")
        if u.strip()
    }

    # Parse --session-thread flag: CHANNEL:THREAD_TS.
    session_thread: tuple[str, str] | None = None
    if args.session_thread:
        parts = args.session_thread.split(":", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise SystemExit(
                f"--session-thread must be CHANNEL:THREAD_TS, got: {args.session_thread!r}"
            )
        session_thread = (parts[0], parts[1])
        log.info("session-bound mode: channel=%s thread_ts=%s", parts[0], parts[1])

    # Effective channel: session-bound channel wins for all posts when in session mode.
    effective_channel = session_thread[0] if session_thread else project_channel

    # Per-run state + pid files.
    state_path = run_dir / "slack-state.json"
    pid_path = run_dir / "slack-listener.pid"
    write_pid_file(pid_path)

    # Project-wide root used only for resolving cross-listener click deliveries.
    runs_root = project_path / ".pipeline" / "runs"

    # B5: Boot-time orphan tmp cleanup + routing index build — only in session-bound mode.
    # In legacy (no --session-thread) mode, skip these: they require message.channels scope
    # and add recursive watchdog cost for users who never bound a session.
    from session_slack import SESSIONS_ROOT as _SESS_ROOT
    if session_thread is not None:
        for sdir in (_SESS_ROOT.glob("*/inbox") if _SESS_ROOT.is_dir() else []):
            _cleanup_orphan_tmps(sdir)
        _rebuild_routing_index()

    app = App(token=bot_token)
    state = State(state_path)
    poster = SlackPoster(
        app,
        state,
        effective_channel,
        project_name,
        project_path,
        session_thread=session_thread,
        project_channel=project_channel,
        run_dir=run_dir,
    )
    idle_monitor = IdleMonitor(run_dir, pid_path=pid_path)

    # Button click handlers (one per option letter; bolt requires action_id match)
    def on_pick(ack: Any, body: dict[str, Any], client: Any) -> None:
        ack()
        try:
            user_id = body["user"]["id"]
            if allowed_users and user_id not in allowed_users:
                client.chat_postEphemeral(
                    channel=body["channel"]["id"],
                    user=user_id,
                    text="You are not authorized to pick for this pipeline.",
                )
                return
            value = body["actions"][0]["value"]
            run_id, decision_id, choice = value.split("|")
            run_dir = runs_root / run_id
            if not run_dir.is_dir():
                client.chat_postEphemeral(
                    channel=body["channel"]["id"],
                    user=user_id,
                    text=f"Run dir missing: {run_id}",
                )
                return
            write_decision_file(run_dir, decision_id, choice, user_id)
            message_ts = body["message"]["ts"]
            thread_ts = body["message"].get("thread_ts", message_ts)
            poster.confirm_pick(
                run_id, decision_id, choice, user_id, message_ts, thread_ts
            )
            # Awaiting file just unlinked; re-evaluate idle state.
            idle_monitor.tick()
        except Exception:
            log.exception("pick handler failed")

    for letter in "ABCD":
        app.action(f"decision_pick_{letter}")(on_pick)

    def on_pick_question(ack: Any, body: dict[str, Any], client: Any) -> None:
        """Handle question button click; writes answer-r<N>.md."""
        ack()
        try:
            user_id = body["user"]["id"]
            if allowed_users and user_id not in allowed_users:
                client.chat_postEphemeral(
                    channel=body["channel"]["id"],
                    user=user_id,
                    text="You are not authorized to answer for this pipeline.",
                )
                return
            value = body["actions"][0]["value"]
            run_id, question_id, choice = value.split("|")
            run_dir_q = runs_root / run_id
            if not run_dir_q.is_dir():
                client.chat_postEphemeral(
                    channel=body["channel"]["id"],
                    user=user_id,
                    text=f"Run dir missing: {run_id}",
                )
                return
            # Resolve chosen label by re-reading question file.
            n = question_id.lstrip("q")
            qfile = run_dir_q / f"question-r{n}.md"
            chosen_label = choice
            if qfile.exists():
                _, options = parse_question_file(qfile)
                for opt in options:
                    if opt["key"] == choice:
                        chosen_label = opt["title"]
                        break
            write_answer_file(run_dir_q, question_id, choice, chosen_label, user_id)
            message_ts = body["message"]["ts"]
            thread_ts = body["message"].get("thread_ts", message_ts)
            poster.confirm_question_pick(
                run_id, question_id, choice, user_id, message_ts, thread_ts
            )
            idle_monitor.tick()
        except Exception:
            log.exception("question pick handler failed")

    for letter in "ABCD":
        app.action(f"question_pick_{letter}")(on_pick_question)

    # B5: Inbound thread-message handler + sessions watchdog — session-bound mode only.
    # Gating on session_thread prevents registering message.channels scope requirement
    # and recursive watchdog cost for users in legacy (no-bind) mode.
    if session_thread is not None:
        _session_channel_id = session_thread[0]

        @app.event("message")
        def on_thread_message(event: dict[str, Any], body: dict[str, Any]) -> None:  # noqa: ARG001
            """Capture thread replies to known session threads (session-bound mode only).

            M3/M4: verify event channel matches the bound session channel before
            writing inbox, preventing cross-channel poisoning.
            """
            if event.get("subtype") is not None:
                return  # skip edits, joins, file shares, thread_broadcast
            thread_ts = event.get("thread_ts")
            if not thread_ts:
                return  # top-level message, not a reply
            # M3/M4: channel verification — must match session-bound channel.
            event_channel = event.get("channel", "")
            if event_channel and event_channel != _session_channel_id:
                log.debug(
                    "inbox drop: event channel %s != session channel %s",
                    event_channel, _session_channel_id,
                )
                return
            with _ROUTING_LOCK:
                sid = _THREAD_TO_SID.get(thread_ts)
                if sid is None:
                    return
                inbox = _SID_TO_INBOX.get(sid)
            if inbox is None:
                return
            _write_inbox_file(inbox, event)

    # Filesystem watch — scoped to this run only.
    handler = AwaitingHandler(poster, run_dir, idle_monitor)
    observer = Observer()
    observer.schedule(handler, str(run_dir), recursive=False)
    # B5: Also watch ~/.claude/sessions/ for routing index refresh — session-bound only.
    from session_slack import SESSIONS_ROOT as _SESS_ROOT_OBS
    if session_thread is not None:
        sessions_watcher = _SessionsWatcher()
        if _SESS_ROOT_OBS.is_dir():
            observer.schedule(sessions_watcher, str(_SESS_ROOT_OBS), recursive=True)
    observer.start()
    log.info(
        "watching %s | run=%s | channel=%s | project=%s | session_bound=%s",
        run_dir, args.run_id, effective_channel, project_name, session_thread is not None,
    )

    # Sweep existing awaiting files at startup (orchestrator may have written
    # the awaiting file before spawning us).
    for p in run_dir.glob("awaiting-decision-r*.md"):
        m = AWAITING_RE.match(p.name)
        if m:
            handler._handle(p, m.group(1))
    # Sweep existing question files at startup (CLI may have written the
    # question file before spawning us; same race window as decisions).
    for p in run_dir.glob("question-r*.md"):
        m = QUESTION_RE.match(p.name)
        if m:
            handler._handle_question(p, m.group(1))

    # Initial idle evaluation: if orchestrator's spawn raced with awaiting-file
    # writes such that nothing is present, we exit after the grace window.
    idle_monitor.tick()

    try:
        SocketModeHandler(app, app_token).start()
    finally:
        observer.stop()
        observer.join()


if __name__ == "__main__":
    main()
