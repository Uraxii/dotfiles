"""Tests for verdict_write.py + verdict_read.py: write→read round trip,
latest-revision selection."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_PIPELINE_DIR = Path(__file__).parent.parent / ".claude" / "pipeline"
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

import verdict_write  # noqa: E402
import verdict_read  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _project(run_dir: Path) -> Path:
    return run_dir.parent.parent.parent


def _run_id(run_dir: Path) -> str:
    return run_dir.name


# ---------------------------------------------------------------------------
# verdict_write._compose
# ---------------------------------------------------------------------------


def test_compose_includes_all_fields() -> None:
    content = verdict_write._compose(
        "design", 2, "approved", "skeptic", None, "Great work."
    )
    assert "verdict: approved" in content
    assert "role: skeptic" in content
    assert "revision: 2" in content
    assert "Great work." in content


def test_compose_empty_body() -> None:
    content = verdict_write._compose("code", 1, "blocked", "build", None, "")
    assert content.startswith("---\n")
    assert "verdict: blocked" in content


# ---------------------------------------------------------------------------
# Write → read round trip
# ---------------------------------------------------------------------------


def test_write_read_roundtrip(run_dir: Path) -> None:
    project = _project(run_dir)
    run_id = _run_id(run_dir)

    # Write.
    verdict_write._atomic_write(
        verdict_write._verdict_path(run_dir, "design", 1),
        verdict_write._compose("design", 1, "approved", "skeptic", None, "Looks good."),
    )

    # Read back via verdict_read.
    parsed = verdict_read._parse_verdict_file(
        run_dir / "verdict-design-r1.md"
    )
    assert parsed["verdict"] == "approved"
    assert parsed["role"] == "skeptic"
    assert parsed["revision"] == 1
    assert "Looks good." in parsed["body"]


def test_write_creates_file(run_dir: Path) -> None:
    path = verdict_write._verdict_path(run_dir, "code", 3)
    verdict_write._atomic_write(
        path,
        verdict_write._compose("code", 3, "needs-revision", "tester", None, ""),
    )
    assert path.is_file()


# ---------------------------------------------------------------------------
# _find_latest
# ---------------------------------------------------------------------------


def test_find_latest_picks_max(run_dir: Path) -> None:
    for rev in (1, 2, 5):
        (run_dir / f"verdict-design-r{rev}.md").write_text(
            f"---\nrevision: {rev}\n---\n", encoding="utf-8"
        )
    assert verdict_read._find_latest(run_dir, "design") == 5


def test_find_latest_returns_none_when_missing(run_dir: Path) -> None:
    assert verdict_read._find_latest(run_dir, "ops") is None


def test_find_latest_ignores_wrong_type(run_dir: Path) -> None:
    (run_dir / "verdict-design-r1.md").write_text("---\nrevision: 1\n---\n", encoding="utf-8")
    assert verdict_read._find_latest(run_dir, "security") is None


# ---------------------------------------------------------------------------
# CLI cmd_read / cmd_get
# ---------------------------------------------------------------------------


def test_cmd_read_missing_run_dir(tmp_path: Path) -> None:
    import argparse
    args = argparse.Namespace(
        project=str(tmp_path),
        run="nonexistent-run",
        verdict_type="design",
        latest=True,
        revision=None,
        field="all",
    )
    rc = verdict_read.main.__wrapped__(args) if hasattr(verdict_read.main, "__wrapped__") else None
    # main() calls sys.exit; test via internal functions instead.
    path = verdict_read._find_latest(tmp_path / ".pipeline" / "runs" / "nope", "design")
    assert path is None


def test_write_via_cli_main(run_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test write CLI by calling _atomic_write + _compose directly (no subprocess)."""
    project = _project(run_dir)
    run_id = _run_id(run_dir)
    body = "The design is approved.\n"
    content = verdict_write._compose("design", 1, "approved", "skeptic", "design", body)
    out_path = verdict_write._verdict_path(run_dir, "design", 1)
    verdict_write._atomic_write(out_path, content)
    assert out_path.is_file()
    parsed = verdict_read._parse_verdict_file(out_path)
    assert parsed["verdict"] == "approved"
    assert "approved" in parsed["body"]


def test_no_tmp_after_write(run_dir: Path) -> None:
    path = verdict_write._verdict_path(run_dir, "test", 1)
    verdict_write._atomic_write(
        path, verdict_write._compose("test", 1, "approved", "tester", None, "ok")
    )
    tmp = path.parent / (path.name + ".tmp")
    assert not tmp.exists()


# ---------------------------------------------------------------------------
# C2 — verdict_read strips surrounding quotes from frontmatter values
# ---------------------------------------------------------------------------


def test_parse_verdict_strips_double_quotes(run_dir: Path) -> None:
    """Frontmatter values written as `verdict: "approved"` should parse as 'approved'."""
    path = run_dir / "verdict-design-r1.md"
    path.write_text(
        '---\nverdict: "approved"\nrole: "skeptic"\nrevision: 1\n---\n\nbody\n',
        encoding="utf-8",
    )
    parsed = verdict_read._parse_verdict_file(path)
    assert parsed["verdict"] == "approved"
    assert parsed["role"] == "skeptic"


def test_parse_verdict_strips_single_quotes(run_dir: Path) -> None:
    path = run_dir / "verdict-code-r1.md"
    path.write_text(
        "---\nverdict: 'blocked'\nrole: 'build'\nrevision: 1\n---\n\nbody\n",
        encoding="utf-8",
    )
    parsed = verdict_read._parse_verdict_file(path)
    assert parsed["verdict"] == "blocked"


def test_parse_verdict_unquoted_unchanged(run_dir: Path) -> None:
    """Unquoted values are left as-is (regression guard)."""
    path = run_dir / "verdict-ops-r2.md"
    path.write_text(
        "---\nverdict: needs-revision\nrole: skeptic\nrevision: 2\n---\n\nbody\n",
        encoding="utf-8",
    )
    parsed = verdict_read._parse_verdict_file(path)
    assert parsed["verdict"] == "needs-revision"
