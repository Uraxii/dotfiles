"""pipeline-core tool handlers.

Each handler signature: `(args: dict, **kwargs) -> str` (JSON string).
Errors return `json.dumps({"error": "<msg>"})` — NEVER raise.

Many handlers are intentionally thin first-pass implementations. They wire up
the contract enumerated in schemas.py and the port plan. Tighten internals as
the build phase exercises them.

Stdlib only (except PyYAML — Hermes ships it for plugin config parsing).
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import random
import re
import string
import subprocess
from pathlib import Path

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]


# ---- Word lists for artifact_slug -----------------------------------------

_ADJ = [
    "crisp", "daring", "icy", "bold", "calm", "eager", "fancy", "gentle",
    "happy", "jolly", "kind", "lively", "merry", "noble", "proud", "quick",
    "rapid", "silent", "tidy", "vivid", "witty", "young", "zesty", "amber",
]
_MID = [
    "cooking", "swimming", "racing", "dancing", "writing", "thinking",
    "building", "running", "flying", "climbing", "diving", "skating",
]
_NOUN = [
    "plum", "zebra", "puddle", "tiger", "river", "mountain", "forest",
    "ocean", "valley", "garden", "harbor", "meadow", "bridge", "island",
]


def _err(msg: str) -> str:
    return json.dumps({"error": msg})


def _ok(payload: dict) -> str:
    return json.dumps(payload)


# ---- artifact_slug --------------------------------------------------------

def artifact_slug(args: dict, **_: object) -> str:
    seed = (args or {}).get("seed") or "none"
    if seed and seed != "none":
        rng = random.Random(seed)
    else:
        rng = random.Random()
    adj = rng.choice(_ADJ)
    mid = rng.choice(_MID)
    noun = rng.choice(_NOUN)
    hex6 = "".join(rng.choices(string.hexdigits.lower()[:16], k=6))
    return _ok({"slug": f"{adj}-{mid}-{noun}-{hex6}"})


# ---- verdict_parse --------------------------------------------------------

_VERDICT_TYPES = {
    "design", "code", "ops", "security", "test",
    "review-standards", "review-spec", "friction",
}

_VERDICT_FILENAME_RE = re.compile(r"^verdict-([a-z-]+)-r(\d+)\.md$")


def verdict_parse(args: dict, **_: object) -> str:
    args = args or {}
    run_dir = args.get("run_dir")
    vtype = args.get("type")
    if not run_dir or not vtype:
        return _err("run_dir and type required")
    if vtype not in _VERDICT_TYPES:
        return _err(f"unknown verdict type {vtype!r}; allowed: {sorted(_VERDICT_TYPES)}")

    rd = Path(run_dir)
    if not rd.is_dir():
        return _err(f"run_dir not found: {run_dir}")

    candidates: list[tuple[int, Path]] = []
    for child in rd.iterdir():
        m = _VERDICT_FILENAME_RE.match(child.name)
        if not m:
            continue
        if m.group(1) != vtype:
            continue
        candidates.append((int(m.group(2)), child))

    if not candidates:
        return _ok({"found": False, "revision": 0, "path": None, "frontmatter": None})

    candidates.sort(key=lambda t: t[0], reverse=True)
    revision, path = candidates[0]
    fm = _parse_frontmatter(path)
    return _ok({"found": True, "revision": revision, "path": str(path), "frontmatter": fm})


def _parse_frontmatter(path: Path) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    block = text[4:end]
    if yaml is None:
        return None
    try:
        return yaml.safe_load(block) or {}
    except yaml.YAMLError:
        return None


# ---- dep_graph_compose ----------------------------------------------------

# Default static dependency graph (from .claude/agents/orchestrator.md
# "Dependency Graph" section). Override by passing roles_included.
_DEFAULT_DEPS: dict[str, list[str]] = {
    "researcher": [],
    "plan": [],
    "architect": ["plan"],
    "ui-ux-designer": ["plan"],
    "skeptic-design": ["architect"],
    "build": ["skeptic-design"],
    "skeptic-code": ["build"],
    "reviewer-standards": ["build"],
    "reviewer-spec": ["build"],
    "security-auditor": ["build"],
    "tester": ["skeptic-code", "reviewer-standards", "reviewer-spec", "security-auditor"],
    "pr_publish": ["tester"],
    "friction-audit": ["pr_publish"],
}


def dep_graph_compose(args: dict, **_: object) -> str:
    args = args or {}
    payload_raw = args.get("payload_json") or "{}"
    try:
        payload = json.loads(payload_raw)
    except json.JSONDecodeError as e:
        return _err(f"payload_json invalid JSON: {e}")

    roles_included = payload.get("roles_included") or list(_DEFAULT_DEPS.keys())
    decision_points = payload.get("decision_points") or {}

    # Topological sort
    deps = {r: [d for d in _DEFAULT_DEPS.get(r, []) if d in roles_included]
            for r in roles_included}
    ordered: list[str] = []
    remaining = dict(deps)
    warnings: list[str] = []
    while remaining:
        # Find roles w/ no remaining deps.
        ready = [r for r, ds in remaining.items() if not ds]
        if not ready:
            warnings.append(f"cycle or missing dep among: {list(remaining)}")
            ordered.extend(remaining.keys())
            break
        ready.sort()
        for r in ready:
            ordered.append(r)
            del remaining[r]
        for r in remaining:
            remaining[r] = [d for d in remaining[r] if d in remaining]

    # Resolve decision injection points (after which role each fires).
    decision_inject_points: list[dict] = []
    for did, decl in decision_points.items():
        after = decl.get("after")
        if after and after in ordered:
            decision_inject_points.append({"decision_id": did, "after": after})

    K = int(payload.get("K") or 1)
    return _ok({
        "ordered_roles": ordered,
        "decision_inject_points": decision_inject_points,
        "K": K,
        "warnings": warnings,
    })


# ---- revision_route -------------------------------------------------------

# verdict-type -> (revisable role to respawn, loop cap)
_REVISION_MAP: dict[str, tuple[str, int]] = {
    "design": ("architect", 3),
    "code": ("build", 3),
    "ops": ("build", 1),
    "security": ("build", 3),       # post-build path; design path handled separately
    "test": ("tester", 3),
    "review-standards": ("build", 3),
    "review-spec": ("build", 3),
}


def revision_route(args: dict, **_: object) -> str:
    args = args or {}
    verdict_path = args.get("verdict_path")
    if not verdict_path:
        return _err("verdict_path required")
    p = Path(verdict_path)
    if not p.is_file():
        return _err(f"verdict file not found: {verdict_path}")

    m = _VERDICT_FILENAME_RE.match(p.name)
    if not m:
        return _err(f"filename does not match verdict-<type>-r<N>.md: {p.name}")
    vtype, rev_str = m.group(1), m.group(2)
    revision_n = int(rev_str)

    fm = _parse_frontmatter(p) or {}
    verdict = (fm.get("verdict") or "").strip()

    if verdict.lower() == "approved":
        return _ok({
            "action": "approved",
            "target_role": None,
            "revision_n": revision_n,
            "reason": "verdict=Approved",
            "loop_cap_hit": False,
            "verdict_summary": fm,
        })

    target_role, loop_cap = _REVISION_MAP.get(vtype, (None, 3))
    if target_role is None:
        return _ok({
            "action": "halt",
            "target_role": None,
            "revision_n": revision_n,
            "reason": f"unknown verdict type {vtype!r}",
            "loop_cap_hit": False,
            "verdict_summary": fm,
        })

    if revision_n >= loop_cap:
        return _ok({
            "action": "halt",
            "target_role": target_role,
            "revision_n": revision_n,
            "reason": f"loop cap {loop_cap} hit for {vtype}",
            "loop_cap_hit": True,
            "verdict_summary": fm,
        })

    return _ok({
        "action": "revise",
        "target_role": target_role,
        "revision_n": revision_n + 1,
        "reason": f"verdict={verdict or 'Blocked'} ; respawning {target_role} at r{revision_n + 1}",
        "loop_cap_hit": False,
        "verdict_summary": fm,
    })


# ---- worktree_lifecycle ---------------------------------------------------

def _run_git(args: list[str], cwd: str | None = None) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except FileNotFoundError:
        return 127, "", "git not found"


def worktree_lifecycle(args: dict, **_: object) -> str:
    args = args or {}
    op = args.get("op")
    if op == "create":
        worktree_path = args.get("worktree_path")
        branch = args.get("branch")
        base_ref = args.get("base_ref") or "main"
        if not worktree_path or not branch:
            return _err("create requires worktree_path + branch")
        rc, out, err = _run_git([
            "worktree", "add", "-b", branch, worktree_path, base_ref,
        ])
        return _ok({"ok": rc == 0, "rc": rc, "stdout": out, "stderr": err})

    if op == "probe":
        worktree_path = args.get("worktree_path")
        if not worktree_path:
            return _err("probe requires worktree_path")
        rc, out, err = _run_git(["status", "--porcelain"], cwd=worktree_path)
        return _ok({"ok": rc == 0, "dirty": bool(out), "stdout": out, "stderr": err})

    if op == "cleanup":
        worktree_path = args.get("worktree_path")
        if not worktree_path:
            return _err("cleanup requires worktree_path")
        rc, out, err = _run_git(["worktree", "remove", "--force", worktree_path])
        return _ok({"ok": rc == 0, "stdout": out, "stderr": err})

    if op == "scope-check":
        worktree_path = args.get("worktree_path")
        scope = args.get("scope") or []
        base_sha = args.get("base_sha")
        if not worktree_path or not base_sha:
            return _err("scope-check requires worktree_path + base_sha")
        rc, out, err = _run_git([
            "diff", "--name-only", f"{base_sha}...HEAD",
        ], cwd=worktree_path)
        if rc != 0:
            return _ok({"ok": False, "rc": rc, "stderr": err})
        changed = out.splitlines()
        out_of_scope = []
        for f in changed:
            if not any(fnmatch.fnmatch(f, g) for g in scope):
                out_of_scope.append(f)
        return _ok({"ok": not out_of_scope, "changed": changed, "out_of_scope": out_of_scope})

    if op == "drift-intersect":
        base_ref = args.get("base_ref") or "main"
        base_sha = args.get("base_sha")
        scope = args.get("scope") or []
        if not base_sha:
            return _err("drift-intersect requires base_sha")
        rc_new, new_sha, _ = _run_git(["rev-parse", base_ref])
        if rc_new != 0:
            return _err(f"cannot rev-parse {base_ref}")
        if new_sha == base_sha:
            return _ok({"drift": False, "new_sha": new_sha, "intersecting_paths": []})
        rc, out, err = _run_git(["diff", "--name-only", f"{base_sha}..{new_sha}"])
        if rc != 0:
            return _ok({"drift": True, "new_sha": new_sha, "intersecting_paths": [], "warn": err})
        changed = out.splitlines()
        intersecting = [
            f for f in changed
            if any(fnmatch.fnmatch(f, g) for g in scope) or f.startswith(".claude/rules/")
        ]
        return _ok({
            "drift": True,
            "new_sha": new_sha,
            "stored_sha": base_sha,
            "all_changed": changed,
            "intersecting_paths": intersecting,
        })

    return _err(f"unknown op {op!r}; expected one of create/probe/cleanup/scope-check/drift-intersect")


# ---- test_path_resolve ----------------------------------------------------

_DEFAULT_TEST_GLOBS = [
    "tests/**", "test/**", "spec/**",
    "**/*_test.py", "**/test_*.py", "**/*.test.ts", "**/*.test.tsx",
    "**/*.spec.ts", "**/*.spec.tsx",
]


def test_path_resolve(args: dict, **_: object) -> str:
    args = args or {}
    run_dir = args.get("run_dir") or ""
    repo_root = args.get("repo_root") or "."

    globs: list[str] = []
    manifest = Path(run_dir) / "test-paths.txt"
    if manifest.is_file():
        for line in manifest.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                globs.append(line)
    if not globs:
        globs = list(_DEFAULT_TEST_GLOBS)

    matched: list[str] = []
    root = Path(repo_root)
    if root.is_dir():
        for g in globs:
            matched.extend(str(p) for p in root.glob(g))
    return _ok({"globs": globs, "matched": sorted(set(matched))})


# ---- prod_diff_sha --------------------------------------------------------

_DEFAULT_TEST_EXCLUDES = [
    "tests/**", "test/**", "spec/**",
    "**/*_test.*", "**/test_*.*", "**/*.test.*", "**/*.spec.*",
]


def prod_diff_sha(args: dict, **_: object) -> str:
    args = args or {}
    base_sha = args.get("base_sha")
    repo_root = args.get("repo_root") or "."
    exclude_globs = args.get("exclude_globs") or _DEFAULT_TEST_EXCLUDES
    if not base_sha:
        return _err("base_sha required")

    rc, out, err = _run_git(["diff", "--name-only", f"{base_sha}...HEAD"], cwd=repo_root)
    if rc != 0:
        return _err(f"git diff failed: {err}")
    files = [f for f in out.splitlines() if f.strip()]

    prod_files = [f for f in files if not any(fnmatch.fnmatch(f, g) for g in exclude_globs)]
    if not prod_files:
        return _ok({"prod_diff_sha": hashlib.sha1(b"").hexdigest(), "files": []})

    rc, out, err = _run_git(
        ["diff", base_sha, "--", *prod_files], cwd=repo_root,
    )
    if rc != 0:
        return _err(f"git diff content failed: {err}")
    digest = hashlib.sha1(out.encode("utf-8")).hexdigest()
    return _ok({"prod_diff_sha": digest, "files": prod_files})


# ---- friction_audit -------------------------------------------------------

def friction_audit(args: dict, **_: object) -> str:
    """Stub: enumerate run-dir artifacts + write friction-findings-r<N>.md.

    Full doctrine-adherence check tracked under Claude Code
    `pipeline-friction-audit` skill. Port surface here matches the schema;
    populate the real audit logic during build phase.
    """
    args = args or {}
    run_dir = args.get("run_dir")
    if not run_dir:
        return _err("run_dir required")
    rd = Path(run_dir)
    if not rd.is_dir():
        return _err(f"run_dir not found: {run_dir}")

    # Find next revision suffix.
    existing = [int(m.group(1)) for f in rd.iterdir()
                if (m := re.match(r"^friction-findings-r(\d+)\.md$", f.name))]
    rN = (max(existing) + 1) if existing else 1
    out_path = rd / f"friction-findings-r{rN}.md"

    artifacts = sorted(p.name for p in rd.iterdir() if p.is_file())
    body = [
        f"# Friction findings r{rN}",
        "",
        "Non-gating meta audit. Populated by pipeline_friction_audit tool stub.",
        "",
        "## Run artifacts",
        "",
    ] + [f"- {a}" for a in artifacts]
    out_path.write_text("\n".join(body) + "\n", encoding="utf-8")
    return _ok({
        "findings_count": 0,
        "severity_breakdown": {"blocker": 0, "major": 0, "minor": 0},
        "output_path": str(out_path),
    })
