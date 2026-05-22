#!/usr/bin/env python3
"""Update model lines in ~/.config/opencode/agents/*.md.

Loads models.defaults, then models.local (if present) for overrides.
Both files use KEY="value" lines (shell-compatible). Lines starting with
# and blank lines are ignored.

Agent-to-model key mapping comes from agent-model-map.cfg.
Format per line: <agent-file>.md: <MODEL_KEY>
Example: security-auditor.md: MODEL_SECURITY_AUDITOR
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CONFIG_DIR = Path.home() / "dotfiles" / ".config" / "opencode"
AGENTS_DIR = CONFIG_DIR / "agents"
DEFAULTS = CONFIG_DIR / "models.defaults"
LOCAL = CONFIG_DIR / "models.local"
MAP_FILE = CONFIG_DIR / "agent-model-map.cfg"

ASSIGN_RE = re.compile(r'^\s*([A-Z_][A-Z0-9_]*)\s*=\s*"?([^"\n]*)"?\s*$')
MODEL_LINE_RE = re.compile(r"^(\s*model:\s*)(\S+)(\s*)$", re.MULTILINE)
MAP_RE = re.compile(r"^\s*([a-z0-9][a-z0-9-]*\.md)\s*:\s*([A-Z_][A-Z0-9_]*)\s*$")


def load_vars(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = ASSIGN_RE.match(line)
        if not m:
            print(
                f"warn: skipping unparsable line in {path.name}: {raw!r}",
                file=sys.stderr,
            )
            continue
        out[m.group(1)] = m.group(2)
    return out


def load_map(path: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = MAP_RE.match(line)
        if not m:
            print(
                f"warn: skipping unparsable map line in {path.name}: {raw!r}",
                file=sys.stderr,
            )
            continue
        mapping[m.group(1)] = m.group(2)
    return mapping


def main() -> int:
    if not DEFAULTS.is_file():
        print(f"missing: {DEFAULTS}", file=sys.stderr)
        return 1
    if not AGENTS_DIR.is_dir():
        print(f"missing: {AGENTS_DIR}", file=sys.stderr)
        return 1
    if not MAP_FILE.is_file():
        print(f"missing: {MAP_FILE}", file=sys.stderr)
        return 1

    values = load_vars(DEFAULTS)
    if LOCAL.is_file():
        values.update(load_vars(LOCAL))
    map_cfg = load_map(MAP_FILE)

    missing: set[str] = set()
    updated = 0

    for agent_file in sorted(AGENTS_DIR.glob("*.md")):
        model_key = map_cfg.get(agent_file.name)
        if model_key is None:
            missing.add(f"MAP:{agent_file.name}")
            continue
        model = values.get(model_key)
        if model is None:
            missing.add(model_key)
            continue

        original = agent_file.read_text()
        replaced, count = MODEL_LINE_RE.subn(rf"\1{model}\3", original, count=1)
        if count == 0:
            print(f"warn: no model line in {agent_file.name}", file=sys.stderr)
            continue
        if replaced != original:
            agent_file.write_text(replaced)
            updated += 1

    if missing:
        print("missing model keys:", file=sys.stderr)
        for key in sorted(missing):
            print(f"  {key}", file=sys.stderr)
        return 1

    print(f"updated {updated} agent file(s) in {AGENTS_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
