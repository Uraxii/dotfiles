#!/usr/bin/env python3
"""review-serve — stage and serve generated artifacts for review.

Rebuild of artifact-serve into a review app: deep-zoom image gallery
(OpenSeadragon), pin-to-region annotations (Annotorious), threaded resolvable
comments, per-line code feedback, and an optional bd mirror. Same bones as the
legacy script: staging-by-symlink, stdlib http.server + sqlite3 daemon,
optional `tailscale serve` HTTPS, durable DB + uploads under
~/.local/share/claude-artifacts/, agent read-back as JSON.

stdlib only. See spikes/review-app/DESIGN.md for the full design.
"""
from __future__ import annotations

import argparse
import errno
import html
import http.server
import io
import json
import logging
import mimetypes
import os
import re
import shutil
import signal
import socket
import socketserver
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.parse
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

__all__ = [
    "Anchor",
    "Reply",
    "Thread",
    "Upload",
    "build_parser",
    "db_connect",
    "main",
]

log = logging.getLogger("review-serve")

# ── names + paths ─────────────────────────────────────────────────────

# Names allowed for --project and --as (kebab-case + underscore). The first
# character class forbids a project literally named "_", so the entire
# reserved "/_/..." app namespace can never collide with a pushed artifact.
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

# Throwaway staging root (wipes on reboot).
ROOT = Path("/tmp/claude-artifacts")
PID_FILE = ROOT / ".serve.pid"
PORT_FILE = ROOT / ".serve.port"
LOG_FILE = ROOT / ".serve.log"
INDEX_FILE = ROOT / "index.html"

# Durable feedback storage (survives /tmp/ wipe + reboot).
FEEDBACK_ROOT = Path.home() / ".local" / "share" / "claude-artifacts"
FEEDBACK_DB = FEEDBACK_ROOT / "feedback.db"
UPLOAD_ROOT = FEEDBACK_ROOT / "uploads"

# Vendored static frontend (OpenSeadragon + Annotorious), served under
# /_/assets/. Lives beside this script in the skill dir.
SKILL_DIR = Path(__file__).resolve().parent.parent
ASSETS_ROOT = SKILL_DIR / "assets"

# Dotfiles repo root, used only to locate scripts/beads-hub.sh for the
# optional bd mirror (section 11). This script always lives at
# <repo>/.claude/skills/artifact-serve/scripts/review-serve.py, so the repo
# root is computed relative to this file rather than hardcoded — keeps the
# path-standard identity-leak lint happy and the script portable.
REPO_ROOT = Path(__file__).resolve().parents[4]
BEADS_HUB_SCRIPT = REPO_ROOT / "scripts" / "beads-hub.sh"

DEFAULT_PORT = 9099
EXIT_OK = 0
EXIT_CALLER = 1
EXIT_SERVER = 2

# ── review-app constants ──────────────────────────────────────────────

# Current on-disk schema version. Bumped by the v1->v2 backfill migration.
SCHEMA_VERSION = 2

# Anchor kinds a thread may carry.
ANCHOR_PAGE = "page"
ANCHOR_IMAGE_REGION = "image_region"
ANCHOR_CODE_LINE = "code_line"
ANCHOR_KINDS = frozenset({ANCHOR_PAGE, ANCHOR_IMAGE_REGION, ANCHOR_CODE_LINE})

# Selector types accepted inside an image_region anchor. SvgSelector is
# rejected server-side: Annotorious's setAnnotations() parses SVG selector
# markup into the live DOM (stored XSS), and the drawing UI only ever emits
# FragmentSelector rects, so SvgSelector is attacker-only input.
SELECTOR_FRAGMENT = "FragmentSelector"

# Hard cap on the anchor_data JSON blob (defensive: do not trust client JSON).
MAX_ANCHOR_BYTES = 8 * 1024

# Strict media-fragment value for a FragmentSelector (x,y,w,h).
FRAGMENT_XYWH_RE = re.compile(
    r"^xywh=(pixel:|percent:)?"
    r"\d+(\.\d+)?,\d+(\.\d+)?,\d+(\.\d+)?,\d+(\.\d+)?$"
)

