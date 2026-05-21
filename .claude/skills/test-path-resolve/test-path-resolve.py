#!/usr/bin/env python3
"""Resolve canonical test-path glob set for a pipeline run.

If <run-dir>/test-paths.txt exists, reads it. Otherwise emits DEFAULT_GLOBS.
Output: newline-separated glob patterns (no JSON — shell-chain compat).

Usage:
  python3 test-path-resolve.py --run-dir <path>

Exit codes:
  0  success
  1  error
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

__all__ = ["main"]

# Mirror of DEFAULT_GLOBS in prod-diff-sha.py. Keep in sync.
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resolve canonical test path globs for a pipeline run."
    )
    parser.add_argument("--run-dir", required=True, help="Pipeline run directory")
    args = parser.parse_args()

    run_dir = Path(args.run_dir).expanduser()
    if not run_dir.is_dir():
        print(f"ERROR: run-dir not found: {run_dir}", file=sys.stderr)
        return 1

    test_paths_file = run_dir / "test-paths.txt"
    if test_paths_file.exists():
        globs = [
            ln.strip()
            for ln in test_paths_file.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
    else:
        globs = DEFAULT_GLOBS

    print("\n".join(globs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
