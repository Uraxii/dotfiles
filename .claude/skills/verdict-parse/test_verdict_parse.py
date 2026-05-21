#!/usr/bin/env python3
"""Tests for verdict-parse.py CLI."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent / "verdict-parse.py"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


def write_verdict(d: Path, name: str, body: str) -> Path:
    p = d / name
    p.write_text(body)
    return p


SAMPLE_FM = textwrap.dedent("""\
    ---
    verdict: Approved
    role: skeptic-design
    review_type: design
    loops: 1
    revision: r1
    prod_diff_sha: abcd1234abcd1234abcd1234abcd1234abcd1234
    ---
    Body text here.
""")

BLOCKED_FM = textwrap.dedent("""\
    ---
    verdict: Blocked
    role: skeptic-code
    review_type: code
    loops: 2
    revision: r2
    blocker_class: [impl-defect, scope-creep]
    ---
""")

MISSING_BLOCKER_FM = textwrap.dedent("""\
    ---
    verdict: Approved
    role: tester
    review_type: test-audit
    loops: 1
    revision: r1
    ---
""")


class TestHelp(unittest.TestCase):
    def test_help_exit_zero(self) -> None:
        r = run("--help")
        self.assertEqual(r.returncode, 0)
        self.assertIn("usage", r.stdout.lower())


class TestErrorModes(unittest.TestCase):
    def test_missing_run_dir(self) -> None:
        r = run("--run-dir", "/nonexistent/path/xyz", "--type", "design")
        self.assertEqual(r.returncode, 1)
        self.assertIn("run-dir not found", r.stderr)

    def test_no_verdict_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            r = run("--run-dir", td, "--type", "design")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no verdict-design", r.stderr)

    def test_invalid_type_rejected(self) -> None:
        r = run("--run-dir", ".", "--type", "bogus")
        self.assertNotEqual(r.returncode, 0)


class TestParsing(unittest.TestCase):
    def test_basic_parse(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            write_verdict(Path(td), "verdict-design-r1.md", SAMPLE_FM)
            r = run("--run-dir", td, "--type", "design")
        self.assertEqual(r.returncode, 0)
        data = json.loads(r.stdout)
        self.assertEqual(data["verdict"], "Approved")
        self.assertEqual(data["role"], "skeptic-design")
        self.assertEqual(data["review_type"], "design")
        self.assertEqual(data["loops"], "1")
        self.assertEqual(data["revision"], "r1")
        self.assertEqual(
            data["prod_diff_sha"],
            "abcd1234abcd1234abcd1234abcd1234abcd1234",
        )
        self.assertEqual(data["blocker_class"], [])

    def test_blocker_class_flow_seq(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            write_verdict(Path(td), "verdict-code-r1.md", BLOCKED_FM)
            r = run("--run-dir", td, "--type", "code")
        self.assertEqual(r.returncode, 0)
        data = json.loads(r.stdout)
        self.assertEqual(data["verdict"], "Blocked")
        self.assertEqual(data["blocker_class"], ["impl-defect", "scope-creep"])

    def test_blocker_class_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            write_verdict(Path(td), "verdict-test-audit-r1.md", MISSING_BLOCKER_FM)
            r = run("--run-dir", td, "--type", "test-audit")
        self.assertEqual(r.returncode, 0)
        data = json.loads(r.stdout)
        self.assertEqual(data["blocker_class"], [])

    def test_max_revision_pick(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            for n in (1, 2, 3):
                body = SAMPLE_FM.replace("revision: r1", f"revision: r{n}")
                write_verdict(d, f"verdict-design-r{n}.md", body)
            r = run("--run-dir", td, "--type", "design")
        self.assertEqual(r.returncode, 0)
        data = json.loads(r.stdout)
        self.assertEqual(data["revision"], "r3")

    def test_path_field_present(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            write_verdict(Path(td), "verdict-design-r1.md", SAMPLE_FM)
            r = run("--run-dir", td, "--type", "design")
        self.assertEqual(r.returncode, 0)
        data = json.loads(r.stdout)
        self.assertIn("path", data)
        self.assertTrue(data["path"].endswith("verdict-design-r1.md"))

    def test_review_type_aggregated(self) -> None:
        """verdict-review has aggregated body; frontmatter still parses."""
        body = textwrap.dedent("""\
            ---
            verdict: Conditional
            role: reviewer
            review_type: review
            loops: 1
            revision: r1
            blocker_class: []
            ---
            ## Standards
            verdict: Conditional
            ## Spec
            verdict: Approved
        """)
        with tempfile.TemporaryDirectory() as td:
            write_verdict(Path(td), "verdict-review-r1.md", body)
            r = run("--run-dir", td, "--type", "review")
        self.assertEqual(r.returncode, 0)
        data = json.loads(r.stdout)
        self.assertEqual(data["verdict"], "Conditional")


if __name__ == "__main__":
    unittest.main()
