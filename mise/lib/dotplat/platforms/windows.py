"""Windows: winget for system packages. mise installs the CLI tools.

Not on Windows: the sway desktop stack, fish/zsh/tmux, ghostty, stow.
mise reads its config from MISE_CONFIG_DIR, so point that at this repo's
mise/ directory instead of a stow link (see README).
"""

from __future__ import annotations

from .. import common
from ..runner import Step

CORE = [
    "Git.Git",
    "BrechtSanders.WinLibs.POSIX.UCRT",  # gcc for treesitter and Mason builds
    "ezwinports.make",
]

DESKTOP = [
    "Obsidian.Obsidian",
    "Docker.DockerDesktop",
]


def steps() -> list[Step]:
    return [
        *(common.winget(i) for i in CORE),
        *(common.winget(i, group="desktop") for i in DESKTOP),
        common.nerd_font(),
    ]
