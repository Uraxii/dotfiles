"""Fedora: dnf, plus upstream installers.

Bazzite is NOT here; it has its own module (atomic image, no dnf layering).
"""

from __future__ import annotations

from .. import common
from ..runner import Step, command, manual

DNF = ["sudo", "dnf", "install", "-y"]

CORE = [
    "git", "stow", "fish", "zsh", "tmux",
    "gcc", "make", "unzip",
    "pango", "cairo", "gdk-pixbuf2", "libffi",
]

DESKTOP = [
    "sway", "swayidle", "swaybg", "waybar", "wofi",
    "pavucontrol", "wl-clipboard",
]


def steps() -> list[Step]:
    return [
        command("dnf: core", DNF + CORE),
        command("dnf: desktop", DNF + DESKTOP, group="desktop"),
        common.docker_script(),
        common.networkmanager_dmenu(),
        common.nerd_font(),
        common.godots_linux(),
        manual("swaylock-effects", "build from https://github.com/jirutka/swaylock-effects",
               group="desktop", skip_if_bin=("swaylock",)),
        manual("ghostty", "see https://ghostty.org/docs/install/binary",
               group="desktop", skip_if_bin=("ghostty",)),
        manual("obsidian", "install the flatpak md.obsidian.Obsidian or the AppImage",
               group="desktop", skip_if_bin=("obsidian",)),
        common.hermes(),
        common.login_shell(),
    ]
