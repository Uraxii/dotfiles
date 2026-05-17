#!/usr/bin/env python3
"""pipeline-ask — block until human answers a comms question.

Agent-callable CLI. Writes a question artifact to a pipeline run dir, posts
via pipeline_notify.py (which routes through the host router), then blocks
until the answer artifact lands (or hard timeout reached).

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
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Strict artifact-slug format: `<adj>-<mid>-<noun>-<hex6>`.
# Must match `_RUN_ID_RE` in comms/router.py — router rejects button clicks
# carrying any other shape, so the ask side fails fast w/ a clear error.
_RUN_ID_RE = re.compile(r"^[a-z]+(?:-[a-z]+){2}-[a-f0-9]{6}$")

_PIPELINE_DIR = Path(__file__).parent
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

from comms.session import resolve_session_binding  # noqa: E402

POLL_INTERVAL = 1.0
NOTIFY_SCRIPT = _PIPELINE_DIR / "pipeline_notify.py"


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


def html_to_pdf(html_path: Path) -> Path:
    """Render HTML to sibling PDF via `uvx weasyprint`. Returns PDF on success."""
    pdf_path = html_path.with_suffix(".pdf")
    try:
        if (
            pdf_path.is_file()
            and pdf_path.stat().st_mtime >= html_path.stat().st_mtime
        ):
            return pdf_path
    except OSError:
        pass
    try:
        result = subprocess.run(
            ["uvx", "--from", "weasyprint", "weasyprint",
             str(html_path), str(pdf_path)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        sys.stderr.write(f"html->pdf conversion failed ({exc}); uploading raw html\n")
        return html_path
    if result.returncode != 0 or not pdf_path.is_file():
        sys.stderr.write(
            f"weasyprint failed (rc={result.returncode}); uploading raw html\n"
            f"  stderr: {result.stderr.strip()[:200]}\n"
        )
        return html_path
    return pdf_path


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
    attachments: list[Path] | None = None,
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
    ]
    if attachments:
        lines.append("attachments:")
        for ap in attachments:
            lines.append(f"  - {ap}")
    lines.append("---")
    lines.append("")
    for k, label in options:
        lines.append(f"## Option {k}: {label}")
    qfile.write_text("\n".join(lines) + "\n")
    return qfile


def _write_initial_comms_context(
    run_dir: Path,
    project_path: Path,
    run_id: str,
    qid: str,
    header: str,
    prompt: str,
    options: list[tuple[str, str]],
) -> None:
    """Write initial .comms-context.json (no message_ts/channel/thread_ts -- notify fills)."""
    ctx_path = run_dir / ".comms-context.json"
    if ctx_path.is_file():
        # Preserve any notify-owned fields already populated on re-run.
        try:
            existing = json.loads(ctx_path.read_text())
            if existing.get("message_ts"):
                return
        except (OSError, json.JSONDecodeError):
            pass

    phash = hashlib.sha1(str(project_path).encode()).hexdigest()[:8]
    opts_list = [[k, label] for k, label in options]
    payload = {
        "schema_version": 2,
        "project_path": str(project_path),
        "project_path_hash": phash,
        "run_id": run_id,
        "kind": "question",
        "qid": qid,
        "did": None,
        "options": opts_list,
        "header": header,
        "prompt": prompt,
        "channel": None,
        "thread_ts": None,
        "message_ts": None,
        "attachment_permalinks": [],
        "created_at": now_iso(),
    }
    from comms.env import atomic_write_text  # noqa: E402, PLC0415
    atomic_write_text(ctx_path, json.dumps(payload, indent=2), mode=0o600)


def _require_binding_or_degrade(run_dir: Path) -> bool:
    """Return True if active binding exists; else emit warning + return False."""
    binding = resolve_session_binding()
    if binding is not None:
        return True
    msg = (
        "no active Slack session binding; async question cannot be posted.\n"
        "Run 'uv run --script ~/.config/opencode/pipeline/session_bind.py activate' first,\n"
        "or use AskUserQuestion for synchronous fallback.\n"
    )
    sys.stderr.write(msg)
    return False


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


def _invoke_notify(run_dir: Path, run_id: str, qid: str) -> bool:
    """Call pipeline_notify.py --kind question. Returns True on success."""
    if not NOTIFY_SCRIPT.is_file():
        sys.stderr.write(f"notify script missing: {NOTIFY_SCRIPT}\n")
        return False
    result = subprocess.run(
        [
            "uv", "run", "--script", str(NOTIFY_SCRIPT),
            "--kind", "question",
            "--run-dir", str(run_dir),
            "--run", run_id,
            "--qid", qid,
        ],
        check=False,
        timeout=60,
    )
    if result.returncode != 0:
        sys.stderr.write(
            f"notify failed rc={result.returncode}; "
            "falling through to local poll (answer may arrive via router)\n"
        )
        return False
    return True


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
    p.add_argument("--attach", action="append", default=[],
                   help="absolute path to attach to question post (repeatable)")
    args = p.parse_args()

    project_path = Path(args.project).expanduser().resolve()
    if not project_path.is_dir():
        sys.stderr.write(f"project path not a directory: {project_path}\n")
        return 4
    if not _RUN_ID_RE.match(args.run):
        sys.stderr.write(
            f"run id {args.run!r} does not match artifact-slug format "
            "(<adj>-<mid>-<noun>-<hex6>); the router will reject button "
            "clicks carrying this id. Generate one with:\n"
            "  python3 ~/.config/opencode/tools/artifact-slug.py\n"
        )
        return 4
    run_dir = project_path / ".pipeline" / "runs" / args.run
    if not run_dir.is_dir():
        sys.stderr.write(f"run dir missing: {run_dir}\n")
        return 4

    qid = alloc_question_id(run_dir, args.id)
    n = qid.lstrip("q")
    qfile = run_dir / f"question-r{n}.md"
    afile = run_dir / f"answer-r{n}.md"

    # Fast path: answer already exists.
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

    # Validate binding before writing artifacts.
    if not _require_binding_or_degrade(run_dir):
        return 4

    # New question: validate + write artifact.
    if not qfile.exists():
        missing = [name for name, val in (("--header", args.header), ("--prompt", args.prompt))
                   if not val]
        if missing:
            sys.stderr.write(f"required on first call: {', '.join(missing)}\n")
            return 4
        if not (2 <= len(args.opt) <= 4):
            sys.stderr.write(f"--opt count must be 2..4 (got {len(args.opt)})\n")
            return 4
        try:
            options = parse_options(args.opt)
        except ValueError as exc:
            sys.stderr.write(f"{exc}\n")
            return 4
        attachments: list[Path] = []
        for ap in args.attach:
            apath = Path(ap).expanduser().resolve()
            if not apath.is_file():
                sys.stderr.write(f"--attach not a file: {apath}\n")
                return 4
            if apath.suffix.lower() == ".html":
                apath = html_to_pdf(apath)
            attachments.append(apath)
        deadline = datetime.now(timezone.utc) + timedelta(seconds=args.hard_timeout)
        write_question(run_dir, qid, args.header or "", args.prompt or "", options,
                       args.role, deadline, attachments=attachments)

        _write_initial_comms_context(
            run_dir, project_path, args.run, qid,
            args.header or "", args.prompt or "", options,
        )

    # Post via notify subprocess.
    _invoke_notify(run_dir, args.run, qid)

    # Read deadline from artifact.
    qfm = parse_frontmatter(qfile)
    deadline_dt: datetime | None = None
    if qfm.get("timeout_at"):
        try:
            deadline_dt = parse_iso(qfm["timeout_at"])
        except ValueError:
            pass

    # Block on answer file (router writes answer-r<N>.md on button click).
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
