#!/usr/bin/env python3
"""kb-serve.py -- containerizable HTTP facade over the personal
knowledgebase vault (see scripts/kb.sh).

A thin facade, not a rewrite: every endpoint delegates to the existing
kb-index.py (FTS5 build/query) and kb-clip.py (deterministic web capture)
scripts, loaded by path since their hyphenated filenames aren't importable
as normal modules. The only genuinely new logic here is deterministic
atomization (kb-atomize.py, sibling script) and the optional, pluggable
LLM enrichment pass.

Endpoints (all JSON):
    GET  /health              -> {status, kb_home, indexed_count}
    POST /put                 -> write a note, atomize, reindex
    POST /clip                -> capture a URL, atomize, reindex
    GET  /query                -> FTS5 search (q, project, type, all)
    POST /enrich               -> fill question/summary via the configured
                                   LLM provider; clean no-op if disabled

CLI (also usable without the HTTP server, same functions):
    kb-serve.py run [--host H] [--port P] [--kb-home DIR]
    kb-serve.py put PROJECT TITLE [--type T] [--source S] [--kb-home DIR]
                    (content read from stdin)
    kb-serve.py clip URL [--project P] [--kb-home DIR]
    kb-serve.py query Q [--project P] [--type T] [--all] [--kb-home DIR]
    kb-serve.py resolve-secret [--kb-home DIR]
                    prints "KB_LLM_API_KEY=<value>" for an EnvironmentFile=
                    to consume; never logs the value.

Enrichment config (env, optionally sourced from the gitignored
<kb_home>/kb.env): KB_ENRICH (0/1, default 0), KB_LLM_BASE_URL (default
OpenRouter), KB_LLM_MODEL (default openai/gpt-4o-mini), and the API key
via either KB_LLM_API_KEY (static) or KB_LLM_API_KEY_CMD (a vault CLI
command whose stdout is the key, e.g. Proton Pass's pass-cli -- wins over
the static value if both are set). With KB_ENRICH=0 or no resolvable key,
/enrich is a clean no-op: zero network calls, zero crashes. The
put/clip/query/atomize path never depends on any of this.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import os
import re
import sqlite3
import subprocess
import sys
import types
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

__all__ = [
    "KbServeConfig",
    "build_config",
    "build_parser",
    "kb_atomize",
    "kb_clip_and_atomize",
    "kb_enrich",
    "kb_put",
    "load_kb_env",
    "main",
    "resolve_api_key",
]

log = logging.getLogger("kb-serve")

SCRIPT_DIR = Path(__file__).resolve().parent

DEFAULT_PORT = 9100
TYPE_TO_DIR = {
    "decision": "decisions", "note": "notes",
    "research": "research", "source": "sources",
}
DEFAULT_NOTE_TYPE = "note"

DEFAULT_LLM_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_LLM_MODEL = "openai/gpt-4o-mini"
LLM_TIMEOUT_SEC = 30.0
API_KEY_CMD_TIMEOUT_SEC = 15.0
# ponytail: bounds one /enrich call's model spend to a fixed batch; call
# /enrich again to keep going rather than adding pagination for a personal
# vault of this size.
ENRICH_BATCH_LIMIT = 20

# Bounds the frontmatter block a rewrite touches: "---\n...\n---\n", so
# question/summary get patched in place without disturbing the body.
FRONTMATTER_BOUNDS_RE = re.compile(r"^(---\n)(.*?)(\n---\n)", re.DOTALL)


def _load_sibling(name: str) -> types.ModuleType:
    """Dynamically import a hyphenated sibling script as a module.

    kb-index.py / kb-clip.py are executable CLIs with hyphenated
    filenames, which a normal `import` statement cannot name. Loading them
    by path lets kb-serve.py call their functions directly instead of
    copy-pasting logic (it stays a thin facade, per its own docstring).
    """
    path = SCRIPT_DIR / f"{name}.py"
    module_name = name.replace("-", "_")
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load sibling module {path}")
    module = importlib.util.module_from_spec(spec)
    # dataclasses (3.11+) resolves annotations via sys.modules[cls.__module__],
    # so the module must be registered there BEFORE exec_module runs any
    # @dataclass decorators inside it, else that lookup returns None and
    # dataclass() raises AttributeError.
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


kb_index = _load_sibling("kb-index")
kb_clip = _load_sibling("kb-clip")
kb_atomize_mod = _load_sibling("kb-atomize")


# ── config + secret resolution ────────────────────────────────────────


@dataclass(frozen=True)
class KbServeConfig:
    """Resolved runtime config for one server/CLI invocation."""

    kb_home: Path
    enrich_enabled: bool
    llm_base_url: str
    llm_model: str
    llm_api_key: str | None


def load_kb_env(kb_home: Path) -> dict[str, str]:
    """Parse simple KEY=VALUE lines from <kb_home>/kb.env.

    Missing file, blank lines, and '#' comments are silently skipped;
    never raises. Not a shell parser -- values may be optionally wrapped
    in matching quotes, nothing fancier (matches kb.env.example's shape).
    """
    env_path = kb_home / "kb.env"
    values: dict[str, str] = {}
    if not env_path.is_file():
        return values
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def resolve_api_key(env: Mapping[str, str]) -> str | None:
    """Resolve the LLM API key: KB_LLM_API_KEY_CMD (a vault CLI command,
    e.g. Proton Pass's `pass-cli item view ... --field api-key`) wins over
    a static KB_LLM_API_KEY. Returns None if neither yields one. Never
    logs the resolved value.
    """
    cmd = env.get("KB_LLM_API_KEY_CMD", "").strip()
    if cmd:
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=API_KEY_CMD_TIMEOUT_SEC, check=True,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            log.warning("KB_LLM_API_KEY_CMD failed (%s); no key resolved", exc)
            return None
        return result.stdout.strip() or None
    return env.get("KB_LLM_API_KEY", "").strip() or None


def build_config(kb_home: Path) -> KbServeConfig:
    """Merge kb.env under the real process env (env wins) and resolve the
    enrichment flags + API key. The put/clip/query/atomize path never
    touches any value built here."""
    merged: dict[str, str] = {**load_kb_env(kb_home), **os.environ}
    enrich_enabled = merged.get("KB_ENRICH", "0") == "1"
    api_key = resolve_api_key(merged) if enrich_enabled else None
    return KbServeConfig(
        kb_home=kb_home,
        enrich_enabled=enrich_enabled,
        llm_base_url=merged.get("KB_LLM_BASE_URL", DEFAULT_LLM_BASE_URL),
        llm_model=merged.get("KB_LLM_MODEL", DEFAULT_LLM_MODEL),
        llm_api_key=api_key,
    )


# ── deterministic core: put / clip / atomize / query ──────────────────


def _require_str(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise KeyError(f"{key!r} is required")
    return value


def render_note(note_type: str, title: str, source: str, project: str, body: str) -> str:
    """Serialize one manually-put note: LOCKED frontmatter + body + Refs.

    Same frontmatter shape as kb-clip.py's captured source notes (reuses
    its field list + quoting helpers), just generic to any note type.
    """
    frontmatter = {
        "type": note_type, "title": title, "source": source, "author": "",
        "site": "", "published": "", "fetched": date.today().isoformat(),
        "description": "", "tags": kb_clip.yaml_list([]), "project": project,
        "status": "active", "question": "", "summary": "",
    }
    lines = ["---"]
    for key in kb_clip.FRONTMATTER_FIELDS:
        value = frontmatter[key]
        rendered = value if key == "tags" else kb_clip.yaml_quote(str(value))
        lines.append(f"{key}: {rendered}")
    lines.extend(["---", "", body, "", "## Refs", ""])
    if source:
        lines.append(f"- {source}")
    return "\n".join(lines) + "\n"


def build_index(kb_home: Path) -> None:
    """Rebuild kb.db from every project. Thin wrapper over kb-index.py."""
    kb_index.build_index(kb_home, kb_home / "index" / "kb.db")


def kb_atomize(note_path: Path, kb_home: Path) -> list[Path]:
    """Split a long source/research note into atomic children. See
    kb-atomize.py's own docstring for the deterministic split rule."""
    return kb_atomize_mod.kb_atomize(note_path, kb_home)


def kb_put(kb_home: Path, payload: Mapping[str, object]) -> dict[str, object]:
    """Write one note, atomize it if it qualifies, reindex. Returns the
    created note path(s). Raises KeyError/ValueError on bad input."""
    project = _require_str(payload, "project")
    content = _require_str(payload, "content")
    note_type = str(payload.get("type") or DEFAULT_NOTE_TYPE)
    dir_name = TYPE_TO_DIR.get(note_type)
    if dir_name is None:
        raise ValueError(f"unknown type {note_type!r}, expected one of {sorted(TYPE_TO_DIR)}")
    title = str(payload.get("title") or "untitled")
    source = str(payload.get("source") or "")

    notes_dir = kb_home / project / dir_name
    notes_dir.mkdir(parents=True, exist_ok=True)
    note_path = kb_clip.build_note_path(notes_dir, kb_clip.slugify(title))
    note_path.write_text(render_note(note_type, title, source, project, content), encoding="utf-8")

    children = kb_atomize(note_path, kb_home)
    build_index(kb_home)
    return {"path": str(note_path), "children": [str(p) for p in children]}


def kb_clip_and_atomize(kb_home: Path, payload: Mapping[str, object]) -> dict[str, object]:
    """Capture a URL (kb-clip.py), atomize it if it qualifies, reindex."""
    url = _require_str(payload, "url")
    project = _require_str(payload, "project")
    note_path = kb_clip.clip(url, project, kb_home)
    children = kb_atomize(note_path, kb_home)
    build_index(kb_home)
    return {"path": str(note_path), "children": [str(p) for p in children]}


def run_query(kb_home: Path, q: str, project: str | None, note_type: str | None, include_all: bool) -> list[dict]:
    """Thin wrapper over kb-index.py's FTS5 query."""
    db_path = kb_home / "index" / "kb.db"
    return kb_index.query_index(db_path, q, project, note_type, include_all)


def count_indexed_notes(kb_home: Path) -> int:
    """Row count in kb.db, or 0 if it hasn't been built yet."""
    db_path = kb_home / "index" / "kb.db"
    if not db_path.exists():
        return 0
    con = sqlite3.connect(db_path)
    try:
        return con.execute("SELECT COUNT(*) FROM kb").fetchone()[0]
    finally:
        con.close()


# ── LLM enrichment (the only model-spend path, off by default) ────────


def find_unenriched_notes(
    kb_home: Path, project: str | None, note_filter: str | None,
) -> list[Path]:
    """Notes with an empty question or summary, capped at
    ENRICH_BATCH_LIMIT. note_filter, if given, targets exactly that path,
    resolved against kb_home -- an absolute or ../-escaping value that
    lands outside kb_home is treated as "no matching note" (empty list),
    never read, per this module's clean-no-op philosophy."""
    if note_filter:
        candidate = (kb_home / note_filter).resolve()
        if not candidate.is_relative_to(kb_home.resolve()) or not candidate.is_file():
            return []
        return [candidate]
    unenriched: list[Path] = []
    for path in kb_index.find_markdown_files(kb_home):
        if project and kb_index.derive_project(path, kb_home) != project:
            continue
        fields, _ = kb_index.parse_frontmatter(path.read_text(encoding="utf-8"))
        if not fields.get("question") or not fields.get("summary"):
            unenriched.append(path)
        if len(unenriched) >= ENRICH_BATCH_LIMIT:
            break
    return unenriched


def request_enrichment(config: KbServeConfig, title: str, body: str) -> dict[str, str]:
    """One chat-completions call asking for {question, summary} JSON.

    Raises on any network/parse failure; kb_enrich decides how to degrade
    (skip that note, keep going).
    """
    prompt = (
        "Given this knowledgebase note, respond with ONLY a JSON object "
        '{"question": "...", "summary": "..."}. question = the question '
        "someone would search to find this note. summary = a 2-3 sentence "
        f"summary of its content.\n\nTitle: {title}\n\n{body[:4000]}"
    )
    payload = json.dumps({
        "model": config.llm_model,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    request = urllib.request.Request(
        f"{config.llm_base_url}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {config.llm_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=LLM_TIMEOUT_SEC) as response:
        data = json.loads(response.read())
    content = data["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    return {
        "question": str(parsed.get("question", "")),
        "summary": str(parsed.get("summary", "")),
    }


def apply_enrichment(note_path: Path, question: str, summary: str) -> None:
    """Rewrite only the question/summary frontmatter lines in place; every
    other line, including the body, is left byte-for-byte untouched."""
    text = note_path.read_text(encoding="utf-8")
    match = FRONTMATTER_BOUNDS_RE.match(text)
    if not match:
        return
    head, raw_fields, tail = match.groups()
    raw_fields = re.sub(
        r"^question:.*$", f"question: {kb_clip.yaml_quote(question)}",
        raw_fields, count=1, flags=re.MULTILINE,
    )
    raw_fields = re.sub(
        r"^summary:.*$", f"summary: {kb_clip.yaml_quote(summary)}",
        raw_fields, count=1, flags=re.MULTILINE,
    )
    note_path.write_text(head + raw_fields + tail + text[match.end():], encoding="utf-8")


def kb_enrich(config: KbServeConfig, payload: Mapping[str, object]) -> dict[str, object]:
    """Fill question/summary on unenriched notes via the configured LLM.

    Clean no-op (zero network calls) if KB_ENRICH=0 or no API key
    resolved -- the caller always gets a 200 with a clear `message`,
    never a crash.
    """
    if not config.enrich_enabled:
        return {"enriched": 0, "message": "KB_ENRICH is 0; enrichment disabled"}
    if not config.llm_api_key:
        return {
            "enriched": 0,
            "message": "KB_ENRICH=1 but no API key resolved "
                       "(checked KB_LLM_API_KEY_CMD, KB_LLM_API_KEY)",
        }

    project = payload.get("project")
    note_filter = payload.get("note")
    notes = find_unenriched_notes(
        config.kb_home,
        str(project) if project else None,
        str(note_filter) if note_filter else None,
    )
    enriched: list[str] = []
    for note_path in notes:
        try:
            fields, body = kb_index.parse_frontmatter(note_path.read_text(encoding="utf-8"))
            result = request_enrichment(config, str(fields.get("title", note_path.stem)), body)
        except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, IndexError) as exc:
            log.warning("enrichment failed for %s: %s", note_path, exc)
            continue
        apply_enrichment(note_path, result["question"], result["summary"])
        enriched.append(str(note_path))

    if enriched:
        build_index(config.kb_home)
    return {"enriched": len(enriched), "notes": enriched}


# ── HTTP server ─────────────────────────────────────────────────────────


class KbHTTPServer(ThreadingHTTPServer):
    """ThreadingHTTPServer carrying the resolved KbServeConfig."""

    def __init__(self, address: tuple[str, int], handler_cls: type, config: KbServeConfig) -> None:
        self.config = config
        super().__init__(address, handler_cls)


class KbRequestHandler(BaseHTTPRequestHandler):
    """Dispatches the 4 JSON endpoints onto the module-level pure
    functions above; carries no logic of its own beyond wiring."""

    server: KbHTTPServer  # type: ignore[assignment]  # narrows the stdlib base's untyped .server attr

    def log_message(self, fmt: str, *args: object) -> None:
        log.info("%s - %s", self.address_string(), fmt % args)

    def _send_json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b""
        return json.loads(raw) if raw else {}

    def do_GET(self) -> None:  # noqa: N802 stdlib override name
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            kb_home = self.server.config.kb_home
            return self._send_json(200, {
                "status": "ok", "kb_home": str(kb_home),
                "indexed_count": count_indexed_notes(kb_home),
            })
        if parsed.path == "/query":
            return self._handle_query(parse_qs(parsed.query))
        self._send_json(404, {"error": "not found"})

    def _handle_query(self, qs: dict[str, list[str]]) -> None:
        q = (qs.get("q") or [""])[0]
        if not q:
            return self._send_json(400, {"error": "q is required"})
        project = (qs.get("project") or [None])[0]
        note_type = (qs.get("type") or [None])[0]
        include_all = (qs.get("all") or ["0"])[0] == "1"
        results = run_query(self.server.config.kb_home, q, project, note_type, include_all)
        self._send_json(200, {"results": results})

    def do_POST(self) -> None:  # noqa: N802 stdlib override name
        parsed = urlparse(self.path)
        try:
            payload = self._read_json_body()
        except json.JSONDecodeError as exc:
            return self._send_json(400, {"error": f"invalid JSON body: {exc}"})

        if parsed.path == "/put":
            return self._handle_put(payload)
        if parsed.path == "/clip":
            return self._handle_clip(payload)
        if parsed.path == "/enrich":
            return self._send_json(200, kb_enrich(self.server.config, payload))
        self._send_json(404, {"error": "not found"})

    def _handle_put(self, payload: dict[str, object]) -> None:
        try:
            result = kb_put(self.server.config.kb_home, payload)
        except (KeyError, ValueError) as exc:
            return self._send_json(400, {"error": str(exc)})
        self._send_json(201, result)

    def _handle_clip(self, payload: dict[str, object]) -> None:
        try:
            result = kb_clip_and_atomize(self.server.config.kb_home, payload)
        except (KeyError, ValueError) as exc:
            return self._send_json(400, {"error": str(exc)})
        except (OSError, urllib.error.URLError) as exc:
            return self._send_json(502, {"error": f"clip fetch failed: {exc}"})
        self._send_json(201, result)


def serve_forever(config: KbServeConfig, host: str, port: int) -> None:
    server = KbHTTPServer((host, port), KbRequestHandler, config)
    log.info("kb-serve listening on %s:%s (kb_home=%s)", host, port, config.kb_home)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


# ── CLI ─────────────────────────────────────────────────────────────────


def cmd_run(args: argparse.Namespace) -> int:
    kb_home = kb_index.resolve_kb_home(args.kb_home)
    (kb_home / "index").mkdir(parents=True, exist_ok=True)
    serve_forever(build_config(kb_home), args.host, args.port)
    return 0


def cmd_put(args: argparse.Namespace) -> int:
    kb_home = kb_index.resolve_kb_home(args.kb_home)
    payload = {
        "project": args.project, "title": args.title, "type": args.type,
        "source": args.source, "content": sys.stdin.read(),
    }
    print(json.dumps(kb_put(kb_home, payload)))
    return 0


def cmd_clip(args: argparse.Namespace) -> int:
    kb_home = kb_index.resolve_kb_home(args.kb_home)
    print(json.dumps(kb_clip_and_atomize(kb_home, {"url": args.url, "project": args.project})))
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    kb_home = kb_index.resolve_kb_home(args.kb_home)
    results = run_query(kb_home, args.q, args.project, args.type, args.all)
    print(json.dumps({"results": results}, indent=2))
    return 0


def cmd_resolve_secret(args: argparse.Namespace) -> int:
    """Print `KB_LLM_API_KEY=<value>` for an EnvironmentFile= to consume.

    The only line ever written to stdout; the resolved value is never
    logged. Empty value (still prints the key, blank) if neither
    KB_LLM_API_KEY_CMD nor KB_LLM_API_KEY resolves -- callers treat that
    the same as "no key configured".
    """
    kb_home = kb_index.resolve_kb_home(args.kb_home)
    merged = {**load_kb_env(kb_home), **os.environ}
    print(f"KB_LLM_API_KEY={resolve_api_key(merged) or ''}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    run_cmd = sub.add_parser("run", help="serve the HTTP facade in the foreground")
    run_cmd.add_argument("--host", default=os.environ.get("KB_SERVE_HOST", "127.0.0.1"))
    run_cmd.add_argument("--port", type=int, default=int(os.environ.get("KB_SERVE_PORT", DEFAULT_PORT)))
    run_cmd.add_argument("--kb-home", default=None)

    put_cmd = sub.add_parser("put", help="write + atomize + index one note (content on stdin)")
    put_cmd.add_argument("project")
    put_cmd.add_argument("title")
    put_cmd.add_argument("--type", default=DEFAULT_NOTE_TYPE)
    put_cmd.add_argument("--source", default="")
    put_cmd.add_argument("--kb-home", default=None)

    clip_cmd = sub.add_parser("clip", help="capture a URL + atomize + index")
    clip_cmd.add_argument("url")
    clip_cmd.add_argument("--project", default="inbox")
    clip_cmd.add_argument("--kb-home", default=None)

    query_cmd = sub.add_parser("query", help="full-text search the index")
    query_cmd.add_argument("q")
    query_cmd.add_argument("--project", default=None)
    query_cmd.add_argument("--type", default=None)
    query_cmd.add_argument("--all", action="store_true", help="include superseded notes")
    query_cmd.add_argument("--kb-home", default=None)

    secret_cmd = sub.add_parser(
        "resolve-secret",
        help="print the resolved LLM API key for a systemd EnvironmentFile=",
    )
    secret_cmd.add_argument("--kb-home", default=None)

    return parser


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    args = build_parser().parse_args(argv)
    dispatch = {
        "run": cmd_run, "put": cmd_put, "clip": cmd_clip,
        "query": cmd_query, "resolve-secret": cmd_resolve_secret,
    }
    return dispatch[args.command](args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
