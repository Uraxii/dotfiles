"""Tests for pipeline_state.py: get/set/stage round trips, dot-path resolution."""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

_PIPELINE_DIR = Path(__file__).parent.parent / ".claude" / "pipeline"
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

import pipeline_state  # noqa: E402
from pipeline_state import (  # noqa: E402
    dot_get,
    dot_set,
    merge_frontmatter,
    split_frontmatter,
    _coerce_value,
)


# ---------------------------------------------------------------------------
# Frontmatter parse / serialise
# ---------------------------------------------------------------------------


def test_split_frontmatter_basic() -> None:
    text = "---\nstatus: active\nrevision: 3\n---\n\n# Body\n"
    fm, body = split_frontmatter(text)
    assert fm["status"] == "active"
    assert fm["revision"] == 3
    assert "Body" in body


def test_split_frontmatter_no_frontmatter() -> None:
    text = "# Just body\n"
    fm, body = split_frontmatter(text)
    assert fm == {}
    assert body == text


def test_merge_roundtrip() -> None:
    original = "---\nstatus: active\nslack:\n  bound_session: null\n  thread_ts: 123.456\n---\n\n# body\n"
    fm, body = split_frontmatter(original)
    reassembled = merge_frontmatter(fm, body)
    fm2, body2 = split_frontmatter(reassembled)
    assert fm2["status"] == "active"
    assert "body" in body2


# ---------------------------------------------------------------------------
# dot_get / dot_set
# ---------------------------------------------------------------------------


def test_dot_get_flat_key() -> None:
    data = {"status": "active", "revision": 2}
    assert dot_get(data, "status") == "active"


def test_dot_get_nested() -> None:
    data = {"slack": {"thread_ts": "abc", "channel_id": "C123"}}
    assert dot_get(data, "slack.thread_ts") == "abc"


def test_dot_get_missing_raises() -> None:
    with pytest.raises(KeyError):
        dot_get({"a": 1}, "a.b")


def test_dot_set_flat() -> None:
    data: dict = {}
    dot_set(data, "key", "value")
    assert data["key"] == "value"


def test_dot_set_nested_creates_intermediates() -> None:
    data: dict = {}
    dot_set(data, "slack.thread_ts", "123.456")
    assert data["slack"]["thread_ts"] == "123.456"


def test_dot_set_overwrites_existing() -> None:
    data = {"slack": {"thread_ts": "old"}}
    dot_set(data, "slack.thread_ts", "new")
    assert data["slack"]["thread_ts"] == "new"


# ---------------------------------------------------------------------------
# _coerce_value
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw,expected", [
    ("null", None),
    ("true", True),
    ("false", False),
    ("42", 42),
    ("3.14", 3.14),
    ("hello", "hello"),
])
def test_coerce_value(raw: str, expected: object) -> None:
    assert _coerce_value(raw) == expected


# ---------------------------------------------------------------------------
# CLI round trips via file I/O
# ---------------------------------------------------------------------------


def test_get_set_roundtrip(run_dir: Path) -> None:
    project = run_dir.parent.parent.parent
    run_id = run_dir.name

    # set slack.thread_ts
    import argparse
    args = argparse.Namespace(
        project=str(project),
        run=run_id,
        key="slack.thread_ts",
        value="999.888",
        log_level="WARNING",
    )
    rc = pipeline_state.cmd_set(args)
    assert rc == 0

    # get it back
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        args_get = argparse.Namespace(
            project=str(project),
            run=run_id,
            key="slack.thread_ts",
            log_level="WARNING",
        )
        rc2 = pipeline_state.cmd_get(args_get)
    assert rc2 == 0
    # cmd_get writes JSON; value was stored as float by coerce.
    val = json.loads(buf.getvalue())
    assert float(val) == pytest.approx(999.888)


