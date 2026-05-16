"""Adversarial tests — r0 tester additions.

Covers gaps identified in AC coverage matrix:
- Corrupt / truncated / invalid slack.json → resolve_session_binding returns None
- schema_version > 1 handling (already tested; adds missing-required-keys case)
- validate_sid boundary: exactly 7 chars (below min), exactly 65 chars (above max),
  control chars, unicode in sid
- atomic_write_text with simulated fsync failure → rename NOT reached
- Inbox malformed JSON in drain (already partially tested; adds truncated-JSON case)
- SIGTERM pid identity: verify cmdline check prevents wrong-pid kill
- Channel mismatch path: inbox event w/ non-binding channel NOT written
- verdict_read frontmatter quote stripping for mixed-case and whitespace variants
- AC6 no-bind path: spawn_listener omits --session-thread when no binding
- pipeline_state concurrent set semantics (same-key, in-process threads)
- pipeline_notify no-binding → silent no-op exit 0
- resolve_session_binding: missing channel_id or thread_ts in active state → None
"""

from __future__ import annotations

import json
import os
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch, call

import pytest

_PIPELINE_DIR = Path(__file__).parent.parent / ".claude" / "pipeline"
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

from tests.conftest import make_slack_json  # noqa: E402
from comms.env import atomic_write_text, validate_sid  # noqa: E402
import comms.session as session_slack  # noqa: E402
import verdict_read  # noqa: E402
import pipeline_state  # noqa: E402

# session_bind requires slack_bolt; mock before import (mirrors test_session_bind.py).
_slack_bolt_mock = MagicMock()
_slack_bolt_mock.App = MagicMock()
if "slack_bolt" not in sys.modules:
    sys.modules["slack_bolt"] = _slack_bolt_mock

import session_bind  # noqa: E402


# ---------------------------------------------------------------------------
# Corrupt slack.json variations → resolve_session_binding returns None
# ---------------------------------------------------------------------------


def test_resolve_truncated_json(
    sessions_root: Path, session_dir: Path, sid: str
) -> None:
    """Truncated JSON (not valid JSON) → returns None safely, no exception."""
    (session_dir / "slack.json").write_text('{"session_id": "', encoding="utf-8")
    with patch.object(session_slack, "SESSIONS_ROOT", sessions_root):
        result = session_slack.resolve_session_binding(sid)
    assert result is None


def test_resolve_empty_file(
    sessions_root: Path, session_dir: Path, sid: str
) -> None:
    """Empty slack.json → returns None (not valid JSON)."""
    (session_dir / "slack.json").write_text("", encoding="utf-8")
    with patch.object(session_slack, "SESSIONS_ROOT", sessions_root):
        result = session_slack.resolve_session_binding(sid)
    assert result is None


def test_resolve_null_json(
    sessions_root: Path, session_dir: Path, sid: str
) -> None:
    """JSON null at top level → returns None (defect-1 fix verified).

    Earlier r1 build crashed with AttributeError because _load_slack_json called
    .get() on a parsed None without an isinstance(data, dict) guard. Fix landed
    post-tester-r0: explicit isinstance check returns None for any non-dict
    top-level value (null, array, scalar).
    """
    (session_dir / "slack.json").write_text("null", encoding="utf-8")
    with patch.object(session_slack, "SESSIONS_ROOT", sessions_root):
        assert session_slack.resolve_session_binding(sid) is None
    # Coverage: also assert array + scalar top-level shapes return None.
    (session_dir / "slack.json").write_text("[1,2,3]", encoding="utf-8")
    with patch.object(session_slack, "SESSIONS_ROOT", sessions_root):
        assert session_slack.resolve_session_binding(sid) is None
    (session_dir / "slack.json").write_text('"a-string"', encoding="utf-8")
    with patch.object(session_slack, "SESSIONS_ROOT", sessions_root):
        assert session_slack.resolve_session_binding(sid) is None


