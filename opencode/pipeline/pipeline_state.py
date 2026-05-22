#!/usr/bin/env python3
"""pipeline_state — pipeline.md ledger CLI.

Reads / writes the YAML frontmatter of pipeline.md in a pipeline run dir.
Atomic writes via tmp + rename. flock during read-modify-write.

Usage:
    pipeline_state.py read  --run <id> --project <path>
    pipeline_state.py get   --run <id> --project <path> --key <dot.path>
    pipeline_state.py set   --run <id> --project <path> --key <dot.path> --value <v>
    pipeline_state.py stage --run <id> --project <path> --name <role> --status <status> \\
                            [--revision rN]

Stdlib-only; PyYAML used when available, with a minimal stdlib fallback.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

_PIPELINE_DIR = Path(__file__).parent
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

from comms.env import atomic_write_text  # noqa: E402

log = logging.getLogger("pipeline_state")

# ---------------------------------------------------------------------------
# YAML shim — PyYAML if present, minimal stdlib fallback otherwise
# ---------------------------------------------------------------------------

try:
    import yaml as _yaml

    def _yaml_safe_load(text: str) -> Any:
        return _yaml.safe_load(text)

    def _yaml_dump(data: Any) -> str:
        return _yaml.dump(data, default_flow_style=False, allow_unicode=True)

except ImportError:
    def _yaml_safe_load(text: str) -> Any:  # type: ignore[misc]
        """Minimal YAML scalar / mapping parser (no sequences, no anchors).

        Stack entries are (key_indent, dict). Pop until the top's key_indent is
        strictly less than the current line's indent — that top is our parent.
        """
        result: dict[str, Any] = {}
        # Each stack entry: (key_indent_of_this_dict, dict).
        # Root dict was "introduced" at indent=-1 so all real lines parent to it.
        stack: list[tuple[int, dict[str, Any]]] = [(-1, result)]
        for raw in text.splitlines():
            if not raw.strip() or raw.strip().startswith("#"):
                continue
            stripped = raw.lstrip(" ")
            indent = len(raw) - len(stripped)
            if ":" not in stripped:
                continue
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()
            # Pop stack entries whose indent >= current indent: they are siblings
            # or ancestors at the same/higher level, not parents.
            while len(stack) > 1 and stack[-1][0] >= indent:
                stack.pop()
            parent = stack[-1][1]
            if val == "" or val == "{}":
                child: dict[str, Any] = {}
                parent[key] = child
                # Push with THIS key's indent; children will be at > indent.
                stack.append((indent, child))
            elif val.lower() in ("null", "~"):
                parent[key] = None
            elif val.lower() == "true":
                parent[key] = True
            elif val.lower() == "false":
                parent[key] = False
            else:
                try:
                    parent[key] = int(val)
                except ValueError:
                    try:
                        parent[key] = float(val)
                    except ValueError:
                        # Strip surrounding quotes.
                        if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                            val = val[1:-1]
                        parent[key] = val
        return result

    def _yaml_dump(data: Any, indent: int = 0) -> str:  # type: ignore[misc]
        """Minimal dict→YAML serialiser with arbitrary nesting depth."""
        lines: list[str] = []
        prefix = "  " * indent
        for k, v in data.items():
            if isinstance(v, dict):
                lines.append(f"{prefix}{k}:")
                lines.append(_yaml_dump(v, indent + 1).rstrip("\n"))
            else:
                lines.append(f"{prefix}{k}: {_scalar(v)}")
        return "\n".join(lines) + "\n"

    def _scalar(v: Any) -> str:
        if v is None:
            return "null"
        if isinstance(v, bool):
            return "true" if v else "false"
        return str(v)


# ---------------------------------------------------------------------------
# Frontmatter parse / serialise
# ---------------------------------------------------------------------------

FRONTMATTER_SEP = "---\n"


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split pipeline.md into (frontmatter_dict, body_text).

    Returns ({}, original_text) when no frontmatter found.
    """
    if not text.startswith(FRONTMATTER_SEP):
        return {}, text
    end = text.find("\n---\n", len(FRONTMATTER_SEP))
    if end < 0:
        return {}, text
    fm_raw = text[len(FRONTMATTER_SEP): end]
    body = text[end + len("\n---\n"):]
    try:
        fm = _yaml_safe_load(fm_raw) or {}
    except Exception as exc:
        log.warning("frontmatter parse error: %s", exc)
        fm = {}
    return fm, body


