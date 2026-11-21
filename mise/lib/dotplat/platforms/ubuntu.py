"""Ubuntu, Debian, Mint, Pop!_OS: apt, plus upstream installers."""

from __future__ import annotations

from .. import common
from ..runner import Step, command, manual

APT = ["sudo", "apt-get", "install", "-y"]

CORE = [
    "git", "stow", "fish", "zsh", "tmux",
    "gcc", "make", "unzip", "curl",
    "libpango-1.0-0", "libcairo2", "libgdk-pixbuf-2.0-0", "libffi8",
]

DESKTOP = [
    "sway", "swayidle", "swaybg", "waybar", "wofi",
    "pavucontrol", "wl-clipboard",
]


def steps() -> list[Step]:
    return [
        command("apt: update", ["sudo", "apt-get", "update"]),
        command("apt: core", APT + CORE),
        command("apt: desktop", APT + DESKTOP, group="desktop"),
        common.docker_script(),
        common.networkmanager_dmenu(),
        common.nerd_font(),
        common.godots_linux(),
        manual("swaylock-effects", "build from https://github.com/jirutka/swaylock-effects",
               group="desktop", skip_if_bin=("swaylock",)),
        manual("ghostty", "see https://ghostty.org/docs/install/binary",
               group="desktop", skip_if_bin=("ghostty",)),
        manual("obsidian", "download the .deb from https://obsidian.md/download",
               group="desktop", skip_if_bin=("obsidian",)),
        common.hermes(),
        common.login_shell(),
    ]
