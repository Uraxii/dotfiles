"""Arch Linux and derivatives (Manjaro, EndeavourOS, Garuda): pacman + AUR."""

from __future__ import annotations

from .. import common
from ..runner import Step, command

PACMAN = ["sudo", "pacman", "-S", "--needed", "--noconfirm"]

CORE = [
    "git", "stow", "fish", "zsh", "tmux",
    "gcc", "make", "unzip",             # treesitter and Mason builds
    "docker",
    "pango", "cairo", "gdk-pixbuf2", "libffi",  # native libs for the python pipeline
]

DESKTOP = [
    "sway", "swayidle", "swaybg", "waybar", "wofi",
    "pavucontrol", "wl-clipboard", "obsidian",
]

# paru/yay also resolve repo packages, so a package that moved from the AUR
# to the official repos still installs.
DESKTOP_AUR = [
    "swaylock-effects", "networkmanager-dmenu", "ghostty",
    "ttf-0xproto-nerd", "godots-bin",
]


def steps() -> list[Step]:
    return [
        command("pacman: core", PACMAN + CORE),
        command("pacman: desktop", PACMAN + DESKTOP, group="desktop"),
        common.aur(DESKTOP_AUR, group="desktop"),
        common.hermes(),
        common.login_shell(),
    ]
