#!/usr/bin/env python3
"""Pipeline shard worktree primitives: create, probe, cleanup, scope-check.

Usage:
  python3 worktree-lifecycle.py --op create --run-id <id> --shard-id <s1> \
    --base-sha <sha> --repo-root <path>
  python3 worktree-lifecycle.py --op probe --worktree-path <path>
  python3 worktree-lifecycle.py --op cleanup --worktree-path <path>
  python3 worktree-lifecycle.py --op scope-check --base-sha <sha> \
    --head <ref> --scope-globs <glob1> [<glob2>...]
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path

__all__ = ["main"]


def op_create(args: argparse.Namespace) -> int:
    if not all([args.run_id, args.shard_id, args.base_sha, args.repo_root]):
        print("ERROR: create requires --run-id --shard-id --base-sha --repo-root",
              file=sys.stderr)
        return 1
    repo_root = Path(args.repo_root)
    wt_path = repo_root / ".pipeline" / "runs" / args.run_id / "worktrees" / args.shard_id
    branch = f"pipeline/{args.run_id}/{args.shard_id}"
    result = subprocess.run(
        ["git", "worktree", "add", str(wt_path), "-b", branch, args.base_sha],
        capture_output=True, text=True, cwd=str(repo_root)
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
        capture_output=True, text=True
    )
    registered = str(p) in result.stdout
    if p.exists() and not registered:
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
        capture_output=True, text=True
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
    globs = args.scope_globs or ["."]
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{args.base_sha}...{args.head}"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"ERROR: {result.stderr.strip()}", file=sys.stderr)
        return 1
    changed = [f.strip() for f in result.stdout.splitlines() if f.strip()]
    # For each changed file, check if it matches at least one scope glob
    leaks = []
    for f in changed:
        in_scope = any(fnmatch.fnmatch(f, g) or f.startswith(g.rstrip("*"))
                       for g in globs)
        if not in_scope and "." not in globs:
            leaks.append(f)
    if leaks:
        print(json.dumps({"status": "LEAK", "files": leaks}))
    else:
        print(json.dumps({"status": "OK", "files": changed}))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Pipeline worktree lifecycle ops.")
    parser.add_argument("--op", required=True,
                        choices=["create", "probe", "cleanup", "scope-check"])
    parser.add_argument("--run-id")
    parser.add_argument("--shard-id")
    parser.add_argument("--base-sha")
    parser.add_argument("--repo-root")
    parser.add_argument("--worktree-path")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--scope-globs", nargs="*")
    args = parser.parse_args()

    ops = {
        "create": op_create,
        "probe": op_probe,
        "cleanup": op_cleanup,
        "scope-check": op_scope_check,
    }
    return ops[args.op](args)


if __name__ == "__main__":
    raise SystemExit(main())
