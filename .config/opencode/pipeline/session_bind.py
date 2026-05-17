#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "slack-bolt>=1.18",
# ]
# ///
"""session_bind — activate / deactivate / status CLI for session-bound comms threading.

Usage:
    session_bind.py activate    # bind current session to a comms thread
    session_bind.py deactivate  # unbind and post closing message
    session_bind.py status      # print JSON state or "unbound"

Reads CLAUDE_CODE_SESSION_ID from env. Exits non-zero with a clear stderr
message if the var is unset (caller is not inside a Claude Code process).

Environment (auto-loaded from ~/.config/opencode/pipeline/slack.env.local):
    SLACK_BOT_TOKEN     xoxb-...
    SLACK_APP_TOKEN     xapp-...
    SLACK_CHANNEL       fallback channel ID when pipeline.toml absent
    CLAUDE_CODE_SESSION_ID   harness-owned session UUID (inherited)

Per-project channel override: <cwd>/.pipeline/pipeline.toml [slack].channel
"""

from __future__ import annotations

import argparse
import fcntl
import json
import logging
import os
import signal
import subprocess
import sys
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_PIPELINE_DIR = Path(__file__).parent
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

from comms.env import (  # noqa: E402
    atomic_write_text,
    default_env_path,
    load_env_file,
    validate_sid,
)

log = logging.getLogger("session_bind")

SESSIONS_ROOT = Path("~/.config/opencode/sessions").expanduser()
COMMS_ROOT = Path("~/.config/opencode/comms-router").expanduser()
LEGACY_ROOT = Path("~/.config/opencode/slack-router").expanduser()
LEGACY_PID = LEGACY_ROOT / "router.pid"

ROUTER_SCRIPT = _PIPELINE_DIR / "comms" / "router.py"
SCHEMA_VERSION = 1

_COMMS_ROUTER_SCRIPT_NAME = "comms/router.py"