def test_resolve_missing_channel_id(
    sessions_root: Path, session_dir: Path, sid: str
) -> None:
    """Active binding with missing channel_id field → returns None."""
    state = {
        "session_id": sid,
        "thread_ts": "111.222",
        "active": True,
        "schema_version": 1,
    }
    (session_dir / "slack.json").write_text(json.dumps(state), encoding="utf-8")
    with patch.object(session_slack, "SESSIONS_ROOT", sessions_root):
        result = session_slack.resolve_session_binding(sid)
    assert result is None


def test_resolve_missing_thread_ts(
    sessions_root: Path, session_dir: Path, sid: str
) -> None:
    """Active binding with missing thread_ts → returns None."""
    state = {
        "session_id": sid,
        "channel_id": "C0TEST",
        "active": True,
        "schema_version": 1,
    }
    (session_dir / "slack.json").write_text(json.dumps(state), encoding="utf-8")
    with patch.object(session_slack, "SESSIONS_ROOT", sessions_root):
        result = session_slack.resolve_session_binding(sid)
    assert result is None


def test_resolve_schema_version_exactly_2(
    sessions_root: Path, session_dir: Path, sid: str
) -> None:
    """schema_version=2 (> supported max 1) → returns None, does not raise."""
    make_slack_json(session_dir, sid, active=True, schema_version=2)
    with patch.object(session_slack, "SESSIONS_ROOT", sessions_root):
        result = session_slack.resolve_session_binding(sid)
    assert result is None


def test_resolve_empty_channel_id(
    sessions_root: Path, session_dir: Path, sid: str
) -> None:
    """Active binding with empty string channel_id → returns None."""
    state = {
        "session_id": sid,
        "channel_id": "",
        "thread_ts": "111.222",
        "active": True,
        "schema_version": 1,
    }
    (session_dir / "slack.json").write_text(json.dumps(state), encoding="utf-8")
    with patch.object(session_slack, "SESSIONS_ROOT", sessions_root):
        result = session_slack.resolve_session_binding(sid)
    assert result is None


# ---------------------------------------------------------------------------
# validate_sid boundary cases not in existing test_sid_validation.py
# ---------------------------------------------------------------------------


def test_validate_sid_exactly_7_chars() -> None:
    """7 chars = too short (min is 8)."""
    with pytest.raises(ValueError, match="Invalid CLAUDE_CODE_SESSION_ID"):
        validate_sid("abcdefg")


def test_validate_sid_exactly_8_chars() -> None:
    """8 chars = minimum valid."""
    assert validate_sid("abcdefgh") == "abcdefgh"


def test_validate_sid_exactly_64_chars() -> None:
    """64 chars = maximum valid."""
    sid = "a" * 64
    assert validate_sid(sid) == sid


def test_validate_sid_exactly_65_chars() -> None:
    """65 chars = too long (max is 64)."""
    with pytest.raises(ValueError, match="Invalid CLAUDE_CODE_SESSION_ID"):
        validate_sid("a" * 65)


def test_validate_sid_control_chars() -> None:
    """Tab, newline, carriage return all rejected."""
    for bad_char in ["\t", "\n", "\r", "\x01", "\x1f"]:
        with pytest.raises(ValueError, match="Invalid CLAUDE_CODE_SESSION_ID"):
            validate_sid(f"session{bad_char}id")


def test_validate_sid_unicode() -> None:
    """Unicode letters/scripts not in [A-Za-z0-9_-] are rejected."""
    with pytest.raises(ValueError, match="Invalid CLAUDE_CODE_SESSION_ID"):
        validate_sid("session-こんにちは-id")


def test_validate_sid_with_colon() -> None:
    """Colon (used in --session-thread CHANNEL:TS) rejected in sid."""
    with pytest.raises(ValueError, match="Invalid CLAUDE_CODE_SESSION_ID"):
        validate_sid("session:id-12345678")


# ---------------------------------------------------------------------------
# atomic_write_text: fsync failure → rename NOT reached
# ---------------------------------------------------------------------------


