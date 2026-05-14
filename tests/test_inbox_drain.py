"""Tests for inbox_drain.py: list, consume idempotency, malformed file handling."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_PIPELINE_DIR = Path(__file__).parent.parent / ".claude" / "pipeline"
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

import inbox_drain  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_inbox_msg(inbox: Path, ts: str, user: str = "U001", text: str = "hello") -> Path:
    payload = {
        "session_id": "test-sid",
        "thread_ts": "111.222",
        "message_ts": ts,
        "user_id": user,
        "text": text,
        "received_at": "2026-05-14T12:00:00Z",
    }
    path = inbox / f"{ts}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# drain function
# ---------------------------------------------------------------------------


def test_drain_lists_messages(session_dir: Path, sid: str) -> None:
    inbox = session_dir / "inbox"
    _write_inbox_msg(inbox, "100.001", text="first")
    _write_inbox_msg(inbox, "100.002", text="second")

    from unittest.mock import patch
    with patch.object(inbox_drain, "SESSIONS_ROOT", session_dir.parent):
        rc = inbox_drain.drain(sid, consume=False, as_json=False)
    assert rc == 0


def test_drain_json_output(session_dir: Path, sid: str, capsys: pytest.CaptureFixture[str]) -> None:
    inbox = session_dir / "inbox"
    _write_inbox_msg(inbox, "200.001", text="hi")

    from unittest.mock import patch
    with patch.object(inbox_drain, "SESSIONS_ROOT", session_dir.parent):
        inbox_drain.drain(sid, consume=False, as_json=True)

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["sid"] == sid
    assert len(data["messages"]) == 1
    assert data["messages"][0]["content"]["text"] == "hi"


def test_drain_consume_moves_files(session_dir: Path, sid: str) -> None:
    inbox = session_dir / "inbox"
    msg = _write_inbox_msg(inbox, "300.001", text="consume me")

    from unittest.mock import patch
    with patch.object(inbox_drain, "SESSIONS_ROOT", session_dir.parent):
        inbox_drain.drain(sid, consume=True, as_json=False)

    # File should be moved to .consumed/.
    consumed = inbox / ".consumed" / "300.001.json"
    assert consumed.is_file()
    assert not msg.exists()


def test_drain_consume_idempotent(session_dir: Path, sid: str) -> None:
    """Consuming twice does not error — consumed dir already has the file."""
    inbox = session_dir / "inbox"
    _write_inbox_msg(inbox, "400.001")

    from unittest.mock import patch
    with patch.object(inbox_drain, "SESSIONS_ROOT", session_dir.parent):
        inbox_drain.drain(sid, consume=True, as_json=False)
        # Second drain: inbox is empty, no error.
        rc = inbox_drain.drain(sid, consume=True, as_json=False)
    assert rc == 0


def test_drain_empty_inbox_ok(session_dir: Path, sid: str) -> None:
    from unittest.mock import patch
    with patch.object(inbox_drain, "SESSIONS_ROOT", session_dir.parent):
        rc = inbox_drain.drain(sid, consume=False, as_json=True)
    assert rc == 0


def test_drain_malformed_file_skipped(
    session_dir: Path, sid: str, capsys: pytest.CaptureFixture[str]
) -> None:
    inbox = session_dir / "inbox"
    bad = inbox / "bad.json"
    bad.write_text("NOT JSON", encoding="utf-8")
    _write_inbox_msg(inbox, "500.001", text="good")

    from unittest.mock import patch
    with patch.object(inbox_drain, "SESSIONS_ROOT", session_dir.parent):
        rc = inbox_drain.drain(sid, consume=False, as_json=True)

    assert rc == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    # Good message present, bad file in errors.
    assert len(data["messages"]) == 1
    assert "errors" in data
    assert "bad.json" in data["errors"]


def test_drain_malformed_not_consumed(session_dir: Path, sid: str) -> None:
    """Malformed files are not moved to .consumed/ even with --consume."""
    inbox = session_dir / "inbox"
    bad = inbox / "bad2.json"
    bad.write_text("{bad json", encoding="utf-8")

    from unittest.mock import patch
    with patch.object(inbox_drain, "SESSIONS_ROOT", session_dir.parent):
        inbox_drain.drain(sid, consume=True, as_json=False)

    # Malformed file stays in inbox.
    assert bad.exists()
    consumed = inbox / ".consumed" / "bad2.json"
    assert not consumed.exists()


def test_drain_no_inbox_dir(tmp_path: Path) -> None:
    """Missing inbox dir is not an error."""
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    (sessions / "no-inbox-sid").mkdir()

    from unittest.mock import patch
    with patch.object(inbox_drain, "SESSIONS_ROOT", sessions):
        rc = inbox_drain.drain("no-inbox-sid", consume=False, as_json=True)
    assert rc == 0


# ---------------------------------------------------------------------------
# M2 — provenance markers in output
# ---------------------------------------------------------------------------


def test_drain_text_wraps_provenance(
    session_dir: Path, sid: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Text output wraps each message in <<<UNTRUSTED-SLACK-MESSAGE>>> markers (M2)."""
    inbox = session_dir / "inbox"
    _write_inbox_msg(inbox, "600.001", user="U001", text="hello attack")

    from unittest.mock import patch
    with patch.object(inbox_drain, "SESSIONS_ROOT", session_dir.parent):
        inbox_drain.drain(sid, consume=False, as_json=False)

    captured = capsys.readouterr()
    assert "<<<UNTRUSTED-SLACK-MESSAGE" in captured.out
    assert "<<<END-UNTRUSTED-SLACK-MESSAGE>>>" in captured.out
    assert "hello attack" in captured.out
    assert "id=600.001" in captured.out
    assert "user=U001" in captured.out


def test_drain_json_adds_provenance_field(
    session_dir: Path, sid: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """JSON output includes _provenance: untrusted-slack-user-content per message (M2)."""
    inbox = session_dir / "inbox"
    _write_inbox_msg(inbox, "700.001", text="injected content")

    from unittest.mock import patch
    with patch.object(inbox_drain, "SESSIONS_ROOT", session_dir.parent):
        inbox_drain.drain(sid, consume=False, as_json=True)

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert len(data["messages"]) == 1
    msg_content = data["messages"][0]["content"]
    assert msg_content.get("_provenance") == "untrusted-slack-user-content"


def test_drain_provenance_preserved_on_consume(session_dir: Path, sid: str) -> None:
    """Provenance field present even when --consume flag used."""
    inbox = session_dir / "inbox"
    _write_inbox_msg(inbox, "800.001", text="consume me")

    import io, contextlib
    from unittest.mock import patch
    buf = io.StringIO()
    with patch.object(inbox_drain, "SESSIONS_ROOT", session_dir.parent):
        with contextlib.redirect_stdout(buf):
            inbox_drain.drain(sid, consume=True, as_json=True)

    data = json.loads(buf.getvalue())
    assert data["messages"][0]["content"]["_provenance"] == "untrusted-slack-user-content"
