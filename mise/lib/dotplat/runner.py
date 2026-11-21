"""Step model and runner shared by every platform module.

A platform module returns a list of Steps. Each Step belongs to a group.
The profile picks which groups run:

    desktop (default)  core + desktop
    server             core only (no GUI, Wayland stack, fonts, or games)

Set the profile with `--profile` or DOTFILES_PROFILE.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

PROFILE_ENV = "DOTFILES_PROFILE"
PROFILES: dict[str, frozenset[str]] = {
    "desktop": frozenset({"core", "desktop"}),
    "server": frozenset({"core"}),
}


class StepFailed(Exception):
    pass


@dataclass
class Ctx:
    platform: str
    profile: str = "desktop"
    dry_run: bool = False
    home: Path = field(default_factory=Path.home)
    notes: list[str] = field(default_factory=list)

    def run(self, argv: list[str], env: dict[str, str] | None = None) -> None:
        print(f"  + {shlex.join(argv)}", flush=True)
        if self.dry_run:
            return
        full_env = {**os.environ, **env} if env else None
        rc = subprocess.run(argv, env=full_env, check=False).returncode
        if rc != 0:
            raise StepFailed(f"exit {rc}: {shlex.join(argv)}")

    def sh(self, script: str) -> None:
        """Run a bash snippet (upstream installers that need a pipe)."""
        self.run(["bash", "-c", script])

    def note(self, text: str) -> None:
        self.notes.append(text)


@dataclass
class Step:
    name: str
    action: Callable[[Ctx], None]
    group: str = "core"
    # Skip the step when any of these binaries is already on PATH.
    skip_if_bin: tuple[str, ...] = ()


def has_bin(*names: str) -> bool:
    return any(shutil.which(n) for n in names)


def command(name: str, argv: list[str], group: str = "core",
            skip_if_bin: tuple[str, ...] = (), env: dict[str, str] | None = None) -> Step:
    return Step(name, lambda ctx: ctx.run(argv, env), group, skip_if_bin)


def shell(name: str, script: str, group: str = "core",
          skip_if_bin: tuple[str, ...] = ()) -> Step:
    return Step(name, lambda ctx: ctx.sh(script), group, skip_if_bin)


def manual(name: str, how: str, group: str = "core",
           skip_if_bin: tuple[str, ...] = ()) -> Step:
    """A package that no automatic installer handles on this platform."""
    return Step(name, lambda ctx: ctx.note(f"{name}: {how}"), group, skip_if_bin)


def run_steps(ctx: Ctx, steps: list[Step]) -> int:
    if ctx.profile not in PROFILES:
        raise SystemExit(f"unknown profile {ctx.profile!r}; use one of: {', '.join(PROFILES)}")
    groups = PROFILES[ctx.profile]
    mode = " (dry run)" if ctx.dry_run else ""
    print(f"platform={ctx.platform} profile={ctx.profile}{mode}")

    failed: list[str] = []
    for step in steps:
        if step.group not in groups:
            print(f"- {step.name}: skip (group {step.group!r} not in profile {ctx.profile!r})")
            continue
        if step.skip_if_bin and has_bin(*step.skip_if_bin):
            print(f"- {step.name}: skip (already on PATH)")
            continue
        print(f"- {step.name}", flush=True)
        try:
            step.action(ctx)
        except Exception as exc:  # noqa: BLE001 - one bad step must not stop the rest
            print(f"  ! {step.name} failed: {exc}")
            failed.append(step.name)

    if ctx.notes:
        print("\nInstall these by hand:")
        for n in ctx.notes:
            print(f"  * {n}")
    if failed:
        print(f"\nFailed steps: {', '.join(failed)}")
        return 1
    return 0