# Image extensions the gallery + OSD viewer treat as viewable.
IMAGE_EXT = frozenset(
    {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
)

# Upload guardrails (unchanged from legacy — do not regress).
MAX_UPLOAD_BYTES = 100 * 1024 * 1024
MAX_REQUEST_BYTES = 500 * 1024 * 1024
UPLOAD_EXT_ALLOW = frozenset(
    {
        ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff",
        ".pdf", ".txt", ".md", ".log", ".csv", ".json", ".yaml", ".yml",
        ".toml", ".zip", ".tar", ".gz", ".7z",
        ".fig", ".psd", ".xcf", ".sketch",
        ".mp4", ".webm", ".mov",
    }
)
UPLOAD_EXT_BLOCK = frozenset(
    {".exe", ".dll", ".sh", ".bash", ".zsh", ".bat", ".cmd",
     ".ps1", ".js", ".mjs", ".html", ".htm", ".xhtml", ".svg", ".com"}
)

# Comment body length cap (unchanged from legacy).
MAX_BODY_CHARS = 20000


# ── data model ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Upload:
    """One file attached to a reply, stored on disk under UPLOAD_ROOT."""

    id: int
    reply_id: int | None
    filename: str
    stored_path: Path
    mime: str | None
    size: int
    created_at: int


@dataclass(frozen=True)
class Reply:
    """One message within a thread. A thread's first reply is its opener."""

    id: int
    thread_id: int
    body: str
    author: str | None
    created_at: int
    uploads: Sequence[Upload] = field(default_factory=tuple)


@dataclass(frozen=True)
class Anchor:
    """Where a thread is pinned.

    kind is one of ANCHOR_KINDS. data is the parsed, already-validated anchor
    payload: None for a page anchor, the W3C selector dict for an image region,
    or {"line": int, "end_line": int | None} for a code line. The raw JSON
    string that produced this is never trusted; see validate_anchor.
    """

    kind: str
    data: dict[str, object] | None


@dataclass(frozen=True)
class Thread:
    """A comment thread anchored somewhere on a served page or file."""

    id: int
    artifact_id: str
    sub_path: str
    anchor: Anchor
    resolved: bool
    author: str | None
    created_at: int
    bd_ticket: str | None = None
    replies: Sequence[Reply] = field(default_factory=tuple)


# ── schema ────────────────────────────────────────────────────────────

# Full DDL. Idempotent (CREATE ... IF NOT EXISTS). The v1->v2 backfill in
# migrate_schema handles the one-time upload-table rebuild and legacy
# comment -> thread/reply copy. See DESIGN.md section 6-7.
SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS artifact_index (
    project     TEXT NOT NULL,
    subdir      TEXT NOT NULL,
    artifact_id TEXT NOT NULL,
    src_path    TEXT NOT NULL,
    last_pushed INTEGER NOT NULL,
    PRIMARY KEY (project, subdir)
);
CREATE INDEX IF NOT EXISTS idx_index_artifact
    ON artifact_index(artifact_id);

CREATE TABLE IF NOT EXISTS comment (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    artifact_id TEXT NOT NULL,
    sub_path    TEXT NOT NULL DEFAULT '',
    body        TEXT NOT NULL,
    author      TEXT,
    created_at  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_comment_artifact_path
    ON comment(artifact_id, sub_path);

CREATE TABLE IF NOT EXISTS setting (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS thread (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    artifact_id TEXT NOT NULL,
    sub_path    TEXT NOT NULL DEFAULT '',
    anchor_kind TEXT NOT NULL DEFAULT 'page',
    anchor_data TEXT,
    resolved    INTEGER NOT NULL DEFAULT 0,
    author      TEXT,
    created_at  INTEGER NOT NULL,
    bd_ticket   TEXT,
    CHECK (anchor_kind IN ('page', 'image_region', 'code_line')),
    CHECK (resolved IN (0, 1))
);
CREATE INDEX IF NOT EXISTS idx_thread_artifact_path
    ON thread(artifact_id, sub_path);

CREATE TABLE IF NOT EXISTS reply (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id  INTEGER NOT NULL REFERENCES thread(id) ON DELETE CASCADE,
    body       TEXT NOT NULL,
    author     TEXT,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reply_thread ON reply(thread_id);

CREATE TABLE IF NOT EXISTS upload (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    reply_id    INTEGER REFERENCES reply(id) ON DELETE CASCADE,
    comment_id  INTEGER,
    filename    TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    mime        TEXT,
    size        INTEGER NOT NULL,
    created_at  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_upload_reply ON upload(reply_id);
CREATE INDEX IF NOT EXISTS idx_upload_comment ON upload(comment_id);
"""


def db_connect() -> sqlite3.Connection:
    """Open feedback DB; ensure schema + run pending migrations.

    Postcondition: returns a live connection with foreign_keys ON, all tables
    from SCHEMA_DDL present, and setting['schema_version'] == str(SCHEMA_VERSION).
    Caller owns closing.
    """
    ensure_feedback_root()
    conn = sqlite3.connect(str(FEEDBACK_DB), timeout=10.0)
    conn.execute("PRAGMA foreign_keys = ON")

    ddl = SCHEMA_DDL
    upload_cols = {row[1] for row in conn.execute("PRAGMA table_info(upload)")}
    if upload_cols and "reply_id" not in upload_cols:
        # ponytail: a real legacy DB's `upload` table predates the reply_id
        # column, and CREATE TABLE IF NOT EXISTS is a no-op against it, so
        # SCHEMA_DDL's trailing `CREATE INDEX ... ON upload(reply_id)` would
        # fail before that column exists. Skip just that one index here;
        # migrate_schema's one-time rebuild (_rebuild_upload_table_if_legacy)
        # recreates both upload indexes once the table has the new shape.
        ddl = ddl.replace(
            "CREATE INDEX IF NOT EXISTS idx_upload_reply ON upload(reply_id);",
            "",
        )
    conn.executescript(ddl)
    conn.commit()
    migrate_schema(conn)
    return conn


def _rebuild_upload_table_if_legacy(conn: sqlite3.Connection) -> None:
    """Rebuild `upload` once so comment_id is nullable and reply_id exists.

    No-op if the table already has the new shape (fresh DB, or an already
    migrated one) — sqlite cannot drop a NOT NULL constraint in place, so a
    one-time table rebuild is the standard move (DESIGN.md section 7 step 2).
    """
    cols = {row[1] for row in conn.execute("PRAGMA table_info(upload)")}
    if "reply_id" in cols:
        return
    conn.execute(
        "CREATE TABLE upload_new ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "reply_id INTEGER REFERENCES reply(id) ON DELETE CASCADE, "
        "comment_id INTEGER, filename TEXT NOT NULL, "
        "stored_path TEXT NOT NULL, mime TEXT, size INTEGER NOT NULL, "
        "created_at INTEGER NOT NULL)"
    )
    conn.execute(
        "INSERT INTO upload_new "
        "(id, comment_id, filename, stored_path, mime, size, created_at) "
        "SELECT id, comment_id, filename, stored_path, mime, size, created_at "
        "FROM upload"
    )
    conn.execute("DROP TABLE upload")
    conn.execute("ALTER TABLE upload_new RENAME TO upload")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_upload_reply ON upload(reply_id)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_upload_comment ON upload(comment_id)"
    )


def _backfill_legacy_comments(conn: sqlite3.Connection) -> None:
    """Copy each legacy comment row into one page-level thread + one reply.

    Remaps that comment's uploads onto the new reply. Ordered by id so the
    result is deterministic; the caller's schema_version gate is what makes
    a second run a no-op (DESIGN.md section 7 step 3).
    """
    rows = conn.execute(
        "SELECT id, artifact_id, sub_path, body, author, created_at "
        "FROM comment ORDER BY id ASC"
    ).fetchall()
    for cid, artifact_id, sub_path, body, author, created_at in rows:
        thread_id = conn.execute(
            "INSERT INTO thread "
            "(artifact_id, sub_path, anchor_kind, anchor_data, resolved, "
            " author, created_at) VALUES (?, ?, 'page', NULL, 0, ?, ?)",
            (artifact_id, sub_path, author, created_at),
        ).lastrowid
        reply_id = conn.execute(
            "INSERT INTO reply (thread_id, body, author, created_at) "
            "VALUES (?, ?, ?, ?)",
            (thread_id, body, author, created_at),
        ).lastrowid
        conn.execute(
            "UPDATE upload SET reply_id=? WHERE comment_id=?", (reply_id, cid)
        )


def migrate_schema(conn: sqlite3.Connection) -> None:
    """Run the one-time idempotent v1->v2 backfill if not already applied.

    Gated by setting['schema_version'] < SCHEMA_VERSION. All steps run in one
    transaction (see DESIGN.md section 7):
      1. CREATE IF NOT EXISTS the new tables (already done by SCHEMA_DDL).
      2. Rebuild `upload` once so comment_id is nullable and reply_id exists.
      3. Copy each legacy `comment` row into one page-level thread + one reply,
         remap that comment's uploads onto the new reply.
      4. Set setting['schema_version'] = str(SCHEMA_VERSION); commit.
    Idempotent: a second call is a no-op once the version gate is stamped.
    """
    row = conn.execute(
        "SELECT value FROM setting WHERE key='schema_version'"
    ).fetchone()
    current = int(row[0]) if row else 1
    if current >= SCHEMA_VERSION:
        return

    conn.execute("BEGIN IMMEDIATE")
    try:
        _rebuild_upload_table_if_legacy(conn)
        _backfill_legacy_comments(conn)
        conn.execute(
            "INSERT INTO setting (key, value) VALUES ('schema_version', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (str(SCHEMA_VERSION),),
        )
    except sqlite3.Error:
        conn.rollback()
        raise
    else:
        conn.commit()


# ── setting k/v ───────────────────────────────────────────────────────


def setting_get(key: str) -> str | None:
    """Fetch a value from the `setting` table, or None if absent."""
    try:
        conn = db_connect()
        try:
            row = conn.execute(
                "SELECT value FROM setting WHERE key=?", (key,)
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return None
    return row[0] if row else None


def setting_set(key: str, value: str) -> None:
    """Upsert (key, value) into the `setting` table."""
    conn = db_connect()
    try:
        conn.execute(
            "INSERT INTO setting (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        conn.commit()
    finally:
        conn.close()


def setting_delete(key: str) -> None:
    """Remove a row from the `setting` table. No-op if absent."""
    conn = db_connect()
    try:
        conn.execute("DELETE FROM setting WHERE key=?", (key,))
        conn.commit()
    finally:
        conn.close()


# ── artifact resolution + fs helpers (preserved from legacy) ──────────


def ensure_root() -> None:
    """Create /tmp/claude-artifacts/ if missing. Idempotent."""
    ROOT.mkdir(parents=True, exist_ok=True)


def ensure_feedback_root() -> None:
    """Create durable feedback dirs. Idempotent."""
    FEEDBACK_ROOT.mkdir(parents=True, exist_ok=True)
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)


def _check_name(value: str, kind: str) -> str:
    """Validate a project or subdir name against NAME_RE; raise if bad."""
    if not value or not NAME_RE.match(value):
        raise ValueError(
            f"invalid --{kind} {value!r}: must match {NAME_RE.pattern} "
            "(lowercase kebab-case + underscore)"
        )
    return value


def _check_artifact_id(value: str) -> str:
    """Validate a user-supplied --id against NAME_RE (plus one `/`).

    Same charset as project/subdir names, since artifact_id is embedded
    unescaped into an inline `<script>` json.dumps(...) call on the viewer
    and code pages (see _api_*_page). Rejects anything that could break out
    of that script block, e.g. `</script>`.
    """
    parts = value.split("/")
    if len(parts) > 2 or not all(NAME_RE.match(p) for p in parts):
        raise ValueError(
            f"invalid --id {value!r}: must match {NAME_RE.pattern}, "
            "optionally as <project>/<subdir>"
        )
    return value


def project_dir(project: str) -> Path:
    """Return /tmp/claude-artifacts/<project>/, creating it on access."""
    safe = _check_name(project, "project")
    p = ROOT / safe
    p.mkdir(parents=True, exist_ok=True)
    return p


def atomic_write(target: Path, content: str) -> None:
    """Write file via tempfile + os.replace for crash safety."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", dir=str(target.parent), delete=False, encoding="utf-8"
    ) as fh:
        fh.write(content)
        tmp = Path(fh.name)
    os.replace(tmp, target)


def remove_entry(entry: Path) -> None:
    """Delete a pushed entry (symlink, file, or dir). No-op if absent."""
    if entry.is_symlink() or entry.is_file():
        entry.unlink(missing_ok=True)
    elif entry.is_dir():
        shutil.rmtree(entry)


def resolve_artifact_id(url_path: str) -> tuple[str | None, str]:
    """Map a URL path to (artifact_id, sub_path).

    URL form: /<project>/<subdir>/<rest...>. Looks up (project, subdir) in
    artifact_index; falls back to "<project>/<subdir>". Returns (None, "") for
    URLs that do not address a staged artifact (root index, /_/... reserved
    paths, depth < 2). Preserved verbatim from legacy.
    """
    parts = [p for p in url_path.split("/") if p]
    if len(parts) < 2:
        return None, ""
    project, subdir = parts[0], parts[1]
    if not (NAME_RE.match(project) and NAME_RE.match(subdir)):
        return None, ""
    sub_path = "/".join(parts[2:])
    try:
        conn = db_connect()
        try:
            row = conn.execute(
                "SELECT artifact_id FROM artifact_index "
                "WHERE project=? AND subdir=?",
                (project, subdir),
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        row = None
    artifact_id = row[0] if row else f"{project}/{subdir}"
    return artifact_id, sub_path


def _artifact_location(artifact_id: str) -> tuple[Path, str, str] | None:
    """Resolve (root_dir, project, subdir) for an artifact_id, or None.

    Looks up artifact_index first (trusted values from a real push); only
    falls back to splitting "<project>/<subdir>" when both halves pass
    NAME_RE, which blocks path traversal via an unvalidated artifact_id
    (NAME_RE forbids '.' and '/', so no ".." can survive the fallback).
    """
    try:
        conn = db_connect()
        try:
            row = conn.execute(
                "SELECT project, subdir FROM artifact_index "
                "WHERE artifact_id=? ORDER BY last_pushed DESC LIMIT 1",
                (artifact_id,),
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        row = None

    if row:
        project, subdir = row
    elif "/" in artifact_id:
        project, subdir = artifact_id.split("/", 1)
        if not (NAME_RE.match(project) and NAME_RE.match(subdir)):
            return None
    else:
        return None

    root = (ROOT / project / subdir).resolve()
    if not root.is_dir():
        return None
    return root, project, subdir


def staged_source_path(artifact_id: str, rel: str) -> Path | None:
    """Resolve a review `src` relpath to a real file under the staged root.

    Used by the /_/review image and code routes. Returns the resolved real
    path only if it stays inside the pushed artifact's staged directory
    (normalize + is_relative_to guard); returns None on traversal escape or
    missing file. See DESIGN.md section 10.4.
    """
    loc = _artifact_location(artifact_id)
    if loc is None:
        return None
    root = loc[0]
    target = (root / rel).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        return None
    return target


def iso_utc(ts: int | None) -> str | None:
    """Format an epoch int as ISO-8601 UTC, or None. Preserved from legacy."""
    if ts is None:
        return None
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def safe_upload_filename(name: str) -> str:
    """Sanitize an uploaded filename: basename, kebab-safe. Preserved."""
    base = Path(name).name or "unnamed"
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", base)
    base = base.lstrip(".") or "unnamed"
    return base[:200]


def upload_ext_ok(filename: str) -> tuple[bool, str]:
    """Validate extension against allowlist/blocklist. Preserved."""
    ext = Path(filename).suffix.lower()
    if ext in UPLOAD_EXT_BLOCK:
        return False, f"extension {ext!r} is blocked"
    if ext not in UPLOAD_EXT_ALLOW:
        return False, f"extension {ext!r} is not in allowlist"
    return True, ""


# Multipart boundary regex helpers (preserved from legacy).
_BOUNDARY_RE = re.compile(r'boundary="?([^";]+)"?', re.IGNORECASE)
_DISP_NAME_RE = re.compile(r'name="([^"]+)"')
_DISP_FILENAME_RE = re.compile(r'filename="([^"]*)"')


def parse_multipart_form(
    content_type: str, body: bytes
) -> tuple[dict[str, str], list[dict[str, object]]]:
    """Parse multipart/form-data into (fields, files). Preserved from legacy.

    stdlib-only replacement for the removed cgi.FieldStorage. Loads the whole
    body into memory; callers enforce MAX_REQUEST_BYTES first.
    """
    m = _BOUNDARY_RE.search(content_type)
    if not m:
        raise ValueError("Content-Type has no boundary")
    boundary = b"--" + m.group(1).encode("latin-1")
    fields: dict[str, str] = {}
    files: list[dict[str, object]] = []
    for raw in body.split(boundary):
        chunk = raw.strip(b"\r\n")
        if not chunk or chunk == b"--":
            continue
        if b"\r\n\r\n" not in chunk:
            continue
        header_blob, _, payload = chunk.partition(b"\r\n\r\n")
        if payload.endswith(b"\r\n"):
            payload = payload[:-2]
        headers: dict[str, str] = {}
        for line in header_blob.split(b"\r\n"):
            if b":" in line:
                k, _, v = line.partition(b":")
                headers[k.strip().lower().decode("ascii", "replace")] = (
                    v.strip().decode("latin-1", "replace")
                )
        disp = headers.get("content-disposition", "")
        name_m = _DISP_NAME_RE.search(disp)
        if not name_m:
            continue
        name = name_m.group(1)
        fname_m = _DISP_FILENAME_RE.search(disp)
        if fname_m and fname_m.group(1):
            files.append(
                {
                    "name": name,
                    "filename": fname_m.group(1),
                    "content_type": headers.get(
                        "content-type", "application/octet-stream"
                    ),
                    "data": payload,
                }
            )
        else:
            fields[name] = payload.decode("utf-8", errors="replace")
    return fields, files


# ── anchor validation (trust boundary) ────────────────────────────────


def _validate_fragment_selector(selector: dict[str, object]) -> dict[str, object]:
    """Validate + re-serialize a FragmentSelector. Raises ValueError."""
    value = selector.get("value")
    if not isinstance(value, str) or not FRAGMENT_XYWH_RE.match(value):
        raise ValueError("FragmentSelector value is malformed")
    clean: dict[str, object] = {"type": SELECTOR_FRAGMENT, "value": value}
    conforms_to = selector.get("conformsTo")
    if isinstance(conforms_to, str):
        clean["conformsTo"] = conforms_to
    return clean


def validate_anchor(anchor_kind: str, anchor_data_raw: str | None) -> Anchor:
    """Validate a client-supplied anchor and return a normalized Anchor.

    Defensive: never trust the raw JSON blob (see DESIGN.md section 10.2).
    Contract:
      - anchor_kind must be in ANCHOR_KINDS, else ValueError.
      - anchor_data_raw longer than MAX_ANCHOR_BYTES -> ValueError.
      - page: anchor_data_raw must be empty/None; Anchor.data is None.
      - image_region: object with a `selector` object whose `type` is
        SELECTOR_FRAGMENT (value matches FRAGMENT_XYWH_RE). Any other selector
        type (e.g. SvgSelector) is rejected: ValueError.
      - code_line: object with int `line` >= 1 and optional int `end_line`
        >= line. Else ValueError.
    Returns an Anchor holding the re-serialized, validated payload (unknown
    extra keys dropped). Raises ValueError with a caller-safe message on any
    violation.
    """
    if anchor_kind not in ANCHOR_KINDS:
        raise ValueError(f"invalid anchor_kind {anchor_kind!r}")
    if anchor_data_raw and len(anchor_data_raw.encode("utf-8")) > MAX_ANCHOR_BYTES:
        raise ValueError(f"anchor_data exceeds {MAX_ANCHOR_BYTES}B cap")

    if anchor_kind == ANCHOR_PAGE:
        if anchor_data_raw and anchor_data_raw.strip():
            raise ValueError("page anchor must not carry anchor_data")
        return Anchor(kind=ANCHOR_PAGE, data=None)

    if not anchor_data_raw or not anchor_data_raw.strip():
        raise ValueError(f"{anchor_kind} anchor requires anchor_data")
    try:
        parsed = json.loads(anchor_data_raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"anchor_data is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("anchor_data must be a JSON object")

    if anchor_kind == ANCHOR_IMAGE_REGION:
        selector = parsed.get("selector")
        if not isinstance(selector, dict):
            raise ValueError("image_region anchor requires a selector object")
        sel_type = selector.get("type")
        if sel_type == SELECTOR_FRAGMENT:
            clean_selector = _validate_fragment_selector(selector)
        else:
            raise ValueError(f"unsupported selector type {sel_type!r}")
        return Anchor(kind=ANCHOR_IMAGE_REGION, data={"selector": clean_selector})

    # ANCHOR_CODE_LINE
    line = parsed.get("line")
    if not isinstance(line, int) or isinstance(line, bool) or line < 1:
        raise ValueError("code_line anchor requires integer line >= 1")
    data: dict[str, object] = {"line": line}
    end_line = parsed.get("end_line")
    if end_line is not None:
        if (
            not isinstance(end_line, int)
            or isinstance(end_line, bool)
            or end_line < line
        ):
            raise ValueError("code_line end_line must be an integer >= line")
        data["end_line"] = end_line
    return Anchor(kind=ANCHOR_CODE_LINE, data=data)


def serialize_anchor(anchor: Anchor) -> str | None:
    """Serialize a validated Anchor back to the anchor_data column string.

    Returns None for a page anchor, else compact JSON. Inverse of the parse
    half of validate_anchor.
    """
    if anchor.kind == ANCHOR_PAGE:
        return None
    return json.dumps(anchor.data, separators=(",", ":"), sort_keys=True)


# ── thread + reply store ──────────────────────────────────────────────


def _store_uploads(
    conn: sqlite3.Connection, reply_id: int, files: Iterable[dict[str, object]]
) -> list[dict[str, object]]:
    """Write upload files to disk under UPLOAD_ROOT/<reply_id>/ + insert rows.

    Returns saved upload metadata dicts. Caller commits the transaction.
    """
    saved: list[dict[str, object]] = []
    files = list(files)
    if not files:
        return saved
    rdir = UPLOAD_ROOT / str(reply_id)
    rdir.mkdir(parents=True, exist_ok=True)
    for f in files:
        raw_name = str(f.get("filename") or "unnamed")
        safe = safe_upload_filename(raw_name)
        data: bytes = f.get("data", b"")  # type: ignore[assignment]  # multipart part payload is always bytes
        target = rdir / safe
        i = 1
        stem, suf = target.stem, target.suffix
        while target.exists():
            target = rdir / f"{stem}-{i}{suf}"
            i += 1
        target.write_bytes(data)
        mime, _ = mimetypes.guess_type(safe)
        conn.execute(
            "INSERT INTO upload "
            "(reply_id, filename, stored_path, mime, size, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (reply_id, safe, str(target), mime, len(data), int(time.time())),
        )
        saved.append({"filename": safe, "size": len(data), "mime": mime})
    return saved


def uploads_for_reply(reply_id: int) -> list[dict[str, object]]:
    """Fetch one reply's uploads, in the same shape GET /_/api/threads uses.

    Used by the create-thread/create-reply API handlers so their 201 bodies
    carry an `uploads` list matching DESIGN.md section 9, same shape as
    _thread_json's replies[].uploads. Empty list if the reply has none.
    """
    conn = db_connect()
    try:
        rows = conn.execute(
            "SELECT id, reply_id, filename, stored_path, mime, size, "
            "created_at FROM upload WHERE reply_id=? ORDER BY id ASC",
            (reply_id,),
        ).fetchall()
    finally:
        conn.close()
    return [
        _upload_json(
            Upload(id=u[0], reply_id=u[1], filename=u[2],
                   stored_path=Path(u[3]), mime=u[4], size=u[5],
                   created_at=u[6])
        )
        for u in rows
    ]


def create_thread(
    artifact_id: str,
    sub_path: str,
    anchor: Anchor,
    body: str,
    author: str | None,
    files: Iterable[dict[str, object]],
) -> tuple[int, int]:
    """Open a thread with its first reply. Returns (thread_id, reply_id).

    Preconditions: anchor is already validated; body non-empty and within the
    length cap; files already passed upload_ext_ok + size caps. Author falls
    back to setting['author'] when None (preserved behavior). Inserts thread +
    reply + uploads in one transaction, writes upload bytes under
    UPLOAD_ROOT/<reply_id>/. If the bd_mirror setting is on, best-effort
    mirror_thread_create (never raises out).
    """
    if author is None:
        author = setting_get("author")
    now = int(time.time())
    anchor_data = serialize_anchor(anchor)
    conn = db_connect()
    try:
        cur = conn.execute(
            "INSERT INTO thread "
            "(artifact_id, sub_path, anchor_kind, anchor_data, resolved, "
            " author, created_at) VALUES (?, ?, ?, ?, 0, ?, ?)",
            (artifact_id, sub_path, anchor.kind, anchor_data, author, now),
        )
        thread_id = cur.lastrowid
        if thread_id is None:
            raise sqlite3.Error("no rowid from thread insert")
        reply_cur = conn.execute(
            "INSERT INTO reply (thread_id, body, author, created_at) "
            "VALUES (?, ?, ?, ?)",
            (thread_id, body, author, now),
        )
        reply_id = reply_cur.lastrowid
        if reply_id is None:
            raise sqlite3.Error("no rowid from reply insert")
        _store_uploads(conn, reply_id, files)
        conn.commit()
    finally:
        conn.close()

    if bd_mirror_enabled():
        reply = Reply(id=reply_id, thread_id=thread_id, body=body, author=author,
                       created_at=now, uploads=())
        thread_obj = Thread(
            id=thread_id, artifact_id=artifact_id, sub_path=sub_path,
            anchor=anchor, resolved=False, author=author, created_at=now,
            bd_ticket=None, replies=(reply,),
        )
        ticket = mirror_thread_create(thread_obj)
        if ticket:
            conn2 = db_connect()
            try:
                conn2.execute(
                    "UPDATE thread SET bd_ticket=? WHERE id=?",
                    (ticket, thread_id),
                )
                conn2.commit()
            finally:
                conn2.close()
    return thread_id, reply_id


def add_reply(
    thread_id: int,
    body: str,
    author: str | None,
    files: Iterable[dict[str, object]],
) -> int:
    """Append a reply to an existing thread. Returns reply_id.

    Preconditions as create_thread's reply half. Raises KeyError if thread_id
    is absent. If the thread has a bd_ticket, best-effort mirror_reply_add.
    """
    if author is None:
        author = setting_get("author")
    now = int(time.time())
    conn = db_connect()
    try:
        row = conn.execute(
            "SELECT id, bd_ticket FROM thread WHERE id=?", (thread_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"thread {thread_id} not found")
        bd_ticket = row[1]
        cur = conn.execute(
            "INSERT INTO reply (thread_id, body, author, created_at) "
            "VALUES (?, ?, ?, ?)",
            (thread_id, body, author, now),
        )
        reply_id = cur.lastrowid
        if reply_id is None:
            raise sqlite3.Error("no rowid from reply insert")
        _store_uploads(conn, reply_id, files)
        conn.commit()
    finally:
        conn.close()

    if bd_ticket:
        reply = Reply(id=reply_id, thread_id=thread_id, body=body,
                       author=author, created_at=now, uploads=())
        mirror_reply_add(bd_ticket, reply)
    return reply_id


def set_resolved(thread_id: int, resolved: bool | None) -> bool:
    """Set or toggle a thread's resolved flag. Returns the new state.

    resolved None toggles; True/False sets. Raises KeyError if absent. If the
    thread has a bd_ticket, best-effort mirror_resolve_toggle.
    """
    conn = db_connect()
    try:
        row = conn.execute(
            "SELECT resolved, bd_ticket FROM thread WHERE id=?", (thread_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"thread {thread_id} not found")
        current, bd_ticket = bool(row[0]), row[1]
        new_state = (not current) if resolved is None else bool(resolved)
        conn.execute(
            "UPDATE thread SET resolved=? WHERE id=?",
            (1 if new_state else 0, thread_id),
        )
        conn.commit()
    finally:
        conn.close()
    if bd_ticket:
        mirror_resolve_toggle(bd_ticket, new_state)
    return new_state


def list_threads(artifact_id: str, sub_path: str) -> list[Thread]:
    """Return all threads for (artifact_id, sub_path) with replies + uploads.

    Ordered by thread.created_at, replies by reply.created_at. anchor_data is
    parsed into Anchor.data. Empty list if none.
    """
    conn = db_connect()
    try:
        thread_rows = conn.execute(
            "SELECT id, artifact_id, sub_path, anchor_kind, anchor_data, "
            "resolved, author, created_at, bd_ticket FROM thread "
            "WHERE artifact_id=? AND sub_path=? ORDER BY created_at ASC",
            (artifact_id, sub_path),
        ).fetchall()
        threads: list[Thread] = []
        for (tid, aid, sp, kind, adata, resolved, author, created_at,
             bd_ticket) in thread_rows:
            anchor = Anchor(kind=kind, data=json.loads(adata) if adata else None)
            reply_rows = conn.execute(
                "SELECT id, body, author, created_at FROM reply "
                "WHERE thread_id=? ORDER BY created_at ASC",
                (tid,),
            ).fetchall()
            replies: list[Reply] = []
            for rid, body, r_author, r_created in reply_rows:
                upload_rows = conn.execute(
                    "SELECT id, reply_id, filename, stored_path, mime, "
                    "size, created_at FROM upload "
                    "WHERE reply_id=? ORDER BY id ASC",
                    (rid,),
                ).fetchall()
                uploads = [
                    Upload(id=u[0], reply_id=u[1], filename=u[2],
                           stored_path=Path(u[3]), mime=u[4], size=u[5],
                           created_at=u[6])
                    for u in upload_rows
                ]
                replies.append(
                    Reply(id=rid, thread_id=tid, body=body, author=r_author,
                          created_at=r_created, uploads=tuple(uploads))
                )
            threads.append(
                Thread(id=tid, artifact_id=aid, sub_path=sp, anchor=anchor,
                       resolved=bool(resolved), author=author,
                       created_at=created_at, bd_ticket=bd_ticket,
                       replies=tuple(replies))
            )
    finally:
        conn.close()
    return threads


def _upload_json(u: Upload) -> dict[str, object]:
    """Build the agent-facing JSON dict for one upload."""
    return {
        "id": u.id,
        "filename": u.filename,
        "stored_path": str(u.stored_path),
        "mime": u.mime,
        "size": u.size,
        "created_at": u.created_at,
        "created_at_iso": iso_utc(u.created_at),
    }


def _reply_json(r: Reply) -> dict[str, object]:
    """Build the agent-facing JSON dict for one reply."""
    return {
        "id": r.id,
        "body": r.body,
        "author": r.author,
        "created_at": r.created_at,
        "created_at_iso": iso_utc(r.created_at),
        "uploads": [_upload_json(u) for u in r.uploads],
    }


def _thread_json(t: Thread) -> dict[str, object]:
    """Build the agent-facing JSON dict for one thread (DESIGN.md section 8)."""
    return {
        "id": t.id,
        "sub_path": t.sub_path,
        "anchor_kind": t.anchor.kind,
        "anchor": t.anchor.data,
        "resolved": t.resolved,
        "author": t.author,
        "created_at": t.created_at,
        "created_at_iso": iso_utc(t.created_at),
        "bd_ticket": t.bd_ticket,
        "replies": [_reply_json(r) for r in t.replies],
    }


def feedback_dump(artifact_id: str) -> dict[str, object]:
    """Build the full agent-facing JSON payload for one artifact.

    Shape per DESIGN.md section 8: {artifact_id, pushes[], threads[], comments[]}
    where `threads` is canonical (anchor parsed, resolved bool, replies with
    uploads) and `comments` is the deprecated flattened page-level convenience.
    Used by cmd_feedback and reusable by tests.
    """
    conn = db_connect()
    try:
        idx_rows = conn.execute(
            "SELECT project, subdir, src_path, last_pushed FROM artifact_index "
            "WHERE artifact_id=?",
            (artifact_id,),
        ).fetchall()
        sub_path_rows = conn.execute(
            "SELECT DISTINCT sub_path FROM thread WHERE artifact_id=? "
            "ORDER BY sub_path ASC",
            (artifact_id,),
        ).fetchall()
    finally:
        conn.close()

    threads: list[Thread] = []
    for (sub_path,) in sub_path_rows:
        threads.extend(list_threads(artifact_id, sub_path))
    threads.sort(key=lambda t: (t.sub_path, t.created_at))

    comments_json: list[dict[str, object]] = []
    for t in threads:
        if t.anchor.kind != ANCHOR_PAGE:
            continue
        for r in t.replies:
            comments_json.append(
                {
                    "id": r.id,
                    "thread_id": t.id,
                    "sub_path": t.sub_path,
                    "body": r.body,
                    "author": r.author,
                    "created_at": r.created_at,
                    "created_at_iso": iso_utc(r.created_at),
                    "resolved": t.resolved,
                    "uploads": [_upload_json(u) for u in r.uploads],
                }
            )

    return {
        "artifact_id": artifact_id,
        "pushes": [
            {
                "project": r[0], "subdir": r[1], "src_path": r[2],
                "last_pushed": r[3], "last_pushed_iso": iso_utc(r[3]),
            }
            for r in idx_rows
        ],
        "threads": [_thread_json(t) for t in threads],
        "comments": comments_json,
    }


# ── optional bd mirror (flag-gated, never a hard dependency) ──────────


def bd_mirror_enabled() -> bool:
    """True only if setting['bd_mirror'] is on AND the `bd` CLI is on PATH.

    Absence of bd is a no-op, never an error. See DESIGN.md section 11.
    """
    return setting_get("bd_mirror") == "1" and shutil.which("bd") is not None


def _bd_beads_dir(artifact_id: str) -> str | None:
    """Resolve the ~/.beads-hub board dir for the project that pushed
    artifact_id, via `scripts/beads-hub.sh path <project>`. None on any
    failure (missing script, unknown project, non-zero exit)."""
    if not BEADS_HUB_SCRIPT.is_file():
        return None
    try:
        conn = db_connect()
        try:
            row = conn.execute(
                "SELECT project FROM artifact_index WHERE artifact_id=? "
                "ORDER BY last_pushed DESC LIMIT 1",
                (artifact_id,),
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        row = None
    if not row:
        return None
    try:
        proc = subprocess.run(
            [str(BEADS_HUB_SCRIPT), "path", row[0]],
            check=False, capture_output=True, text=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def _bd_run(beads_dir: str, args: list[str]) -> subprocess.CompletedProcess[str] | None:
    """Run a bd CLI invocation against beads_dir. None on any failure."""
    env = os.environ.copy()
    env["BEADS_DIR"] = beads_dir
    try:
        return subprocess.run(
            ["bd", *args], check=False, capture_output=True, text=True,
            timeout=15, env=env,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None


def _artifact_id_for_thread(thread_id: int) -> str | None:
    """Look up a thread's artifact_id. None if the thread is gone or on
    any db error (best-effort, used only by the bd mirror)."""
    try:
        conn = db_connect()
        try:
            row = conn.execute(
                "SELECT artifact_id FROM thread WHERE id=?", (thread_id,)
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return None
    return row[0] if row else None


def _artifact_id_for_bd_ticket(bd_ticket: str) -> str | None:
    """Look up the artifact_id of the thread carrying bd_ticket. None if
    absent or on any db error (best-effort, used only by the bd mirror)."""
    try:
        conn = db_connect()
        try:
            row = conn.execute(
                "SELECT artifact_id FROM thread WHERE bd_ticket=? LIMIT 1",
                (bd_ticket,),
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return None
    return row[0] if row else None


def mirror_thread_create(thread: Thread) -> str | None:
    """Best-effort create a bd ticket for a new thread. Returns ticket id/None.

    No-op returning None if bd_mirror_enabled() is False. Any subprocess
    failure logs a warning and returns None; never raises.
    """
    if not bd_mirror_enabled():
        return None
    # ponytail: assumes `bd create <title>` prints the new ticket id as the
    # first whitespace-separated token of stdout. Reasonable, unverified
    # against a live bd CLI (best-effort mirror only; never blocks a write).
    beads_dir = _bd_beads_dir(thread.artifact_id)
    if not beads_dir:
        return None
    first_body = thread.replies[0].body if thread.replies else ""
    title = (
        f"[review] {thread.artifact_id} {thread.sub_path} "
        f"({thread.anchor.kind}): {first_body[:80]}"
    )
    proc = _bd_run(beads_dir, ["create", title])
    if proc is None or proc.returncode != 0:
        log.warning("bd mirror create failed for thread %s", thread.id)
        return None
    tokens = proc.stdout.strip().split()
    return tokens[0] if tokens else None


def mirror_reply_add(bd_ticket: str, reply: Reply) -> None:
    """Best-effort append a reply as a bd comment. No-op if disabled/absent."""
    if not bd_mirror_enabled():
        return
    artifact_id = _artifact_id_for_thread(reply.thread_id)
    if not artifact_id:
        return
    beads_dir = _bd_beads_dir(artifact_id)
    if not beads_dir:
        return
    proc = _bd_run(beads_dir, ["comment", bd_ticket, reply.body])
    if proc is None or proc.returncode != 0:
        log.warning("bd mirror comment failed for ticket %s", bd_ticket)


def mirror_resolve_toggle(bd_ticket: str, resolved: bool) -> None:
    """Best-effort close/reopen the mirrored bd ticket. No-op if disabled."""
    if not bd_mirror_enabled():
        return
    artifact_id = _artifact_id_for_bd_ticket(bd_ticket)
    if not artifact_id:
        return
    beads_dir = _bd_beads_dir(artifact_id)
    if not beads_dir:
        return
    verb = "close" if resolved else "reopen"
    proc = _bd_run(beads_dir, [verb, bd_ticket])
    if proc is None or proc.returncode != 0:
        log.warning("bd mirror %s failed for ticket %s", verb, bd_ticket)


# ── index regeneration (preserved) ───────────────────────────────────


def _entry_meta(entry: Path) -> tuple[str, int, str]:
    """Return (kind, file_count, mtime_iso) for an entry."""
    if entry.is_symlink():
        target = os.readlink(entry)
        kind = f"symlink &rarr; {html.escape(target)}"
    elif entry.is_dir():
        kind = "copy (dir)"
    elif entry.is_file():
        kind = "copy (file)"
    else:
        kind = "unknown"

    count = 0
    try:
        for sub in entry.rglob("*"):
            if sub.is_file():
                count += 1
                if count > 9999:
                    break
    except OSError:
        count = -1

    try:
        mtime = datetime.fromtimestamp(entry.stat().st_mtime, tz=timezone.utc)
        mtime_iso = mtime.strftime("%Y-%m-%d %H:%M UTC")
    except OSError:
        mtime_iso = "?"

    return kind, count, mtime_iso


def _gallery_href(project: str, entry_name: str) -> str | None:
    """Return the /_/review gallery URL for an entry if it holds any image
    files, else None. Looks up the entry's artifact_id via artifact_index."""
    conn = db_connect()
    try:
        row = conn.execute(
            "SELECT artifact_id FROM artifact_index WHERE project=? AND subdir=?",
            (project, entry_name),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    entry = ROOT / project / entry_name
    has_image = any(
        p.is_file() and p.suffix.lower() in IMAGE_EXT for p in entry.rglob("*")
    )
    if not has_image:
        return None
    return f"/_/review?artifact={urllib.parse.quote(row[0])}"


def regenerate_index() -> None:
    """Rebuild /tmp/claude-artifacts/index.html tile grid. Atomic write.

    Preserved from legacy; tiles now link into the /_/review gallery route for
    image-bearing artifacts. See DESIGN.md section 5.
    """
    ensure_root()
    projects: list[tuple[str, list[Path]]] = []
    for child in sorted(ROOT.iterdir()):
        if child.name.startswith(".") or child.name == "index.html":
            continue
        if not child.is_dir():
            continue
        entries = [p for p in sorted(child.iterdir()) if not p.name.startswith(".")]
        projects.append((child.name, entries))

    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    port = read_port() or DEFAULT_PORT
    total_entries = sum(len(e) for _, e in projects)

    parts: list[str] = []
    parts.append("<!doctype html>")
    parts.append("<html lang='en'><head><meta charset='utf-8'>")
    parts.append("<title>review-serve</title>")
    parts.append(
        "<style>" + _THEME_ROOT_CSS + """
        .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:var(--space-3);padding:var(--space-6)}
        .tile{background:var(--bg-elevated);border:1px solid var(--border);border-radius:var(--radius-md);padding:var(--space-4);text-decoration:none;color:inherit;display:block}
        .tile:hover{border-color:var(--border-strong)}
        .tile h3{margin:0 0 4px;font-size:16px;color:var(--text-primary)}
        .tile .sub{font-size:13px;color:var(--text-muted);word-break:break-all}
        .tile .stats{font-size:12px;color:var(--text-muted);margin-top:8px}
        .tile .gallery-link{display:inline-block;margin-top:8px;font-size:13px}
        .empty{color:var(--text-muted);font-style:italic;padding:var(--space-6)}
        .meta{color:var(--text-muted);font-size:14px;padding:0 var(--space-6)}
        code{background:var(--bg-overlay);padding:1px 4px;border-radius:2px;font-family:var(--font-mono)}
        """ + "</style></head><body>"
    )
    parts.append("<header style='padding:var(--space-6) var(--space-6) 0'>"
                 "<h1>review-serve</h1></header>")
    parts.append(
        f"<div class='meta'>port <code>{port}</code> &middot; "
        f"{len(projects)} project(s) &middot; {total_entries} entry(ies) &middot; "
        f"regenerated {now}</div>"
    )

    if not projects:
        parts.append(
            "<div class='empty'>No artifacts pushed yet. Run "
            "<code>review-serve.py push --project NAME --src PATH</code>.</div>"
        )

    for project_name, entries in projects:
        parts.append(f"<h2 style='padding:0 var(--space-6)'>{html.escape(project_name)}</h2>")
        if not entries:
            parts.append("<div class='empty'>(empty)</div>")
            continue
        parts.append("<div class='grid'>")
        for entry in entries:
            kind, count, mtime_iso = _entry_meta(entry)
            href = f"/{html.escape(project_name)}/{html.escape(entry.name)}/"
            gallery = _gallery_href(project_name, entry.name)
            gallery_html = (
                f"<a class='gallery-link' href='{gallery}'>review gallery &rarr;</a>"
                if gallery else ""
            )
            parts.append(
                f"<a class='tile' href='{href}'>"
                f"<h3>{html.escape(entry.name)}</h3>"
                f"<div class='sub'>{kind}</div>"
                f"<div class='stats'>{count} file(s) &middot; {mtime_iso}</div>"
                f"{gallery_html}"
                "</a>"
            )
        parts.append("</div>")

    parts.append("</body></html>")
    atomic_write(INDEX_FILE, "\n".join(parts))


# ── review page templates (inlined, like the legacy widget) ───────────

# Vendored asset URLs the review pages load. Real files under ASSETS_ROOT,
# served by the daemon under /_/assets/.
OSD_SCRIPT_URL = "/_/assets/openseadragon/openseadragon.min.js"
ANNOTORIOUS_SCRIPT_URL = "/_/assets/annotorious/annotorious-openseadragon.min.js"
ANNOTORIOUS_CSS_URL = "/_/assets/annotorious/annotorious.min.css"

# Linear-theme design tokens (colors, type, spacing, radius) shared by every
# template via one :root{} block, baked into each *_TEMPLATE constant below
# at module load time (search-replace on the __THEME_CSS__ token, same
# mechanism the legacy widget used for __CSS__/__JS__ — avoids a .format()
# call colliding with the CSS/JS braces).
_THEME_ROOT_CSS = r"""
:root {
  --bg-base: #0d0e10;
  --bg-elevated: #18191a;
  --bg-overlay: #232428;
  --text-primary: #f2f3f3;
  --text-secondary: #d0d6e0;
  --text-muted: #8a8f98;
  --border: #23252a;
  --border-strong: #34343a;
  --accent: #5e6ad2;
  --accent-hover: #828fff;
  --status-resolved: #27a644;
  --status-unresolved: #d29922;
  --status-danger: #f85149;
  --font-ui: -apple-system, "Segoe UI", Roboto, system-ui, sans-serif;
  --font-mono: ui-monospace, "SF Mono", "Cascadia Code", "Consolas", monospace;
  --space-1: 4px; --space-2: 8px; --space-3: 12px; --space-4: 16px;
  --space-5: 24px; --space-6: 32px; --space-7: 48px;
  --radius-sm: 4px; --radius-md: 8px; --radius-lg: 12px; --radius-pill: 9999px;
}
* { box-sizing: border-box; }
body {
  background: var(--bg-base); color: var(--text-primary);
  font-family: var(--font-ui); margin: 0; line-height: 1.50; font-size: 16px;
}
h1 { font-size: 28px; font-weight: 600; line-height: 1.20; margin: 0 0 var(--space-4); }
h2 { font-size: 22px; font-weight: 500; line-height: 1.25; margin: 0 0 var(--space-3); }
a { color: var(--accent); }
a:hover { color: var(--accent-hover); }
.mono { font-family: var(--font-mono); font-size: 13px; }

.thread-card {
  background: var(--bg-elevated); border: 1px solid var(--border);
  border-radius: var(--radius-md); padding: var(--space-4);
  margin-bottom: var(--space-3); border-left: 3px solid var(--status-unresolved);
}
.thread-card.resolved { border-left-color: var(--status-resolved); opacity: 0.70; }
.thread-card.danger { border-left-color: var(--status-danger); }
.thread-badge {
  display: inline-block; font-size: 12px; padding: 2px 8px;
  border-radius: var(--radius-pill); font-weight: 500;
}
.thread-badge.unresolved { color: var(--status-unresolved); background: #d2992222; }
.thread-badge.resolved { color: var(--status-resolved); background: #27a64422; }
.thread-body { color: var(--text-primary); white-space: pre-wrap; word-break: break-word; }
.thread-meta { color: var(--text-muted); font-size: 14px; margin-bottom: var(--space-2); }
.empty { color: var(--text-muted); font-style: italic; }
button, .btn {
  background: var(--accent); color: #ffffff; border: none;
  border-radius: var(--radius-sm); padding: var(--space-2) var(--space-4);
  font-family: var(--font-ui); font-size: 14px; cursor: pointer;
}
button:hover, .btn:hover { background: var(--accent-hover); }
textarea, input[type=text] {
  background: var(--bg-overlay); color: var(--text-primary);
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  padding: var(--space-2); font-family: inherit; font-size: 14px; width: 100%;
  box-sizing: border-box;
}
textarea:focus, input:focus { border-color: var(--border-strong); outline: none; }
"""

_GALLERY_PAGE_RAW = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>__TITLE__</title>
<style>__THEME_CSS__
.gallery-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: var(--space-4); padding: var(--space-6);
}
.gallery-tile {
  display: block; background: var(--bg-elevated); border: 1px solid var(--border);
  border-radius: var(--radius-md); overflow: hidden; text-decoration: none;
  color: inherit; transition: border-color .12s;
}
.gallery-tile:hover { border-color: var(--border-strong); }
.gallery-tile img {
  width: 100%; height: 160px; object-fit: cover; display: block;
  background: var(--bg-overlay);
}
.gallery-caption {
  padding: var(--space-2) var(--space-3); font-size: 14px;
  color: var(--text-secondary); word-break: break-all;
}
header.page-header { padding: var(--space-6) var(--space-6) 0; }
</style>
</head>
<body>
<header class="page-header">
  <h1>Gallery</h1>
  <div class="thread-meta mono">__ARTIFACT__</div>
</header>
<div class="gallery-grid">__GRID__</div>
</body>
</html>
"""

GALLERY_PAGE_TEMPLATE = _GALLERY_PAGE_RAW.replace("__THEME_CSS__", _THEME_ROOT_CSS)


def render_gallery_page(artifact_id: str, sub_path: str) -> bytes:
    """Render the image gallery HTML for a staged artifact path.

    Lists IMAGE_EXT files under the staged root; each links to the viewer
    route. Any file/author string html.escape'd. Returns UTF-8 bytes.
    """
    loc = _artifact_location(artifact_id)
    tiles: list[str] = []
    if loc is not None:
        root, project, subdir = loc
        listing_dir = (root / sub_path).resolve()
        if listing_dir.is_relative_to(root) and listing_dir.is_dir():
            images = sorted(
                p for p in listing_dir.iterdir()
                if p.is_file() and p.suffix.lower() in IMAGE_EXT
            )
            for img in images:
                rel = img.relative_to(root).as_posix()
                view_href = (
                    f"/_/review?artifact={urllib.parse.quote(artifact_id)}"
                    f"&src={urllib.parse.quote(rel)}&view=image"
                )
                img_src = (
                    f"/{urllib.parse.quote(project)}/{urllib.parse.quote(subdir)}"
                    f"/{urllib.parse.quote(rel)}"
                )
                tiles.append(
                    f'<a class="gallery-tile" href="{view_href}">'
                    f'<img src="{img_src}" loading="lazy" '
                    f'alt="{html.escape(img.name)}">'
                    f'<div class="gallery-caption">{html.escape(img.name)}'
                    f'</div></a>'
                )

    grid = "".join(tiles) if tiles else '<p class="empty">no images found</p>'
    title = html.escape(f"{artifact_id} / {sub_path or '.'}")
    body = (
        GALLERY_PAGE_TEMPLATE
        .replace("__TITLE__", title)
        .replace("__ARTIFACT__", html.escape(artifact_id))
        .replace("__GRID__", grid)
    )
    return body.encode("utf-8")


# Viewer page: OpenSeadragon simple-image deep zoom + Annotorious OSD plugin
# pins. Pin creation posts an image_region thread; existing region threads
# round-trip through anno.setAnnotations() on load (DESIGN.md section 4.2/4.4).
#
# ponytail: pins use Annotorious's own rectangle shapes (recolored per
# resolved state via its formatter API) rather than custom circular numbered
# SVG badges hand-synced to OSD viewport transforms on every pan/zoom — that
# is a lot of hand-rolled canvas math for a stdlib-only, no-bundler skeleton
# fill. The ordinal number instead appears in the sidebar thread list, which
# also supports click-to-select-annotation. Resolved/unresolved recoloring
# and hover state match the Linear theme exactly; only the "numbered circular
# marker" shape itself is a lighter-weight stand-in.
_VIEWER_PAGE_RAW = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>__TITLE__</title>
<link rel="stylesheet" href="__ANNO_CSS_URL__">
<style>__THEME_CSS__
html, body { height: 100%; }
body { display: flex; }
#osd-viewer { flex: 1 1 auto; height: 100vh; background: var(--bg-base); }
#thread-panel-wrap {
  flex: 0 0 340px; height: 100vh; overflow-y: auto; background: var(--bg-elevated);
  border-left: 1px solid var(--border); padding: var(--space-4);
  box-sizing: border-box;
}
.a9s-annotation.a9s-unresolved .a9s-outer,
.a9s-annotation.a9s-unresolved .a9s-inner { stroke: var(--accent); }
.a9s-annotation.a9s-unresolved:hover .a9s-outer,
.a9s-annotation.a9s-unresolved:hover .a9s-inner { stroke: var(--accent-hover); }
.a9s-annotation.a9s-resolved .a9s-outer,
.a9s-annotation.a9s-resolved .a9s-inner { stroke: var(--status-resolved); opacity: .6; }
</style>
</head>
<body>
<div id="osd-viewer"></div>
<div id="thread-panel-wrap">
  <h2>Comments</h2>
  <div id="thread-panel"><p class="empty">loading...</p></div>
</div>
<script src="__OSD_URL__"></script>
<script src="__ANNO_JS_URL__"></script>
<script>
(function(){
  const IMAGE_URL = __IMAGE_URL__;
  const ARTIFACT_ID = __ARTIFACT_ID__;
  const SUB_PATH = __SUB_PATH__;
  let threadsById = {};

  const viewer = OpenSeadragon({
    id: 'osd-viewer',
    prefixUrl: '/_/assets/openseadragon/images/',
    tileSources: { type: 'image', url: IMAGE_URL },
    showNavigator: true,
  });
  const anno = OpenSeadragon.Annotorious(viewer, { drawingEnabled: true });
  anno.formatter = function(annotation){
    const t = threadsById[annotation.id];
    return { className: (t && t.resolved) ? 'a9s-resolved' : 'a9s-unresolved' };
  };

  function renderSidebar(threads){
    const panel = document.getElementById('thread-panel');
    panel.innerHTML = '';
    if (!threads.length){
      const p = document.createElement('p');
      p.className = 'empty';
      p.textContent = 'no region comments yet';
      panel.appendChild(p);
      return;
    }
    threads.forEach(function(t, i){
      const card = document.createElement('article');
      card.className = 'thread-card' + (t.resolved ? ' resolved' : '');
      const header = document.createElement('div');
      header.className = 'thread-meta';
      const num = document.createElement('span');
      num.className = 'thread-badge unresolved';
      num.textContent = '#' + (i + 1);
      header.appendChild(num);
      const badge = document.createElement('span');
      badge.className = 'thread-badge ' + (t.resolved ? 'resolved' : 'unresolved');
      badge.textContent = t.resolved ? 'Resolved' : 'Open';
      header.appendChild(badge);
      card.appendChild(header);
      for (const r of t.replies){
        const body = document.createElement('div');
        body.className = 'thread-body';
        body.textContent = r.body;
        card.appendChild(body);
      }
      const toggle = document.createElement('button');
      toggle.type = 'button';
      toggle.textContent = t.resolved ? 'reopen' : 'resolve';
      toggle.addEventListener('click', async function(ev){
        ev.stopPropagation();
        await fetch('/_/api/threads/' + t.id + '/resolve', {
          method: 'POST', body: JSON.stringify({resolved: !t.resolved}),
        });
        loadThreads();
      });
      card.appendChild(toggle);
      card.addEventListener('click', function(){
        anno.selectAnnotation('thread-' + t.id);
      });
      panel.appendChild(card);
    });
  }

  async function loadThreads(){
    const r = await fetch('/_/api/threads?artifact=' + encodeURIComponent(ARTIFACT_ID) +
      '&sub_path=' + encodeURIComponent(SUB_PATH));
    if (!r.ok) return;
    const data = await r.json();
    threadsById = {};
    const annotations = [];
    const regionThreads = [];
    for (const t of data.threads){
      if (t.anchor_kind !== 'image_region') continue;
      const id = 'thread-' + t.id;
      threadsById[id] = t;
      annotations.push({ id: id, type: 'Annotation', body: [],
        target: { selector: t.anchor.selector } });
      regionThreads.push(t);
    }
    anno.setAnnotations(annotations);
    renderSidebar(regionThreads);
  }

  anno.on('createAnnotation', async function(annotation){
    anno.removeAnnotation(annotation.id);
    const body = window.prompt('comment:');
    if (!body) return;
    const fd = new FormData();
    fd.append('artifact', ARTIFACT_ID);
    fd.append('sub_path', SUB_PATH);
    fd.append('anchor_kind', 'image_region');
    fd.append('anchor_data', JSON.stringify({ selector: annotation.target.selector }));
    fd.append('body', body);
    const r = await fetch('/_/api/threads', { method: 'POST', body: fd });
    if (r.ok) loadThreads();
  });

  viewer.addHandler('open', loadThreads);
})();
</script>
</body>
</html>
"""

VIEWER_PAGE_TEMPLATE = _VIEWER_PAGE_RAW.replace("__THEME_CSS__", _THEME_ROOT_CSS)


def render_viewer_page(artifact_id: str, src_rel: str) -> bytes:
    """Render the OpenSeadragon deep-zoom viewer HTML for one image.

    Declares the OSD tile source as a single full-res image (simple-image
    mode, no DZI build step; see DESIGN.md section 4.4). Loads Annotorious OSD
    plugin for pins. Thread data is fetched client-side and rendered via
    textContent. Returns UTF-8 bytes.
    """
    loc = _artifact_location(artifact_id)
    project, subdir = (loc[1], loc[2]) if loc else ("", "")
    image_url = (
        f"/{urllib.parse.quote(project)}/{urllib.parse.quote(subdir)}"
        f"/{urllib.parse.quote(src_rel)}"
    )
    title = html.escape(f"{artifact_id} / {src_rel}")
    body = (
        VIEWER_PAGE_TEMPLATE
        .replace("__TITLE__", title)
        .replace("__IMAGE_URL__", json.dumps(image_url))
        .replace("__ARTIFACT_ID__", json.dumps(artifact_id))
        .replace("__SUB_PATH__", json.dumps(src_rel))
        .replace("__OSD_URL__", OSD_SCRIPT_URL)
        .replace("__ANNO_JS_URL__", ANNOTORIOUS_SCRIPT_URL)
        .replace("__ANNO_CSS_URL__", ANNOTORIOUS_CSS_URL)
    )
    return body.encode("utf-8")


_CODE_PAGE_RAW = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>__TITLE__</title>
<style>__THEME_CSS__
.code-view { font-family: var(--font-mono); font-size: 13px; line-height: 1.5; padding: var(--space-4) 0; }
.code-line { display: flex; padding: 0 var(--space-4); cursor: pointer; border-left: 3px solid transparent; }
.code-line:hover { background: var(--bg-elevated); border-left-color: var(--accent); }
.code-line.has-thread { border-left-color: var(--status-unresolved); }
.code-gutter { width: 3.5em; text-align: right; color: var(--text-muted); user-select: none; margin-right: var(--space-3); }
.code-src { white-space: pre; color: var(--text-secondary); }
#code-thread-panel { padding: var(--space-4); max-width: 920px; }
#code-thread-panel textarea { min-height: 4rem; margin: var(--space-2) 0; }
</style>
</head>
<body>
<header style="padding: var(--space-6) var(--space-6) 0"><h1>__TITLE__</h1></header>
<div class="code-view">__CODE__</div>
<div id="code-thread-panel"></div>
<script>
(function(){
  const ARTIFACT_ID = __ARTIFACT_ID__;
  const SUB_PATH = __SUB_PATH__;
  let byLine = {};

  function fmtTime(ts){
    return new Date(ts * 1000).toISOString().replace('T',' ').slice(0,16) + ' UTC';
  }

  function renderThreadCard(t){
    const card = document.createElement('article');
    card.className = 'thread-card' + (t.resolved ? ' resolved' : '');
    const header = document.createElement('div');
    header.className = 'thread-meta';
    const badge = document.createElement('span');
    badge.className = 'thread-badge ' + (t.resolved ? 'resolved' : 'unresolved');
    badge.textContent = t.resolved ? 'Resolved' : 'Open';
    header.appendChild(badge);
    card.appendChild(header);
    for (const r of t.replies){
      const body = document.createElement('div');
      body.className = 'thread-body';
      const meta = document.createElement('div');
      meta.className = 'thread-meta';
      meta.textContent = (r.author || 'anonymous') + ' · ' + fmtTime(r.created_at);
      body.appendChild(meta);
      const text = document.createElement('div');
      text.textContent = r.body;
      body.appendChild(text);
      card.appendChild(body);
    }
    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.textContent = t.resolved ? 'reopen' : 'resolve';
    toggle.addEventListener('click', async function(){
      await fetch('/_/api/threads/' + t.id + '/resolve', {
        method: 'POST', body: JSON.stringify({resolved: !t.resolved}),
      });
      loadThreads();
    });
    card.appendChild(toggle);
    return card;
  }

  function openPanel(line, threads){
    const panel = document.getElementById('code-thread-panel');
    panel.innerHTML = '';
    const h = document.createElement('h2');
    h.textContent = 'Line ' + line;
    panel.appendChild(h);
    for (const t of threads) panel.appendChild(renderThreadCard(t));

    const form = document.createElement('form');
    const ta = document.createElement('textarea');
    ta.placeholder = 'new comment on line ' + line;
    ta.required = true;
    form.appendChild(ta);
    const btn = document.createElement('button');
    btn.type = 'submit';
    btn.textContent = 'post';
    form.appendChild(btn);
    form.addEventListener('submit', async function(e){
      e.preventDefault();
      const fd = new FormData();
      fd.append('artifact', ARTIFACT_ID);
      fd.append('sub_path', SUB_PATH);
      fd.append('anchor_kind', 'code_line');
      fd.append('anchor_data', JSON.stringify({ line: line }));
      fd.append('body', ta.value);
      await fetch('/_/api/threads', { method: 'POST', body: fd });
      loadThreads();
    });
    panel.appendChild(form);
    panel.scrollIntoView({ behavior: 'smooth' });
  }

  async function loadThreads(){
    const r = await fetch('/_/api/threads?artifact=' + encodeURIComponent(ARTIFACT_ID) +
      '&sub_path=' + encodeURIComponent(SUB_PATH));
    if (!r.ok) return;
    const data = await r.json();
    byLine = {};
    document.querySelectorAll('.code-line').forEach(function(el){
      el.classList.remove('has-thread');
    });
    for (const t of data.threads){
      if (t.anchor_kind !== 'code_line') continue;
      const line = t.anchor.line;
      if (!byLine[line]) byLine[line] = [];
      byLine[line].push(t);
      const el = document.getElementById('L' + line);
      if (el) el.classList.add('has-thread');
    }
  }

  document.querySelectorAll('.code-line').forEach(function(el){
    el.addEventListener('click', function(){
      const line = parseInt(el.dataset.line, 10);
      openPanel(line, byLine[line] || []);
    });
  });

  loadThreads();
})();
</script>
</body>
</html>
"""

CODE_PAGE_TEMPLATE = _CODE_PAGE_RAW.replace("__THEME_CSS__", _THEME_ROOT_CSS)


def render_code_page(artifact_id: str, src_rel: str) -> bytes:
    """Render the per-line code view HTML for one served text file.

    Each line gets an anchor; clicking a line opens a code_line thread. Line
    contents html.escape'd. Threads fetched client-side, rendered via
    textContent. Returns UTF-8 bytes.
    """
    path = staged_source_path(artifact_id, src_rel)
    try:
        text = path.read_text(encoding="utf-8", errors="replace") if path else ""
    except OSError:
        text = ""
    lines = text.splitlines()

    rows = [
        f'<div class="code-line" data-line="{i}" id="L{i}">'
        f'<span class="code-gutter">{i}</span>'
        f'<span class="code-src">{html.escape(line)}</span></div>'
        for i, line in enumerate(lines, start=1)
    ]
    code_html = "\n".join(rows) if rows else '<p class="empty">(empty file)</p>'

    title = html.escape(f"{artifact_id} / {src_rel}")
    body = (
        CODE_PAGE_TEMPLATE
        .replace("__TITLE__", title)
        .replace("__CODE__", code_html)
        .replace("__ARTIFACT_ID__", json.dumps(artifact_id))
        .replace("__SUB_PATH__", json.dumps(src_rel))
    )
    return body.encode("utf-8")


# Page-level comment widget, injected before </body> of any served HTML page
# (send_head splices this in — see _make_handler). Upgraded from the legacy
# flat-comment widget to the thread model: shows only anchor_kind='page'
# threads (image/code threads belong to their own /_/review viewer pages),
# supports resolve/reopen. Every user string goes through textContent.
_PAGE_WIDGET_JS_RAW = r"""
(function(){
  const path = window.location.pathname;
  const root = document.getElementById('review-serve-widget');
  if (!root) return;
  const headers = {'Accept': 'application/json'};

  function fmtTime(ts){
    return new Date(ts * 1000).toISOString().replace('T',' ').slice(0,16) + ' UTC';
  }

  async function loadSettings(){
    try {
      const r = await fetch('/_/api/settings', {headers});
      if (!r.ok) return;
      const s = await r.json();
      if (s && typeof s.author === 'string' && s.author){
        const inp = root.querySelector('input[name=author]');
        if (inp && !inp.value) inp.value = s.author;
      }
    } catch (e) { /* ignore */ }
  }

  function renderThread(t){
    const card = document.createElement('article');
    card.className = 'thread-card' + (t.resolved ? ' resolved' : '');
    const header = document.createElement('div');
    header.className = 'thread-meta';
    const badge = document.createElement('span');
    badge.className = 'thread-badge ' + (t.resolved ? 'resolved' : 'unresolved');
    badge.textContent = t.resolved ? 'Resolved' : 'Open';
    header.appendChild(badge);
    header.appendChild(document.createTextNode(' '));
    const authorSpan = document.createElement('span');
    authorSpan.textContent = t.author || 'anonymous';
    header.appendChild(authorSpan);
    card.appendChild(header);

    for (const r of t.replies){
      const reply = document.createElement('div');
      reply.className = 'thread-body';
      const meta = document.createElement('div');
      meta.className = 'thread-meta';
      meta.textContent = (r.author || 'anonymous') + ' · ' + fmtTime(r.created_at);
      reply.appendChild(meta);
      const bodyEl = document.createElement('div');
      bodyEl.textContent = r.body;
      reply.appendChild(bodyEl);
      if (r.uploads && r.uploads.length){
        const ul = document.createElement('ul');
        for (const u of r.uploads){
          const li = document.createElement('li');
          const a = document.createElement('a');
          a.href = '/_/api/uploads/' + u.id;
          a.textContent = u.filename + ' (' + Math.round(u.size/1024) + ' KB)';
          a.target = '_blank';
          li.appendChild(a);
          ul.appendChild(li);
        }
        reply.appendChild(ul);
      }
      card.appendChild(reply);
    }

    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.textContent = t.resolved ? 'reopen' : 'resolve';
    toggle.addEventListener('click', async () => {
      await fetch('/_/api/threads/' + t.id + '/resolve', {
        method: 'POST', body: JSON.stringify({resolved: !t.resolved}),
      });
      load();
    });
    card.appendChild(toggle);
    return card;
  }

  async function load(){
    const r = await fetch('/_/api/threads?url=' + encodeURIComponent(path), {headers});
    if (!r.ok){
      root.querySelector('.rs-list').textContent = 'failed to load: ' + r.status;
      return;
    }
    const data = await r.json();
    root.querySelector('.rs-aid').textContent = data.artifact_id || '';
    const list = root.querySelector('.rs-list');
    list.innerHTML = '';
    const pageThreads = data.threads.filter(t => t.anchor_kind === 'page');
    if (!pageThreads.length){
      const p = document.createElement('p');
      p.className = 'empty';
      p.textContent = 'no comments yet';
      list.appendChild(p);
      return;
    }
    for (const t of pageThreads) list.appendChild(renderThread(t));
  }

  const form = root.querySelector('form');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const status = root.querySelector('.rs-status');
    status.textContent = 'posting...';
    const fd = new FormData(form);
    fd.append('url', path);
    fd.append('anchor_kind', 'page');
    try {
      const r = await fetch('/_/api/threads', {method: 'POST', body: fd});
      if (!r.ok){
        const t = await r.text();
        status.textContent = 'error: ' + r.status + ' ' + t.slice(0, 200);
        return;
      }
      status.textContent = 'posted.';
      form.reset();
      load();
    } catch (err){
      status.textContent = 'network error: ' + err;
    }
  });

  loadSettings();
  load();
})();
"""

_PAGE_WIDGET_CSS_RAW = r"""
#review-serve-widget {
  /* Theme tokens scoped to this widget, not :root — the widget is injected
     into arbitrary pushed HTML that never loads _THEME_ROOT_CSS, so it must
     carry its own copy of the custom properties it uses. */
  --bg-base: #0d0e10; --bg-elevated: #18191a; --bg-overlay: #232428;
  --text-primary: #f2f3f3; --text-secondary: #d0d6e0; --text-muted: #8a8f98;
  --border: #23252a; --border-strong: #34343a;
  --accent: #5e6ad2; --accent-hover: #828fff;
  --status-resolved: #27a644; --status-unresolved: #d29922; --status-danger: #f85149;
  --font-ui: -apple-system, "Segoe UI", Roboto, system-ui, sans-serif;
  --font-mono: ui-monospace, "SF Mono", "Cascadia Code", "Consolas", monospace;
  --space-1: 4px; --space-2: 8px; --space-3: 12px; --space-4: 16px;
  --space-5: 24px; --space-6: 32px; --space-7: 48px;
  --radius-sm: 4px; --radius-md: 8px; --radius-lg: 12px; --radius-pill: 9999px;

  font-family: var(--font-ui); background: var(--bg-base); color: var(--text-primary);
  padding: var(--space-6); border-top: 4px solid var(--border-strong);
  margin-top: var(--space-6);
}
#review-serve-widget .thread-card {
  background: var(--bg-elevated); border: 1px solid var(--border);
  border-radius: var(--radius-md); padding: var(--space-4);
  margin-bottom: var(--space-3); border-left: 3px solid var(--status-unresolved);
}
#review-serve-widget .thread-card.resolved {
  border-left-color: var(--status-resolved); opacity: 0.70;
}
#review-serve-widget .thread-badge {
  display: inline-block; font-size: 12px; padding: 2px 8px;
  border-radius: var(--radius-pill); font-weight: 500;
}
#review-serve-widget .thread-badge.unresolved { color: var(--status-unresolved); background: #d2992222; }
#review-serve-widget .thread-badge.resolved { color: var(--status-resolved); background: #27a64422; }
#review-serve-widget .thread-body { color: var(--text-primary); white-space: pre-wrap; word-break: break-word; }
#review-serve-widget .thread-meta { color: var(--text-muted); font-size: 14px; margin-bottom: var(--space-2); }
#review-serve-widget .empty { color: var(--text-muted); font-style: italic; }
#review-serve-widget button {
  background: var(--accent); color: #ffffff; border: none;
  border-radius: var(--radius-sm); padding: var(--space-2) var(--space-4);
  font-family: var(--font-ui); font-size: 14px; cursor: pointer;
}
#review-serve-widget button:hover { background: var(--accent-hover); }
#review-serve-widget textarea, #review-serve-widget input[type=text] {
  background: var(--bg-overlay); color: var(--text-primary);
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  padding: var(--space-2); font-family: inherit; font-size: 14px; width: 100%;
  box-sizing: border-box;
}
#review-serve-widget textarea:focus, #review-serve-widget input:focus {
  border-color: var(--border-strong); outline: none;
}
#review-serve-widget h2 { margin: 0 0 4px; }
#review-serve-widget .rs-aid { font-family: var(--font-mono); color: var(--text-muted); font-size: 13px; }
#review-serve-widget .rs-list { margin: var(--space-4) 0; max-width: 920px; }
#review-serve-widget form {
  background: var(--bg-elevated); border: 1px solid var(--border);
  border-radius: var(--radius-md); padding: var(--space-4); max-width: 920px;
}
#review-serve-widget label { display: block; font-size: 13px; color: var(--text-muted); margin-bottom: 4px; }
#review-serve-widget textarea { min-height: 5rem; margin-bottom: var(--space-3); }
#review-serve-widget input[type=file] { color: var(--text-muted); font-size: 13px; }
#review-serve-widget .rs-status { margin-top: var(--space-2); font-size: 13px; color: var(--text-muted); }
"""

_PAGE_WIDGET_BLOCK_RAW = """
<style>__CSS__</style>
<section id="review-serve-widget">
  <h2>Feedback</h2>
  <div>artifact: <span class="rs-aid">(loading)</span></div>
  <div class="rs-list"><p class="empty">loading...</p></div>
  <form enctype="multipart/form-data">
    <label>name (optional)</label>
    <input type="text" name="author" maxlength="80" placeholder="anonymous">
    <label>comment</label>
    <textarea name="body" required maxlength="20000"
              placeholder="your feedback..."></textarea>
    <label>attachments (optional, multiple)</label>
    <input type="file" name="files" multiple>
    <button type="submit">post comment</button>
    <div class="rs-status"></div>
  </form>
</section>
<script>__JS__</script>
"""

PAGE_COMMENT_WIDGET = (
    _PAGE_WIDGET_BLOCK_RAW.replace("__CSS__", _PAGE_WIDGET_CSS_RAW)
    .replace("__JS__", _PAGE_WIDGET_JS_RAW)
)


def injected_page_widget() -> bytes:
    """Return the page-level thread widget spliced before </body>.

    Upgraded from the legacy flat-comment widget to the thread model (page
    anchor). All user strings rendered via textContent. Returns UTF-8 bytes.
    """
    return PAGE_COMMENT_WIDGET.encode("utf-8")


# ── http server ───────────────────────────────────────────────────────


def _make_handler() -> type[http.server.SimpleHTTPRequestHandler]:
    """Build the request handler class bound to the staging ROOT.

    Routing (see DESIGN.md section 9). do_GET dispatch order, most specific
    first, so the reserved /_/ namespace always wins over static files:
      GET  /_/assets/<rel>                 -> vendored OSD/Annotorious file
      GET  /_/api/threads                  -> _api_threads_get
      GET  /_/api/uploads/<id>             -> _api_upload_get (preserved)
      GET  /_/api/settings                 -> _api_settings_get (preserved)
      GET  /_/api/comments                 -> legacy read shim (page threads)
      GET  /_/review                       -> gallery|image|code by query params
      *                                    -> static file + page widget inject
    do_POST dispatch:
      POST /_/api/threads                  -> _api_thread_create
      POST /_/api/threads/<id>/replies     -> _api_reply_create
      POST /_/api/threads/<id>/resolve     -> _api_resolve_toggle
      POST /_/api/comments                 -> legacy write shim (page thread)
    """
    root_str = str(ROOT)
    assets_root = ASSETS_ROOT.resolve()

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a: object, **kw: object) -> None:
            super().__init__(*a, directory=root_str, **kw)  # type: ignore[arg-type]  # stdlib base ctor accepts a directory kwarg the typeshed stub for *a/**kw does not model precisely here

        def log_message(self, fmt: str, *args: object) -> None:
            log.info("%s - %s", self.address_string(), fmt % args)

        # ── routing ──────────────────────────────────────────────────

        def do_GET(self) -> None:  # noqa: N802 (stdlib signature)
            url = urllib.parse.urlsplit(self.path)
            if url.path.startswith("/_/assets/"):
                self._serve_asset(url.path[len("/_/assets/"):])
                return
            if url.path == "/_/api/threads":
                self._api_threads_get(url)
                return
            if url.path.startswith("/_/api/uploads/"):
                self._api_upload_get(url.path[len("/_/api/uploads/"):])
                return
            if url.path == "/_/api/settings":
                self._api_settings_get()
                return
            if url.path == "/_/api/comments":
                self._api_comments_get(url)
                return
            if url.path == "/_/review":
                self._serve_review(url)
                return
            super().do_GET()

        def do_POST(self) -> None:  # noqa: N802
            url = urllib.parse.urlsplit(self.path)
            if url.path == "/_/api/threads":
                self._api_thread_create()
                return
            m = re.match(r"^/_/api/threads/(\d+)/replies$", url.path)
            if m:
                self._api_reply_create(int(m.group(1)))
                return
            m = re.match(r"^/_/api/threads/(\d+)/resolve$", url.path)
            if m:
                self._api_resolve_toggle(int(m.group(1)))
                return
            if url.path == "/_/api/comments":
                self._api_comments_post()
                return
            self.send_error(404, "not found")

        # ── static assets ────────────────────────────────────────────

        def _serve_asset(self, rel: str) -> None:
            """Serve a vendored file from ASSETS_ROOT under /_/assets/.

            Traversal-guarded (normalize + is_relative_to ASSETS_ROOT). 404 on
            escape or missing file. Sets mime from the extension.
            """
            rel = urllib.parse.unquote(rel)
            target = (ASSETS_ROOT / rel).resolve()
            if not target.is_relative_to(assets_root) or not target.is_file():
                self.send_error(404, "not found")
                return
            mime, _ = mimetypes.guess_type(str(target))
            mime = mime or "application/octet-stream"
            data = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            super().end_headers()
            self.wfile.write(data)

        # ── review page routes ───────────────────────────────────────

        def _serve_review(self, url: urllib.parse.SplitResult) -> None:
            """Dispatch /_/review by query params to gallery/image/code render."""
            params = urllib.parse.parse_qs(url.query)
            artifact_id = (params.get("artifact") or [""])[0]
            if not artifact_id:
                self.send_error(400, "artifact required")
                return
            view = (params.get("view") or [""])[0]
            src = (params.get("src") or [""])[0]
            path_param = (params.get("path") or [""])[0]

            if view in ("image", "code"):
                if staged_source_path(artifact_id, src) is None:
                    self.send_error(404, "not found")
                    return
                body = (
                    render_viewer_page(artifact_id, src) if view == "image"
                    else render_code_page(artifact_id, src)
                )
            else:
                body = render_gallery_page(artifact_id, path_param)

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            super().end_headers()
            self.wfile.write(body)

        # ── HTML injection (page-level widget, preserved mechanism) ──

        def send_head(self):  # type: ignore[override]  # stdlib returns BinaryIO|None
            """Splice injected_page_widget() into text/html responses.

            Preserved from legacy: keys off the actually-sent Content-Type,
            suppresses Content-Length on text/html (close-framing).
            """
            self._sent_ctype = ""
            f = super().send_head()
            if f is None:
                return None
            if not self._sent_ctype.startswith("text/html"):
                return f
            try:
                body = f.read()
            finally:
                f.close()
            inject = injected_page_widget()
            idx = body.lower().rfind(b"</body>")
            merged = body + inject if idx == -1 else body[:idx] + inject + body[idx:]
            return io.BytesIO(merged)

        def send_header(self, keyword: str, value: str) -> None:  # type: ignore[override]  # legacy content-length suppression
            lk = keyword.lower()
            if lk == "content-type":
                self._sent_ctype = value.lower()
            if lk == "content-length":
                if getattr(self, "_sent_ctype", "").startswith("text/html"):
                    return
            super().send_header(keyword, value)

        # ── API: threads ─────────────────────────────────────────────

        def _resolve_target(
            self, params: dict[str, list[str]]
        ) -> tuple[str | None, str]:
            """Resolve (artifact_id, sub_path) from query params: either
            ?artifact=&sub_path= directly, or ?url= via resolve_artifact_id."""
            if "artifact" in params:
                return params["artifact"][0], (params.get("sub_path") or [""])[0]
            if "url" in params:
                return resolve_artifact_id(params["url"][0])
            return None, ""

        def _resolve_target_fields(
            self, fields: dict[str, str]
        ) -> tuple[str | None, str]:
            """Same as _resolve_target but reading multipart form fields."""
            if fields.get("artifact"):
                return fields["artifact"], fields.get("sub_path", "")
            if fields.get("url"):
                return resolve_artifact_id(fields["url"])
            return None, ""

        def _api_threads_get(self, url: urllib.parse.SplitResult) -> None:
            """GET /_/api/threads?url=|artifact= -> list_threads as JSON."""
            params = urllib.parse.parse_qs(url.query)
            artifact_id, sub_path = self._resolve_target(params)
            if artifact_id is None:
                self._send_json(404, {"error": "could not resolve artifact"})
                return
            try:
                threads = list_threads(artifact_id, sub_path)
            except sqlite3.Error as exc:
                self._send_json(500, {"error": f"db: {exc}"})
                return
            self._send_json(
                200,
                {
                    "artifact_id": artifact_id,
                    "sub_path": sub_path,
                    "threads": [_thread_json(t) for t in threads],
                },
            )

        def _validate_upload_files(self, files: list[dict[str, object]]) -> bool:
            """Validate each file's extension + size cap.

            Sends the error response and returns False on the first
            violation; True if all files pass.
            """
            for f in files:
                raw_name = str(f.get("filename") or "unnamed")
                safe = safe_upload_filename(raw_name)
                ok, why = upload_ext_ok(safe)
                if not ok:
                    self._send_json(400, {"error": f"{raw_name}: {why}"})
                    return False
                size = len(f.get("data", b""))  # type: ignore[arg-type]  # multipart payload is always bytes
                if size > MAX_UPLOAD_BYTES:
                    self._send_json(
                        413,
                        {"error": f"{raw_name}: {size}B exceeds {MAX_UPLOAD_BYTES}B cap"},
                    )
                    return False
            return True

        def _api_thread_create(self) -> None:
            """POST /_/api/threads (multipart) -> create_thread.

            Reads + caps the multipart body, resolves artifact/sub_path,
            validates the anchor (validate_anchor), validates uploads, then
            create_thread. 201 {thread_id, reply_id, ...}. 400 on bad anchor
            or missing body.
            """
            ctype = self.headers.get("Content-Type", "")
            if not ctype.startswith("multipart/form-data"):
                self._send_json(400, {"error": "expected multipart/form-data"})
                return
            raw = self._read_capped_body()
            if raw is None:
                return
            try:
                fields, files = parse_multipart_form(ctype, raw)
            except ValueError as exc:
                self._send_json(400, {"error": f"bad multipart: {exc}"})
                return

            artifact_id, sub_path = self._resolve_target_fields(fields)
            if artifact_id is None:
                self._send_json(400, {"error": "url or artifact required"})
                return

            text_body = (fields.get("body") or "").strip()
            if not text_body:
                self._send_json(400, {"error": "body required"})
                return
            if len(text_body) > MAX_BODY_CHARS:
                self._send_json(
                    400, {"error": f"body too long (>{MAX_BODY_CHARS} chars)"}
                )
                return
            author = (fields.get("author") or "").strip() or None

            anchor_kind = fields.get("anchor_kind", ANCHOR_PAGE)
            try:
                anchor = validate_anchor(anchor_kind, fields.get("anchor_data"))
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
                return

            if not self._validate_upload_files(files):
                return

            try:
                thread_id, reply_id = create_thread(
                    artifact_id, sub_path, anchor, text_body, author, files
                )
            except (sqlite3.Error, OSError) as exc:
                self._send_json(500, {"error": f"create failed: {exc}"})
                return

            self._send_json(
                201,
                {
                    "thread_id": thread_id,
                    "reply_id": reply_id,
                    "artifact_id": artifact_id,
                    "sub_path": sub_path,
                    "anchor_kind": anchor.kind,
                    "uploads": uploads_for_reply(reply_id),
                },
            )

        def _api_reply_create(self, thread_id: int) -> None:
            """POST /_/api/threads/<id>/replies (multipart) -> add_reply."""
            ctype = self.headers.get("Content-Type", "")
            if not ctype.startswith("multipart/form-data"):
                self._send_json(400, {"error": "expected multipart/form-data"})
                return
            raw = self._read_capped_body()
            if raw is None:
                return
            try:
                fields, files = parse_multipart_form(ctype, raw)
            except ValueError as exc:
                self._send_json(400, {"error": f"bad multipart: {exc}"})
                return

            text_body = (fields.get("body") or "").strip()
            if not text_body:
                self._send_json(400, {"error": "body required"})
                return
            if len(text_body) > MAX_BODY_CHARS:
                self._send_json(
                    400, {"error": f"body too long (>{MAX_BODY_CHARS} chars)"}
                )
                return
            author = (fields.get("author") or "").strip() or None

            if not self._validate_upload_files(files):
                return

            try:
                reply_id = add_reply(thread_id, text_body, author, files)
            except KeyError:
                self._send_json(404, {"error": f"thread {thread_id} not found"})
                return
            except (sqlite3.Error, OSError) as exc:
                self._send_json(500, {"error": f"reply failed: {exc}"})
                return

            self._send_json(
                201,
                {
                    "reply_id": reply_id,
                    "thread_id": thread_id,
                    "uploads": uploads_for_reply(reply_id),
                },
            )

        def _api_resolve_toggle(self, thread_id: int) -> None:
            """POST /_/api/threads/<id>/resolve (JSON) -> set_resolved.

            Body {resolved: bool} sets; empty body toggles. 200 {id, resolved}.
            """
            raw = self._read_capped_body()
            if raw is None:
                return
            resolved: bool | None = None
            if raw.strip():
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    self._send_json(400, {"error": "body must be JSON"})
                    return
                if isinstance(payload, dict) and "resolved" in payload:
                    resolved = bool(payload["resolved"])
            try:
                new_state = set_resolved(thread_id, resolved)
            except KeyError:
                self._send_json(404, {"error": f"thread {thread_id} not found"})
                return
            self._send_json(200, {"id": thread_id, "resolved": new_state})

        # ── API: uploads + settings (preserved) ──────────────────────

        def _api_upload_get(self, suffix: str) -> None:
            """GET /_/api/uploads/<id> -> upload bytes. Preserved from legacy."""
            try:
                upload_id = int(suffix.split("/", 1)[0])
            except ValueError:
                self.send_error(404, "not found")
                return
            try:
                conn = db_connect()
                try:
                    row = conn.execute(
                        "SELECT filename, stored_path, mime, size "
                        "FROM upload WHERE id=?",
                        (upload_id,),
                    ).fetchone()
                finally:
                    conn.close()
            except sqlite3.Error as exc:
                self.send_error(500, f"db: {exc}")
                return
            if not row:
                self.send_error(404, "not found")
                return
            filename, stored_path, mime, size = row
            path = Path(stored_path)
            if not path.is_file():
                self.send_error(410, "upload file missing on disk")
                return
            inline_mimes = {
                "image/png", "image/jpeg", "image/webp", "image/gif",
                "image/bmp", "application/pdf", "text/plain",
            }
            mime_used = mime or "application/octet-stream"
            disposition = "inline" if mime_used in inline_mimes else "attachment"
            self.send_response(200)
            self.send_header("Content-Type", mime_used)
            self.send_header("Content-Length", str(size))
            self.send_header("X-Content-Type-Options", "nosniff")
            safe_disp_name = filename.replace('"', '')
            self.send_header(
                "Content-Disposition",
                f'{disposition}; filename="{safe_disp_name}"',
            )
            super().end_headers()
            with path.open("rb") as fh:
                shutil.copyfileobj(fh, self.wfile)

        def _api_settings_get(self) -> None:
            """GET /_/api/settings -> {key: value}. Preserved from legacy."""
            try:
                conn = db_connect()
                try:
                    rows = conn.execute("SELECT key, value FROM setting").fetchall()
                finally:
                    conn.close()
            except sqlite3.Error as exc:
                self._send_json(500, {"error": f"db: {exc}"})
                return
            self._send_json(200, {k: v for k, v in rows})

        # ── API: legacy comment shims ────────────────────────────────

        def _api_comments_get(self, url: urllib.parse.SplitResult) -> None:
            """GET /_/api/comments -> page-level threads flattened to old shape."""
            params = urllib.parse.parse_qs(url.query)
            artifact_id, sub_path = self._resolve_target(params)
            if artifact_id is None:
                self._send_json(404, {"error": "could not resolve artifact"})
                return
            try:
                threads = list_threads(artifact_id, sub_path)
            except sqlite3.Error as exc:
                self._send_json(500, {"error": f"db: {exc}"})
                return
            comments: list[dict[str, object]] = []
            for t in threads:
                if t.anchor.kind != ANCHOR_PAGE:
                    continue
                for r in t.replies:
                    comments.append(
                        {
                            "id": r.id,
                            "body": r.body,
                            "author": r.author,
                            "created_at": r.created_at,
                            "created_at_iso": iso_utc(r.created_at),
                            "uploads": [_upload_json(u) for u in r.uploads],
                        }
                    )
            self._send_json(
                200,
                {"artifact_id": artifact_id, "sub_path": sub_path, "comments": comments},
            )

        def _api_comments_post(self) -> None:
            """POST /_/api/comments -> create a page-level thread (compat)."""
            ctype = self.headers.get("Content-Type", "")
            if not ctype.startswith("multipart/form-data"):
                self._send_json(400, {"error": "expected multipart/form-data"})
                return
            raw = self._read_capped_body()
            if raw is None:
                return
            try:
                fields, files = parse_multipart_form(ctype, raw)
            except ValueError as exc:
                self._send_json(400, {"error": f"bad multipart: {exc}"})
                return

            artifact_id, sub_path = self._resolve_target_fields(fields)
            if artifact_id is None:
                self._send_json(400, {"error": "url or artifact required"})
                return
            text_body = (fields.get("body") or "").strip()
            if not text_body:
                self._send_json(400, {"error": "body required"})
                return
            if len(text_body) > MAX_BODY_CHARS:
                self._send_json(
                    400, {"error": f"body too long (>{MAX_BODY_CHARS} chars)"}
                )
                return
            author = (fields.get("author") or "").strip() or None

            if not self._validate_upload_files(files):
                return

            try:
                thread_id, reply_id = create_thread(
                    artifact_id, sub_path, Anchor(kind=ANCHOR_PAGE, data=None),
                    text_body, author, files,
                )
            except (sqlite3.Error, OSError) as exc:
                self._send_json(500, {"error": f"db: {exc}"})
                return

            self._send_json(
                201,
                {"id": reply_id, "thread_id": thread_id,
                 "artifact_id": artifact_id, "sub_path": sub_path},
            )

        # ── helpers ──────────────────────────────────────────────────

        def _read_capped_body(self) -> bytes | None:
            """Read the request body enforcing MAX_REQUEST_BYTES.

            Returns None (after sending the appropriate 4xx) on missing/oversize
            Content-Length. Content-Length: 0 is valid (e.g. an empty-body
            resolve-toggle POST). Preserved from legacy comment POST, extended
            to allow the zero-length case the new resolve endpoint needs.
            """
            raw_clen = self.headers.get("Content-Length")
            if raw_clen is None:
                self._send_json(411, {"error": "Content-Length required"})
                return None
            try:
                clen = int(raw_clen)
            except ValueError:
                self._send_json(411, {"error": "Content-Length required"})
                return None
            if clen < 0:
                self._send_json(411, {"error": "Content-Length required"})
                return None
            if clen > MAX_REQUEST_BYTES:
                self._send_json(
                    413,
                    {"error": f"request body {clen}B exceeds {MAX_REQUEST_BYTES}B"},
                )
                return None
            try:
                return self.rfile.read(clen)
            except OSError as exc:
                self._send_json(400, {"error": f"read failed: {exc}"})
                return None

        def _send_json(self, code: int, payload: dict[str, object]) -> None:
            """Send a JSON response. Preserved from legacy."""
            body = json.dumps(payload, default=str).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            super().end_headers()
            self.wfile.write(body)

    return Handler


# ── daemon plumbing (preserved from legacy) ───────────────────────────


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def read_pid() -> int | None:
    """Return the live daemon pid, or None if stale/absent. Preserved."""
    if not PID_FILE.exists():
        return None
    try:
        pid = int(PID_FILE.read_text().strip())
    except (ValueError, OSError):
        return None
    try:
        os.kill(pid, 0)
    except OSError as exc:
        if exc.errno in (errno.ESRCH, errno.EPERM):
            return None
        raise
    return pid


def read_port() -> int | None:
    """Return the active port if recorded, else None. Preserved."""
    if not PORT_FILE.exists():
        return None
    try:
        return int(PORT_FILE.read_text().strip())
    except (ValueError, OSError):
        return None


def clear_runtime_files() -> None:
    """Remove pid/port files. Leaves staging + log intact. Preserved."""
    for p in (PID_FILE, PORT_FILE):
        p.unlink(missing_ok=True)


def _redirect_stdio_to_log() -> None:
    """Child process: close stdin, send stdout/stderr to LOG_FILE."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd_in = os.open(os.devnull, os.O_RDONLY)
    fd_out = os.open(str(LOG_FILE), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    os.dup2(fd_in, 0)
    os.dup2(fd_out, 1)
    os.dup2(fd_out, 2)
    os.close(fd_in)
    if fd_out > 2:
        os.close(fd_out)


def _serve_forever(port: int) -> None:
    """Child process entrypoint: bind 127.0.0.1:<port> and serve. Preserved."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )

    def _on_sig(_signum: int, _frame: object) -> None:
        log.info("received signal, shutting down")
        clear_runtime_files()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _on_sig)
    signal.signal(signal.SIGINT, _on_sig)

    handler_cls = _make_handler()
    try:
        with ReusableTCPServer(("127.0.0.1", port), handler_cls) as httpd:
            log.info("serving %s on 127.0.0.1:%d", ROOT, port)
            httpd.serve_forever()
    except OSError as exc:
        log.error("bind failed: %s", exc)
        clear_runtime_files()
        sys.exit(EXIT_SERVER)


def _port_free(port: int) -> bool:
    """Probe whether 127.0.0.1:<port> can be bound (SO_REUSEADDR). Preserved."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


# ── tailscale wiring (preserved from legacy) ──────────────────────────


def _tailscale_available() -> bool:
    return shutil.which("tailscale") is not None


def _tailscale_serve_on(port: int) -> tuple[bool, str]:
    """Publish 127.0.0.1:<port> via `tailscale serve`. Preserved."""
    if not _tailscale_available():
        return False, "tailscale CLI not on PATH"
    try:
        proc = subprocess.run(
            [
                "tailscale",
                "serve",
                "--bg",
                "--https=443",
                f"http://127.0.0.1:{port}",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return False, f"tailscale call failed: {exc}"
    if proc.returncode != 0:
        return False, (proc.stderr or proc.stdout).strip() or f"rc={proc.returncode}"
    return True, (proc.stdout or proc.stderr).strip()


def _tailscale_serve_off() -> tuple[bool, str]:
    """Take down `tailscale serve`. Preserved."""
    if not _tailscale_available():
        return False, "tailscale CLI not on PATH"
    try:
        proc = subprocess.run(
            ["tailscale", "serve", "--https=443", "off"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return False, f"tailscale call failed: {exc}"
    return proc.returncode == 0, (proc.stdout or proc.stderr).strip()


def _tailscale_public_url() -> str | None:
    """Extract the tailnet URL from serve status JSON. Preserved."""
    if not _tailscale_available():
        return None
    try:
        proc = subprocess.run(
            ["tailscale", "serve", "status", "--json"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if proc.returncode != 0:
        return None
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    web = data.get("Web") if isinstance(data, dict) else None
    if not isinstance(web, dict):
        return None
    for key in web.keys():
        if isinstance(key, str) and key.startswith(("https://", "http://")):
            return key.rstrip("/") + "/"
        if isinstance(key, str) and ":" in key:
            host = key.split(":", 1)[0]
            return f"https://{host}/"
    return None


# ── verb implementations ──────────────────────────────────────────────
# Verb surface preserved verbatim (muscle memory):
#   push, unpush, start, expose, unexpose, status, stop, clean, feedback, name


def cmd_push(args: argparse.Namespace) -> int:
    """Stage --src as a relative symlink under <project>/<subdir>. Preserved."""
    # Preserve user's literal path: do NOT call .resolve() (which would
    # dereference any intermediate symlinks). .absolute() only anchors
    # relative paths against cwd without walking the symlink chain.
    src = Path(args.src).expanduser().absolute()
    if not src.exists():
        print(f"error: --src does not exist: {src}", file=sys.stderr)
        return EXIT_CALLER

    ensure_root()
    try:
        project = project_dir(args.project)
        subdir = _check_name(args.as_name or src.name, "as")
        if args.artifact_id:
            _check_artifact_id(args.artifact_id.strip())
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_CALLER

    dest = project / subdir
    remove_entry(dest)

    rel = os.path.relpath(src, dest.parent)
    os.symlink(rel, dest)
    print(f"symlink {dest} → {rel}")

    # Record this push in the durable artifact index for feedback resolution.
    artifact_id = (args.artifact_id or "").strip() or f"{args.project}/{subdir}"
    try:
        conn = db_connect()
        try:
            conn.execute(
                "INSERT INTO artifact_index "
                "(project, subdir, artifact_id, src_path, last_pushed) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(project, subdir) DO UPDATE SET "
                "  artifact_id = excluded.artifact_id, "
                "  src_path    = excluded.src_path, "
                "  last_pushed = excluded.last_pushed",
                (args.project, subdir, artifact_id, str(src), int(time.time())),
            )
            conn.commit()
        finally:
            conn.close()
        print(f"artifact_id: {artifact_id}")
    except sqlite3.Error as exc:
        log.warning("artifact_index update failed: %s", exc)

    regenerate_index()
    return EXIT_OK


def cmd_unpush(args: argparse.Namespace) -> int:
    """Remove a staged entry. Feedback rows untouched. Preserved."""
    try:
        project = project_dir(args.project)
        subdir = _check_name(args.subdir, "subdir")
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_CALLER
    dest = project / subdir
    if not (dest.exists() or dest.is_symlink()):
        print(f"(absent) {dest}")
        return EXIT_OK
    remove_entry(dest)
    print(f"removed {dest}")
    regenerate_index()
    return EXIT_OK


def cmd_start(args: argparse.Namespace) -> int:
    """Boot the local daemon (fork), write pid/port, regen index. Preserved."""
    ensure_root()
    port = args.port

    existing_pid = read_pid()
    existing_port = read_port()
    if existing_pid and existing_port == port:
        print(f"daemon already running pid={existing_pid} port={port}")
        print(f"local:   http://127.0.0.1:{port}/")
        regenerate_index()
        if args.expose:
            ok, msg = _tailscale_serve_on(port)
            if not ok:
                print(f"expose failed: {msg}", file=sys.stderr)
                return EXIT_SERVER
            url = _tailscale_public_url() or "(tailscale URL unknown)"
            print(f"tailnet: {url}")
        return EXIT_OK

    if existing_pid and existing_port and existing_port != port:
        print(
            f"error: daemon already running on port {existing_port} "
            f"(pid {existing_pid}); stop it first",
            file=sys.stderr,
        )
        return EXIT_SERVER

    if not _port_free(port):
        print(f"error: port {port} already in use by another process", file=sys.stderr)
        return EXIT_SERVER

    regenerate_index()

    pid = os.fork()
    if pid > 0:
        # parent
        for _ in range(40):
            if PID_FILE.exists():
                break
            time.sleep(0.05)
        PID_FILE.write_text(str(pid))
        PORT_FILE.write_text(str(port))
        print(f"daemon started pid={pid} port={port}")
        print(f"local:   http://127.0.0.1:{port}/")
        if args.expose:
            ok, msg = _tailscale_serve_on(port)
            if not ok:
                print(f"expose failed: {msg}", file=sys.stderr)
                return EXIT_SERVER
            url = _tailscale_public_url() or "(tailscale URL unknown)"
            print(f"tailnet: {url}")
        return EXIT_OK

    # child
    os.setsid()
    _redirect_stdio_to_log()
    PID_FILE.write_text(str(os.getpid()))
    PORT_FILE.write_text(str(port))
    _serve_forever(port)
    return EXIT_OK  # not reached


def cmd_expose(_args: argparse.Namespace) -> int:
    """Publish the running daemon via tailscale serve. Preserved."""
    pid = read_pid()
    port = read_port()
    if not pid or not port:
        print("error: daemon not running; run `start` first", file=sys.stderr)
        return EXIT_SERVER
    ok, msg = _tailscale_serve_on(port)
    if not ok:
        print(f"expose failed: {msg}", file=sys.stderr)
        return EXIT_SERVER
    url = _tailscale_public_url() or "(tailscale URL unknown)"
    print(f"tailnet: {url}")
    return EXIT_OK


def cmd_unexpose(_args: argparse.Namespace) -> int:
    """Take down tailscale serve. Preserved."""
    ok, msg = _tailscale_serve_off()
    if not ok:
        print(f"unexpose: {msg}", file=sys.stderr)
        return EXIT_SERVER
    print("unexposed")
    return EXIT_OK


def cmd_status(_args: argparse.Namespace) -> int:
    """Print daemon pid/port, URLs, and staged entries. Preserved."""
    pid = read_pid()
    port = read_port()
    if pid and port:
        print(f"daemon:  pid={pid} port={port}")
        print(f"local:   http://127.0.0.1:{port}/")
    else:
        print("daemon:  stopped")
    tailnet = _tailscale_public_url()
    print(f"tailnet: {tailnet or '(not exposed)'}")
    print(f"root:    {ROOT}")
    ensure_root()
    projects = [
        p for p in sorted(ROOT.iterdir())
        if p.is_dir() and not p.name.startswith(".")
    ]
    if not projects:
        print("entries: (none)")
        return EXIT_OK
    print("entries:")
    for proj in projects:
        entries = [e for e in sorted(proj.iterdir()) if not e.name.startswith(".")]
        for entry in entries:
            kind = "→ " + os.readlink(entry) if entry.is_symlink() else "(copy)"
            print(f"  {proj.name}/{entry.name}  {kind}")
    return EXIT_OK


def cmd_stop(_args: argparse.Namespace) -> int:
    """Stop the daemon, unexpose, clear pid/port files. Preserved."""
    pid = read_pid()
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError as exc:
            print(f"kill failed: {exc}", file=sys.stderr)
            return EXIT_SERVER
        for _ in range(40):
            try:
                os.kill(pid, 0)
            except OSError:
                break
            time.sleep(0.05)
        print(f"stopped pid={pid}")
    else:
        print("daemon already stopped")
    _tailscale_serve_off()
    clear_runtime_files()
    return EXIT_OK


def cmd_clean(args: argparse.Namespace) -> int:
    """Remove one project's staging dir. Feedback DB untouched. Preserved."""
    if not args.project:
        print("error: --project required (no global wipe)", file=sys.stderr)
        return EXIT_CALLER
    try:
        name = _check_name(args.project, "project")
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_CALLER
    target = ROOT / name
    if not target.exists():
        print(f"(absent) {target}")
        return EXIT_OK
    if not target.is_dir():
        print(f"error: {target} is not a directory", file=sys.stderr)
        return EXIT_CALLER
    shutil.rmtree(target)
    print(f"removed {target}")
    regenerate_index()
    return EXIT_OK


def cmd_feedback(args: argparse.Namespace) -> int:
    """Print feedback_dump(artifact_id) as JSON for agent consumption.

    Extended shape (threads + anchors + resolved + reply chains) per
    DESIGN.md section 8. Still a single JSON dump; backward friendly.
    """
    artifact_id = args.artifact_id.strip()
    if not artifact_id:
        print("error: --artifact required", file=sys.stderr)
        return EXIT_CALLER
    try:
        payload = feedback_dump(artifact_id)
    except sqlite3.Error as exc:
        print(f"error: db: {exc}", file=sys.stderr)
        return EXIT_SERVER
    print(json.dumps(payload, indent=2, default=str))
    return EXIT_OK


def cmd_name(args: argparse.Namespace) -> int:
    """Get/set/clear the global default comment-author name. Preserved."""
    try:
        if args.clear:
            setting_delete("author")
            print("cleared")
            return EXIT_OK
        if args.value is None:
            current = setting_get("author")
            print(current if current else "(unset)")
            return EXIT_OK
        v = args.value.strip()
        if not v:
            print("error: empty value; use --clear to unset", file=sys.stderr)
            return EXIT_CALLER
        if len(v) > 80:
            print("error: name too long (>80 chars)", file=sys.stderr)
            return EXIT_CALLER
        setting_set("author", v)
        print(f"author = {v}")
    except sqlite3.Error as exc:
        print(f"error: db: {exc}", file=sys.stderr)
        return EXIT_SERVER
    return EXIT_OK


# ── arg parsing ───────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser.

    Preserves the verb surface verbatim: push, unpush, start, expose,
    unexpose, status, stop, clean, feedback, name. New review capabilities are
    reached over HTTP, not new verbs (bd mirror is a `setting`, toggled via the
    existing name/setting path). See DESIGN.md section 11.
    """
    p = argparse.ArgumentParser(
        prog="review-serve",
        description="Stage and serve artifacts for review under /tmp/claude-artifacts/.",
    )
    sub = p.add_subparsers(dest="verb", required=True)

    sp = sub.add_parser("push", help="Stage an artifact (symlink only).")
    sp.add_argument("--project", required=True)
    sp.add_argument("--src", required=True)
    sp.add_argument("--as", dest="as_name", default=None)
    sp.add_argument(
        "--id",
        dest="artifact_id",
        default=None,
        help="Artifact ID for feedback correlation. Default: <project>/<subdir>.",
    )
    sp.set_defaults(func=cmd_push)

    sp = sub.add_parser("unpush", help="Remove a staged entry.")
    sp.add_argument("--project", required=True)
    sp.add_argument("--subdir", required=True)
    sp.set_defaults(func=cmd_unpush)

    sp = sub.add_parser("start", help="Boot the local daemon.")
    sp.add_argument("--port", type=int, default=DEFAULT_PORT)
    sp.add_argument("--expose", action="store_true", help="Also publish via tailscale.")
    sp.set_defaults(func=cmd_start)

    sp = sub.add_parser("expose", help="Publish via tailscale serve.")
    sp.set_defaults(func=cmd_expose)

    sp = sub.add_parser("unexpose", help="Take down tailscale serve.")
    sp.set_defaults(func=cmd_unexpose)

    sp = sub.add_parser("status", help="Show daemon + entries.")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("stop", help="Stop the daemon + unexpose.")
    sp.set_defaults(func=cmd_stop)

    sp = sub.add_parser("clean", help="Remove one project's staging dir.")
    sp.add_argument("--project", required=True)
    sp.set_defaults(func=cmd_clean)

    sp = sub.add_parser(
        "feedback",
        help="Dump threads + reply chains + upload metadata for an artifact as JSON.",
    )
    sp.add_argument("--artifact", dest="artifact_id", required=True)
    sp.set_defaults(func=cmd_feedback)

    sp = sub.add_parser(
        "name",
        help="Get/set/clear the global default comment-author name.",
    )
    sp.add_argument(
        "value",
        nargs="?",
        default=None,
        help="New name. Omit to print current. Use --clear to unset.",
    )
    sp.add_argument("--clear", action="store_true", help="Unset the name.")
    sp.set_defaults(func=cmd_name)

    return p


def main(argv: list[str] | None = None) -> int:
    """Parse args and dispatch to the chosen verb. Returns process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
