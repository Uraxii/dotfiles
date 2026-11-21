"""Platform detection: the switchboard key for every mise task.

The result goes in the DOTFILES_PLATFORM environment variable. If that
variable is already set, it wins: use it to test another platform's rules,
for example `DOTFILES_PLATFORM=fedora mise run system --dry-run`.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ENV_VAR = "DOTFILES_PLATFORM"

PLATFORMS = ("arch", "nixos", "ubuntu", "fedora", "bazzite", "termux", "windows")

# os-release ID / ID_LIKE value -> platform. Order of lookup is ID first,
# then each ID_LIKE word, so a derivative maps to its parent family.
ALIASES: dict[str, str] = {
    "arch": "arch", "manjaro": "arch", "endeavouros": "arch", "garuda": "arch",
    "cachyos": "arch",
    "nixos": "nixos",
    "ubuntu": "ubuntu", "debian": "ubuntu", "linuxmint": "ubuntu", "pop": "ubuntu",
    "fedora": "fedora",
    # Bazzite reports ID=bazzite, ID_LIKE="fedora". It must not map to fedora:
    # dnf layering is discouraged on atomic images, so it has its own rules.
    "bazzite": "bazzite",
}


# Platforms where mise's prebuilt python and node do not run (Android's
# bionic libc; NixOS has no /lib64/ld-linux). There, python and node come
# from the platform's own packages and mise skips them. bootstrap.sh and the
# fish, zsh and bash configs set the same value.
SYSTEM_RUNTIMES: dict[str, str] = {"termux": "python,node", "nixos": "python,node"}


def use_system_runtimes(platform: str, environ: dict[str, str] | None = None) -> None:
    """Set MISE_DISABLE_TOOLS for platforms in SYSTEM_RUNTIMES (if unset)."""
    environ = os.environ if environ is None else environ
    if platform in SYSTEM_RUNTIMES:
        environ.setdefault("MISE_DISABLE_TOOLS", SYSTEM_RUNTIMES[platform])


class UnsupportedPlatform(SystemExit):
    pass


def parse_os_release(text: str) -> dict[str, str]:
    kv: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        k, v = line.split("=", 1)
        kv[k.strip()] = v.strip().strip('"').strip("'")
    return kv


# Enterprise Linux reports ID_LIKE="rhel ... fedora", so without this check it
# would match fedora. Its base repos lack stow, fish and the sway stack.
EL_IDS = frozenset({"rhel", "centos", "rocky", "almalinux", "ol"})


def from_os_release(kv: dict[str, str]) -> str:
    candidates = [kv.get("ID", "").lower(), *kv.get("ID_LIKE", "").lower().split()]
    if EL_IDS.intersection(candidates):
        raise UnsupportedPlatform(
            f"unsupported distro: {kv.get('ID')!r} is Enterprise Linux; the fedora rules "
            "need packages (stow, fish, sway) that its base repos do not have"
        )
    for c in candidates:
        if c in ALIASES:
            return ALIASES[c]
    raise UnsupportedPlatform(
        f"unsupported distro: ID={kv.get('ID')!r} ID_LIKE={kv.get('ID_LIKE')!r}"
    )


def detect(
    environ: dict[str, str] | None = None,
    sys_platform: str | None = None,
    os_release: Path = Path("/etc/os-release"),
) -> str:
    """Detect the platform. Does not read or write DOTFILES_PLATFORM."""
    environ = os.environ if environ is None else environ
    sys_platform = sys.platform if sys_platform is None else sys_platform
    if sys_platform == "win32":
        return "windows"
    # Termux is Android: there is no /etc/os-release on the Android root.
    # Termux always exports TERMUX_VERSION, so that is the signal.
    if environ.get("TERMUX_VERSION"):
        return "termux"
    if sys_platform == "darwin":
        raise UnsupportedPlatform("unsupported platform: macOS has no rules yet")
    if not os_release.exists():
        raise UnsupportedPlatform(f"cannot detect distro: {os_release} is missing")
    return from_os_release(parse_os_release(os_release.read_text()))


def current(environ: dict[str, str] | None = None) -> str:
    """Return the platform and export it in DOTFILES_PLATFORM.

    A value that is already set is the override. It must name a known
    platform. Child processes of the task see the exported value.
    """
    environ = os.environ if environ is None else environ
    override = environ.get(ENV_VAR, "").strip().lower()
    if override:
        if override not in PLATFORMS:
            raise UnsupportedPlatform(
                f"{ENV_VAR}={override!r} is not one of: {', '.join(PLATFORMS)}"
            )
        platform = override
    else:
        platform = detect(environ)
    environ[ENV_VAR] = platform
    return platform
