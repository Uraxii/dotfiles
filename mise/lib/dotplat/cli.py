"""Argument parsing and entry point shared by the file tasks."""

from __future__ import annotations

import argparse
import os

from . import detect
from .platforms import steps_for
from .runner import PROFILE_ENV, Ctx, run_steps


def parse(argv: list[str] | None, description: str) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=description)
    p.add_argument("-n", "--dry-run", action="store_true",
                   default=os.environ.get("DOTFILES_DRY_RUN") == "1",
                   help="print the commands, change nothing (or DOTFILES_DRY_RUN=1)")
    p.add_argument("--profile", default=os.environ.get(PROFILE_ENV, "desktop"),
                   help="desktop (default) or server (or DOTFILES_PROFILE)")
    p.add_argument("--platform", help=f"override detection (or {detect.ENV_VAR})")
    return p.parse_args(argv)


def make_ctx(args: argparse.Namespace) -> Ctx:
    if args.platform:
        os.environ[detect.ENV_VAR] = args.platform
    return Ctx(platform=detect.current(), profile=args.profile, dry_run=args.dry_run)


def system(argv: list[str] | None = None) -> int:
    args = parse(argv, "Install system packages for the detected platform.")
    ctx = make_ctx(args)
    return run_steps(ctx, steps_for(ctx.platform))
