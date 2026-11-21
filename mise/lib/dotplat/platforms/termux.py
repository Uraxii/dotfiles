"""Termux (Android): `pkg`, single user, no sudo, no Wayland.

mise support on Android is limited and some prebuilt binaries do not run
there. So on Termux this module also installs the user tools that mise
installs on the other platforms. Skip `mise install` on Termux.
"""

from __future__ import annotations

from .. import common
from ..runner import Step, command, manual

PKG = ["pkg", "install", "-y"]

CORE = [
    "git", "stow", "fish", "zsh", "tmux",
    "clang", "make", "unzip",           # no gcc on termux
]

# The [tools] of mise/config.toml, from the Termux repos.
TOOLS = [
    "python", "uv", "nodejs", "neovim", "ripgrep", "fd", "fzf", "bat", "jq",
    "gh", "starship", "zoxide", "glow", "tealdeer",
]

NPM_TOOLS = ["@anthropic-ai/claude-code", "opencode-ai", "@earendil-works/pi-coding-agent"]


def steps() -> list[Step]:
    return [
        command("pkg: core", PKG + CORE),
        command("pkg: user tools", PKG + TOOLS),
        command("npm: ai tools", ["npm", "install", "-g", *NPM_TOOLS]),
        command("uv: python tools", ["uv", "tool", "install", "graphifyy"],
                skip_if_bin=("graphify",)),
        command("uv: xonsh", ["uv", "tool", "install", "xonsh[full]"],
                skip_if_bin=("xonsh",)),
        manual("nerd font", "copy 0xProto Nerd Font to ~/.termux/font.ttf, then run termux-reload-settings"),
        common.hermes(),
        common.login_shell(),
    ]
