#!/usr/bin/env python3
"""In plain words: makes sure KDE's window tiler (the Polonium KWin script)
is installed and set up the way Nicole actually runs it, so a fresh machine
gets automatic window tiling instead of her having to click through
Polonium's settings dialog by hand and re-derive the ignore list.

Installs this repo's copy of the Polonium KWin script to
~/.local/share/kwin/scripts/polonium/ if that folder is missing or holds a
different version (read from each side's own metadata.json, never
hardcoded), then writes the four kwinrc settings Polonium reads: whether
the plugin is enabled, whether a new window inserts into the split the
focused window is in, which side of that split it lands on, and which
window classes Polonium must never try to tile.

Idempotent: every setting is read with kreadconfig6 before it is written,
so a value already correct is left untouched, no kwriteconfig6 call, no
rewrite of kwinrc. Ends with a live `qdbus6 ... reconfigure` call so KWin
picks up whatever changed without a logout.

    ./apply-polonium-settings.py            # apply
    ./apply-polonium-settings.py --check    # report only, change nothing
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

KWIN_FILE = "kwinrc"  # bare name: kreadconfig6/kwriteconfig6 resolve it under ~/.config
VENDORED_SCRIPT_DIR = Path(__file__).with_name("polonium")
INSTALLED_SCRIPT_DIR = Path.home() / ".local/share/kwin/scripts/polonium"

# Krohnkite's shipped defaults, kept as-is: krunner, yakuake, kded, polkit,
# plasmashell, xwaylandvideobridge. Everything after that was added by hand:
#
#   winedbg.exe - Wine's crash dialog. It has no parent window, so KDE sees
#     it as an ordinary top-level window and Polonium would otherwise try
#     to tile it.
#   org.kde.polkit-kde-authentication-agent-1 - the real password-prompt
#     dialog's window class. The short "polkit" above is ALSO in this list
#     (inherited from Krohnkite's defaults) and matches nothing on its own:
#     Polonium anchors every entry as an exact match (^...$) whenever
#     RawRegex is false, which it is here, so "polkit" never matches the
#     agent's real class. Kept anyway so nobody "cleans up" the apparent
#     duplicate and re-breaks the password prompt.
#   spectacle, ksplashqml, ksmserver-logout-greeter, kruler, kwin_wayland -
#     the rest of Krohnkite's recommended additions beyond its own shipped
#     defaults: the screenshot tool, the splash screen, the logout screen,
#     the screen-ruler overlay, and KWin's own compositor window.
IGNORE_WINDOW_CLASSES = ", ".join([
    "krunner", "yakuake", "kded", "polkit", "plasmashell",
    "xwaylandvideobridge", "winedbg.exe", "spectacle", "ksplashqml",
    "ksmserver-logout-greeter", "org.kde.polkit-kde-authentication-agent-1",
    "kruler", "kwin_wayland",
])

DESIRED_SETTINGS = [
    # (group, key, value)
    ("Plugins", "poloniumEnabled", "true"),
    ("Script-polonium", "BTreeInsertInActive", "true"),
    ("Script-polonium", "BTreeInsertionStyle", "1"),
    ("Script-polonium", "IgnoreWindowClasses", IGNORE_WINDOW_CLASSES),
]


def kreadconfig(group: str, key: str) -> str:
    result = subprocess.run(
        ["kreadconfig6", "--file", KWIN_FILE, "--group", group, "--key", key],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.rstrip("\n")


def kwriteconfig(group: str, key: str, value: str) -> None:
    subprocess.run(
        ["kwriteconfig6", "--file", KWIN_FILE, "--group", group, "--key", key, value],
        check=True,
    )


def script_version(metadata_path: Path) -> str | None:
    if not metadata_path.exists():
        return None
    metadata = json.loads(metadata_path.read_text())
    return metadata["KPlugin"]["Version"]


def install_script(check: bool) -> bool:
    """Copy the vendored Polonium script over the installed one if missing
    or at a different version. Returns whether a copy happened (or, under
    --check, would happen)."""
    vendored = script_version(VENDORED_SCRIPT_DIR / "metadata.json")
    installed = script_version(INSTALLED_SCRIPT_DIR / "metadata.json")
    if installed == vendored:
        return False
    verb = "would install" if check else "installing"
    print(f"{verb} Polonium {vendored} to {INSTALLED_SCRIPT_DIR} "
          f"(currently {installed or 'not installed'})")
    if not check:
        if INSTALLED_SCRIPT_DIR.exists():
            shutil.rmtree(INSTALLED_SCRIPT_DIR)
        shutil.copytree(VENDORED_SCRIPT_DIR, INSTALLED_SCRIPT_DIR)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="report what would change; write nothing")
    args = parser.parse_args()

    installed = install_script(args.check)

    to_write = [(group, key, value) for group, key, value in DESIRED_SETTINGS
                if kreadconfig(group, key) != value]

    if not to_write and not installed:
        print("nothing to do; Polonium already matches the recorded setup")
        return 0

    for group, key, value in to_write:
        print(f"  [{group}] {key} = {value}")

    if args.check:
        if to_write:
            print("--check given, no changes written")
        return 0

    for group, key, value in to_write:
        kwriteconfig(group, key, value)

    failed = [(g, k, v) for g, k, v in to_write if kreadconfig(g, k) != v]
    if failed:
        print(f"FAILED readback on: {failed}")
        return 1

    subprocess.run(
        ["qdbus6", "org.kde.KWin", "/KWin", "org.kde.KWin.reconfigure"],
        check=True,
    )
    print("done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
