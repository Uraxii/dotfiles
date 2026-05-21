#!/usr/bin/env python3
"""Tests for test-path-resolve.py CLI."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent / "test-path-resolve.py"


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
        r = run("--run-dir", "/nonexistent/xyz")
        self.assertEqual(r.returncode, 1)
        self.assertIn("run-dir not found", r.stderr)


class TestDefaultSet(unittest.TestCase):
    def test_default_set_when_no_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            r = run("--run-dir", td)
        self.assertEqual(r.returncode, 0)
        lines = r.stdout.strip().splitlines()
        self.assertGreater(len(lines), 5)
        self.assertIn("**/test_*.py", lines)
        self.assertIn("**/test_*.gd", lines)

    def test_default_set_line_count(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            r = run("--run-dir", td)
        self.assertEqual(r.returncode, 0)
        lines = r.stdout.strip().splitlines()
        # Design spec: same set as SKILL.md — 19 entries
        self.assertGreaterEqual(len(lines), 19)


class TestManifestOverride(unittest.TestCase):
    def test_manifest_override(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "test-paths.txt").write_text("**/my_tests/**\n**/spec/**\n")
            r = run("--run-dir", td)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), "**/my_tests/**\n**/spec/**")

    def test_manifest_skips_comments_and_blanks(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "test-paths.txt").write_text(
                "# comment\n**/tests/**\n   \n**/spec/**\n"
            )
            r = run("--run-dir", td)
        self.assertEqual(r.returncode, 0)
        lines = r.stdout.strip().splitlines()
        self.assertEqual(lines, ["**/tests/**", "**/spec/**"])


if __name__ == "__main__":
    unittest.main()