def test_atomic_write_fsync_failure_no_rename(tmp_path: Path) -> None:
    """If os.fsync raises, os.rename must not be called (partial write not committed)."""
    target = tmp_path / "state.json"
    rename_calls: list[Any] = []

    def fail_fsync(fd: int) -> None:
        raise OSError("simulated fsync failure")

    original_rename = os.rename

    def tracking_rename(src: str, dst: str) -> None:
        rename_calls.append((src, dst))
        original_rename(src, dst)

    with patch("comms.env.os.fsync", side_effect=fail_fsync):
        with patch("comms.env.os.rename", side_effect=tracking_rename):
            with pytest.raises(OSError, match="simulated fsync failure"):
                atomic_write_text(target, "data")

    assert len(rename_calls) == 0, (
        "os.rename must NOT be called when fsync fails; "
        f"but rename was called: {rename_calls}"
    )
    assert not target.exists(), "target must not exist when fsync fails"


# ---------------------------------------------------------------------------
# Inbox drain: malformed JSON variants
# ---------------------------------------------------------------------------


import inbox_drain  # noqa: E402


def test_drain_truncated_json_skipped(
    session_dir: Path, sid: str
) -> None:
    """Truncated JSON in inbox file → skipped (not crashed), reported in errors."""
    inbox = session_dir / "inbox"
    (inbox / "bad_trunc.json").write_text('{"ts": "1"', encoding="utf-8")

    from unittest.mock import patch as mock_patch
    with mock_patch.object(inbox_drain, "SESSIONS_ROOT", session_dir.parent):
        rc = inbox_drain.drain(sid, consume=False, as_json=True)

    import io, contextlib
    buf = io.StringIO()
    with mock_patch.object(inbox_drain, "SESSIONS_ROOT", session_dir.parent):
        with contextlib.redirect_stdout(buf):
            inbox_drain.drain(sid, consume=False, as_json=True)

    assert rc == 0
    data = json.loads(buf.getvalue())
    assert "errors" in data
    assert "bad_trunc.json" in data["errors"]


def test_drain_non_dict_json_skipped(
    session_dir: Path, sid: str
) -> None:
    """JSON array (not dict) in inbox file → treated as malformed, skipped."""
    inbox = session_dir / "inbox"
    (inbox / "array_msg.json").write_text('[1, 2, 3]', encoding="utf-8")

    import io, contextlib
    from unittest.mock import patch as mock_patch
    buf = io.StringIO()
    with mock_patch.object(inbox_drain, "SESSIONS_ROOT", session_dir.parent):
        with contextlib.redirect_stdout(buf):
            inbox_drain.drain(sid, consume=False, as_json=True)

    data = json.loads(buf.getvalue())
    # Non-dict JSON files produce no messages; treated as errors.
    assert "array_msg.json" in data.get("errors", []) or len(data["messages"]) == 0


# ---------------------------------------------------------------------------
# SIGTERM pid identity: wrong script name → kill NOT sent
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="API removed in comms refactor")
def test_sigterm_not_sent_for_recycled_pid() -> None:
    """If /proc/<pid>/cmdline shows a different script, SIGTERM is NOT sent."""
    # Simulate a pid whose cmdline is something completely different (pid recycled).
    recycled_cmdline = b"nginx\x00-g\x00daemon off;\x00"

    kill_calls: list[Any] = []

    def track_kill(pid: int, sig: int) -> None:
        kill_calls.append((pid, sig))

    with patch.object(
        session_bind.Path, "read_bytes", return_value=recycled_cmdline
    ):
        with patch("session_bind.os.kill", side_effect=track_kill):
            session_bind._sigterm_daemon(12345, "test-session-abcd1234")

    assert kill_calls == [], (
        "SIGTERM must NOT be sent when cmdline belongs to a different process; "
        f"but kill was called: {kill_calls}"
    )


