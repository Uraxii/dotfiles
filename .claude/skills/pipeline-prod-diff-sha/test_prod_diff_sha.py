#!/usr/bin/env python3
"""Tests for prod-diff-sha.py CLI."""
from __future__ import annotations

import ast
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent / "prod-diff-sha.py"
EMPTY_SHA = "0" * 40


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


class TestEmptyDiff(unittest.TestCase):
    def test_empty_diff_returns_zeros(self) -> None:
        """Same SHA vs same SHA → no diff → 40 zeros."""
        import subprocess as sp
        # Get current HEAD SHA for a known zero-diff
        head = sp.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True,
            cwd=Path(__file__).parent,
        ).stdout.strip()
        if not head:
            self.skipTest("Not in a git repo")
        r = run("--base-sha", head, "--head", head)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), EMPTY_SHA)


class TestKnownDiff(unittest.TestCase):
    def test_known_diff_hashed(self) -> None:
        """Monkeypatch: fixed diff bytes → SHA1 matches."""
        diff_bytes = b"diff --git a/src/x.py b/src/x.py\n+foo\n"
        expected = hashlib.sha1(diff_bytes).hexdigest()
        # Use the script's compute fn directly by importing
        sys.path.insert(0, str(SCRIPT.parent))
        try:
            import importlib
            import importlib.util
            spec = importlib.util.spec_from_file_location("prod_diff_sha", SCRIPT)
            mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            # Monkey-patch subprocess.run to return known diff
            import unittest.mock as mock
            fake = mock.MagicMock()
            fake.returncode = 0
            fake.stdout = diff_bytes.decode()
            with mock.patch("subprocess.run", return_value=fake):
                sha = mod.compute_prod_diff_sha("base", "head", [])
            self.assertEqual(sha, expected)
        finally:
            sys.path.pop(0)

    def test_excludes_built_from_default_globs(self) -> None:
        """subprocess.run receives :!glob excludes from DEFAULT_GLOBS."""
        sys.path.insert(0, str(SCRIPT.parent))
        try:
            import importlib.util
            import unittest.mock as mock
            spec = importlib.util.spec_from_file_location("prod_diff_sha", SCRIPT)
            mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            captured: list[list[str]] = []
            fake = mock.MagicMock()
            fake.returncode = 0
            fake.stdout = ""
            def capture_run(cmd: list[str], **_kw: object) -> mock.MagicMock:
                captured.append(cmd)
                return fake
            with mock.patch("subprocess.run", side_effect=capture_run):
                mod.compute_prod_diff_sha("base", "HEAD", mod.DEFAULT_GLOBS)
            self.assertTrue(len(captured) > 0)
            argv = captured[0]
            self.assertIn(":!**/test_*.py", argv)
        finally:
            sys.path.pop(0)


class TestTestPathsFile(unittest.TestCase):
    def test_test_paths_file_override(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tpf = Path(td) / "test-paths.txt"
            tpf.write_text("**/my_tests/**\n**/spec/**\n")
            sys.path.insert(0, str(SCRIPT.parent))
            try:
                import importlib.util
                import unittest.mock as mock
                spec = importlib.util.spec_from_file_location("prod_diff_sha", SCRIPT)
                mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
                spec.loader.exec_module(mod)  # type: ignore[union-attr]
                globs = mod.get_test_globs(str(tpf))
                self.assertEqual(globs, ["**/my_tests/**", "**/spec/**"])
            finally:
                sys.path.pop(0)

    def test_test_paths_file_comments_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tpf = Path(td) / "test-paths.txt"
            tpf.write_text("# comment\n**/tests/**\n   \n**/spec/**\n")
            sys.path.insert(0, str(SCRIPT.parent))
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location("prod_diff_sha", SCRIPT)
                mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
                spec.loader.exec_module(mod)  # type: ignore[union-attr]
                globs = mod.get_test_globs(str(tpf))
                self.assertEqual(globs, ["**/tests/**", "**/spec/**"])
            finally:
                sys.path.pop(0)

    def test_default_globs_parity(self) -> None:
        """DEFAULT_GLOBS in prod-diff-sha.py matches test-path-resolve.py.

        Both embed the same constant. This test catches drift between the two.
        """
        tpr_script = (
            Path(__file__).parent.parent / "test-path-resolve" / "test-path-resolve.py"
        )
        if not tpr_script.exists():
            self.skipTest("test-path-resolve.py not found")

        def extract_default_globs(path: Path) -> list[str]:
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Assign)
                    and any(
                        isinstance(t, ast.Name) and t.id == "DEFAULT_GLOBS"
                        for t in node.targets
                    )
                ):
                    if isinstance(node.value, ast.List):
                        return [
                            elt.s  # type: ignore[attr-defined]
                            for elt in node.value.elts
                            if isinstance(elt, ast.Constant)
                        ]
            return []

        pds_globs = extract_default_globs(SCRIPT)
        tpr_globs = extract_default_globs(tpr_script)
        # test-path-resolve includes **/test_*.gd (Godot) which prod-diff-sha also should
        self.assertEqual(
            sorted(pds_globs),
            sorted(tpr_globs),
            "DEFAULT_GLOBS mismatch between prod-diff-sha.py and test-path-resolve.py",
        )


if __name__ == "__main__":
    unittest.main()
