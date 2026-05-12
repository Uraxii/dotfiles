#!/usr/bin/env python3
"""Resolve canonical test path glob set for a pipeline run.

Usage:
  python3 test-path-resolve.py --run-dir <path>

Output: newline-separated list of glob patterns.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

__all__ = ["main"]

DEFAULT_GLOBS = [
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
    parser = argparse.ArgumentParser(description="Resolve test path globs.")
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    test_paths_file = run_dir / "test-paths.txt"

    if test_paths_file.exists():
        lines = test_paths_file.read_text().splitlines()
        globs = [
            line for line in lines
            if line.strip() and not line.strip().startswith("#")
        ]
    else:
        globs = DEFAULT_GLOBS

    print("\n".join(globs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
