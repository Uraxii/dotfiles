#!/usr/bin/env python3
"""Generate ~/.config/opencode/opencode.json from opencode.json.tmpl.

Loads models.defaults, then models.local (if present) for overrides.
Both files use KEY="value" lines (shell-compatible). Lines starting with
# and blank lines are ignored.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "opencode"
TMPL = CONFIG_DIR / "opencode.json.tmpl"
DEFAULTS = CONFIG_DIR / "models.defaults"
LOCAL = CONFIG_DIR / "models.local"
OUT = CONFIG_DIR / "opencode.json"

ASSIGN_RE = re.compile(r'^\s*([A-Z_][A-Z0-9_]*)\s*=\s*"?([^"\n]*)"?\s*$')
PLACEHOLDER_RE = re.compile(r"##([A-Z_][A-Z0-9_]*)##")


def load_vars(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = ASSIGN_RE.match(line)
        if not m:
            print(f"warn: skipping unparsable line in {path.name}: {raw!r}", file=sys.stderr)
            continue
        out[m.group(1)] = m.group(2)
    return out


def main() -> int:
    for required in (TMPL, DEFAULTS):
        if not required.is_file():
            print(f"missing: {required}", file=sys.stderr)
            return 1

    values = load_vars(DEFAULTS)
    if LOCAL.is_file():
        values.update(load_vars(LOCAL))

    tmpl = TMPL.read_text()
    missing: set[str] = set()

    def sub(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            missing.add(key)
            return match.group(0)
        return values[key]

    rendered = PLACEHOLDER_RE.sub(sub, tmpl)

    if missing:
        print("unsubstituted placeholders:", file=sys.stderr)
        for k in sorted(missing):
            print(f"  ##{k}##", file=sys.stderr)
        return 1

    OUT.write_text(rendered)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
