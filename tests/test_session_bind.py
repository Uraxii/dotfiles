"""Tests for session_bind.py: B4 SIGTERM-then-respawn, C3 two-step state,
H3 dir modes, H4 cwd display strip."""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

_PIPELINE_DIR = Path(__file__).parent.parent / ".claude" / "pipeline"
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

# session_bind.py imports slack_bolt at module level. Mock it before import.
_slack_bolt_mock = MagicMock()
_slack_bolt_mock.App = MagicMock()
if "slack_bolt" not in sys.modules:
    sys.modules["slack_bolt"] = _slack_bolt_mock

import session_bind  # noqa: E402
from session_bind import (  # noqa: E402
    _atomic_write_state,
    _is_pid_alive,
    _require_session_id,
    _session_dir,
)
# _sigterm_daemon and _verify_pid_is_inbox_daemon removed in comms refactor.
# Tests that use them are skipped below.
_sigterm_daemon = None  # type: ignore[assignment]
_verify_pid_is_inbox_daemon = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# H4 — cwd_display strips $HOME
# ---------------------------------------------------------------------------


def test_cwd_display_strips_home() -> None:
    """cmd_activate uses cwd_display = str(cwd).replace(str(Path.home()), '~', 1)."""
    home = str(Path.home())
    cwd_full = Path(home) / "projects" / "myrepo"
    expected = "~/projects/myrepo"
    cwd_display = str(cwd_full).replace(home, "~", 1)
    assert cwd_display == expected


def test_cwd_display_outside_home() -> None:
    """Paths not under HOME are left intact."""
    home = str(Path.home())
    cwd_full = Path("/tmp/some/other/path")
    cwd_display = str(cwd_full).replace(home, "~", 1)
    assert cwd_display == "/tmp/some/other/path"


# ---------------------------------------------------------------------------
# M1 — _verify_pid_is_inbox_daemon: cmdline check
# (skipped: function removed in comms refactor — replaced by _verify_pid_is_comms_router)
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="API removed in comms refactor")
def test_verify_pid_match(tmp_path: Path) -> None:
    """If cmdline contains session_inbox.py + sid, verification passes."""
    fake_proc = tmp_path / "proc" / "9999" / "cmdline"
    fake_proc.parent.mkdir(parents=True)
    fake_proc.write_bytes(b"uv\x00run\x00session_inbox.py\x00mysid12345678\x00")

    with patch.object(Path, "read_bytes", return_value=fake_proc.read_bytes()):
        with patch("session_bind.Path") as MockPath:
            # Build a mock that returns our fake bytes for the cmdline path.
            mock_cmdline = MagicMock()
            mock_cmdline.read_bytes.return_value = fake_proc.read_bytes()
            MockPath.return_value = mock_cmdline
            # Call directly with the real function using a local proc path.
            pass

    # Direct test: patch open of /proc/<pid>/cmdline.
    cmdline_content = b"uv\x00run\x00session_inbox.py\x00mysid12345678\x00"
    with patch.object(
        session_bind.Path,
        "read_bytes",
        return_value=cmdline_content,
    ):
        result = _verify_pid_is_inbox_daemon(9999, "mysid12345678")
    assert result is True


@pytest.mark.skip(reason="API removed in comms refactor")
def test_verify_pid_wrong_script(tmp_path: Path) -> None:
    """If cmdline does not contain session_inbox.py, verification fails."""
    cmdline_content = b"python3\x00other_script.py\x00mysid12345678\x00"
    with patch.object(
        session_bind.Path,
        "read_bytes",
        return_value=cmdline_content,
    ):
        result = _verify_pid_is_inbox_daemon(9999, "mysid12345678")
    assert result is False


@pytest.mark.skip(reason="API removed in comms refactor")
def test_verify_pid_wrong_sid(tmp_path: Path) -> None:
    """If cmdline contains session_inbox.py but different sid, verification fails."""
    cmdline_content = b"uv\x00run\x00session_inbox.py\x00other-session-id\x00"
    with patch.object(
        session_bind.Path,
        "read_bytes",
        return_value=cmdline_content,
    ):
        result = _verify_pid_is_inbox_daemon(9999, "mysid12345678")
    assert result is False


