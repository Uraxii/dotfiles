#!/usr/bin/env python3
"""Pipeline shard worktree primitives.

Ops: create, probe, cleanup, scope-check, drift-intersect.
Canonical glob_to_regex implementation (segment-walk, ** position-dependent).
Replaces fnmatch-based scope-check in prior OC reference impl.

Usage:
  python3 worktree-lifecycle.py --op create \
    --run-id <id> --shard-id <s1> --base-sha <sha> --repo-root <path>
  python3 worktree-lifecycle.py --op probe --worktree-path <path>
  python3 worktree-lifecycle.py --op cleanup --worktree-path <path>
  python3 worktree-lifecycle.py --op scope-check \
    --base-sha <sha> --head <ref> --scope-globs <g1> [<g2>...]
  python3 worktree-lifecycle.py --op drift-intersect \
    --changed-paths-file <path> --scope-globs <g1> [<g2>...]

Exit codes:
  0  success
  1  error
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

__all__ = ["main"]

# Paths that always trigger drift-halt regardless of shard scope.
# Note: ~/.pipeline/adr/** uses tilde-prefixed home path; git diff --name-only
# returns repo-relative paths, so this entry is symbolic (doctrine consistency
# only). See ADR-0007 §Consequences-Negative.
HALT_ANYWHERE_PATHS: list[str] = [
    "**/CLAUDE.md",
    ".claude/rules/**",
    ".claude/agents/**",
    ".claude/skills/**",
    "~/.pipeline/adr/**",
    "pipeline.toml",
    ".gitignore",
    ".claude/settings.json",
]

# --------------------------------------------------------------------------
# Canonical glob_to_regex — ported from orchestrator.md Appendix (PR-6)
# Single source of truth; orchestrator Appendix now cross-refs here.
# --------------------------------------------------------------------------

def normalize_scope(scope: list[str]) -> list[str]:
    """Normalize '.' → '**' (K=1 implicit-all sentinel)."""
    return ["**" if g == "." else g for g in scope]


def glob_to_regex(g: str) -> re.Pattern[str]:
    """Segment-walk glob compiler with NUL sentinel.

    * → [^/]*   ? → [^/]
    ** position-dependent:
      leading  **/x  → (?:.*/)?x
      trailing x/**  → x/.+
      middle   a/**/b → a/(?:.*/)?b
      standalone **  → .*
    """
    if g == "**":
        return re.compile(r"\A.*\Z")
    SENTINEL = "\x00DS\x00"
    parts: list[str] = []
    for seg in g.split("/"):
        if seg == "**":
            parts.append(SENTINEL)
        else:
            out: list[str] = []
            j = 0
            while j < len(seg):
                c = seg[j]
                if c == "*":
                    out.append("[^/]*")
                elif c == "?":
                    out.append("[^/]")
                else:
                    out.append(re.escape(c))
                j += 1
            parts.append("".join(out))
    glued = "/".join(parts)
    if glued.startswith(SENTINEL + "/"):
        glued = "(?:.*/)?" + glued[len(SENTINEL) + 1:]
    if glued.endswith("/" + SENTINEL):
        glued = glued[: -(len(SENTINEL) + 1)] + "/.+"
    glued = glued.replace("/" + SENTINEL + "/", "/(?:.*/)?")
    glued = glued.replace(SENTINEL, ".*")
    return re.compile(r"\A" + glued + r"\Z")


def glob_match(path: str, globs: list[str]) -> bool:
    return any(glob_to_regex(g).match(path) is not None for g in globs)


# --------------------------------------------------------------------------
# Op implementations
# --------------------------------------------------------------------------

def op_create(args: argparse.Namespace) -> int:
    if not all([args.run_id, args.shard_id, args.base_sha, args.repo_root]):
        print(
            "ERROR: create requires --run-id --shard-id --base-sha --repo-root",
            file=sys.stderr,
        )
        return 1
    repo_root = Path(args.repo_root)
    wt_path = (
        repo_root / ".pipeline" / "runs" / args.run_id
        / "worktrees" / args.shard_id
    )
    branch = f"pipeline/{args.run_id}/{args.shard_id}"
    result = subprocess.run(
        ["git", "worktree", "add", str(wt_path), "-b", branch, args.base_sha],
        capture_output=True,
        text=True,
        cwd=str(repo_root),
    )
    if result.returncode != 0:
        print(f"ERROR: {result.stderr.strip()}", file=sys.stderr)
        return 1
    print(json.dumps({"worktree_path": str(wt_path), "branch": branch}))
    return 0


def op_probe(args: argparse.Namespace) -> int:
    if not args.worktree_path:
        print("ERROR: probe requires --worktree-path", file=sys.stderr)
        return 1
    p = Path(args.worktree_path)
    if not p.exists():
        print(json.dumps({"status": "missing"}))
        return 0
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        capture_output=True,
        text=True,
    )
    registered = str(p.resolve()) in result.stdout or str(p) in result.stdout
    if not registered:
        print(json.dumps({"status": "STALE", "path": str(p)}))
        return 0
    print(json.dumps({"status": "ok", "path": str(p)}))
    return 0


def op_cleanup(args: argparse.Namespace) -> int:
    if not args.worktree_path:
        print("ERROR: cleanup requires --worktree-path", file=sys.stderr)
        return 1
    result = subprocess.run(
        ["git", "worktree", "remove", "--force", args.worktree_path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"ERROR: {result.stderr.strip()}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "removed", "path": args.worktree_path}))
    return 0


def op_scope_check(args: argparse.Namespace) -> int:
    if not all([args.base_sha, args.head]):
        print("ERROR: scope-check requires --base-sha --head", file=sys.stderr)
        return 1
    raw_globs: list[str] = args.scope_globs or ["."]
    globs = normalize_scope(raw_globs)
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{args.base_sha}...{args.head}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"ERROR: {result.stderr.strip()}", file=sys.stderr)
        return 1
    changed = [f.strip() for f in result.stdout.splitlines() if f.strip()]
    leaks = [f for f in changed if not glob_match(f, globs)]
    if leaks:
        print(json.dumps({"status": "LEAK", "files": changed, "leaks": leaks}))
    else:
        print(json.dumps({"status": "OK", "files": changed, "leaks": []}))
    return 0


def op_drift_intersect(args: argparse.Namespace) -> int:
    if not args.changed_paths_file:
        print(
            "ERROR: drift-intersect requires --changed-paths-file",
            file=sys.stderr,
        )
        return 1
    cpf = Path(args.changed_paths_file)
    if not cpf.exists():
        print(
            f"ERROR: changed-paths-file not found: {cpf}",
            file=sys.stderr,
        )
        return 1
    raw_changed = [
        ln.strip()
        for ln in cpf.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    raw_globs: list[str] = args.scope_globs or []
    scope_globs = normalize_scope(raw_globs)
    scope_hits = [
        f"scope:{p}" for p in raw_changed if glob_match(p, scope_globs)
    ]
    doctrine_hits = [
        f"doctrine:{p}"
        for p in raw_changed
        if glob_match(p, HALT_ANYWHERE_PATHS)
    ]
    result = scope_hits + doctrine_hits
    print(json.dumps({"intersecting_paths": result}))
    return 0


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

_OPS = {
    "create": op_create,
    "probe": op_probe,
    "cleanup": op_cleanup,
    "scope-check": op_scope_check,
    "drift-intersect": op_drift_intersect,
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pipeline worktree lifecycle primitives."
    )
    parser.add_argument(
        "--op",
        required=True,
        choices=list(_OPS),
        help="Operation to perform",
    )
    parser.add_argument("--run-id")
    parser.add_argument("--shard-id")
    parser.add_argument("--base-sha")
    parser.add_argument("--repo-root")
    parser.add_argument("--worktree-path")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--scope-globs", nargs="+")
    parser.add_argument("--changed-paths-file")
    args = parser.parse_args()
    return _OPS[args.op](args)


if __name__ == "__main__":
    raise SystemExit(main())
