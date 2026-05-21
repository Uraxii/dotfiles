#!/usr/bin/env python3
"""Compute SHA1 of production-only diff, excluding test paths.

Output: 40-char hex SHA1 (or 40 zeros for empty diff). No JSON wrapping —
preserves shell-chain contract.

Usage:
  python3 prod-diff-sha.py --base-sha <sha> --head <ref> \
    [--test-paths-file <path>]

Exit codes:
  0  success
  1  error
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

__all__ = ["main"]

EMPTY_SHA = "0" * 40

# Mirror of DEFAULT_GLOBS in test-path-resolve.py. Keep in sync.
# Parity verified by test_prod_diff_sha.py::test_default_globs_parity.
DEFAULT_GLOBS: list[str] = [
    "**/test_*.py",
    "**/*_test.py",
    "**/tests/**",
    "**/test/**",
    "**/__tests__/**",
    "**/*.test.ts",
    "**/*.spec.ts",
    "**/*.test.tsx",
    "**/*.spec.tsx",
    "**/*.test.js",
    "**/*.spec.js",
    "**/*.test.go",
    "**/*_test.go",
    "**/*Test.java",
    "**/*Tests.java",
    "**/*Spec.java",
    "**/test_*.rb",
    "**/*_spec.rb",
    "**/*Tests.cs",
    "**/*Test.cs",
    "**/test_*.gd",
]


def get_test_globs(test_paths_file: str | None) -> list[str]:
    if test_paths_file:
        p = Path(test_paths_file)
        if p.exists():
            return [
                ln.strip()
                for ln in p.read_text(encoding="utf-8").splitlines()
                if ln.strip() and not ln.strip().startswith("#")
            ]
    return DEFAULT_GLOBS


def compute_prod_diff_sha(
    base_sha: str, head: str, globs: list[str]
) -> str:
    excludes = [f":!{g}" for g in globs]
    cmd = ["git", "diff", base_sha, head, "--"] + excludes
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"git diff failed: {result.stderr.strip()}")
    diff_text = result.stdout
    if not diff_text.strip():
        return EMPTY_SHA
    return hashlib.sha1(diff_text.encode()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compute prod-only diff SHA1. Outputs 40-char hex."
    )
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--head", default="HEAD")
    parser.add_argument(
        "--test-paths-file",
        default=None,
        help="Path to test-paths.txt override. Uses DEFAULT_GLOBS if absent.",
    )
    args = parser.parse_args()

    globs = get_test_globs(args.test_paths_file)
    try:
        sha = compute_prod_diff_sha(args.base_sha, args.head, globs)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print(sha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
