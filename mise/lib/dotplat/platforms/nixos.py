"""NixOS: per-user `nix profile install`.

System services (sway session, docker daemon) belong in configuration.nix.
This module only fills the user profile.

mise's prebuilt python and node do not run on NixOS (no /lib64/ld-linux),
so they come from nixpkgs and mise skips them (detect.SYSTEM_RUNTIMES).
Other prebuilt mise tools need nix-ld (`programs.nix-ld.enable = true;`).
"""

from __future__ import annotations

from .. import common
from ..runner import Step, manual

CORE = [
    "mise", "python3", "nodejs",     # mise skips python and node here
    "git", "stow", "fish", "zsh", "tmux",
    "gcc", "gnumake", "unzip",
    "pango", "cairo", "gdk-pixbuf", "libffi",
]

DESKTOP = [
    "sway", "swayidle", "swaybg", "swaylock-effects", "waybar", "wofi",
    "networkmanager_dmenu", "pavucontrol", "wl-clipboard", "ghostty",
    "nerd-fonts._0xproto",
]

DESKTOP_UNFREE = ["obsidian"]


def steps() -> list[Step]:
    return [
        common.nix_profile(CORE),
        common.nix_profile(DESKTOP, group="desktop"),
        common.nix_profile(DESKTOP_UNFREE, group="desktop", unfree=True),
        manual("docker", "set `virtualisation.docker.enable = true;` in configuration.nix",
               skip_if_bin=("docker",)),
        manual("godots", "no nixpkgs package; use the upstream release zip",
               group="desktop", skip_if_bin=("godots",)),
        common.hermes(),
        common.login_shell(),
    ]
