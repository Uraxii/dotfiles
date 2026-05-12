#!/usr/bin/env python3
"""Render SSoT agent/skill/template bodies to Claude + OpenCode trees.

Usage:
  python3 scripts/pipeline-render.py [--dry-run]

Exit codes:
  0  success
  1  error
  3  hand-edited target detected (missing sentinel) — NO writes occurred
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

__all__ = ["main"]

SENTINEL_TMPL = "<!-- GENERATED FROM {src} — DO NOT EDIT -->"
SENTINEL_RE = re.compile(r"^<!-- GENERATED FROM .+ — DO NOT EDIT -->")

SHARED_DIR = Path(__file__).parent.parent / ".pipeline" / "_shared"
REPO_ROOT = Path(__file__).parent.parent

PLAN_PATH_ID_RE = re.compile(r"\{\{PLAN_PATH:([^}]+)\}\}")
INVOKE_RE = re.compile(r"\{\{INVOKE:([^:}]+):([^}]*)\}\}")
INCLUDE_RE = re.compile(r"\{\{INCLUDE:\s*([^}]+)\}\}")


def load_manifest() -> dict:
    return json.loads((SHARED_DIR / "manifest.json").read_text())


def expand_includes(text: str, base: Path) -> str:
    """Pre-render pass: expand {{INCLUDE:<path>}} directives."""
    def _replace(m: re.Match) -> str:
        rel = m.group(1).strip()
        # Resolve relative to repo root
        target = (
            REPO_ROOT / ".pipeline" / rel
            if not rel.startswith("/")
            else Path(rel)
        )
        if not target.exists():
            raise FileNotFoundError(f"INCLUDE target not found: {target}")
        return target.read_text()
    return INCLUDE_RE.sub(_replace, text)


def apply_placeholders(text: str, platform: str, manifest: dict) -> str:
    """Placeholder substitution pass (5 placeholders)."""
    replacements = manifest["replacements"]

    # {{SPAWN_TOOL}}
    text = text.replace("{{SPAWN_TOOL}}", replacements["{{SPAWN_TOOL}}"][platform])

    # {{ROOT_TOOL_SURFACE}}
    text = text.replace(
        "{{ROOT_TOOL_SURFACE}}",
        replacements["{{ROOT_TOOL_SURFACE}}"][platform]
    )

    # {{AGENTS_DIR}}
    text = text.replace("{{AGENTS_DIR}}", replacements["{{AGENTS_DIR}}"][platform])

    # {{PLAN_PATH:<id>}} — replace <id> with actual id placeholder
    def _plan_path(m: re.Match) -> str:
        plan_id = m.group(1)
        tmpl = manifest["plan_path_template"][platform]
        return tmpl.replace("<id>", plan_id)
    text = PLAN_PATH_ID_RE.sub(_plan_path, text)

    # {{INVOKE:<skill>:<args>}} — platform-aware invocation syntax
    invoke_table = manifest["invoke_table"]
    def _invoke(m: re.Match) -> str:
        skill = m.group(1)
        args = m.group(2)
        if skill not in invoke_table:
            return m.group(0)  # unknown skill — leave as-is
        tmpl = invoke_table[skill][platform]
        return tmpl.replace("<args>", args)
    text = INVOKE_RE.sub(_invoke, text)

    return text


def sentinel_offender(path: Path) -> str | None:
    """Return path string if file exists and lacks sentinel header, else None."""
    if not path.exists():
        return None
    first_line = path.read_text().split("\n", 1)[0]
    if not SENTINEL_RE.match(first_line):
        return str(path)
    return None


def build_claude_frontmatter(role: str, claude_fm: dict) -> str:
    lines = [f"name: {role}"]
    if "description" in claude_fm:
        lines.append(f"description: {claude_fm['description']}")
    if "model" in claude_fm:
        lines.append(f"model: {claude_fm['model']}")
    if "tools" in claude_fm:
        lines.append(f"tools: {claude_fm['tools']}")
    return "---\n" + "\n".join(lines) + "\n---\n\n"


def build_oc_frontmatter(oc_fm: dict) -> str:
    lines = []
    for key in ("description", "mode", "color", "model", "steps"):
        if key in oc_fm:
            lines.append(f"{key}: {oc_fm[key]}")
    # permission block — omit entirely when empty (S16)
    perm = oc_fm.get("permission", {})
    if perm:
        lines.append("permission:")
        for k, v in perm.items():
            if isinstance(v, dict):
                lines.append(f"  {k}:")
                for pk, pv in v.items():
                    lines.append(f"    {pk}: {pv}")
            else:
                lines.append(f"  {k}: {v}")
    return "---\n" + "\n".join(lines) + "\n---\n\n"


def collect_agent_targets(manifest: dict) -> list[Path]:
    """Collect all agent render target paths for pre-flight check."""
    targets: list[Path] = []
    agents_dir = SHARED_DIR / "agents"
    if not agents_dir.exists():
        return targets
    for agent in manifest["agents"]:
        role = agent["role"]
        targets.append(REPO_ROOT / ".claude" / "agents" / f"{role}.md")
        targets.append(REPO_ROOT / ".config" / "opencode" / "agents" / f"{role}.md")
    return targets


def collect_skill_targets(manifest: dict) -> list[Path]:
    """Collect all skill render target paths for pre-flight check."""
    targets: list[Path] = []
    skills_dir = SHARED_DIR / "skills"
    if not skills_dir.exists():
        return targets
    shared_skills = set(manifest["skills"]["shared"])
    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        name = skill_dir.name
        if not (skill_dir / "SKILL.md").exists():
            continue
        targets.append(REPO_ROOT / ".claude" / "skills" / name / "SKILL.md")
        if name in shared_skills:
            targets.append(
                REPO_ROOT / ".config" / "opencode" / "skills" / name / "SKILL.md"
            )
    return targets


def collect_template_targets() -> list[Path]:
    """Collect template render target paths for pre-flight check."""
    if not (SHARED_DIR / "templates" / "role-template.md").exists():
        return []
    return [
        REPO_ROOT / ".claude" / "templates" / "role-template.md",
        REPO_ROOT / ".config" / "opencode" / "templates" / "role-template.md",
    ]


def preflight_sentinel_check(manifest: dict) -> int:
    """Check ALL targets for missing sentinels before any write.

    Returns 0 if all clear, 3 if any offender found.
    """
    all_targets = (
        collect_agent_targets(manifest)
        + collect_skill_targets(manifest)
        + collect_template_targets()
    )
    offenders = [p for p in all_targets if sentinel_offender(p)]
    if not offenders:
        return 0
    print(
        "ERROR: The following targets exist but lack the generated-file sentinel.\n"
        "  Move edits to _shared/ manifest and re-render.",
        file=sys.stderr,
    )
    for p in offenders:
        print(f"  {p}", file=sys.stderr)
    return 3


def write_agent(role: str, platforms: dict, body: str, manifest: dict) -> None:
    """Write agent outputs (sentinel already verified by pre-flight)."""
    body_expanded = expand_includes(body, SHARED_DIR)

    claude_body = apply_placeholders(body_expanded, "claude", manifest)
    oc_body = apply_placeholders(body_expanded, "opencode", manifest)

    claude_fm = build_claude_frontmatter(role, platforms.get("claude", {}))
    oc_fm = build_oc_frontmatter(platforms.get("opencode", {}))

    src_rel = f".pipeline/_shared/agents/{role}.body.md"
    sentinel = SENTINEL_TMPL.format(src=src_rel)

    claude_out = REPO_ROOT / ".claude" / "agents" / f"{role}.md"
    oc_out = REPO_ROOT / ".config" / "opencode" / "agents" / f"{role}.md"

    claude_out.parent.mkdir(parents=True, exist_ok=True)
    oc_out.parent.mkdir(parents=True, exist_ok=True)

    claude_out.write_text(sentinel + "\n" + claude_fm + claude_body)
    oc_out.write_text(sentinel + "\n" + oc_fm + oc_body)


def parse_skill_frontmatter(body: str) -> tuple[dict, str]:
    """Parse SKILL.md frontmatter. Returns (fm_data, body_without_fm)."""
    if not body.startswith("---"):
        return {}, body
    parts = body.split("---", 2)
    if len(parts) < 3:
        return {}, body
    fm_data: dict = {}
    for line in parts[1].strip().splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm_data[k.strip()] = v.strip()
    return fm_data, parts[2].lstrip("\n")


def write_skill(name: str, skill_class: str, body: str, manifest: dict) -> None:
    """Write skill outputs (sentinel already verified by pre-flight)."""
    src_rel = f".pipeline/_shared/skills/{name}/SKILL.md"
    sentinel = SENTINEL_TMPL.format(src=src_rel)

    fm_data, body_only = parse_skill_frontmatter(body)

    body_expanded = expand_includes(body_only, SHARED_DIR)
    claude_body = apply_placeholders(body_expanded, "claude", manifest)
    claude_fm = build_skill_claude_frontmatter(name, fm_data)
    claude_out = REPO_ROOT / ".claude" / "skills" / name / "SKILL.md"
    claude_out.parent.mkdir(parents=True, exist_ok=True)
    claude_out.write_text(sentinel + "\n" + claude_fm + claude_body)

    if skill_class == "shared":
        oc_body = apply_placeholders(body_expanded, "opencode", manifest)
        oc_fm = build_skill_oc_frontmatter(name, fm_data)
        oc_out = REPO_ROOT / ".config" / "opencode" / "skills" / name / "SKILL.md"
        oc_out.parent.mkdir(parents=True, exist_ok=True)
        oc_out.write_text(sentinel + "\n" + oc_fm + oc_body)


def build_skill_claude_frontmatter(name: str, skill_fm: dict) -> str:
    lines = [f"name: {name}"]
    if "description" in skill_fm:
        lines.append(f"description: {skill_fm['description']}")
    for key in ("disable-model-invocation", "source", "output-style"):
        if key in skill_fm:
            lines.append(f"{key}: {skill_fm[key]}")
    return "---\n" + "\n".join(lines) + "\n---\n\n"


def build_skill_oc_frontmatter(name: str, skill_fm: dict) -> str:
    lines = [f"name: {name}"]
    for key in ("description", "license", "compatibility"):
        if key in skill_fm:
            lines.append(f"{key}: {skill_fm[key]}")
    if "metadata" in skill_fm:
        meta = skill_fm["metadata"]
        lines.append("metadata:")
        for k, v in meta.items():
            lines.append(f"  {k}: {v}")
    return "---\n" + "\n".join(lines) + "\n---\n\n"


def write_template(manifest: dict) -> None:
    """Write template outputs (sentinel already verified by pre-flight)."""
    src = SHARED_DIR / "templates" / "role-template.md"
    if not src.exists():
        return
    body = src.read_text()
    sentinel = SENTINEL_TMPL.format(
        src=".pipeline/_shared/templates/role-template.md"
    )
    for platform, out_dir in [
        ("claude", REPO_ROOT / ".claude" / "templates"),
        ("opencode", REPO_ROOT / ".config" / "opencode" / "templates"),
    ]:
        rendered = apply_placeholders(body, platform, manifest)
        out = out_dir / "role-template.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(sentinel + "\n" + rendered)


def dry_run_list(manifest: dict) -> None:
    """Print all planned write targets without executing."""
    print("Dry run — planned writes:")
    for p in collect_agent_targets(manifest):
        print(f"  [dry-run] would write {p}")
    for p in collect_skill_targets(manifest):
        print(f"  [dry-run] would write {p}")
    for p in collect_template_targets():
        print(f"  [dry-run] would write {p}")
    print("Dry run complete.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render SSoT pipeline bodies to Claude + OpenCode trees."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="List planned writes without executing."
    )
    args = parser.parse_args()

    manifest = load_manifest()

    if args.dry_run:
        dry_run_list(manifest)
        return 0

    # --- PASS 1: pre-flight sentinel check (no writes yet) ---
    rc = preflight_sentinel_check(manifest)
    if rc != 0:
        return rc

    # --- PASS 2: write all targets ---
    agents_dir = SHARED_DIR / "agents"
    if agents_dir.exists():
        for agent in manifest["agents"]:
            role = agent["role"]
            body_path = agents_dir / f"{role}.body.md"
            platforms_path = agents_dir / f"{role}.platforms.json"
            if not body_path.exists():
                print(f"WARN: missing body {body_path}", file=sys.stderr)
                continue
            if not platforms_path.exists():
                print(f"WARN: missing platforms {platforms_path}", file=sys.stderr)
                continue
            body = body_path.read_text()
            platforms = json.loads(platforms_path.read_text())
            write_agent(role, platforms, body, manifest)
            print(f"  rendered agent: {role}")

    skills_dir = SHARED_DIR / "skills"
    shared_skills = set(manifest["skills"]["shared"])
    custom_tool_skills = set(manifest["skills"]["custom-tool-only"])
    if skills_dir.exists():
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            name = skill_dir.name
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue
            if name in shared_skills:
                skill_class = "shared"
            elif name in custom_tool_skills:
                skill_class = "custom-tool-only"
            else:
                skill_class = "unknown"
            body = skill_md.read_text()
            write_skill(name, skill_class, body, manifest)
            print(f"  rendered skill: {name} ({skill_class})")

    write_template(manifest)
    print("  rendered template: role-template.md")
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