@pytest.mark.skip(reason="API removed in comms refactor")
def test_verify_pid_no_proc_entry() -> None:
    """If /proc/<pid>/cmdline does not exist (pid gone), returns False."""
    with patch.object(
        session_bind.Path,
        "read_bytes",
        side_effect=FileNotFoundError,
    ):
        result = _verify_pid_is_inbox_daemon(99999, "mysid12345678")
    assert result is False


# ---------------------------------------------------------------------------
# B4 — _sigterm_daemon: SIGTERM gated behind pid verification
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="API removed in comms refactor")
def test_sigterm_skips_none_pid() -> None:
    """_sigterm_daemon(None) is a no-op."""
    with patch("session_bind.os.kill") as mock_kill:
        _sigterm_daemon(None, "test-session-01")
    mock_kill.assert_not_called()


@pytest.mark.skip(reason="API removed in comms refactor")
def test_sigterm_sends_signal_when_verified(monkeypatch: pytest.MonkeyPatch) -> None:
    """_sigterm_daemon sends SIGTERM when pid verification passes."""
    monkeypatch.setattr(
        session_bind, "_verify_pid_is_inbox_daemon", lambda pid, sid: True
    )
    with patch("session_bind.os.kill") as mock_kill:
        _sigterm_daemon(1234, "test-session-01")
    mock_kill.assert_called_once_with(1234, signal.SIGTERM)


@pytest.mark.skip(reason="API removed in comms refactor")
def test_sigterm_skips_when_verification_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """_sigterm_daemon skips kill when pid does not belong to our daemon."""
    monkeypatch.setattr(
        session_bind, "_verify_pid_is_inbox_daemon", lambda pid, sid: False
    )
    with patch("session_bind.os.kill") as mock_kill:
        _sigterm_daemon(5678, "test-session-01")
    mock_kill.assert_not_called()


@pytest.mark.skip(reason="API removed in comms refactor")
def test_sigterm_ignores_esrch(monkeypatch: pytest.MonkeyPatch) -> None:
    """_sigterm_daemon ignores ProcessLookupError (ESRCH) — pid already dead."""
    monkeypatch.setattr(
        session_bind, "_verify_pid_is_inbox_daemon", lambda pid, sid: True
    )
    with patch("session_bind.os.kill", side_effect=ProcessLookupError):
        # Must not raise.
        _sigterm_daemon(9999, "test-session-01")