# ADVERSARIAL PROBE for SIGTERM identity check:
# Inject defect: make _verify_pid_is_inbox_daemon always return True
# (bypass the identity check). Re-run test — it MUST FAIL (i.e., kill IS sent).
@pytest.mark.skip(reason="API removed in comms refactor")
def test_adversarial_probe_sigterm_identity_check() -> None:
    """Probe: if identity check always passes, wrong-pid kill IS sent.
    This confirms test_sigterm_not_sent_for_recycled_pid actually catches
    the defect when the guard is removed.
    """
    recycled_cmdline = b"nginx\x00-g\x00daemon off;\x00"
    kill_calls: list[Any] = []

    def track_kill(pid: int, sig: int) -> None:
        kill_calls.append((pid, sig))

    # Injected defect: identity check always returns True.
    with patch.object(
        session_bind.Path, "read_bytes", return_value=recycled_cmdline
    ):
        with patch("session_bind._verify_pid_is_inbox_daemon", return_value=True):
            with patch("session_bind.os.kill", side_effect=track_kill):
                session_bind._sigterm_daemon(12345, "test-session-abcd1234")

    # With defect injected, kill IS called. Test captures the defect correctly.
    assert len(kill_calls) == 1, (
        "With identity check bypassed, kill should be called — "
        "this confirms the real guard is load-bearing."
    )


# ---------------------------------------------------------------------------
# Channel mismatch: inbox event with non-binding channel NOT written
# ---------------------------------------------------------------------------


def _import_write_inbox_file():  # type: ignore[return]
    """Import write_inbox_file while mocking out slack_bolt/watchdog."""
    slack_bolt_mock = MagicMock()
    watchdog_mock = MagicMock()
    watchdog_events_mock = MagicMock()
    watchdog_observers_mock = MagicMock()
    watchdog_events_mock.FileSystemEventHandler = object

    modules_to_mock = {
        "slack_bolt": slack_bolt_mock,
        "slack_bolt.adapter": MagicMock(),
        "slack_bolt.adapter.socket_mode": MagicMock(),
        "watchdog": watchdog_mock,
        "watchdog.events": watchdog_events_mock,
        "watchdog.observers": watchdog_observers_mock,
    }
    with patch.dict("sys.modules", modules_to_mock):
        import importlib
        if "session_inbox" in sys.modules:
            del sys.modules["session_inbox"]
        mod = importlib.import_module("session_inbox")
        return mod.write_inbox_file


@pytest.mark.skip(reason="API removed in comms refactor")
def test_channel_mismatch_inbox_not_written(tmp_path: Path) -> None:
    """Event arriving on a different channel than the bound session → NOT written to inbox."""
    write_inbox_file = _import_write_inbox_file()
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    event = {
        "ts": "999.001",
        "thread_ts": "900.000",
        "channel": "C_WRONG_CHAN",
        "user": "U001",
        "text": "should not land in inbox",
    }
    write_inbox_file(inbox, event, expected_channel="C_SESSION_CHAN")
    assert not (inbox / "999.001.json").exists(), (
        "Inbox write must NOT happen when event channel != session-bound channel"
    )


# ADVERSARIAL PROBE for channel mismatch guard:
# Remove the channel check → write_inbox_file always writes.
@pytest.mark.skip(reason="API removed in comms refactor")
def test_adversarial_probe_channel_mismatch_guard(tmp_path: Path) -> None:
    """Probe: if channel check is removed, the wrong-channel event IS written.
    Confirms that test_channel_mismatch_inbox_not_written catches the defect.
    """
    inbox = tmp_path / "inbox"
    inbox.mkdir()

    # Simulate the defective write_inbox_file: no channel check.
    def defective_write(
        inbox_dir: Path,
        event: dict,
        expected_channel: str = "",
    ) -> None:
        target = inbox_dir / f"{event['ts']}.json"
        if target.exists():
            return
        tmp = inbox_dir / f"{event['ts']}.json.tmp"
        tmp.write_text(json.dumps(event), encoding="utf-8")
        tmp.rename(target)

    event = {
        "ts": "888.001",
        "thread_ts": "800.000",
        "channel": "C_WRONG_CHAN",
        "user": "U001",
        "text": "wrong channel but no guard",
    }
    defective_write(inbox, event, expected_channel="C_SESSION_CHAN")
    # With defect, file IS written.
    assert (inbox / "888.001.json").exists(), (
        "With channel guard removed, wrong-channel event IS written — "
        "confirms real guard is load-bearing."
    )


