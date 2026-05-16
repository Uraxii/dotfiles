"""Tests for H1 — sid validation rejects path-traversal and malformed values."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_PIPELINE_DIR = Path(__file__).parent.parent / ".claude" / "pipeline"
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

from comms.env import validate_sid  # noqa: E402


# ---------------------------------------------------------------------------
# Valid sids
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("sid", [
    "abcdefgh",                                   # 8 chars — min valid
    "ABCDEFGH12345678",                           # mixed case + digits
    "my-session-id-1234",                         # hyphens allowed
    "my_session_id_5678",                         # underscores allowed
    "a" * 64,                                     # 64 chars — max valid
    "test-session-deadbeef-1234-5678-abcd-0001",  # UUID-like shape
])
def test_valid_sid_passes(sid: str) -> None:
    assert validate_sid(sid) == sid


# ---------------------------------------------------------------------------
# Invalid sids — must raise ValueError
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("sid", [
    "",                             # empty
    "short",                        # 5 chars — too short
    "a" * 65,                       # 65 chars — too long
    "../",                          # path-traversal prefix
    "../../etc/cron.d/x",           # path-traversal
    "..",                           # dot-dot
    "/etc/passwd",                  # absolute path
    "session id",                   # space not allowed
    "session\x00id",                # null byte
    "session!id",                   # special char !
    "session@host",                 # special char @
    "session/inbox",                # slash not allowed
    "session\\path",                # backslash not allowed
])
def test_invalid_sid_raises(sid: str) -> None:
    with pytest.raises(ValueError, match="Invalid CLAUDE_CODE_SESSION_ID"):
        validate_sid(sid)


# ---------------------------------------------------------------------------
# Integration: inbox_drain._get_sid rejects bad sids
# ---------------------------------------------------------------------------


def test_inbox_drain_rejects_path_traversal(monkeypatch: pytest.MonkeyPatch) -> None:
    """_get_sid calls validate_sid; bad sid → sys.exit(1)."""
    import inbox_drain  # type: ignore[import]
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "../../etc/passwd")
    with pytest.raises(SystemExit) as exc_info:
        inbox_drain._get_sid(None)
    assert exc_info.value.code == 1


def test_inbox_drain_accepts_valid_sid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "valid-session-id-1234")
    import inbox_drain  # type: ignore[import]
    result = inbox_drain._get_sid(None)
    assert result == "valid-session-id-1234"
