#!/usr/bin/env python3
"""Set up dream-apply archive prune scheduler.

Installs a recurring job that removes ~/.pipeline/memory/.archive/<iso8601>/
subdirectories older than N days. Companion to the `dream-apply` skill.

Modes:
- cron (default): edits user crontab via `crontab -l` / `crontab -`.
- systemd: writes ~/.config/systemd/user/dream-archive-prune.{service,timer}
  + enables timer via `systemctl --user`.

Idempotent: detects existing install + skips if already present (or upgrades
in place when --hour/--days change). --remove uninstalls.

USER-INVOKED. Pipeline agents MUST NOT invoke this script.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Final

CRON_TAG: Final[str] = "# dream-apply-archive-prune"
ARCHIVE_DIR: Final[str] = "~/.pipeline/memory/.archive"
SYSTEMD_UNIT_NAME: Final[str] = "dream-archive-prune"
SYSTEMD_USER_DIR: Final[Path] = Path.home() / ".config" / "systemd" / "user"


def _find_command(args: argparse.Namespace) -> str:
    """Return the `find -exec rm` command body shared by both modes."""
    return (
        f"find {ARCHIVE_DIR} -mindepth 1 -maxdepth 1 -type d "
        f"-mtime +{args.days} -exec rm -rf {{}} \\;"
    )


def _cron_line(args: argparse.Namespace) -> str:
    """Return single crontab line including tag for idempotency."""
    return f"{args.minute} {args.hour} * * * {_find_command(args)} {CRON_TAG}"


def _read_crontab() -> list[str]:
    """Return current crontab lines (empty list if no crontab installed)."""
    result = subprocess.run(
        ["crontab", "-l"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        # `crontab -l` exits non-zero when no crontab exists; treat as empty.
        return []
    return result.stdout.splitlines()


def _write_crontab(lines: list[str], dry_run: bool) -> None:
    payload = "\n".join(lines) + "\n" if lines else ""
    if dry_run:
        print("--- crontab would be set to: ---")
        print(payload, end="")
        print("--- end ---")
        return
    proc = subprocess.run(
        ["crontab", "-"],
        input=payload,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(f"crontab - exited {proc.returncode}")


def install_cron(args: argparse.Namespace) -> int:
    if shutil.which("crontab") is None:
        print("ERROR: `crontab` not found in PATH. Use --mode systemd instead.", file=sys.stderr)
        return 2

    lines = _read_crontab()
    tagged = [line for line in lines if line.rstrip().endswith(CRON_TAG)]
    new_line = _cron_line(args)

    if tagged == [new_line]:
        print(f"No change: cron entry already installed and current.")
        return 0

    # Remove any existing tagged lines, then append the new one.
    pruned = [line for line in lines if not line.rstrip().endswith(CRON_TAG)]
    pruned.append(new_line)
    _write_crontab(pruned, args.dry_run)
    if not args.dry_run:
        print(f"Installed cron entry:\n  {new_line}")
    return 0


def remove_cron(args: argparse.Namespace) -> int:
    if shutil.which("crontab") is None:
        return 0  # Nothing to remove if `crontab` is absent.
    lines = _read_crontab()
    pruned = [line for line in lines if not line.rstrip().endswith(CRON_TAG)]
    if pruned == lines:
        print("No tagged cron entry found; nothing to remove.")
        return 0
    _write_crontab(pruned, args.dry_run)
    if not args.dry_run:
        print("Removed cron entry.")
    return 0


def _systemd_service(args: argparse.Namespace) -> str:
    return (
        "[Unit]\n"
        "Description=Prune dream-apply archive directories older than configured retention\n"
        "Documentation=file://"
        f"{Path(__file__).resolve().parent.parent}/REFERENCE.md\n"
        "\n"
        "[Service]\n"
        "Type=oneshot\n"
        f"ExecStart=/usr/bin/env sh -c '{_find_command(args)}'\n"
    )


def _systemd_timer(args: argparse.Namespace) -> str:
    return (
        "[Unit]\n"
        f"Description=Daily trigger for {SYSTEMD_UNIT_NAME}.service\n"
        "\n"
        "[Timer]\n"
        f"OnCalendar=*-*-* {args.hour:02d}:{args.minute:02d}:00\n"
        "Persistent=true\n"
        f"Unit={SYSTEMD_UNIT_NAME}.service\n"
        "\n"
        "[Install]\n"
        "WantedBy=timers.target\n"
    )


def install_systemd(args: argparse.Namespace) -> int:
    if shutil.which("systemctl") is None:
        print("ERROR: `systemctl` not found. Use --mode cron instead.", file=sys.stderr)
        return 2

    service_path = SYSTEMD_USER_DIR / f"{SYSTEMD_UNIT_NAME}.service"
    timer_path = SYSTEMD_USER_DIR / f"{SYSTEMD_UNIT_NAME}.timer"
    service_body = _systemd_service(args)
    timer_body = _systemd_timer(args)

    if args.dry_run:
        print(f"--- would write {service_path}: ---")
        print(service_body, end="")
        print(f"--- would write {timer_path}: ---")
        print(timer_body, end="")
        print(f"--- would run: systemctl --user daemon-reload ---")
        print(f"--- would run: systemctl --user enable --now {SYSTEMD_UNIT_NAME}.timer ---")
        return 0

    SYSTEMD_USER_DIR.mkdir(parents=True, exist_ok=True)
    service_path.write_text(service_body)
    timer_path.write_text(timer_body)

    for cmd in (
        ["systemctl", "--user", "daemon-reload"],
        ["systemctl", "--user", "enable", "--now", f"{SYSTEMD_UNIT_NAME}.timer"],
    ):
        proc = subprocess.run(cmd, check=False)
        if proc.returncode != 0:
            print(f"ERROR: {' '.join(cmd)} exited {proc.returncode}", file=sys.stderr)
            return proc.returncode

    print(f"Installed systemd timer: {SYSTEMD_UNIT_NAME}.timer")
    print(f"Status: systemctl --user status {SYSTEMD_UNIT_NAME}.timer")
    print(f"Logs:   journalctl --user -u {SYSTEMD_UNIT_NAME}.service")
    return 0


def remove_systemd(args: argparse.Namespace) -> int:
    if shutil.which("systemctl") is None:
        return 0
    service_path = SYSTEMD_USER_DIR / f"{SYSTEMD_UNIT_NAME}.service"
    timer_path = SYSTEMD_USER_DIR / f"{SYSTEMD_UNIT_NAME}.timer"

    if args.dry_run:
        print(f"--- would run: systemctl --user disable --now {SYSTEMD_UNIT_NAME}.timer ---")
        print(f"--- would delete: {service_path}, {timer_path} ---")
        return 0

    subprocess.run(
        ["systemctl", "--user", "disable", "--now", f"{SYSTEMD_UNIT_NAME}.timer"],
        check=False,
    )
    for p in (service_path, timer_path):
        if p.exists():
            p.unlink()
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    print(f"Removed systemd timer + service.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("cron", "systemd"),
        default="cron",
        help="Scheduler backend (default: cron).",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Retention period in days. Archives older than this are pruned (default: 30).",
    )
    parser.add_argument(
        "--hour",
        type=int,
        default=3,
        help="Hour of day to run (0-23). Default: 3 (03:00).",
    )
    parser.add_argument(
        "--minute",
        type=int,
        default=0,
        help="Minute of hour to run (0-59). Default: 0.",
    )
    parser.add_argument(
        "--remove",
        action="store_true",
        help="Uninstall the scheduled job.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print intended changes without applying.",
    )
    args = parser.parse_args(argv)

    if not (0 <= args.hour <= 23):
        parser.error("--hour must be 0-23")
    if not (0 <= args.minute <= 59):
        parser.error("--minute must be 0-59")
    if args.days < 1:
        parser.error("--days must be >= 1")

    if args.mode == "cron":
        return remove_cron(args) if args.remove else install_cron(args)
    return remove_systemd(args) if args.remove else install_systemd(args)


if __name__ == "__main__":
    sys.exit(main())
