"""Tests for B6 — atomic_write_text fsyncs tmp and parent dir before rename."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import call, patch

import pytest

_PIPELINE_DIR = Path(__file__).parent.parent / ".claude" / "pipeline"
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

from comms.env import atomic_write_text  # noqa: E402


def test_atomic_write_creates_file(tmp_path: Path) -> None:
    target = tmp_path / "output.txt"
    atomic_write_text(target, "hello world")
    assert target.read_text(encoding="utf-8") == "hello world"


def test_atomic_write_no_tmp_remains(tmp_path: Path) -> None:
    target = tmp_path / "state.json"
    atomic_write_text(target, '{"key": "value"}')
    tmp = Path(str(target) + ".tmp")
    assert not tmp.exists()


def test_atomic_write_mode(tmp_path: Path) -> None:
    target = tmp_path / "secret.json"
    atomic_write_text(target, "data", mode=0o600)
    st = target.stat()
    assert (st.st_mode & 0o777) == 0o600


def test_atomic_write_fsync_called(tmp_path: Path) -> None:
    """Verify os.fsync is called at least once during an atomic write."""
    target = tmp_path / "pipeline.md"
    fsync_calls: list[int] = []

    real_fsync = os.fsync

    def tracking_fsync(fd: int) -> None:
        fsync_calls.append(fd)
        real_fsync(fd)

    with patch("comms.env.os.fsync", side_effect=tracking_fsync):
        atomic_write_text(target, "content")

    # At minimum the tmp file fd should be fsynced.
    assert len(fsync_calls) >= 1


def test_atomic_write_overwrites_existing(tmp_path: Path) -> None:
    target = tmp_path / "data.txt"
    target.write_text("old", encoding="utf-8")
    atomic_write_text(target, "new")
    assert target.read_text(encoding="utf-8") == "new"


def test_atomic_write_unicode(tmp_path: Path) -> None:
    target = tmp_path / "unicode.txt"
    atomic_write_text(target, "こんにちは")
    assert target.read_text(encoding="utf-8") == "こんにちは"


def test_pipeline_state_atomic_write_uses_helper(tmp_path: Path) -> None:
    """pipeline_state._atomic_write delegates to atomic_write_text (B6)."""
    import pipeline_state  # type: ignore[import]
    target = tmp_path / "pipeline.md"
    with patch("pipeline_state.atomic_write_text") as mock_aw:
        mock_aw.side_effect = lambda p, d, mode=0o644: p.write_text(d)
        pipeline_state._atomic_write(target, "content")
    mock_aw.assert_called_once()


def test_verdict_write_atomic_write_uses_helper(tmp_path: Path) -> None:
    """verdict_write._atomic_write delegates to atomic_write_text (B6)."""
    import verdict_write  # type: ignore[import]
    target = tmp_path / "verdict.md"
    with patch("verdict_write.atomic_write_text") as mock_aw:
        mock_aw.side_effect = lambda p, d, mode=0o644: p.write_text(d)
        verdict_write._atomic_write(target, "content")
    mock_aw.assert_called_once()
