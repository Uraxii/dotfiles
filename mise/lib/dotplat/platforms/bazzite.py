"""Bazzite (Universal Blue atomic KDE): Homebrew for CLI, flatpak for GUI.

dnf/rpm-ostree layering is discouraged on atomic images. The sway desktop
stack does not apply: Bazzite runs KDE Plasma.
"""

from __future__ import annotations

from .. import common
from ..runner import Step, command, manual

BREW = ["brew", "install"]

# git and unzip ship in the image.
CORE = [
    "stow", "fish", "zsh", "tmux",
    "gcc", "make",
    "pango", "cairo", "gdk-pixbuf", "libffi",
]

FLATPAK = ["flatpak", "install", "--user", "-y", "flathub"]

DESKTOP_FLATPAK = ["md.obsidian.Obsidian", "io.github.MakovWait.Godots"]


def steps() -> list[Step]:
    return [
        command("brew: core", BREW + CORE),
        command("flatpak: desktop", FLATPAK + DESKTOP_FLATPAK, group="desktop"),
        common.nerd_font(),
        manual("docker", "ships in the image; enable it with `ujust` (see the Bazzite docs)",
               skip_if_bin=("docker", "podman")),
        manual("ghostty", "install with `ujust` or the ghostty COPR/flatpak",
               group="desktop", skip_if_bin=("ghostty",)),
        common.hermes(),
        common.login_shell(),
    ]
