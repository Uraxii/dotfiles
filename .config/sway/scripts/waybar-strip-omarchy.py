#!/usr/bin/env python3
"""Strip Omarchy-dependent modules from a HANCORE waybar config.

Why: HANCORE themes call commands like omarchy-voxtype-status, wttrbar,
waybar-module-pacman-updates, and scripts under $OMARCHY_PATH. When those
are absent (we are not on Omarchy), the custom modules either log errors
or SEGV waybar — especially modules declaring return-type: json that
receive non-JSON on stdin.

Behavior:
- Reads waybar config (jsonc) from argv[1].
- Removes any "custom/*" module whose exec/on-click/etc. references one of
  the Omarchy-specific patterns.
- Also drops references to those module names from modules-left,
  modules-center, modules-right (and any "modules" array).
- Strips // line comments and /* */ block comments outside strings.
- Writes plain JSON back over the same file.

Idempotent: safe to run on already-stripped config.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

OMARCHY_PATTERNS = re.compile(
    r"omarchy|wttrbar|waybar-module-pacman-updates|\$OMARCHY_PATH"
)


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


def is_omarchy_module(name: str, body: dict | None) -> bool:
    """A custom/* module is Omarchy-tied if its name or any string field
    matches the OMARCHY_PATTERNS regex."""
    if not name.startswith("custom/"):
        return False
    haystack = [name]
    if isinstance(body, dict):
        for v in body.values():
            if isinstance(v, str):
                haystack.append(v)
    return any(OMARCHY_PATTERNS.search(s) for s in haystack)


def filter_modules(cfg: dict) -> dict:
    """Remove Omarchy module definitions + references in a single bar config."""
    omarchy_names: set[str] = set()
    for key, val in list(cfg.items()):
        if key.startswith("custom/") and is_omarchy_module(key, val):
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
