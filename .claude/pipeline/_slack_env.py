"""Shared env-file loader + atomic write helper for pipeline Slack scripts.

Extracted from slack_listener.py so session_bind.py, session_inbox.py,
pipeline_notify.py, and the listener all share one canonical implementation.

Stdlib-only. No third-party deps.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

__all__ = [
    "load_env_file",
    "default_env_path",
    "atomic_write_text",
    "validate_sid",
]

log = logging.getLogger(__name__)

_DEFAULT_ENV_PATH = "~/.claude/pipeline/slack.env.local"

# Session IDs must be UUID-shaped alphanumeric strings (8-64 chars).
_SID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")

_FORCE_LOAD_ENV = "SLACK_ENV_FORCE_LOAD"


def default_env_path() -> Path:
    """Return the default env file path, honouring SLACK_ENV_FILE override."""
    raw = os.environ.get("SLACK_ENV_FILE", _DEFAULT_ENV_PATH)
    return Path(raw).expanduser()


def validate_sid(sid: str) -> str:
    """Validate session id matches ^[A-Za-z0-9_-]{8,64}$.

    Returns sid unchanged on success. Raises ValueError on invalid input.
    This prevents path-traversal via malicious CLAUDE_CODE_SESSION_ID values.
    """
    if not _SID_RE.fullmatch(sid):
        raise ValueError(
            f"Invalid CLAUDE_CODE_SESSION_ID {sid!r}: "
            "must match [A-Za-z0-9_-]{8,64}"
        )
    return sid


def load_env_file(path: Path) -> None:
    """Populate os.environ from a KEY=VAL env file. Existing env wins.

    Tolerates: blank lines, ``#`` comments, ``export KEY=VAL``, quoted values
    (single or double, stripped). Does not perform shell interpolation.

    H2: refuses to load if the file is group- or world-readable/writable
    (mode bits 0o077 set). Override with SLACK_ENV_FORCE_LOAD=1 env var.
    """
    if not path.is_file():
        return
    try:
        st = path.stat()
    except OSError as exc:
        log.warning("could not stat env file %s: %s", path, exc)
        return
    if st.st_mode & 0o077:
        force = os.environ.get(_FORCE_LOAD_ENV, "").strip()
        if force not in ("1", "true", "yes"):
            raise PermissionError(
                f"Refusing to load {path}: file permissions are too open "
                f"(mode {oct(st.st_mode & 0o777)}). "
                "Run: chmod 600 " + str(path) + "\n"
                f"Override: {_FORCE_LOAD_ENV}=1"
            )
        log.warning(
            "env file %s has loose permissions (mode %s); "
            "loading anyway because %s=1",
            path, oct(st.st_mode & 0o777), _FORCE_LOAD_ENV,
        )
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        if key and key not in os.environ:
            os.environ[key] = val


def atomic_write_text(path: Path, data: str, mode: int = 0o600) -> None:
    """Write *data* to *path* atomically with fsync.

    Steps:
    1. Write to ``<path>.tmp`` with ``os.open`` (avoids umask surprises).
    2. fsync the tmp file descriptor.
    3. ``os.rename`` tmp → path (atomic on POSIX same-fs).
    4. Best-effort fsync the parent directory.

    The mode argument sets the tmp file permissions before rename.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    try:
        os.write(fd, data.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    os.rename(str(tmp), str(path))
    # Best-effort dir fsync — non-fatal on failure (e.g. some network FS).
    try:
        dir_fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        pass
