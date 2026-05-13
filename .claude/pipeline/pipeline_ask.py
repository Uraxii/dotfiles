#!/usr/bin/env python3
"""pipeline-ask — block until human answers a Slack question.

Agent-callable CLI. Writes a question artifact to a pipeline run dir, ensures
the Slack listener daemon is alive for that run, then blocks until the answer
artifact lands (or hard timeout reached).

Idempotent: re-invoking with the same --id and --run reuses the existing
question artifact. Caller can pass `timeout=<ms>` to the Bash tool; if the
harness SIGKILLs this process, the question persists and the next invocation
simply resumes blocking.

Exit codes:
  0  answered          stdout = chosen key (e.g. "A")
  3  hard timeout      stdout = "TIMEOUT q<N>"; writes answer-r<N>.md verdict=timeout
  4  error             stderr message; no stdout

Stdlib-only. No third-party deps.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

POLL_INTERVAL = 1.0
LISTENER_SCRIPT = Path.home() / ".claude/pipeline/slack_listener.py"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def parse_frontmatter(path: Path) -> dict[str, str]:
    fm: dict[str, str] = {}
    try:
        text = path.read_text()
    except OSError:
        return fm
    if not text.startswith("---\n"):
        return fm
    end = text.find("\n---\n", 4)
    if end < 0:
        return fm
    for line in text[4:end].splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm


def ensure_listener(project_path: Path, run_id: str, run_dir: Path) -> None:
    """Spawn listener daemon if not already alive for this run."""
    pid_file = run_dir / "slack-listener.pid"
    if pid_file.is_file():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)
            return
        except (ValueError, ProcessLookupError, PermissionError, OSError):
            pass
    if not LISTENER_SCRIPT.is_file():
        sys.stderr.write(f"listener missing: {LISTENER_SCRIPT}\n")
        return
    log_path = run_dir / "slack-listener.log"
    try:
        log_fh = open(log_path, "a")
        subprocess.Popen(
            ["uv", "run", "--script", str(LISTENER_SCRIPT),
             str(project_path), run_id],
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            close_fds=True,
        )
    except OSError as e:
        sys.stderr.write(f"listener spawn failed: {e}\n")


def alloc_question_id(run_dir: Path, requested: str | None) -> str:
    if requested:
        return requested if requested.startswith("q") else f"q{requested}"
    n = 1
    while (run_dir / f"question-r{n}.md").exists():
        n += 1
    return f"q{n}"


def write_question(
    run_dir: Path,
    qid: str,
    header: str,
    prompt: str,
    options: list[tuple[str, str]],
    role: str,
    timeout_at: datetime,
) -> Path:
    n = qid.lstrip("q")
    qfile = run_dir / f"question-r{n}.md"
    if qfile.exists():
        return qfile
    lines = [
        "---",
        f"question_id: {qid}",
        f"header: {header}",
        f"prompt: {prompt}",
        f"requesting_role: {role}",
        "delivery_mode: async",
        f"opened_at: {now_iso()}",
        f"timeout_at: {timeout_at.isoformat()}",
        "---",
        "",
    ]
    for k, label in options:
        lines.append(f"## Option {k}: {label}")
    qfile.write_text("\n".join(lines) + "\n")
    return qfile


def write_timeout_answer(run_dir: Path, qid: str, qfm: dict[str, str]) -> None:
    n = qid.lstrip("q")
    afile = run_dir / f"answer-r{n}.md"
    if afile.exists():
        return
    body = (
        "---\n"
        f"question_id: {qid}\n"
        "verdict: timeout\n"
        "chosen_key: null\n"
        "chosen_label: null\n"
        "delivery_mode: async\n"
        f"opened_at: {qfm.get('opened_at', 'null')}\n"
        f"answered_at: {now_iso()}\n"
        "answered_by_slack_user: null\n"
        f"requesting_role: {qfm.get('requesting_role', 'unknown')}\n"
        "---\n\n## Notes\n(hard timeout reached)\n"
    )
    afile.write_text(body)


def parse_options(opt_args: list[str]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for o in opt_args:
        if ":" not in o:
            raise ValueError(f"bad --opt format: {o!r} (expected KEY:LABEL)")
        k, _, label = o.partition(":")
        k = k.strip()
        label = label.strip()
        if not k or not label:
            raise ValueError(f"bad --opt format: {o!r} (empty key or label)")
        out.append((k, label))
    return out


def main() -> int:
    p = argparse.ArgumentParser(
        prog="pipeline-ask",
        description="Ask human a question via Slack; block until answered.",
    )
    p.add_argument("--run", required=True, help="run id (artifact-slug); run dir basename")
    p.add_argument("--project", default=str(Path.cwd()),
                   help="project root containing .pipeline/ (default: cwd)")
    p.add_argument("--id", help="question id (q1, q2, ...); auto-allocated if absent")
    p.add_argument("--header", help="short label (<=12 chars); required on first call")
    p.add_argument("--prompt", help="full question text; required on first call")
    p.add_argument("--opt", action="append", default=[],
                   help="KEY:LABEL; repeat 2-4x; required on first call")
    p.add_argument("--role", default="unknown", help="requesting role name")
    p.add_argument("--hard-timeout", type=int, default=86400,
                   help="seconds until verdict=timeout (default 86400 = 24h)")
    args = p.parse_args()

    project_path = Path(args.project).expanduser().resolve()
    if not project_path.is_dir():
        sys.stderr.write(f"project path not a directory: {project_path}\n")
        return 4
    run_dir = project_path / ".pipeline" / "runs" / args.run
    if not run_dir.is_dir():
        sys.stderr.write(f"run dir missing: {run_dir}\n")
        return 4

    qid = alloc_question_id(run_dir, args.id)
    n = qid.lstrip("q")
    qfile = run_dir / f"question-r{n}.md"
    afile = run_dir / f"answer-r{n}.md"

    # Fast path: answer already exists (e.g. re-invoke after listener crash recovery).
    if afile.exists():
        fm = parse_frontmatter(afile)
        key = fm.get("chosen_key", "")
        verdict = fm.get("verdict", "")
        if verdict == "timeout":
            sys.stdout.write(f"TIMEOUT {qid}\n")
            return 3
        if key and key.lower() != "null":
            sys.stdout.write(f"{key}\n")
            return 0
        sys.stderr.write(f"answer file present but malformed: {afile}\n")
        return 4

    # New question: validate + write artifact.
    if not qfile.exists():
        missing = [n for n, v in (("--header", args.header), ("--prompt", args.prompt))
                   if not v]
        if missing:
            sys.stderr.write(f"required on first call: {', '.join(missing)}\n")
            return 4
        if not (2 <= len(args.opt) <= 4):
            sys.stderr.write(f"--opt count must be 2..4 (got {len(args.opt)})\n")
            return 4
        try:
            options = parse_options(args.opt)
        except ValueError as e:
            sys.stderr.write(f"{e}\n")
            return 4
        deadline = datetime.now(timezone.utc) + timedelta(seconds=args.hard_timeout)
        write_question(run_dir, qid, args.header, args.prompt, options,
                       args.role, deadline)

    # Ensure listener alive (idempotent).
    ensure_listener(project_path, args.run, run_dir)

    # Read deadline from artifact (re-invoke case may differ from arg).
    qfm = parse_frontmatter(qfile)
    deadline_dt: datetime | None = None
    if qfm.get("timeout_at"):
        try:
            deadline_dt = parse_iso(qfm["timeout_at"])
        except ValueError:
            pass

    # Block until answer or hard-timeout.
    while True:
        if afile.exists():
            fm = parse_frontmatter(afile)
            key = fm.get("chosen_key", "")
            if fm.get("verdict") == "timeout":
                sys.stdout.write(f"TIMEOUT {qid}\n")
                return 3
            if key and key.lower() != "null":
                sys.stdout.write(f"{key}\n")
                return 0
            sys.stderr.write(f"answer file malformed: {afile}\n")
            return 4
        if deadline_dt and datetime.now(timezone.utc) >= deadline_dt:
            write_timeout_answer(run_dir, qid, qfm)
            sys.stdout.write(f"TIMEOUT {qid}\n")
            return 3
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    sys.exit(main())
