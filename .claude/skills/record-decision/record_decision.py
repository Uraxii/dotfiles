#!/usr/bin/env python3
"""Record and audit architectural decisions as dated vault notes.

Each decision is one markdown file under vault/20 Permanent/decisions/,
grouped by a stable `topic` key. Recording a new decision for a topic
that already has an `active` note flips that prior note to `superseded`
and points the new note's `supersedes` field at it, so the audit chain
is the file history plus frontmatter, never a separate database.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


def git_root() -> Path:
    """Repo root via `git rev-parse --show-toplevel`; cwd if not a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path.cwd()


def resolve_decisions_dir(cli_value: str | None) -> Path:
    """--decisions-dir > KB_DECISIONS_DIR env > <gitroot>/vault/20 Permanent/decisions."""
    if cli_value:
        return Path(cli_value)
    env = os.environ.get("KB_DECISIONS_DIR")
    if env:
        return Path(env)
    return git_root() / "vault" / "20 Permanent" / "decisions"


# Placeholder; main() resolves the real value from CLI/env before any
# function below reads it. Lets other scripts import parse_frontmatter
# from this module without triggering a git subprocess call.
DECISIONS_DIR = Path()


@dataclass
class Decision:
    """One decision note: its frontmatter plus body text."""

    path: Path
    title: str
    topic: str
    decision_date: str
    status: str
    supersedes: str
    tags: list[str]
    body: str


def slugify(text: str) -> str:
    """Lowercase, hyphenate for a filesystem-safe filename component."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "untitled"


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Split '---\\nkey: val\\n---\\nbody' into (fields, body).

    # ponytail: hand-rolled scalar-only YAML (no pyyaml). Tags are the one
    # list field and get bracket-parsed inline; anything fancier belongs
    # to a real YAML lib, which this project intentionally avoids.
    """
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    raw_fields, body = match.groups()
    fields: dict[str, str] = {}
    for line in raw_fields.splitlines():
        if not line.strip() or ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields, body.strip()


def parse_tags(raw: str) -> list[str]:
    """Parse a bracketed inline tag list: '[a, b, c]' -> ['a', 'b', 'c']."""
    stripped = raw.strip().strip("[]")
    if not stripped:
        return []
    return [tag.strip() for tag in stripped.split(",") if tag.strip()]


def load_decision(path: Path) -> Decision:
    """Read one decision note off disk into a Decision record."""
    fields, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    return Decision(
        path=path,
        title=fields.get("title", path.stem),
        topic=fields.get("topic", ""),
        decision_date=fields.get("date", ""),
        status=fields.get("status", "active"),
        supersedes=fields.get("supersedes", ""),
        tags=parse_tags(fields.get("tags", "[]")),
        body=body,
    )


def render_decision(decision: Decision) -> str:
    """Serialize a Decision back to frontmatter + body markdown."""
    tags = ", ".join(decision.tags)
    return (
        "---\n"
        f"title: {decision.title}\n"
        f"topic: {decision.topic}\n"
        f"date: {decision.decision_date}\n"
        f"status: {decision.status}\n"
        f"supersedes: {decision.supersedes}\n"
        f"tags: [{tags}]\n"
        "---\n\n"
        f"{decision.body}\n"
    )


def find_notes_for_topic(topic: str) -> list[Decision]:
    """Load every decision note recorded under a topic, any status."""
    if not DECISIONS_DIR.exists():
        return []
    notes = [load_decision(p) for p in DECISIONS_DIR.glob("*.md")]
    return [note for note in notes if note.topic == topic]


def find_active_note(topic: str) -> Decision | None:
    """Return the current active note for a topic, if one exists."""
    for note in find_notes_for_topic(topic):
        if note.status == "active":
            return note
    return None


def resolve_supersedes_path(supersedes_arg: str | None, topic: str) -> Path | None:
    """Pick the note being superseded: explicit --supersedes wins,
    otherwise the topic's current active note (if any).
    """
    if supersedes_arg:
        return Path(supersedes_arg)
    active = find_active_note(topic)
    return active.path if active else None


def build_note_path(topic_slug: str, today: str) -> Path:
    """Pick the destination filename, suffixing on a same-day collision.

    # ponytail: same topic + same day is rare (manual command, one call
    # per decision moment); suffix -2, -3... rather than building a
    # timestamp-in-filename scheme nobody asked for.
    """
    base = DECISIONS_DIR / f"{topic_slug}__{today}.md"
    if not base.exists():
        return base
    n = 2
    while (candidate := DECISIONS_DIR / f"{topic_slug}__{today}-{n}.md").exists():
        n += 1
    return candidate


def record(args: argparse.Namespace) -> None:
    """Write a new active decision note, superseding the prior one."""
    DECISIONS_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    note_path = build_note_path(slugify(args.topic), today)

    supersedes_path = resolve_supersedes_path(args.supersedes, args.topic)
    if supersedes_path is not None:
        prior = load_decision(supersedes_path)
        prior.status = "superseded"
        prior.path.write_text(render_decision(prior), encoding="utf-8")

    body_parts = [args.text.strip()]
    if args.rationale:
        body_parts.append(f"## Rationale\n\n{args.rationale.strip()}")
    if args.refs:
        body_parts.append(f"## Refs\n\n{args.refs.strip()}")

    new_note = Decision(
        path=note_path,
        title=args.title,
        topic=args.topic,
        decision_date=today,
        status="active",
        supersedes=str(supersedes_path) if supersedes_path else "",
        tags=[t.strip() for t in (args.tags or "").split(",") if t.strip()],
        body="\n\n".join(body_parts),
    )
    note_path.write_text(render_decision(new_note), encoding="utf-8")
    print(json.dumps({"path": str(note_path), "supersedes": new_note.supersedes}))


def audit(topic: str, human: bool) -> None:
    """Print the full supersession chain for a topic, oldest first."""
    notes = sorted(find_notes_for_topic(topic), key=lambda n: n.decision_date)
    if human:
        for note in notes:
            print(f"{note.decision_date}  {note.status:12} {note.title}"
                  f"  (supersedes: {note.supersedes or '-'})")
        return
    chain = [
        {
            "date": note.decision_date,
            "status": note.status,
            "title": note.title,
            "path": str(note.path),
            "supersedes": note.supersedes,
        }
        for note in notes
    ]
    print(json.dumps(chain, indent=2))


def build_parser() -> argparse.ArgumentParser:
    """Construct the record/audit CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--decisions-dir",
        default=None,
        help="override the decisions notes dir (else KB_DECISIONS_DIR env, "
        "else <gitroot>/vault/20 Permanent/decisions)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    record_cmd = sub.add_parser("record", help="record a new decision")
    record_cmd.add_argument("--topic", required=True)
    record_cmd.add_argument("--title", required=True)
    record_cmd.add_argument("--text", required=True)
    record_cmd.add_argument("--rationale", default="")
    record_cmd.add_argument("--refs", default="")
    record_cmd.add_argument("--tags", default="")
    record_cmd.add_argument("--supersedes", default=None)

    audit_cmd = sub.add_parser("audit", help="show a topic's decision chain")
    audit_cmd.add_argument("topic")
    audit_cmd.add_argument("--human", action="store_true")

    return parser


def main(argv: list[str]) -> int:
    """CLI entry point: dispatch to record or audit."""
    args = build_parser().parse_args(argv)
    global DECISIONS_DIR
    DECISIONS_DIR = resolve_decisions_dir(args.decisions_dir)
    if args.command == "record":
        record(args)
    elif args.command == "audit":
        audit(args.topic, args.human)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
