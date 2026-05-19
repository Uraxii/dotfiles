#!/usr/bin/env python3
"""inbox_wait — block until a file exists or timeout expires.

Usage:
    inbox_wait.py --path <abs-path> [--timeout-seconds <int>]

Polls (1s sleep) until the file at <abs-path> exists. Exits 0 on
success; exits 1 on timeout.

Default timeout: 86400 (24h).

Stdlib-only.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

DEFAULT_TIMEOUT_S = 86400
POLL_INTERVAL_S = 1.0


def wait(path: Path, timeout_s: int) -> int:
    """Wait for path to exist. Returns 0 on found, 1 on timeout."""
    deadline = time.monotonic() + timeout_s
    while True:
        if path.exists():
            return 0
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            sys.stderr.write(
                f"timeout after {timeout_s}s waiting for: {path}\n"
            )
            return 1
        time.sleep(min(POLL_INTERVAL_S, remaining))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="inbox_wait.py",
        description=(
            "Block until a file exists. Exits 0 on success, 1 on timeout. "
            "Used as a foreground alternative to ScheduleWakeup-poll for short waits."
        ),
    )
    parser.add_argument("--path", required=True, help="Absolute path to wait for")
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_S,
        help=f"Seconds until timeout (default: {DEFAULT_TIMEOUT_S})",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    target = Path(args.path).expanduser().resolve()
    sys.exit(wait(target, args.timeout_seconds))


if __name__ == "__main__":
    main()
