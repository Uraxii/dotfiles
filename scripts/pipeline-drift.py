#!/usr/bin/env python3
"""Drift detection: verify rendered files match _shared/ sources.

Exit codes:
  0  all parity checks pass
  1  drift detected
  2  missing _shared/ source or invalid manifest
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

__all__ = ["main"]

SHARED_DIR = Path(__file__).parent.parent / ".pipeline" / "_shared"
REPO_ROOT = Path(__file__).parent.parent
SENTINEL_RE = re.compile(r"^<!-- GENERATED FROM .+ — DO NOT EDIT -->")


def load_manifest() -> dict:
    path = SHARED_DIR / "manifest.json"
    if not path.exists():
        print(f"ERROR: missing manifest {path}", file=sys.stderr)
        sys.exit(2)
    return json.loads(path.read_text())


def check_sentinel(path: Path, drift: list) -> None:
    if not path.exists():
        return
    first_line = path.read_text().split("\n", 1)[0]
    if not SENTINEL_RE.match(first_line):
        drift.append(f"SENTINEL: {path} missing generated-file header")


def check_rules_parity(drift: list) -> None:
    for name in ("csharp", "gdscript", "python", "typescript"):
        c = REPO_ROOT / ".claude" / "rules" / f"{name}.md"
        o = REPO_ROOT / ".config" / "opencode" / "rules" / f"{name}.md"
        if not c.exists() or not o.exists():
            drift.append(f"RULES: missing {name}.md in one or both trees")
            continue
        if c.read_text() != o.read_text():
            drift.append(f"RULES: {name}.md differs between trees")


def check_inventory(manifest: dict, drift: list) -> None:
    c_dir = REPO_ROOT / ".claude" / "agents"
    o_dir = REPO_ROOT / ".config" / "opencode" / "agents"
    if not c_dir.exists() or not o_dir.exists():
        return
    c_set = {p.name for p in c_dir.glob("*.md")}
    o_set = {p.name for p in o_dir.glob("*.md")}
    for f in sorted(c_set - o_set):
        drift.append(f"INVENTORY: only in claude: {f}")
    for f in sorted(o_set - c_set):
        drift.append(f"INVENTORY: only in opencode: {f}")


def parse_fm(text: str) -> dict:
    """Parse key:value pairs from first YAML frontmatter block."""
    lines = text.splitlines()
    # skip sentinel
    if lines and SENTINEL_RE.match(lines[0]):
        lines = lines[1:]
    fm: dict = {}
    in_fm = False
    for line in lines:
        if line.strip() == "---":
            if not in_fm:
                in_fm = True
            else:
                break
        elif in_fm and ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm


def check_frontmatter(manifest: dict, drift: list) -> None:
    for agent in manifest["agents"]:
        role = agent["role"]
        pf = SHARED_DIR / "agents" / f"{role}.platforms.json"
        if not pf.exists():
            continue
        platforms = json.loads(pf.read_text())
        for platform, out_dir in [
            ("claude", REPO_ROOT / ".claude" / "agents"),
            ("opencode", REPO_ROOT / ".config" / "opencode" / "agents"),
        ]:
            out = out_dir / f"{role}.md"
            if not out.exists():
                continue
            fm = parse_fm(out.read_text())
            expected = platforms.get(platform, {})
            for key in ("description", "model", "mode", "steps"):
                if key in expected and fm.get(key) != str(expected[key]):
                    drift.append(
                        f"FRONTMATTER: {role}/{platform} {key}="
                        f"expected={expected[key]!r} got={fm.get(key)!r}"
                    )


def main() -> int:
    manifest = load_manifest()
    drift: list = []

    check_rules_parity(drift)

    for agent in manifest["agents"]:
        role = agent["role"]
        for path in [
            REPO_ROOT / ".claude" / "agents" / f"{role}.md",
            REPO_ROOT / ".config" / "opencode" / "agents" / f"{role}.md",
        ]:
            check_sentinel(path, drift)

    for skill_class in ("shared", "custom-tool-only"):
        for name in manifest["skills"][skill_class]:
            check_sentinel(
                REPO_ROOT / ".claude" / "skills" / name / "SKILL.md", drift
            )
            if skill_class == "shared":
                check_sentinel(
                    REPO_ROOT / ".config" / "opencode" / "skills" / name / "SKILL.md",
                    drift
                )

    check_inventory(manifest, drift)
    check_frontmatter(manifest, drift)

    if drift:
        for msg in drift:
            print(f"DRIFT: {msg}")
        return 1

    print("All parity checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
