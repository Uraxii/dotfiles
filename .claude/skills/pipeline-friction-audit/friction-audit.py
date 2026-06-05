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


def check_ledger_ref(run_dir: Path) -> dict | None:
    pipeline_md = run_dir / "pipeline.md"
    if not pipeline_md.exists():
        return {"check": "ledger-ref", "citation": "pipeline.md missing", "severity": "high"}
    text = pipeline_md.read_text(encoding="utf-8", errors="replace")
    if not re.search(r"^ledger_id\s*:", text, re.MULTILINE) and "ledger_query:" not in text:
        return {
            "check": "ledger-ref",
            "citation": "pipeline.md manifest missing ledger_id or artifacts.ledger_query pointer",
            "severity": "med",
        }
    return None


def check_context_digest(run_dir: Path) -> dict | None:
    digest = run_dir / "context-digest.md"
    if not digest.exists():
        return {
            "check": "context-digest",
            "citation": "context-digest.md missing",
            "severity": "med",
        }
    return None


def check_preflight(run_dir: Path) -> dict | None:
    """Check verdict files cite preflight + pre-emit critique sections per agent-preflight doctrine."""
    verdicts = list(run_dir.glob("verdict-*.md"))
    if not verdicts:
        return None
    missing_critique = []
    for v in verdicts:
        text = v.read_text(encoding="utf-8", errors="replace")
        if not re.search(r"##\s*Pre-emit critique", text, re.IGNORECASE):
            missing_critique.append(v.name)
    if missing_critique:
        return {
            "check": "preflight-critique",
            "citation": f"verdicts missing ## Pre-emit critique section: {', '.join(missing_critique)}",
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
    unreferenced = declared_skills - invoked - {
        "caveman",
        "pipeline-agent-preflight",  # doctrine loaded by role text, not Skill tool
        "pipeline-prod-diff-sha",    # script utility used by pin-validation tooling
    }
    # Only flag pipeline-native skills
    pipeline_native = {
        "pipeline-agent-brief-format", "pipeline-artifact-slug",
        "pipeline-decision-elicitation", "context-rotation-summary",
        "pipeline-prod-diff-sha", "pipeline-test-path-resolve",
        "pipeline-verdict-parse", "pipeline-worktree-lifecycle",
        "pipeline-friction-audit", "pipeline-revision-route",
        "pipeline-dep-graph-compose", "pipeline-agent-preflight",
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
    ("ledger-ref", check_ledger_ref),
    ("context-digest", check_context_digest),
    ("preflight-critique", check_preflight),
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