def merge_frontmatter(fm: dict[str, Any], body: str) -> str:
    """Reassemble pipeline.md from frontmatter dict + body."""
    return FRONTMATTER_SEP + _yaml_dump(fm) + FRONTMATTER_SEP + body


# ---------------------------------------------------------------------------
# Dot-path resolver
# ---------------------------------------------------------------------------


def dot_get(data: dict[str, Any], key: str) -> Any:
    """Resolve a dot-path key into nested dicts. Raises KeyError on miss."""
    parts = key.split(".")
    cur: Any = data
    for part in parts:
        if not isinstance(cur, dict):
            raise KeyError(f"path '{key}': '{part}' is not a mapping")
        if part not in cur:
            raise KeyError(f"path '{key}': key '{part}' not found")
        cur = cur[part]
    return cur


def dot_set(data: dict[str, Any], key: str, value: Any) -> None:
    """Set a dot-path key in nested dicts; creates intermediate dicts."""
    parts = key.split(".")
    cur: Any = data
    for part in parts[:-1]:
        if part not in cur or not isinstance(cur[part], dict):
            cur[part] = {}
        cur = cur[part]
    cur[parts[-1]] = value


def _coerce_value(raw: str) -> Any:
    """Coerce CLI string to Python value."""
    low = raw.lower()
    if low in ("null", "~", "none"):
        return None
    if low == "true":
        return True
    if low == "false":
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


# ---------------------------------------------------------------------------
# File I/O helpers
# ---------------------------------------------------------------------------


def _run_dir(project: Path, run_id: str) -> Path:
    return project / ".pipeline" / "runs" / run_id


def _pipeline_md(run_dir: Path) -> Path:
    return run_dir / "pipeline.md"


def _atomic_write(path: Path, content: str) -> None:
    """Write atomically with fsync: tmp + os.rename (same dir for same-fs guarantee)."""
    atomic_write_text(path, content, mode=0o644)


def _read_with_lock(path: Path) -> tuple[str, int]:
    """Return (text, fd) with LOCK_SH held.  Caller must close fd."""
    fd = os.open(str(path), os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_SH)
    except OSError as exc:
        os.close(fd)
        raise OSError(f"could not lock {path}: {exc}") from exc
    with os.fdopen(os.dup(fd), "r", encoding="utf-8") as fh:
        text = fh.read()
    return text, fd


def _lock_path(path: Path) -> Path:
    """Return stable sidecar lock path for *path*."""
    return path.parent / (path.name + ".lock")