# Scopes required for end-to-end session-bound threading.
_REQUIRED_BOT_SCOPES: frozenset[str] = frozenset(
    {"chat:write", "channels:history", "groups:history"}
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sid_short(sid: str) -> str:
    """Display-only 8-char prefix. Not a recovery key."""
    return sid[:8]


def _require_session_id() -> str:
    """Read + validate CLAUDE_CODE_SESSION_ID. Exits 1 on missing or invalid."""
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID", "").strip()
    if not sid:
        sys.stderr.write(
            "CLAUDE_CODE_SESSION_ID is not set.\n"
            "This CLI must be invoked inside an active Claude Code process.\n"
        )
        sys.exit(1)
    try:
        return validate_sid(sid)
    except ValueError as exc:
        sys.stderr.write(f"{exc}\n")
        sys.exit(1)


def _session_dir(sid: str) -> Path:
    return SESSIONS_ROOT / sid


def _lock_path(sid: str) -> Path:
    return _session_dir(sid) / ".lock"


def _state_path(sid: str) -> Path:
    return _session_dir(sid) / "slack.json"


def _inbox_path(sid: str) -> Path:
    return _session_dir(sid) / "inbox"


def _acquire_lock(sid: str) -> tuple[int, Path]:
    """Open + flock LOCK_EX|LOCK_NB on the session .lock file.

    Returns (fd, path). Caller must close fd to release.
    Exits non-zero with clear message on contention.
    """
    lock_p = _lock_path(sid)
    _session_dir(sid).mkdir(parents=True, exist_ok=True)
    lock_p.touch(mode=0o600, exist_ok=True)
    fd = os.open(str(lock_p), os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        sys.stderr.write(
            "Another activate/deactivate is in progress for this session.\n"
            "Retry in a moment, or run 'session_bind.py status' to confirm state.\n"
        )
        sys.exit(1)
    return fd, lock_p


def _release_lock(fd: int) -> None:
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:
        pass
    try:
        os.close(fd)
    except OSError:
        pass


def _atomic_write_state(sid: str, state: dict[str, Any]) -> None:
    """Write state atomically with fsync; file mode 600 (H3)."""
    path = _state_path(sid)
    atomic_write_text(path, json.dumps(state, indent=2, default=str), mode=0o600)


def _read_state(sid: str) -> dict[str, Any] | None:
    path = _state_path(sid)
    if not path.is_file():
        return None
    try:
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        sys.stderr.write(f"State file corrupt ({exc}); treating as unbound.\n")
        return None
    version = data.get("schema_version", 1)
    if version > SCHEMA_VERSION:
        sys.stderr.write(
            f"Incompatible slack.json schema_version={version} "
            f"(max supported={SCHEMA_VERSION}).\n"
            "Please upgrade pipeline scripts.\n"
        )
        sys.exit(1)
    return data


def _resolve_channel(project_path: Path) -> str | None:
    """Resolve Slack channel: per-project pipeline.toml -> env SLACK_CHANNEL."""
    toml_path = project_path / ".pipeline" / "pipeline.toml"
    if toml_path.is_file():
        try:
            with toml_path.open("rb") as fh:
                cfg = tomllib.load(fh)
            channel = cfg.get("slack", {}).get("channel")
            if channel:
                return str(channel)
        except Exception as exc:
            log.warning("failed to read pipeline.toml: %s", exc)
    return os.environ.get("SLACK_CHANNEL") or None


def _is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, OSError):
        return False


def _verify_pid_is_comms_router(pid: int) -> bool:
    """Best-effort: check /proc/<pid>/cmdline contains comms/router.py."""
    cmdline_path = Path(f"/proc/{pid}/cmdline")
    try:
        raw = cmdline_path.read_bytes()
    except FileNotFoundError:
        log.debug("pid=%d already gone (no /proc entry)", pid)
        return False
    except OSError:
        return True
    cmdline = raw.replace(b"\x00", b" ").decode("utf-8", errors="replace")
    return _COMMS_ROUTER_SCRIPT_NAME in cmdline


def _verify_pid_is_slack_router(pid: int) -> bool:
    """Best-effort: check /proc/<pid>/cmdline contains slack_router.py.

    Used for N2 identity check before SIGKILL on legacy pidfile reap.
    """
    cmdline_path = Path(f"/proc/{pid}/cmdline")
    try:
        raw = cmdline_path.read_bytes()
    except FileNotFoundError:
        return False
    except OSError:
        return True
    cmdline = raw.replace(b"\x00", b" ").decode("utf-8", errors="replace")
    return "slack_router.py" in cmdline


def _read_router_pid() -> int | None:
    """Read PID from comms-router/router.pid. Returns None if absent or unparseable."""
    pid_path = COMMS_ROOT / "router.pid"
    if not pid_path.is_file():
        return None
    try:
        return int(pid_path.read_text().strip())
    except (ValueError, OSError):
        return None


def _get_pid_owner_uid(pid: int) -> int | None:
    """Return uid of process pid via /proc/<pid>/status, or None on error."""
    status_path = Path(f"/proc/{pid}/status")
    try:
        for line in status_path.read_text().splitlines():
            if line.startswith("Uid:"):
                parts = line.split()
                if len(parts) >= 2:
                    return int(parts[1])  # real uid
    except (OSError, ValueError):
        pass
    return None


def _reap_legacy_slack_router() -> None:
    """One-shot migration reap of legacy ~/.config/opencode/slack-router daemon.

    Algorithm (B5 soft-reap / N2 identity check):
      1. LEGACY_PID absent -> no-op.
      2. Read pid. Unreadable -> log + skip kill + rmtree.
      3. Stat /proc/<pid> owner uid.
         - cross-uid -> log warning + return (new daemon spawns alongside).
         - proc absent -> process gone; unlink + rmtree.
      4. Same uid + alive: N2 identity check via _verify_pid_is_slack_router.
         - Not a slack_router process (stale pid): log warning + skip kill.
      5. SIGTERM -> poll 2s -> SIGKILL -> unlink -> rmtree.
      6. Hard-error only when same-uid kill raises unexpected EPERM.
    """
    if not LEGACY_PID.is_file():
        return

    try:
        pid = int(LEGACY_PID.read_text().strip())
    except (ValueError, OSError) as exc:
        log.warning("legacy slack_router pidfile unreadable (%s); skipping kill; rmtree", exc)
        try:
            import shutil
            shutil.rmtree(str(LEGACY_ROOT), ignore_errors=True)
        except OSError:
            pass
        return

    owner_uid = _get_pid_owner_uid(pid)
    if owner_uid is None:
        # Process already gone.
        log.debug("legacy slack_router pid=%d already gone; unlinking + rmtree", pid)
        try:
            LEGACY_PID.unlink(missing_ok=True)
            import shutil
            shutil.rmtree(str(LEGACY_ROOT), ignore_errors=True)
        except OSError as exc:
            log.warning("legacy rmtree failed: %s", exc)
        return

    current_uid = os.getuid()
    if owner_uid != current_uid:
        log.warning(
            "legacy slack_router pid=%d owned by uid=%d (not current %d); "
            "skipping reap; new daemon will spawn alongside",
            pid, owner_uid, current_uid,
        )
        return

    # Same uid: N2 identity check before kill.
    if not _verify_pid_is_slack_router(pid):
        log.warning(
            "legacy pidfile pid=%d does not appear to be slack_router.py "
            "(stale pid reused by another process); skipping kill",
            pid,
        )
        try:
            LEGACY_PID.unlink(missing_ok=True)
        except OSError:
            pass
        return

    log.info("reaping legacy slack_router pid=%d", pid)
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    except OSError as exc:
        raise RuntimeError(
            f"Failed to SIGTERM legacy slack_router pid={pid}: {exc}. "
            "Cannot safely spawn new router daemon."
        ) from exc

    # Poll 2s for termination.
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        if not _is_pid_alive(pid):
            break
        time.sleep(0.1)

    if _is_pid_alive(pid):
        # N2: identity check again before SIGKILL.
        if _verify_pid_is_slack_router(pid):
            try:
                os.kill(pid, signal.SIGKILL)
                log.info("SIGKILL to surviving legacy slack_router pid=%d", pid)
            except OSError as exc:
                if not _is_pid_alive(pid):
                    pass  # already gone
                else:
                    raise RuntimeError(
                        f"Failed to SIGKILL legacy slack_router pid={pid}: {exc}"
                    ) from exc

    try:
        LEGACY_PID.unlink(missing_ok=True)
        import shutil
        shutil.rmtree(str(LEGACY_ROOT), ignore_errors=True)
    except OSError as exc:
        log.warning("legacy rmtree failed (cosmetic): %s", exc)


def _ensure_router_alive() -> int | None:
    """Ensure comms router is alive. Spawn if absent or stale. Returns router PID."""
    if not ROUTER_SCRIPT.is_file():
        log.warning("comms/router.py not found at %s; router not spawned", ROUTER_SCRIPT)
        return None

    pid = _read_router_pid()
    if pid is not None and _is_pid_alive(pid) and _verify_pid_is_comms_router(pid):
        log.debug("router already alive: pid=%d", pid)
        return pid

    # One-shot legacy reap BEFORE spawning new daemon (D10 / §8.1).
    try:
        _reap_legacy_slack_router()
    except RuntimeError as exc:
        sys.stderr.write(f"[session_bind] {exc}\n")
        return None

    COMMS_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    log_path = COMMS_ROOT / "router.log"
    try:
        with open(str(log_path), "a") as log_fh:
            proc = subprocess.Popen(
                ["uv", "run", "--script", str(ROUTER_SCRIPT)],
                start_new_session=True,
                stdin=subprocess.DEVNULL,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                close_fds=True,
            )
        log.info("spawned comms router pid=%d", proc.pid)
        time.sleep(0.5)
        return proc.pid
    except OSError as exc:
        log.warning("router spawn failed: %s", exc)
        return None


def _reap_legacy_listeners() -> None:
    """SIGTERM any surviving slack_listener.py processes (one-shot migration)."""
    try:
        result = subprocess.run(
            ["pgrep", "-af", "slack_listener.py"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        log.debug("pgrep unavailable: %s", exc)
        return

    pids: list[int] = []
    for line in result.stdout.splitlines():
        parts = line.split(None, 1)
        if parts:
            try:
                pids.append(int(parts[0]))
            except ValueError:
                pass

    if not pids:
        return

    log.info("reaping %d legacy listener(s): %s", len(pids), pids)
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except OSError as exc:
            log.warning("SIGTERM to pid=%d failed: %s", pid, exc)

    time.sleep(2)

    for pid in pids:
        if _is_pid_alive(pid):
            try:
                os.kill(pid, signal.SIGKILL)
                log.info("SIGKILL to surviving listener pid=%d", pid)
            except OSError:
                pass


def _preflight_via_provider(project_path: Path) -> tuple[bool, str]:
    """Verify provider creds/scopes before binding.

    Delegates to CommsRegistry.active_provider().auth_preflight().
    Returns (ok, message).
    """
    from comms.registry import get_registry  # noqa: PLC0415
    try:
        provider = get_registry().active_provider(project_path)
        result = provider.auth_preflight()
        return result.ok, result.message
    except Exception as exc:  # noqa: BLE001
        return False, f"auth preflight failed: {exc}"


def _get_provider(project_path: Path) -> Any:
    """Get active comms provider for project_path."""
    from comms.registry import get_registry  # noqa: PLC0415
    return get_registry().active_provider(project_path)


def _make_thread_ref(channel_id: str, thread_ts: str) -> Any:
    """Build a ThreadRef for Slack channel+thread_ts."""
    from types import MappingProxyType  # noqa: PLC0415
    from comms.types import ThreadRef  # noqa: PLC0415
    return ThreadRef(
        provider="slack",
        provider_data=MappingProxyType({"channel_id": channel_id, "thread_ts": thread_ts}),
    )


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def cmd_activate(args: argparse.Namespace) -> int:
    """Activate or reactivate session binding."""
    os.umask(0o077)
    sid = _require_session_id()
    cwd_full = Path.cwd()
    cwd_display = str(cwd_full).replace(str(Path.home()), "~", 1)
    project_path = Path(args.project).expanduser().resolve() if args.project else cwd_full

    load_env_file(default_env_path())

    channel = _resolve_channel(project_path)
    if not channel:
        sys.stderr.write(
            "No Slack channel configured.\n"
            f"Set SLACK_CHANNEL in {default_env_path()} or "
            "[slack].channel in <project>/.pipeline/pipeline.toml\n"
        )
        return 1

    ok, msg = _preflight_via_provider(project_path)
    if not ok:
        sys.stderr.write(msg + "\n")
        return 1

    session_d = _session_dir(sid)
    session_d.mkdir(mode=0o700, parents=True, exist_ok=True)
    session_d.chmod(0o700)

    # Reap legacy listeners BEFORE ensuring router alive.
    _reap_legacy_listeners()

    lock_fd, _ = _acquire_lock(sid)
    try:
        existing = _read_state(sid)

        if existing is not None:
            if existing.get("active", False):
                # Idempotent: already active. Ensure router alive.
                _ensure_router_alive()
                existing["last_bound_at"] = now_iso()
                existing.pop("inbox_daemon_pid", None)
                # B7: schema_version always present; B8-write: always set provider.
                existing.setdefault("schema_version", SCHEMA_VERSION)
                existing["provider"] = "slack"
                _atomic_write_state(sid, existing)
                result = {
                    "channel": existing["channel_id"],
                    "thread_ts": existing["thread_ts"],
                    "session_id": sid,
                    "status": "already_active",
                }
                sys.stdout.write(json.dumps(result) + "\n")
                return 0

            # Previously deactivated — reopen same thread.
            existing["active"] = True
            existing["ended_at"] = None
            existing["last_bound_at"] = now_iso()
            existing.pop("inbox_daemon_pid", None)
            existing.setdefault("schema_version", SCHEMA_VERSION)
            existing["provider"] = "slack"
            _atomic_write_state(sid, existing)

            thread_ts = existing["thread_ts"]
            reopen_channel = existing["channel_id"]
            provider = _get_provider(project_path)
            _thread_ref = _make_thread_ref(reopen_channel, thread_ts)
            try:
                provider.post_simple(
                    _thread_ref,
                    "status",
                    f":arrows_counterclockwise: Session reopened at {now_iso()}",
                )
            except Exception as exc:
                log.warning("reopen post failed: %s", exc)

            _ensure_router_alive()
            result = {
                "channel": reopen_channel,
                "thread_ts": thread_ts,
                "session_id": sid,
                "status": "reactivated",
            }
            sys.stdout.write(json.dumps(result) + "\n")
            return 0

        # No existing state — first bind.
        provider = _get_provider(project_path)
        sid_short = _sid_short(sid)
        opening_text = (
            f":hourglass_flowing_sand: *Session started* `{sid_short}` "
            f"(cwd={cwd_display})"
        )
        thread_ref = provider.open_thread(channel, opening_text)
        thread_ts_new: str = thread_ref.provider_data["thread_ts"]

        inbox_p = _inbox_path(sid)
        inbox_p.mkdir(mode=0o700, parents=True, exist_ok=True)
        inbox_p.chmod(0o700)

        # B7: schema_version written; provider field written (new additive field).
        state: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "session_id": sid,
            "provider": "slack",
            "channel_id": channel,
            "thread_ts": thread_ts_new,
            "cwd": str(cwd_full),
            "started_at": now_iso(),
            "last_bound_at": now_iso(),
            "ended_at": None,
            "active": True,
        }
        _atomic_write_state(sid, state)

        _ensure_router_alive()

        result = {
            "channel": channel,
            "thread_ts": thread_ts_new,
            "session_id": sid,
            "status": "activated",
        }
        sys.stdout.write(json.dumps(result) + "\n")
        return 0

    finally:
        _release_lock(lock_fd)


def cmd_deactivate(args: argparse.Namespace) -> int:
    """Deactivate session binding and post closing message."""
    del args  # unused
    sid = _require_session_id()

    load_env_file(default_env_path())

    lock_fd, _ = _acquire_lock(sid)
    try:
        state = _read_state(sid)
        if state is None:
            sys.stderr.write(f"Session {sid[:8]}... is not bound.\n")
            return 1

        if not state.get("active", False):
            sys.stdout.write("already_inactive\n")
            return 0

        project_path = Path(state.get("cwd", str(Path.cwd()))).expanduser().resolve()
        provider = _get_provider(project_path)
        thread_ref = _make_thread_ref(state["channel_id"], state["thread_ts"])
        try:
            provider.close_thread(
                thread_ref,
                f":checkered_flag: *Session ended at {now_iso()}*",
            )
        except Exception as exc:
            log.warning("close_thread failed: %s", exc)

        state["active"] = False
        state["ended_at"] = now_iso()
        state.pop("inbox_daemon_pid", None)
        # B7 + lazy-rewrite: always set schema_version and provider on write.
        state.setdefault("schema_version", SCHEMA_VERSION)
        state["provider"] = "slack"
        _atomic_write_state(sid, state)

        # Router stays alive to serve other sessions.
        sys.stdout.write("ok\n")
        return 0

    finally:
        _release_lock(lock_fd)


def cmd_status(args: argparse.Namespace) -> int:
    """Print JSON state or 'unbound'."""
    del args  # unused
    sid = _require_session_id()
    state = _read_state(sid)
    if state is None:
        sys.stdout.write("unbound\n")
        return 0

    out = dict(state)
    # Show router liveness in status output.
    router_pid = _read_router_pid()
    out["router_pid"] = router_pid
    out["router_pid_alive"] = _is_pid_alive(router_pid) if router_pid else False
    sys.stdout.write(json.dumps(out, indent=2, default=str) + "\n")
    return 0


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="session_bind.py",
        description=(
            "Activate / deactivate / status for session-bound comms threading. "
            "Reads CLAUDE_CODE_SESSION_ID from env."
        ),
    )
    parser.add_argument("--log-level", default="WARNING", help="logging level")
    sub = parser.add_subparsers(dest="command", required=True)

    act = sub.add_parser("activate", help="Bind session to a comms thread")
    act.add_argument(
        "--project",
        default=None,
        help="Project path for pipeline.toml channel lookup (default: cwd)",
    )

    sub.add_parser("deactivate", help="Unbind session and post closing message")
    sub.add_parser("status", help="Print JSON state or 'unbound'")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    dispatch = {
        "activate": cmd_activate,
        "deactivate": cmd_deactivate,
        "status": cmd_status,
    }
    fn = dispatch.get(args.command)
    if fn is None:
        parser.print_help(sys.stderr)
        sys.exit(1)
    sys.exit(fn(args))


if __name__ == "__main__":
    main()
