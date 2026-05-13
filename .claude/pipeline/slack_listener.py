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
seconds. Pipeline re-spawns this process if a later decision point fires
in the same run.

Outbound-only: uses Socket Mode WebSocket. No inbound port. No public URL.

Usage:
    slack_listener.py <project-path> <run-id>

Environment (auto-loaded from ~/.claude/pipeline/slack.env.local if not in env;
override path via SLACK_ENV_FILE):
    SLACK_BOT_TOKEN     xoxb-... (chat:write, chat:write.public, reactions:write)
    SLACK_APP_TOKEN     xapp-... (connections:write)
    SLACK_ALLOWED_USERS comma-separated Slack user IDs allowed to click buttons
                        (empty = anyone in channel)

Per-project config: <project>/.pipeline/pipeline.toml
    [slack]
    channel = "C0123ABC"          # required, channel ID (not name)
    project_name = "myproject"    # optional, shown in parent msg

Per-run state: <run-dir>/slack-state.json (thread_ts, posted decision_ids).
Per-run PID:   <run-dir>/slack-listener.pid (written at start, removed at exit).
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
OPTIONS_RE = re.compile(r"^## Option ([A-D]): (.+)$")
TRADEOFF_RE = re.compile(r"^- \*\*Tradeoff:\*\* (.+)$")


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

    GRACE_SECONDS = 30

    def __init__(self, run_dir: Path, pid_path: Path | None = None) -> None:
        self.run_dir = run_dir
        self.pid_path = pid_path
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None

    def _count_awaiting(self) -> int:
        return sum(1 for _ in self.run_dir.glob("awaiting-decision-r*.md"))

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
    ) -> None:
        self.app = app
        self.state = state
        self.channel = channel
        self.project_name = project_name
        self.project_path = project_path

    def ensure_thread(self, run_id: str, brief: str) -> str:
        """Return thread_ts for run, posting parent message if first decision."""
        ts = self.state.get_thread_ts(run_id)
        if ts:
            return ts
        text = f":hourglass_flowing_sand: *Pipeline started* `{run_id}`\nProject: `{self.project_name}`"
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

        blocks: list[dict[str, Any]] = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Decision {decision_id}*: {topic}",
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
            text=f"Decision {decision_id}: {topic}",
            blocks=blocks,
            unfurl_links=False,
            unfurl_media=False,
        )
        ts = resp["ts"]
        self.state.mark_posted(decision_key, ts, self.channel)
        log.info("posted decision %s ts=%s", decision_key, ts)
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


# ----------------------------------------------------------------------------
# Decision file writer
# ----------------------------------------------------------------------------


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
        m = AWAITING_RE.match(path.name)
        if not m:
            return
        # New awaiting file landed → cancel any scheduled idle exit.
        self.idle.tick()
        self._handle(path, m.group(1))

    def on_modified(self, event: Any) -> None:
        # Handle atomic-write rename-into-place
        if event.is_directory:
            return
        path = Path(event.src_path)
        m = AWAITING_RE.match(path.name)
        if not m:
            return
        self.idle.tick()
        self._handle(path, m.group(1))

    def on_deleted(self, event: Any) -> None:
        # Awaiting file removed (decision resolved); re-evaluate idle state.
        if event.is_directory:
            return
        path = Path(event.src_path)
        if not AWAITING_RE.match(path.name):
            return
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


def load_env_file(path: Path) -> None:
    """Populate os.environ from a KEY=VAL env file. Existing env wins.

    Tolerates: blank lines, `#` comments, `export KEY=VAL`, quoted values
    (single or double, stripped). Does not perform shell interpolation.
    """
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        if key and key not in os.environ:
            os.environ[key] = val


def write_pid_file(pid_path: Path) -> None:
    """Write current PID; register atexit removal."""
    pid_path.write_text(f"{os.getpid()}\n")
    import atexit
    atexit.register(lambda: pid_path.unlink(missing_ok=True))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_path", help="Project root containing .pipeline/")
    parser.add_argument("run_id", help="Pipeline run id (artifact-slug; matches run dir name)")
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
    env_path = Path(
        os.environ.get("SLACK_ENV_FILE", "~/.claude/pipeline/slack.env.local")
    ).expanduser()
    load_env_file(env_path)

    cfg = load_project_config(project_path)
    slack_cfg = cfg.get("slack", {}) if isinstance(cfg, dict) else {}

    # Channel resolution: per-project override (pipeline.toml) → env default.
    channel = slack_cfg.get("channel") or os.environ.get("SLACK_CHANNEL")
    if not channel:
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
        u.strip() for u in os.environ.get("SLACK_ALLOWED_USERS", "").split(",") if u.strip()
    }

    # Per-run state + pid files.
    state_path = run_dir / "slack-state.json"
    pid_path = run_dir / "slack-listener.pid"
    write_pid_file(pid_path)

    # Project-wide root used only for resolving cross-listener click deliveries.
    # (Slack Socket Mode load-balances clicks across all listeners on the same
    # app; any listener may receive a button event for another listener's run.
    # The run-id in the button value lets us resolve the correct run dir.)
    runs_root = project_path / ".pipeline" / "runs"

    app = App(token=bot_token)
    state = State(state_path)
    poster = SlackPoster(app, state, channel, project_name, project_path)
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

    # Filesystem watch — scoped to this run only.
    handler = AwaitingHandler(poster, run_dir, idle_monitor)
    observer = Observer()
    observer.schedule(handler, str(run_dir), recursive=False)
    observer.start()
    log.info(
        "watching %s | run=%s | channel=%s | project=%s",
        run_dir, args.run_id, channel, project_name,
    )

    # Sweep existing awaiting files at startup (orchestrator may have written
    # the awaiting file before spawning us).
    for p in run_dir.glob("awaiting-decision-r*.md"):
        m = AWAITING_RE.match(p.name)
        if m:
            handler._handle(p, m.group(1))

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
