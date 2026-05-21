#!/usr/bin/env python3
"""pr-publish — generate per-shard PR publication plan from pipeline.md.

Default mode: plan-only JSON to stdout (no subprocess side effects beyond gh probe).
--apply mode: execute git push + gh pr create + gh pr merge; emit JSONL action log.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

# ── frontmatter parser (R6: constrained YAML subset) ─────────────────────────

_FM_BLOCK = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
_SCALAR = re.compile(r"^(\w[\w-]*)\s*:\s*(.+)$")
_BLOCK_KEY = re.compile(r"^(\w[\w-]*)\s*:\s*$")
_FLOW_MAP = re.compile(r"^\{(.+)\}$")
_FLOW_SEQ = re.compile(r"^\[(.+)\]$")
_BARE_KEY = re.compile(r"(\w[\w-]*)\s*:")
# Match bare-word values (not null/true/false, not numbers, not already-quoted).
# Lead char class includes digits so hex git SHAs (e.g. commit_sha: 0855bbb...)
# are captured; without digit-lead, _fix_bare_vals would skip them and json.loads
# would fail, causing _parse_flow to fall back to raw.strip() → str not dict.
# Also matches absolute paths starting with /.
_BARE_VAL = re.compile(r":\s*([a-zA-Z0-9/][a-zA-Z0-9/_.-]*)([,}\]]|$)")


def _fix_bare_keys(s: str) -> str:
    """Convert bare YAML keys to quoted JSON keys."""
    return _BARE_KEY.sub(lambda m: f'"{m.group(1)}":', s)


def _fix_bare_vals(s: str) -> str:
    """Quote bare-word string values (skip null, true, false)."""
    null_true_false = {"null", "true", "false"}

    def _repl(m: re.Match) -> str:
        val = m.group(1)
        if val in null_true_false:
            return m.group(0)
        return f': "{val}"{m.group(2)}'

    return _BARE_VAL.sub(_repl, s)


def _parse_flow(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        fixed = _fix_bare_vals(_fix_bare_keys(raw))
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            return raw.strip()


def _parse_frontmatter(text: str) -> dict[str, Any]:
    m = _FM_BLOCK.match(text)
    if not m:
        return {}
    block = m.group(1)
    result: dict[str, Any] = {}
    lines = block.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        sk = _SCALAR.match(line)
        bk = _BLOCK_KEY.match(line)
        if sk:
            raw_val = sk.group(2).strip()
            fm_match = _FLOW_MAP.match(raw_val)
            fs_match = _FLOW_SEQ.match(raw_val)
            if fm_match or fs_match:
                result[sk.group(1)] = _parse_flow(raw_val)
            else:
                result[sk.group(1)] = raw_val
            i += 1
        elif bk:
            key = bk.group(1)
            nested: dict[str, Any] = {}
            i += 1
            while i < len(lines) and lines[i].startswith("  "):
                nl = lines[i].strip()
                nm = _SCALAR.match(nl)
                if nm:
                    raw_v = nm.group(2).strip()
                    fm2 = _FLOW_MAP.match(raw_v)
                    fs2 = _FLOW_SEQ.match(raw_v)
                    if fm2 or fs2:
                        nested[nm.group(1)] = _parse_flow(raw_v)
                    else:
                        nested[nm.group(1)] = raw_v
                i += 1
            result[key] = nested
        else:
            i += 1
    return result


# ── gh probe ─────────────────────────────────────────────────────────────────

def _probe_gh() -> tuple[bool, str | None]:
    """Returns (available, reason_if_not)."""
    probe = subprocess.run(
        ["command", "-v", "gh"],
        capture_output=True, text=True, shell=False,
        executable="/bin/sh",
    )
    # Try shutil.which fallback
    import shutil
    if shutil.which("gh") is None:
        return False, "gh not in PATH"
    auth = subprocess.run(
        ["gh", "auth", "status"],
        capture_output=True, text=True,
    )
    if auth.returncode != 0:
        return False, "gh auth status failed"
    remote = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        capture_output=True, text=True,
    )
    if remote.returncode != 0 or not re.search(r"github\.com[:/]", remote.stdout):
        return False, "remote not github.com"
    return True, None


# ── Kahn's topo sort ──────────────────────────────────────────────────────────

def _kahn_sort(shards: dict[str, dict]) -> list[str]:
    shard_ids = list(shards.keys())
    in_degree: dict[str, int] = {s: 0 for s in shard_ids}
    adj: dict[str, list[str]] = {s: [] for s in shard_ids}

    for sid in shard_ids:
        deps = shards[sid].get("depends_on", [])
        if isinstance(deps, str):
            deps = json.loads(deps) if deps.startswith("[") else []
        for dep in deps:
            if dep in shards:
                adj[dep].append(sid)
                in_degree[sid] += 1

    queue = sorted(s for s, d in in_degree.items() if d == 0)
    order: list[str] = []
    while queue:
        node = queue.pop(0)
        order.append(node)
        for neighbor in sorted(adj.get(node, [])):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
                queue.sort()

    if len(order) != len(shard_ids):
        remaining = set(shard_ids) - set(order)
        print(
            f"pr-publish: cyclic depends_on detected among shards: {remaining}",
            file=sys.stderr,
        )
        sys.exit(2)
    return order


# ── plan builder ──────────────────────────────────────────────────────────────

def _build_shard_plan(
    sid: str,
    shard: dict,
    artifact_id: str,
    base_ref: str,
    base_sha: str,
    gh_available: bool,
    task_summary: str,
) -> dict[str, Any]:
    branch = shard.get("branch", f"pipeline/{artifact_id}/{sid}")
    depends_on = shard.get("depends_on", [])
    if isinstance(depends_on, str):
        depends_on = json.loads(depends_on) if depends_on.startswith("[") else []

    title = f"[{artifact_id}] {task_summary}"

    push_cmd = ["git", "push", "origin", branch]
    recommit_cmd = ["git", "reset", "--soft", base_sha]

    if gh_available:
        pr_create = [
            "gh", "pr", "create",
            "--base", base_ref,
            "--head", branch,
            "--title", title,
        ]
        pr_merge = ["gh", "pr", "merge", "--merge", branch]
    else:
        pr_create = None
        pr_merge = None

    return {
        "shard_id": sid,
        "branch": branch,
        "depends_on": depends_on,
        "commands": {
            "recommit": recommit_cmd,
            "push": push_cmd,
            "pr_create": pr_create,
            "pr_merge": pr_merge,
        },
        "title": title,
        "body_path": None,
    }


# ── apply mode ───────────────────────────────────────────────────────────────

def _apply(
    plan: dict,
    merge_order: list[str],
    shard_plans: dict[str, dict],
) -> int:
    failed: list[str] = []
    counts = {"pushed": 0, "pr_opened": 0, "merged": 0}

    for sid in merge_order:
        sp = shard_plans[sid]
        cmds = sp["commands"]

        for action_name, cmd in [
            ("push", cmds["push"]),
            ("pr_create", cmds.get("pr_create")),
            ("pr_merge", cmds.get("pr_merge")),
        ]:
            if cmd is None:
                continue
            result = subprocess.run(cmd, capture_output=True, text=True)
            line: dict[str, Any] = {
                "shard": sid,
                "action": action_name,
                "exit": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
            print(json.dumps(line))
            if result.returncode != 0:
                failed.append(f"{sid}/{action_name}")
            else:
                if action_name == "push":
                    counts["pushed"] += 1
                elif action_name == "pr_create":
                    counts["pr_opened"] += 1
                elif action_name == "pr_merge":
                    counts["merged"] += 1

    summary = {
        "summary": {
            "total_shards": len(merge_order),
            **counts,
            "failed": failed,
        }
    }
    print(json.dumps(summary))
    return 1 if failed else 0


# ── main ─────────────────────────────────────────────────────────────────────

def _die(msg: str) -> None:
    print(f"pr-publish: {msg}", file=sys.stderr)
    sys.exit(2)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="pr-publish",
        description="Generate per-shard PR publication plan from pipeline.md.",
    )
    parser.add_argument(
        "--pipeline-md",
        required=True,
        metavar="PATH",
        type=Path,
        help="Absolute path to pipeline.md ledger",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Execute git/gh subprocesses; emit JSONL action log",
    )
    parser.add_argument(
        "--artifact-id",
        metavar="ID",
        default=None,
        help="Override artifact-id (else parsed from pipeline.md run_id)",
    )
    parser.add_argument(
        "--task-summary",
        metavar="TEXT",
        default=None,
        help="Override task summary for PR title",
    )
    parser.add_argument(
        "--no-git-probe",
        action="store_true",
        help="Skip git base_sha stability probe (for testing)",
    )
    parser.add_argument(
        "--no-gh-probe",
        action="store_true",
        help="Skip gh availability probe; treat as unavailable (for testing)",
    )
    args = parser.parse_args()

    pipeline_path: Path = args.pipeline_md.expanduser().resolve()
    if not pipeline_path.exists():
        _die(f"pipeline.md not found: {pipeline_path}")

    try:
        text = pipeline_path.read_text(encoding="utf-8")
    except OSError as exc:
        _die(f"cannot read pipeline.md: {exc}")

    fm = _parse_frontmatter(text)
    if not fm:
        _die("pipeline.md has no YAML frontmatter")

    required = {"run_id", "base_ref", "base_sha", "shards"}
    missing = required - fm.keys()
    if missing:
        _die(f"pipeline.md missing required frontmatter keys: {', '.join(sorted(missing))}")

    artifact_id: str = args.artifact_id or fm["run_id"]
    base_ref: str = fm["base_ref"]
    base_sha: str = fm["base_sha"]
    task_summary: str = args.task_summary or fm.get("brief", artifact_id)
    shards_raw = fm.get("shards", {})

    if not isinstance(shards_raw, dict) or len(shards_raw) == 0:
        _die("pipeline.md shards must be a non-empty mapping")

    # Parse each shard's depends_on from inline flow notation
    shards: dict[str, dict] = {}
    for sid, sv in shards_raw.items():
        if isinstance(sv, dict):
            shards[sid] = sv
        else:
            _die(f"shard {sid!r} value is not a mapping")

    # Base SHA stability check
    base_sha_stable = True
    warnings: list[str] = []
    if not args.no_git_probe:
        probe = subprocess.run(
            ["git", "rev-parse", base_ref],
            capture_output=True, text=True,
        )
        if probe.returncode == 0:
            actual = probe.stdout.strip()
            if actual != base_sha:
                base_sha_stable = False
                warnings.append(f"base_sha drift: expected {base_sha}, got {actual}")
        else:
            warnings.append(f"git rev-parse {base_ref} failed: {probe.stderr.strip()}")

    # gh availability probe
    if args.no_gh_probe:
        gh_available = False
        gh_reason: str | None = "gh not in PATH"
    else:
        gh_available, gh_reason = _probe_gh()

    mode = "pr" if gh_available else "branches-only"

    # Kahn sort
    merge_order = _kahn_sort(shards)

    # Build per-shard plans
    shard_plans_list = []
    shard_plans_map: dict[str, dict] = {}
    for sid in merge_order:
        sp = _build_shard_plan(
            sid, shards[sid], artifact_id, base_ref, base_sha,
            gh_available, task_summary,
        )
        shard_plans_list.append(sp)
        shard_plans_map[sid] = sp

    if args.apply:
        return _apply({"mode": mode}, merge_order, shard_plans_map)

    output: dict[str, Any] = {
        "mode": mode,
        "gh_available": gh_available,
        "gh_reason": gh_reason,
        "base_sha": base_sha,
        "base_ref": base_ref,
        "base_sha_stable": base_sha_stable,
        "shards": shard_plans_list,
        "merge_order": merge_order,
        "warnings": warnings,
    }
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
