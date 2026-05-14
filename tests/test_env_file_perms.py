"""Tests for H2 — load_env_file refuses files with loose permissions."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

_PIPELINE_DIR = Path(__file__).parent.parent / ".claude" / "pipeline"
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

from _slack_env import load_env_file  # noqa: E402


def _write_env(path: Path, content: str = "KEY=value\n") -> None:
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Mode 600 — should load OK
# ---------------------------------------------------------------------------


def test_load_mode_600(tmp_path: Path) -> None:
    env = tmp_path / "slack.env.local"
    _write_env(env, "TESTKEY_H2A=hello\n")
    env.chmod(0o600)
    load_env_file(env)
    assert os.environ.get("TESTKEY_H2A") == "hello"


# ---------------------------------------------------------------------------
# Mode 644 — group-readable: should raise PermissionError
# ---------------------------------------------------------------------------


def test_refuse_mode_644(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = tmp_path / "slack.env.local"
    _write_env(env, "TESTKEY_H2B=secret\n")
    env.chmod(0o644)
    monkeypatch.delenv("SLACK_ENV_FORCE_LOAD", raising=False)
    with pytest.raises(PermissionError, match="too open"):
        load_env_file(env)


# ---------------------------------------------------------------------------
# Mode 664 — group-writable: should raise
# ---------------------------------------------------------------------------


def test_refuse_mode_664(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = tmp_path / "slack.env.local"
    _write_env(env)
    env.chmod(0o664)
    monkeypatch.delenv("SLACK_ENV_FORCE_LOAD", raising=False)
    with pytest.raises(PermissionError):
        load_env_file(env)


# ---------------------------------------------------------------------------
# SLACK_ENV_FORCE_LOAD=1 — override: should load despite loose perms
# ---------------------------------------------------------------------------


def test_force_load_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = tmp_path / "slack.env.local"
    _write_env(env, "TESTKEY_H2C=forced\n")
    env.chmod(0o644)
    monkeypatch.setenv("SLACK_ENV_FORCE_LOAD", "1")
    load_env_file(env)
    assert os.environ.get("TESTKEY_H2C") == "forced"


# ---------------------------------------------------------------------------
# Mode 700 directory-only restriction (700 on file = 600 effective)
# ---------------------------------------------------------------------------


def test_load_mode_400(tmp_path: Path) -> None:
    """Read-only file (no write bits) should still load if other bits clear."""
    env = tmp_path / "slack.env.local"
    _write_env(env, "TESTKEY_H2D=ro\n")
    env.chmod(0o400)
    load_env_file(env)
    # 0o400 has no group/other bits set — should succeed.
    assert os.environ.get("TESTKEY_H2D") == "ro"
