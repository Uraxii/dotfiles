#!/usr/bin/env python3
"""Strip broken custom modules from a waybar config.

Why: third-party waybar themes routinely call helper commands the local
system doesn't have (omarchy-*, wttrbar, waybar-module-pacman-updates,
$OMARCHY_PATH/...sh, custom scripts that ship in OTHER themes, etc.).
When a custom module declares `return-type: json` and its exec emits
non-JSON (or the shell can't even find the binary), waybar SEGVs in the
glib event loop.

Two strip rules:
  1. Pattern-based: known-bad commands (omarchy/wttrbar/etc.).
  2. Resolvability: any custom/* module whose `exec` target doesn't
     resolve to an existing file or PATH command gets dropped.

Behavior:
- Reads waybar config (jsonc) from argv[1].
- Removes matching "custom/*" module defs.
- Removes their names from modules-{left,center,right} and any "modules"
  array, including inside `group/*` containers.
- Strips // line and /* */ block comments outside strings + trailing
  commas so stock json.loads can parse.
- Writes plain JSON back over the same file.

Idempotent.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import sys
from pathlib import Path

OMARCHY_PATTERNS = re.compile(
    r"omarchy|wttrbar|waybar-module-pacman-updates|\$OMARCHY_PATH"
)


def exec_target_missing(exec_str: str) -> bool:
    """Return True if the exec's first word can't be found on the system.

    Handles three shapes seen in waybar custom modules:
      - `~/.config/waybar/scripts/foo.sh -j`   (path with tilde + args)
      - `/usr/bin/foo`                          (absolute path)
      - `bare-binary --flag`                    (PATH lookup)
    """
    if not exec_str:
        return False  # no exec key — not an exec module (e.g. format-only)
    try:
        words = shlex.split(exec_str, posix=True)
    except ValueError:
        return False  # unparseable; leave alone
    if not words:
        return False
    first = os.path.expanduser(os.path.expandvars(words[0]))
    if "/" in first:
        return not (os.path.isfile(first) and os.access(first, os.X_OK))
    return shutil.which(first) is None


def strip_jsonc(text: str) -> str:
    """Remove // and /* */ comments outside strings."""
    out: list[str] = []
    i = 0
    n = len(text)
    in_str = False
    str_quote = ""
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(nxt)
                i += 2
                continue
            if c == str_quote:
                in_str = False
            i += 1
            continue
        if c in ('"', "'"):
            in_str = True
            str_quote = c
            out.append(c)
            i += 1
            continue
        if c == "/" and nxt == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c == "/" and nxt == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def strip_trailing_commas(text: str) -> str:
    """waybar allows trailing commas; stock json.loads does not."""
    return re.sub(r",(\s*[}\]])", r"\1", text)


def is_broken_module(name: str, body: dict | None) -> bool:
    """A custom/* module should be stripped if either:
      - Any string field matches the known-bad pattern set, OR
      - Its `exec` field's first word doesn't resolve on this system.
    """
    if not name.startswith("custom/"):
        return False
    if isinstance(body, dict):
        for v in body.values():
            if isinstance(v, str) and OMARCHY_PATTERNS.search(v):
                return True
        if OMARCHY_PATTERNS.search(name):
            return True
        if exec_target_missing(body.get("exec", "")):
            return True
    elif OMARCHY_PATTERNS.search(name):
        return True
    return False


def filter_modules(cfg: dict) -> dict:
    """Remove Omarchy module definitions + references in a single bar config.

    Strips:
      1. Top-level custom/* defs that match OMARCHY_PATTERNS.
      2. Their names from modules-left/center/right.
      3. Their names from group/*.modules arrays (nested module containers).
    """
    omarchy_names: set[str] = set()
    for key, val in list(cfg.items()):
        if key.startswith("custom/") and is_broken_module(key, val):
            omarchy_names.add(key)
            cfg.pop(key)
    if not omarchy_names:
        return cfg
    for arr_key in (
        "modules-left",
        "modules-center",
        "modules-right",
        "modules",
    ):
        arr = cfg.get(arr_key)
        if isinstance(arr, list):
            cfg[arr_key] = [m for m in arr if m not in omarchy_names]
    # Recurse into group/* containers: each defines its own `modules` array.
    for key, val in cfg.items():
        if key.startswith("group/") and isinstance(val, dict):
            inner = val.get("modules")
            if isinstance(inner, list):
                val["modules"] = [m for m in inner if m not in omarchy_names]
    return cfg


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: waybar-strip-omarchy.py <config-file>", file=sys.stderr)
        return 2
    path = Path(argv[1])
    raw = path.read_text(encoding="utf-8")
    cleaned = strip_trailing_commas(strip_jsonc(raw))
    data = json.loads(cleaned)
    if isinstance(data, list):
        data = [filter_modules(bar) for bar in data]
    elif isinstance(data, dict):
        data = filter_modules(data)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
