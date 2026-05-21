#!/usr/bin/env python3
"""Tests for handoff-doc.py CLI."""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent / "handoff-doc.py"
TS_RE = re.compile(r"\d{8}T\d{6}Z")


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


class TestHelp(unittest.TestCase):
    def test_help_exit_zero(self) -> None:
        r = run("--help")
        self.assertEqual(r.returncode, 0)


class TestErrorModes(unittest.TestCase):
    def test_missing_run_dir_errors(self) -> None:
        r = run(
            "--role", "build",
            "--run-dir", "/nonexistent/xyz",
            "--next-focus", "fix the thing",
        )
        self.assertEqual(r.returncode, 1)
        self.assertIn("run-dir not found", r.stderr)


class TestOutput(unittest.TestCase):
    def test_writes_file_and_prints_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            r = run(
                "--role", "architect",
                "--run-dir", td,
                "--next-focus", "finish design",
            )
            self.assertEqual(r.returncode, 0)
            path = Path(r.stdout.strip())
            self.assertTrue(path.exists())
            body = path.read_text()
        self.assertIn("architect", body)
        self.assertIn("finish design", body)

    def test_run_id_inferred_from_dirname(self) -> None:
        with tempfile.TemporaryDirectory(suffix="-foo-bar-baz-abc123") as td:
            run_id = Path(td).name
            r = run(
                "--role", "build",
                "--run-dir", td,
                "--next-focus", "continue",
            )
            self.assertEqual(r.returncode, 0)
            path = Path(r.stdout.strip())
            body = path.read_text()
        self.assertIn(run_id, body)

    def test_iso_timestamp_format_in_filename(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            r = run(
                "--role", "skeptic",
                "--run-dir", td,
                "--next-focus", "check code",
            )
            self.assertEqual(r.returncode, 0)
            filename = Path(r.stdout.strip()).name
        self.assertRegex(filename, r"\d{8}T\d{6}Z")

    def test_template_sections_present(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            r = run(
                "--role", "tester",
                "--run-dir", td,
                "--next-focus", "run regression",
            )
            self.assertEqual(r.returncode, 0)
            body = Path(r.stdout.strip()).read_text()
        self.assertIn("# Handoff:", body)
        self.assertIn("## Next session focus", body)
        self.assertIn("## Referenced artifacts", body)
        self.assertIn("## State summary", body)
        self.assertIn("run regression", body)


if __name__ == "__main__":
    unittest.main()