def _write_with_lock(path: Path, content: str) -> None:
    """Write content atomically under LOCK_EX on a stable sidecar lock file.

    Locks <path>.lock rather than <path> itself so the rename in _atomic_write
    does not invalidate the locked inode (classic flock-replace race avoidance).
    """
    lock_p = _lock_path(path)
    # Create lock file if absent (mode 600; idempotent).
    if not lock_p.exists():
        try:
            fd_c = os.open(str(lock_p), os.O_CREAT | os.O_WRONLY, 0o600)
            os.close(fd_c)
        except OSError:
            pass
    fd = os.open(str(lock_p), os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        os.close(fd)
        raise BlockingIOError(
            f"pipeline.md is locked by another writer: {path}"
        ) from exc
    try:
        _atomic_write(path, content)
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass
        os.close(fd)


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def cmd_read(args: argparse.Namespace) -> int:
    project = Path(args.project).expanduser().resolve()
    run_dir = _run_dir(project, args.run)
    md_path = _pipeline_md(run_dir)
    if not md_path.is_file():
        sys.stderr.write(f"pipeline.md not found: {md_path}\n")
        return 1
    text, fd = _read_with_lock(md_path)
    os.close(fd)
    fm, body = split_frontmatter(text)
    out = {"frontmatter": fm, "body": body}
    sys.stdout.write(json.dumps(out, indent=2, default=str) + "\n")
    return 0


def cmd_get(args: argparse.Namespace) -> int:
    project = Path(args.project).expanduser().resolve()
    run_dir = _run_dir(project, args.run)
    md_path = _pipeline_md(run_dir)
    if not md_path.is_file():
        sys.stderr.write(f"pipeline.md not found: {md_path}\n")
        return 1
    text, fd = _read_with_lock(md_path)
    os.close(fd)
    fm, _ = split_frontmatter(text)
    try:
        val = dot_get(fm, args.key)
    except KeyError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    sys.stdout.write(json.dumps(val, default=str) + "\n")
    return 0


def cmd_set(args: argparse.Namespace) -> int:
    project = Path(args.project).expanduser().resolve()
    run_dir = _run_dir(project, args.run)
    md_path = _pipeline_md(run_dir)
    if not md_path.is_file():
        sys.stderr.write(f"pipeline.md not found: {md_path}\n")
        return 1
    text, fd = _read_with_lock(md_path)
    os.close(fd)
    fm, body = split_frontmatter(text)
    value = _coerce_value(args.value)
    dot_set(fm, args.key, value)
    new_text = merge_frontmatter(fm, body)
    try:
        _write_with_lock(md_path, new_text)
    except BlockingIOError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    return 0


def cmd_stage(args: argparse.Namespace) -> int:
    project = Path(args.project).expanduser().resolve()
    run_dir = _run_dir(project, args.run)
    md_path = _pipeline_md(run_dir)
    if not md_path.is_file():
        sys.stderr.write(f"pipeline.md not found: {md_path}\n")
        return 1
    text, fd = _read_with_lock(md_path)
    os.close(fd)
    fm, body = split_frontmatter(text)

    stages: dict[str, Any] = fm.get("stages", {})
    if not isinstance(stages, dict):
        stages = {}
    entry: dict[str, Any] = stages.get(args.name, {})
    entry["status"] = args.status
    if args.revision:
        entry["revision"] = args.revision
    stages[args.name] = entry
    fm["stages"] = stages
    new_text = merge_frontmatter(fm, body)
    try:
        _write_with_lock(md_path, new_text)
    except BlockingIOError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    return 0


# ---------------------------------------------------------------------------
# Argparse
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pipeline_state.py",
        description="Read / write pipeline.md frontmatter ledger.",
    )
    parser.add_argument("--log-level", default="WARNING")
    sub = parser.add_subparsers(dest="command", required=True)

    def _common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--run", required=True, help="Run artifact-id (run dir basename)")
        p.add_argument(
            "--project",
            default=str(Path.cwd()),
            help="Project root containing .pipeline/ (default: cwd)",
        )

    r = sub.add_parser("read", help="Print parsed YAML frontmatter + body as JSON")
    _common(r)

    g = sub.add_parser("get", help="Get a dot-path value from frontmatter as JSON")
    _common(g)
    g.add_argument("--key", required=True, help="Dot-path key (e.g. slack.thread_ts)")

    s = sub.add_parser("set", help="Set a dot-path value in frontmatter")
    _common(s)
    s.add_argument("--key", required=True, help="Dot-path key")
    s.add_argument("--value", required=True, help="Value (coerced: null/true/false/int/float/str)")

    st = sub.add_parser("stage", help="Update a stage entry in frontmatter")
    _common(st)
    st.add_argument("--name", required=True, help="Stage/role name")
    st.add_argument("--status", required=True, help="Stage status string")
    st.add_argument("--revision", default=None, help="Revision label (e.g. r1)")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    dispatch = {
        "read": cmd_read,
        "get": cmd_get,
        "set": cmd_set,
        "stage": cmd_stage,
    }
    fn = dispatch.get(args.command)
    if fn is None:
        parser.print_help(sys.stderr)
        sys.exit(1)
    sys.exit(fn(args))


if __name__ == "__main__":
    main()