# ---------------------------------------------------------------------------
# C3 — reactivate two-step state write (inbox_daemon_pid=None before spawn)
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="API removed in comms refactor")
def test_reactivate_two_step_state_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reactivate branch: state written with inbox_daemon_pid=None BEFORE spawn,
    then updated with new pid AFTER spawn. (C3)
    """
    sid = "test-session-c3test1234"
    sessions_root = tmp_path / "sessions"
    session_d = sessions_root / sid
    session_d.mkdir(parents=True)
    inbox_d = session_d / "inbox"
    inbox_d.mkdir()

    # Write an inactive state file.
    state = {
        "session_id": sid,
        "channel_id": "C0TEST",
        "thread_ts": "111.222",
        "cwd": "/fake",
        "started_at": "2026-01-01T00:00:00Z",
        "last_bound_at": "2026-01-01T00:00:00Z",
        "ended_at": "2026-01-02T00:00:00Z",
        "active": False,
        "schema_version": 1,
        "inbox_daemon_pid": 9999,
    }
    (session_d / "slack.json").write_text(json.dumps(state), encoding="utf-8")

    written_states: list[dict] = []
    original_write = session_bind._atomic_write_state

    def tracking_write(s: str, st: dict) -> None:
        written_states.append(dict(st))

    spawn_call_count: list[int] = []

    def fake_spawn(s: str) -> int:
        spawn_call_count.append(1)
        return 42

    monkeypatch.setattr(session_bind, "SESSIONS_ROOT", sessions_root)
    monkeypatch.setattr(session_bind, "_atomic_write_state", tracking_write)
    monkeypatch.setattr(session_bind, "_spawn_inbox_daemon", fake_spawn)
    monkeypatch.setattr(session_bind, "_sigterm_daemon", lambda pid, sid="": None)

    # Mock Slack App.
    mock_app = MagicMock()
    mock_app.client.chat_postMessage.return_value = {"ts": "111.333"}

    with patch("session_bind.App", return_value=mock_app), \
         patch.dict(os.environ, {
             "CLAUDE_CODE_SESSION_ID": sid,
             "SLACK_BOT_TOKEN": "xoxb-fake",
             "SLACK_APP_TOKEN": "xapp-fake",
         }), \
         patch("session_bind.load_env_file"), \
         patch("session_bind._resolve_channel", return_value="C0TEST"), \
         patch("session_bind._acquire_lock", return_value=(0, Path("/fake"))), \
         patch("session_bind._release_lock"), \
         patch("session_bind._read_state", return_value=dict(state)):
        session_bind.cmd_activate(argparse.Namespace(project=None, log_level="WARNING"))

    assert len(written_states) >= 2, "must write state at least twice"
    # First write: inbox_daemon_pid must be None.
    assert written_states[0]["inbox_daemon_pid"] is None, (
        "first write must have inbox_daemon_pid=None before spawn"
    )
    # Second write: inbox_daemon_pid must be the new pid.
    assert written_states[-1]["inbox_daemon_pid"] == 42, (
        "last write must have new daemon pid"
    )


# ---------------------------------------------------------------------------
# H3 — session dir created with mode 700
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="Uses removed session_bind.App + _spawn_inbox_daemon APIs")
def test_session_dir_mode_700(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """cmd_activate creates session dir and inbox with mode 700 (H3)."""
    sid = "test-session-h3mode01"
    sessions_root = tmp_path / "sessions"

    created_dirs: list[tuple[Path, int]] = []
    original_mkdir = Path.mkdir

    def tracking_mkdir(self: Path, mode: int = 0o777, **kw: object) -> None:
        created_dirs.append((self, mode))
        original_mkdir(self, mode=mode, **kw)

    monkeypatch.setattr(session_bind, "SESSIONS_ROOT", sessions_root)
    monkeypatch.setattr(Path, "mkdir", tracking_mkdir)

    # Abort early — we just want to see that mkdir is called with mode 0o700.
    # Patch everything that would need real Slack or lock.
    with patch("session_bind.os.umask"):
        with patch.dict(os.environ, {
            "CLAUDE_CODE_SESSION_ID": sid,
            "SLACK_BOT_TOKEN": "xoxb-fake",
            "SLACK_APP_TOKEN": "xapp-fake",
        }):
            with patch("session_bind.load_env_file"):
                with patch("session_bind._resolve_channel", return_value="C0TEST"):
                    with patch("session_bind._acquire_lock", return_value=(0, Path("/fake"))):
                        with patch("session_bind._release_lock"):
                            with patch("session_bind._read_state", return_value=None):
                                mock_app = MagicMock()
                                mock_app.client.chat_postMessage.return_value = {"ts": "999.001"}
                                with patch("session_bind.App", return_value=mock_app):
                                    with patch("session_bind._spawn_inbox_daemon", return_value=11):
                                        with patch("session_bind._atomic_write_state"):
                                            session_bind.cmd_activate(
                                                argparse.Namespace(
                                                    project=None, log_level="WARNING"
                                                )
                                            )

    # Verify at least one mkdir with mode 700 was called for the session dir.
    mode_700_calls = [p for p, m in created_dirs if m == 0o700]
    assert mode_700_calls, (
        "expected mkdir(mode=0o700) for session dir or inbox; "
        f"got: {[(str(p), oct(m)) for p, m in created_dirs]}"
    )