def test_stage_creates_entry(run_dir: Path) -> None:
    project = run_dir.parent.parent.parent
    run_id = run_dir.name
    import argparse

    args = argparse.Namespace(
        project=str(project),
        run=run_id,
        name="build",
        status="done",
        revision="r1",
        log_level="WARNING",
    )
    rc = pipeline_state.cmd_stage(args)
    assert rc == 0

    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        args_get = argparse.Namespace(
            project=str(project),
            run=run_id,
            key="stages.build.status",
            log_level="WARNING",
        )
        rc3 = pipeline_state.cmd_get(args_get)
    assert rc3 == 0
    assert json.loads(buf.getvalue()) == "done"


def test_get_missing_key_exits_nonzero(run_dir: Path) -> None:
    project = run_dir.parent.parent.parent
    run_id = run_dir.name
    import argparse
    args = argparse.Namespace(
        project=str(project),
        run=run_id,
        key="nonexistent.deep.key",
        log_level="WARNING",
    )
    rc = pipeline_state.cmd_get(args)
    assert rc != 0


def test_read_returns_json(run_dir: Path) -> None:
    project = run_dir.parent.parent.parent
    run_id = run_dir.name
    import argparse, io, contextlib

    buf = io.StringIO()
    args = argparse.Namespace(
        project=str(project),
        run=run_id,
        log_level="WARNING",
    )
    with contextlib.redirect_stdout(buf):
        rc = pipeline_state.cmd_read(args)
    assert rc == 0
    data = json.loads(buf.getvalue())
    assert "frontmatter" in data
    assert "body" in data


def test_atomic_write_no_tmp_left(run_dir: Path) -> None:
    """After a set, no .tmp file should remain."""
    project = run_dir.parent.parent.parent
    run_id = run_dir.name
    import argparse

    args = argparse.Namespace(
        project=str(project),
        run=run_id,
        key="status",
        value="done",
        log_level="WARNING",
    )
    pipeline_state.cmd_set(args)
    md_path = run_dir / "pipeline.md"
    assert not (md_path.parent / "pipeline.md.tmp").exists()


# ---------------------------------------------------------------------------
# B3 — sidecar lock file used by _write_with_lock
# ---------------------------------------------------------------------------


def test_write_with_lock_uses_sidecar(run_dir: Path) -> None:
    """_write_with_lock must lock <path>.lock not <path> itself (B3).

    Verify the sidecar lock file is created when _write_with_lock is called.
    """
    md_path = run_dir / "pipeline.md"
    pipeline_state._write_with_lock(md_path, md_path.read_text(encoding="utf-8"))
    lock_path = run_dir / "pipeline.md.lock"
    assert lock_path.exists(), "sidecar .lock file must be created by _write_with_lock"


def test_lock_path_helper(run_dir: Path) -> None:
    md_path = run_dir / "pipeline.md"
    assert pipeline_state._lock_path(md_path) == run_dir / "pipeline.md.lock"


# ---------------------------------------------------------------------------
# B2 — warning update goes through pipeline_state.cmd_set (not inline regex)
# ---------------------------------------------------------------------------


def test_warning_set_via_pipeline_state(run_dir: Path) -> None:
    """The slack.warning field can be set via pipeline_state cmd_set (B2 pathway).

    This verifies the pipeline_state path works correctly for warning writes;
    the full SlackPoster integration is a manual smoke test (requires bolt).
    """
    project = run_dir.parent.parent.parent
    run_id = run_dir.name
    import argparse

    rc = pipeline_state.cmd_set(argparse.Namespace(
        project=str(project),
        run=run_id,
        key="slack.warning",
        value="channel-mismatch: cwd-channel=C001 session-channel=C002",
        log_level="WARNING",
    ))
    assert rc == 0
    text = (run_dir / "pipeline.md").read_text(encoding="utf-8")
    assert "channel-mismatch" in text
    # Ensure no .tmp file left behind.
    assert not (run_dir / "pipeline.md.tmp").exists()
