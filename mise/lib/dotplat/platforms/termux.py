"""Termux (Android): `pkg`, single user, no sudo, no Wayland.

mise installs the user tools here too (Termux ships its own `mise` build).
Python and Node are the exception: they come from pkg, and mise skips them
through MISE_DISABLE_TOOLS=python,node (set by bootstrap.sh, the setup
task, and the shell configs), because mise's own builds of them are not
known to run on Android.
"""

from __future__ import annotations

from .. import common
from ..runner import Step, command, manual

PKG = ["pkg", "install", "-y"]

CORE = [
    "mise", "python", "nodejs",         # mise skips python and node here
    "git", "stow", "fish", "zsh", "tmux",
    "clang", "make", "unzip",           # no gcc on termux
]


def steps() -> list[Step]:
    return [
        command("pkg: core", PKG + CORE),
        manual("nerd font", "copy 0xProto Nerd Font to ~/.termux/font.ttf, then run termux-reload-settings"),
        common.hermes(),
        common.login_shell(),
    ]
