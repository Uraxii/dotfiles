#!/usr/bin/env python3
"""Friction audit — deterministic post-run doctrine checks.

Emits JSON findings to stdout. Non-gating.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def check_brief_format(run_dir: Path) -> dict | None:
    brief = run_dir / "brief.md"
    if not brief.exists():
        return {"check": "agent-brief-format", "citation": "brief.md missing", "severity": "high"}
    text = brief.read_text(encoding="utf-8", errors="replace")
    required = ["# AGENT-BRIEF", "## Request", "## Scope", "## Acceptance criteria"]
    missing = [s for s in required if s not in text]
    if missing:
        return {
            "check": "agent-brief-format",
            "citation": f"brief.md missing sections: {', '.join(missing)}",
            "severity": "med",
        }
    return None


def check_two_axis_review(run_dir: Path) -> dict | None:
    review_files = list(run_dir.glob("verdict-review-r*.md"))
    if not review_files:
        return None  # review didn't run this pipeline
    standards = list(run_dir.glob("verdict-review-standards-r*.md"))
    spec = list(run_dir.glob("verdict-review-spec-r*.md"))
    if not standards or not spec:
        missing = []
        if not standards:
            missing.append("verdict-review-standards-r*.md")
        if not spec:
            missing.append("verdict-review-spec-r*.md")
        return {
            "check": "two-axis-review",
            "citation": f"aggregated verdict-review-r*.md exists but missing per-axis files: {', '.join(missing)}",
            "severity": "high",
        }
    return None


def check_tdd_evidence(run_dir: Path) -> dict | None:
    evidence = list(run_dir.glob("build-evidence-r*-s*.md"))
    if not evidence:
        # No build ran — not a failure
        return None
    rg_pat = re.compile(r"(red-green|TDD:\s*skipped,\s*reason:)", re.IGNORECASE)
    missing = [e.name for e in evidence if not rg_pat.search(e.read_text(encoding="utf-8", errors="replace"))]
    if missing:
        return {
            "check": "tdd-evidence",
            "citation": f"missing red-green sequence OR TDD-skipped note: {', '.join(missing)}",
            "severity": "med",
        }
    return None


def check_adr_assertion(run_dir: Path) -> dict | None:
    design_verdicts = list(run_dir.glob("verdict-design-r*.md"))
    if not design_verdicts:
        return None  # architect didn't run
    latest = max(design_verdicts, key=lambda p: int(re.search(r"-r(\d+)", p.name).group(1)))
    text = latest.read_text(encoding="utf-8", errors="replace")
    if not re.search(r"adr_emitted\s*:", text):
        return {
            "check": "adr-assertion",
            "citation": f"{latest.name} missing adr_emitted: assertion",
            "severity": "high",
        }
    return None


def check_task_id_continuity(run_dir: Path) -> dict | None:
    pipeline_md = run_dir / "pipeline.md"
    if not pipeline_md.exists():
        return {"check": "task-id-continuity", "citation": "pipeline.md missing", "severity": "high"}
    text = pipeline_md.read_text(encoding="utf-8", errors="replace")
    # Persistent roles per orchestrator doctrine
    persistent = ["architect", "build", "skeptic", "reviewer", "security-auditor",
                  "tester", "ui-ux-designer", "content-designer"]
    # Only flag roles that ran (mentioned in Stages section)
    mentioned = [r for r in persistent if re.search(rf"^\s*-\s*{re.escape(r)}\b", text, re.MULTILINE)]
    if not mentioned:
        return None
    # task_id keying tracked as 'task_id:' or 'task_ids:' anywhere in pipeline.md
    if not re.search(r"task_id[s]?\s*:", text):
        return {
            "check": "task-id-continuity",
            "citation": f"pipeline.md has no task_id record; persistent roles ran: {', '.join(mentioned)}",
            "severity": "low",
        }
    return None


def check_phase_field(run_dir: Path) -> dict | None:
    pipeline_md = run_dir / "pipeline.md"
    if not pipeline_md.exists():
        return None
    text = pipeline_md.read_text(encoding="utf-8", errors="replace")
    if not re.search(r"^phase\s*:", text, re.MULTILINE):
        return {
            "check": "phase-field",
            "citation": "pipeline.md missing phase: field (PR-5 deferred check)",
            "severity": "low",
        }
    return None


def check_skill_invocation(run_dir: Path, repo_root: Path) -> dict | None:
    agents_dir = repo_root / ".claude" / "agents"
    skills_dir = repo_root / ".claude" / "skills"
    if not agents_dir.exists() or not skills_dir.exists():
        return None
    declared_skills = {p.name for p in skills_dir.iterdir() if p.is_dir()}
    invoked = set()
    pat = re.compile(r'Skill\(\s*skill:\s*"([^"]+)"')
    for f in agents_dir.glob("*.md"):
        for m in pat.findall(f.read_text(encoding="utf-8", errors="replace")):
            invoked.add(m)
    unreferenced = declared_skills - invoked - {"caveman", "frontend-design"}  # filter known-external
    # Only flag pipeline-native skills
    pipeline_native = {
        "agent-brief-format", "artifact-slug", "decision-elicitation", "handoff-doc",
        "prod-diff-sha", "test-path-resolve", "verdict-parse", "worktree-lifecycle",
        "friction-audit",
    }
    unreferenced &= pipeline_native
    if unreferenced:
        return {
            "check": "skill-invocation",
            "citation": f"declared but never invoked by any agent: {', '.join(sorted(unreferenced))}",
            "severity": "low",
        }
    return None


CHECKS = [
    ("agent-brief-format", check_brief_format),
    ("two-axis-review", check_two_axis_review),
    ("tdd-evidence", check_tdd_evidence),
    ("adr-assertion", check_adr_assertion),
    ("task-id-continuity", check_task_id_continuity),
    ("phase-field", check_phase_field),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--repo-root", type=Path, default=None,
                        help="Repo root for skill-invocation check. Inferred if omitted.")
    args = parser.parse_args()

    run_dir: Path = args.run_dir.expanduser().resolve()
    if not run_dir.is_dir():
        print(json.dumps({"error": f"run-dir not a directory: {run_dir}"}), file=sys.stderr)
        return 2

    # Infer repo root: walk up from run_dir until .claude/ found
    repo_root = args.repo_root
    if repo_root is None:
        cur = run_dir
        for _ in range(10):
            if (cur / ".claude").is_dir():
                repo_root = cur
                break
            if cur.parent == cur:
                break
            cur = cur.parent

    passed: list[str] = []
    failed: list[dict] = []

    for check_id, fn in CHECKS:
        finding = fn(run_dir)
        if finding is None:
            passed.append(check_id)
        else:
            failed.append(finding)

    # repo-scoped check
    if repo_root is not None:
        finding = check_skill_invocation(run_dir, repo_root)
        if finding is None:
            passed.append("skill-invocation")
        else:
            failed.append(finding)

    print(json.dumps({"passed": passed, "failed": failed}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