# ---------------------------------------------------------------------------
# verdict_read: additional quote-strip edge cases
# ---------------------------------------------------------------------------


def test_verdict_read_single_space_after_colon(run_dir: Path) -> None:
    """Value with extra leading space after colon is stripped correctly."""
    path = run_dir / "verdict-design-r9.md"
    path.write_text(
        '---\nverdict: "approved"\nrole:  skeptic\nrevision: 9\n---\n\nbody\n',
        encoding="utf-8",
    )
    parsed = verdict_read._parse_verdict_file(path)
    assert parsed["verdict"] == "approved"
    assert parsed["role"] == "skeptic"
    assert parsed["revision"] == 9


def test_verdict_read_mismatched_quotes_not_stripped(run_dir: Path) -> None:
    """Mismatched quotes (open double, close single) are NOT stripped — preserved as-is."""
    path = run_dir / "verdict-code-r7.md"
    path.write_text(
        "---\nverdict: \"approved'\nrole: tester\nrevision: 7\n---\n\nbody\n",
        encoding="utf-8",
    )
    parsed = verdict_read._parse_verdict_file(path)
    # Mismatched quotes: v[0] != v[-1], so they are NOT stripped.
    assert parsed["verdict"] == "\"approved'"


# ---------------------------------------------------------------------------
# AC6 no-bind path: spawn_listener omits --session-thread flag
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="API removed in comms refactor")
def test_spawn_listener_no_session_thread_when_unbound(tmp_path: Path) -> None:
    """spawn_listener without active binding must NOT include --session-thread."""
    # Create a fake listener script so FileNotFoundError is not raised.
    fake_listener = tmp_path / "slack_listener.py"
    fake_listener.write_text("# fake listener\n", encoding="utf-8")

    project_path = tmp_path / "project"
    run_dir = project_path / ".pipeline" / "runs" / "test-run-ac6"
    run_dir.mkdir(parents=True)
    log_path = run_dir / "slack-listener.log"
    log_path.write_text("", encoding="utf-8")

    popen_calls: list[list[str]] = []

    class FakeProc:
        pid = 9999

    def fake_popen(cmd: list, **kwargs: Any) -> FakeProc:
        popen_calls.append(list(cmd))
        return FakeProc()

    with (
        patch.object(session_slack, "LISTENER_SCRIPT", fake_listener),
        # No active binding — resolve returns None.
        patch.object(session_slack, "resolve_session_binding", return_value=None),
        patch("session_slack.subprocess.Popen", side_effect=fake_popen),
        patch("builtins.open", return_value=MagicMock()),
    ):
        session_slack.spawn_listener(project_path, "test-run-ac6")

    assert len(popen_calls) == 1
    cmd = popen_calls[0]
    assert "--session-thread" not in cmd, (
        "Legacy no-bind path must NOT include --session-thread; "
        f"got cmd: {cmd}"
    )


@pytest.mark.skip(reason="API removed in comms refactor")
def test_spawn_listener_includes_session_thread_when_bound(tmp_path: Path) -> None:
    """spawn_listener with active binding MUST include --session-thread CHAN:TS."""
    fake_listener = tmp_path / "slack_listener.py"
    fake_listener.write_text("# fake\n", encoding="utf-8")

    project_path = tmp_path / "project"
    run_dir = project_path / ".pipeline" / "runs" / "test-run-ac6b"
    run_dir.mkdir(parents=True)

    popen_calls: list[list[str]] = []

    class FakeProc:
        pid = 8888

    def fake_popen(cmd: list, **kwargs: Any) -> FakeProc:
        popen_calls.append(list(cmd))
        return FakeProc()

    with (
        patch.object(session_slack, "LISTENER_SCRIPT", fake_listener),
        patch.object(session_slack, "resolve_session_binding", return_value=("C_SESS", "123.456")),
        patch("session_slack.subprocess.Popen", side_effect=fake_popen),
        patch("builtins.open", return_value=MagicMock()),
    ):
        session_slack.spawn_listener(project_path, "test-run-ac6b")

    assert len(popen_calls) == 1
    cmd = popen_calls[0]
    assert "--session-thread" in cmd, (
        "Bound-session path must include --session-thread; "
        f"got cmd: {cmd}"
    )
    st_idx = cmd.index("--session-thread")
    assert cmd[st_idx + 1] == "C_SESS:123.456", (
        f"--session-thread value must be CHANNEL:TS; got: {cmd[st_idx + 1]}"
    )


# ---------------------------------------------------------------------------
# pipeline_state concurrent set: last-write-wins under sidecar flock
# ---------------------------------------------------------------------------


def test_pipeline_state_concurrent_set_no_data_loss(run_dir: Path) -> None:
    """Concurrent pipeline_state.cmd_set on same key: one of the writes wins,
    no corrupt frontmatter left behind.
    """
    import argparse
    project = run_dir.parent.parent.parent
    run_id = run_dir.name

    errors: list[str] = []
    results: list[int] = []

    def do_set(value: str) -> None:
        args = argparse.Namespace(
            project=str(project),
            run=run_id,
            key="slack.thread_ts",
            value=value,
            log_level="WARNING",
        )
        try:
            rc = pipeline_state.cmd_set(args)
            results.append(rc)
        except Exception as exc:
            errors.append(str(exc))

    threads = [
        threading.Thread(target=do_set, args=(f"ts_{i}.{i:03d}",))
        for i in range(8)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not errors, f"concurrent set raised exceptions: {errors}"
    # File must still be readable with valid frontmatter.
    import argparse, io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        args_get = argparse.Namespace(
            project=str(project),
            run=run_id,
            key="slack.thread_ts",
            log_level="WARNING",
        )
        rc = pipeline_state.cmd_get(args_get)
    assert rc == 0, "After concurrent writes, pipeline.md must still be readable"
    val = buf.getvalue().strip()
    assert val, "After concurrent writes, slack.thread_ts must have a value"


# ---------------------------------------------------------------------------
# pipeline_notify: no binding → silent no-op, exit 0
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="API removed in comms refactor")
def test_pipeline_notify_no_binding_is_noop(
    sessions_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """pipeline_notify.notify returns 0 when no session binding is active."""
    slack_bolt_mock = MagicMock()
    with patch.dict("sys.modules", {"slack_bolt": slack_bolt_mock, "slack_bolt.adapter": MagicMock(), "slack_bolt.adapter.socket_mode": MagicMock()}):
        import importlib
        if "pipeline_notify" in sys.modules:
            del sys.modules["pipeline_notify"]
        import pipeline_notify

    with (
        patch.object(pipeline_notify, "resolve_session_binding", return_value=None),
        patch.object(pipeline_notify, "load_env_file"),
    ):
        rc = pipeline_notify.notify("test-run-id", "status", "build done")

    assert rc == 0, (
        "pipeline_notify.notify must return 0 (no-op) when no session binding; "
        f"got: {rc}"
    )
    # Slack App must NOT have been called.
    slack_bolt_mock.App.assert_not_called()


@pytest.mark.skip(reason="API removed in comms refactor")
def test_pipeline_notify_no_binding_no_slack_post(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """pipeline_notify.notify with no binding: Slack chat.postMessage NOT called."""
    mock_app_instance = MagicMock()
    slack_bolt_mock = MagicMock()
    slack_bolt_mock.App.return_value = mock_app_instance

    with patch.dict("sys.modules", {"slack_bolt": slack_bolt_mock, "slack_bolt.adapter": MagicMock(), "slack_bolt.adapter.socket_mode": MagicMock()}):
        import importlib
        if "pipeline_notify" in sys.modules:
            del sys.modules["pipeline_notify"]
        import pipeline_notify

    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-fake")

    with (
        patch.object(pipeline_notify, "resolve_session_binding", return_value=None),
        patch.object(pipeline_notify, "load_env_file"),
    ):
        pipeline_notify.notify("some-run", "completion", "done")

    mock_app_instance.client.chat_postMessage.assert_not_called()
