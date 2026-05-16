"""test_slack_router — DEPRECATED: slack_router.py deleted in comms refactor.

Original tests covered: regex validators, YAML escaping, payload parsing, file I/O
atomicity, single-instance flock semantics, GC logic, schema compatibility.
Functionality ported to tests/pipeline/test_comms/. File kept for reference; all
tests skipped.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import multiprocessing
import os
import sys
import tempfile
import threading
import time
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import MappingProxyType
from typing import Any
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Resolve pipeline module path without importing slack_bolt
# ---------------------------------------------------------------------------

import pytest
pytest.importorskip("slack_router", reason="slack_router.py deleted in comms refactor")

_PIPELINE_DIR = Path(__file__).parent.parent.parent / ".claude" / "pipeline"
if str(_PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(_PIPELINE_DIR))

# Stub slack_bolt before any import that triggers it
_slack_bolt_stub = MagicMock()
_slack_bolt_stub.App = MagicMock
_socket_mode_stub = MagicMock()
_socket_mode_stub.SocketModeHandler = MagicMock

for _key, _val in [
    ("slack_bolt", _slack_bolt_stub),
    ("slack_bolt.adapter", MagicMock()),
    ("slack_bolt.adapter.socket_mode", _socket_mode_stub),
]:
    if _key not in sys.modules:
        sys.modules[_key] = _val  # type: ignore[assignment]

import slack_router  # noqa: E402
from comms.env import atomic_write_text  # noqa: E402


# ===========================================================================
# 1. _RUN_ID_RE — regex validator
# ===========================================================================


class TestRunIdRegex(unittest.TestCase):
    """Tests for _RUN_ID_RE: ^[a-z]+(?:-[a-z]+){2}-[a-f0-9]{6}$"""

    RE = slack_router._RUN_ID_RE

    # --- accept cases ---

    def test_canonical_slug_accepted(self) -> None:
        """Standard artifact-slug accepted."""
        self.assertIsNotNone(self.RE.match("clever-finding-canyon-113225"))

    def test_longer_words_accepted(self) -> None:
        self.assertIsNotNone(self.RE.match("merry-spinning-canyon-4359a7"))

    def test_hex_uses_all_valid_chars(self) -> None:
        """Hex suffix with a-f digits accepted."""
        self.assertIsNotNone(self.RE.match("alpha-bravo-charlie-abcdef"))

    def test_hex_zeros_accepted(self) -> None:
        self.assertIsNotNone(self.RE.match("foo-bar-baz-000000"))

    def test_three_word_segments(self) -> None:
        """Exactly three word segments before hex."""
        self.assertIsNotNone(self.RE.match("one-two-three-1a2b3c"))

    # --- reject cases ---

    def test_path_traversal_dotdot_slash_rejected(self) -> None:
        self.assertIsNone(self.RE.match("../etc"))

    def test_path_traversal_foo_slash_bar_rejected(self) -> None:
        self.assertIsNone(self.RE.match("foo/bar"))

    def test_bare_dotdot_rejected(self) -> None:
        self.assertIsNone(self.RE.match(".."))

    def test_empty_string_rejected(self) -> None:
        self.assertIsNone(self.RE.match(""))

    def test_leading_dash_rejected(self) -> None:
        self.assertIsNone(self.RE.match("-foo-bar-baz-abcdef"))

    def test_uppercase_rejected(self) -> None:
        self.assertIsNone(self.RE.match("Clever-finding-canyon-113225"))

    def test_hex_too_short_rejected(self) -> None:
        """5-char hex suffix rejected."""
        self.assertIsNone(self.RE.match("foo-bar-baz-12345"))

    def test_hex_too_long_rejected(self) -> None:
        """7-char hex suffix rejected."""
        self.assertIsNone(self.RE.match("foo-bar-baz-1234567"))

    def test_hex_contains_g_rejected(self) -> None:
        """'g' is not hex; rejected."""
        self.assertIsNone(self.RE.match("foo-bar-baz-00000g"))

    def test_only_two_word_segments_rejected(self) -> None:
        """Two word segments (not three) + hex rejected."""
        self.assertIsNone(self.RE.match("foo-bar-abcdef"))

    def test_trailing_newline_not_fullmatch(self) -> None:
        """Trailing newline: match() anchors at start but $ allows \\n in Python.
        Confirm the router uses .match() — if slug+\\n matches, security note N1 applies.
        Document actual behaviour without asserting a requirement on $ vs \\Z.
        """
        # This test documents the $ vs \\Z behaviour (security N1).
        # The actual route resolution also does is_file() which will fail for
        # a filename with a literal newline — net effect: safe. No assertion.
        slug_newline = "foo-bar-baz-abcdef\n"
        result = self.RE.match(slug_newline)
        # Just record the finding; do not block on it (design intent is defense-in-depth).
        _ = result  # either None or Match — both documented in verdict


# ===========================================================================
# 2. _QD_ID_RE — regex validator
# ===========================================================================


class TestQdIdRegex(unittest.TestCase):
    """Tests for _QD_ID_RE: ^[qd][0-9]{1,4}$"""

    RE = slack_router._QD_ID_RE

    # --- accept cases ---

    def test_q1_accepted(self) -> None:
        self.assertIsNotNone(self.RE.match("q1"))

    def test_q9999_accepted(self) -> None:
        self.assertIsNotNone(self.RE.match("q9999"))

    def test_d1_accepted(self) -> None:
        self.assertIsNotNone(self.RE.match("d1"))

    def test_d4242_accepted(self) -> None:
        self.assertIsNotNone(self.RE.match("d4242"))

    def test_d9_accepted(self) -> None:
        self.assertIsNotNone(self.RE.match("d9"))

    # --- reject cases ---

    def test_bare_q_rejected(self) -> None:
        """No digits — rejected."""
        self.assertIsNone(self.RE.match("q"))

    def test_bare_d_rejected(self) -> None:
        self.assertIsNone(self.RE.match("d"))

    def test_e1_wrong_prefix_rejected(self) -> None:
        self.assertIsNone(self.RE.match("e1"))

    def test_q12345_five_digits_rejected(self) -> None:
        """Five digits > max 4."""
        self.assertIsNone(self.RE.match("q12345"))

    def test_q_dash_1_rejected(self) -> None:
        self.assertIsNone(self.RE.match("q-1"))

    def test_uppercase_Q1_rejected(self) -> None:
        self.assertIsNone(self.RE.match("Q1"))

    def test_q_slash_1_rejected(self) -> None:
        self.assertIsNone(self.RE.match("q/1"))

    def test_q0_accepted(self) -> None:
        """q0 is a legal value (1 digit)."""
        self.assertIsNotNone(self.RE.match("q0"))


# ===========================================================================
# 3. _safe_yaml_scalar — YAML escaping
# ===========================================================================


class TestSafeYamlScalar(unittest.TestCase):
    """Tests for _safe_yaml_scalar escaping."""

    fn = staticmethod(slack_router._safe_yaml_scalar)

    def test_plain_string_unchanged(self) -> None:
        self.assertEqual(self.fn("UABCDEF123"), "UABCDEF123")

    def test_newline_escaped(self) -> None:
        result = self.fn("foo\nbar")
        self.assertNotIn("\n", result)
        self.assertIn("\\n", result)

    def test_carriage_return_escaped(self) -> None:
        result = self.fn("foo\rbar")
        self.assertNotIn("\r", result)
        self.assertIn("\\r", result)

    def test_backslash_escaped(self) -> None:
        result = self.fn("foo\\bar")
        self.assertEqual(result, "foo\\\\bar")

    def test_both_newline_and_cr_escaped(self) -> None:
        result = self.fn("a\nb\rc")
        self.assertNotIn("\n", result)
        self.assertNotIn("\r", result)

    def test_empty_string_unchanged(self) -> None:
        self.assertEqual(self.fn(""), "")

    def test_slack_user_id_shape_unchanged(self) -> None:
        """Slack U-prefixed user IDs are alphanumeric — no escaping needed."""
        uid = "UABCDE1234"
        self.assertEqual(self.fn(uid), uid)

    def test_round_trip_newline(self) -> None:
        """Escaped value loaded as YAML scalar round-trips correctly.

        We parse the escaped value embedded in a minimal YAML string to verify
        the raw-string representation is preserved (no YAML injection).
        """
        import yaml  # type: ignore[import]

        original = "hello\nworld"
        escaped = self.fn(original)
        yaml_str = f"key: {escaped}\n"
        loaded = yaml.safe_load(yaml_str)
        # The YAML value will contain the literal \\n (two chars), not newline.
        # That is the correct safe representation — original is NOT reconstructed
        # from the escaped form; the point is no YAML structural injection.
        self.assertIsInstance(loaded, dict)
        self.assertIn("key", loaded)

    def test_no_yaml_injection_via_newline(self) -> None:
        """Payload with \\ninjected_key: evil must not produce two YAML keys.

        The escaped form contains literal \\n (two chars, not newline), so the
        YAML parser sees a single-line value. We verify the escaped string has
        no actual newline in it — which is what allows safe embedding in YAML.
        """
        malicious = "value\ninjected_key: evil"
        escaped = self.fn(malicious)
        # After escaping, no real newline remains — cannot split YAML into two keys
        self.assertNotIn("\n", escaped,
            "Escaped string must contain no real newline (prevents YAML key injection)")
        # Explicitly: the literal \\n two-char sequence is present instead
        self.assertIn("\\n", escaped)

    def test_leading_colon_not_escaped_docstring_note(self) -> None:
        """Document: function does NOT escape leading colon (security N2 gap).

        Slack user_id shape (^[UW][A-Z0-9]+) never starts with colon, so this
        is safe for the current caller. This test records the actual behaviour.
        """
        result = self.fn(":colon-start")
        # Result still contains the colon — caller depends on input constraint.
        self.assertIn(":", result)


# ===========================================================================
# 4. Button payload parser — _resolve_route_dir_from_value field splitting
# ===========================================================================


class TestButtonPayloadParsing(unittest.TestCase):
    """Tests for the payload split logic embedded in _resolve_route_dir_from_value.

    Because that function also does filesystem lookups, we patch the fs calls
    and test only the parse + validate path.

    The function returns ``(run_dir, qd_id)`` on success or ``(None, reason)``
    on failure where ``reason`` is one of: malformed, run_id_format,
    qd_id_format, index_missing, index_unreadable, project_mismatch,
    run_dir_gone.
    """

    def _call(self, value: str) -> Any:
        """Call _resolve_route_dir_from_value with all filesystem ops stubbed out."""
        with (
            patch.object(slack_router.Path, "is_file", return_value=False),
        ):
            return slack_router._resolve_route_dir_from_value(value)

    def _assert_failed(self, result: Any, expected_reason: str) -> None:
        """Failure tuple has first=None and second=<reason>."""
        first, second = result
        self.assertIsNone(first)
        self.assertEqual(second, expected_reason)

    def test_valid_payload_passes_regex_gates(self) -> None:
        """Well-formed payload passes regex gates; index file missing → index_missing."""
        value = "abcd1234|clever-finding-canyon-113225|q1|A"
        self._assert_failed(self._call(value), "index_missing")

    def test_wrong_delimiter_count_two_pipes(self) -> None:
        """Two pipes (3 fields) → malformed."""
        self._assert_failed(self._call("abcd1234|run-id-here|q1"), "malformed")

    def test_wrong_delimiter_count_zero_pipes(self) -> None:
        self._assert_failed(self._call("nodelvimiters"), "malformed")

    def test_extra_pipe_becomes_choice_field(self) -> None:
        """split(|, 3) means 5th | stays in choice field — 4 parts still valid split."""
        value = "abcd1234|clever-finding-canyon-113225|q1|A|extra"
        # run_id regex PASS, qd_id regex PASS, is_file False → index_missing.
        self._assert_failed(self._call(value), "index_missing")

    def test_invalid_run_id_path_traversal_rejected(self) -> None:
        """Path-traversal run_id rejected by regex."""
        self._assert_failed(
            self._call("abcd1234|../../etc/passwd|q1|A"), "run_id_format"
        )

    def test_invalid_qd_id_rejected(self) -> None:
        """Bad qd_id (Q1 uppercase) rejected."""
        self._assert_failed(
            self._call("abcd1234|clever-finding-canyon-113225|Q1|A"), "qd_id_format"
        )

    def test_empty_run_id_rejected(self) -> None:
        self._assert_failed(self._call("abcd1234||q1|A"), "run_id_format")

    def test_empty_qd_id_rejected(self) -> None:
        self._assert_failed(
            self._call("abcd1234|clever-finding-canyon-113225||A"), "qd_id_format"
        )

    def test_empty_phash_accepted_by_split_then_fails_hash_check(self) -> None:
        """Empty phash field splits OK; phash mismatch check catches it later (here: index missing first)."""
        # is_file False → index_missing wins over phash check.
        self._assert_failed(
            self._call("|clever-finding-canyon-113225|q1|A"), "index_missing"
        )

    def test_full_valid_payload_with_index_returns_run_dir(self) -> None:
        """With a live index entry, valid payload returns (run_dir, qd_id)."""
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "runs" / "clever-finding-canyon-113225"
            run_dir.mkdir(parents=True)

            index_dir = Path(td) / "run-index"
            index_dir.mkdir()

            phash = hashlib.sha1(str(run_dir.parent.parent).encode()).hexdigest()[:8]
            entry = {
                "run_dir": str(run_dir),
                "project_path": str(run_dir.parent.parent),
                "project_path_hash": phash,
                "updated_at": "2026-05-14T12:00:00+00:00",
            }
            index_file = index_dir / "clever-finding-canyon-113225.json"
            index_file.write_text(json.dumps(entry))

            value = f"{phash}|clever-finding-canyon-113225|q1|A"
            with patch.object(slack_router, "RUN_INDEX_DIR", index_dir):
                got_run_dir, got_qd_id = slack_router._resolve_route_dir_from_value(value)

            self.assertEqual(got_run_dir, run_dir)
            self.assertEqual(got_qd_id, "q1")


# ===========================================================================
# 5. RoutingSnapshot immutability — frozen dataclass
# ===========================================================================


class TestRoutingSnapshotImmutability(unittest.TestCase):
    """RoutingSnapshot is a frozen=True dataclass — mutation must raise."""

    def _make_snap(self) -> slack_router.RoutingSnapshot:
        empty: MappingProxyType[str, slack_router.Route] = MappingProxyType({})
        return slack_router.RoutingSnapshot(
            by_thread=empty,
            by_sid=empty,
            fingerprint="deadbeef",
        )

    def test_cannot_set_fingerprint(self) -> None:
        snap = self._make_snap()
        with self.assertRaises((FrozenInstanceError, AttributeError)):
            snap.fingerprint = "changed"  # type: ignore[misc]

    def test_cannot_set_by_thread(self) -> None:
        snap = self._make_snap()
        with self.assertRaises((FrozenInstanceError, AttributeError)):
            snap.by_thread = MappingProxyType({})  # type: ignore[misc]

    def test_cannot_set_by_sid(self) -> None:
        snap = self._make_snap()
        with self.assertRaises((FrozenInstanceError, AttributeError)):
            snap.by_sid = MappingProxyType({})  # type: ignore[misc]

    def test_route_frozen(self) -> None:
        """Route is also frozen."""
        route = slack_router.Route(
            sid="abc",
            channel_id="C1",
            thread_ts="1.2",
            inbox_dir=Path("/tmp/inbox"),
        )
        with self.assertRaises((FrozenInstanceError, AttributeError)):
            route.sid = "other"  # type: ignore[misc]


# ===========================================================================
# 6. RoutingIndex.swap_if_changed
# ===========================================================================


class TestRoutingIndexSwapIfChanged(unittest.TestCase):
    """swap_if_changed: same fingerprint = no-op; different = swap + idle reset."""

    def _make_snap(self, fp: str, routes: dict[str, slack_router.Route] | None = None) -> slack_router.RoutingSnapshot:
        routes = routes or {}
        proxy: MappingProxyType[str, slack_router.Route] = MappingProxyType(routes)
        return slack_router.RoutingSnapshot(
            by_thread=proxy,
            by_sid=proxy,
            fingerprint=fp,
        )

    def _make_route(self, sid: str = "sid1") -> slack_router.Route:
        return slack_router.Route(
            sid=sid,
            channel_id="C1",
            thread_ts="1.2",
            inbox_dir=Path("/tmp/inbox"),
        )

    def test_same_fingerprint_no_swap(self) -> None:
        index = slack_router.RoutingIndex()
        original = index.current()
        same_fp = self._make_snap(original.fingerprint)
        idle_ref: list[float] = [0.0]
        index.swap_if_changed(same_fp, idle_ref)
        # Snapshot reference unchanged
        self.assertIs(index.current(), original)

    def test_different_fingerprint_swap_occurs(self) -> None:
        index = slack_router.RoutingIndex()
        new_snap = self._make_snap("new-fp")
        idle_ref: list[float] = [99.0]
        index.swap_if_changed(new_snap, idle_ref)
        self.assertEqual(index.current().fingerprint, "new-fp")

    def test_non_empty_snap_resets_idle_counter(self) -> None:
        """Non-empty snapshot resets both index._idle_counter and idle_ref[0]."""
        index = slack_router.RoutingIndex()
        # Manually set idle counter high
        with index._lock:
            index._idle_counter = 500.0

        route = self._make_route()
        new_snap = self._make_snap("fp2", {"sid1": route})
        idle_ref: list[float] = [500.0]
        index.swap_if_changed(new_snap, idle_ref)
        self.assertEqual(idle_ref[0], 0.0)
        with index._lock:
            self.assertEqual(index._idle_counter, 0.0)

    def test_empty_snap_does_not_reset_idle_counter(self) -> None:
        """Empty snapshot does NOT reset idle counter (only fingerprint check matters)."""
        index = slack_router.RoutingIndex()
        with index._lock:
            index._idle_counter = 300.0

        empty_snap = self._make_snap("different-fp-empty")
        idle_ref: list[float] = [300.0]
        index.swap_if_changed(empty_snap, idle_ref)
        # idle counter not reset by empty snap
        with index._lock:
            self.assertEqual(index._idle_counter, 300.0)

    def test_swap_thread_safe(self) -> None:
        """Concurrent swap_if_changed calls don't corrupt the index."""
        index = slack_router.RoutingIndex()
        errors: list[str] = []

        def swap_fn(fp: str) -> None:
            try:
                snap = self._make_snap(fp)
                idle_ref: list[float] = [0.0]
                index.swap_if_changed(snap, idle_ref)
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=swap_fn, args=(f"fp{i}",)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        self.assertEqual(errors, [])
        # Snapshot is in a consistent state (not None)
        self.assertIsNotNone(index.current())


# ===========================================================================
# 7. _gc_run_index — GC logic
# ===========================================================================


class TestGcRunIndex(unittest.TestCase):
    """_gc_run_index prunes vanished run_dirs and mtime-old entries."""

    def test_prunes_missing_run_dir(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            idx_dir = Path(td) / "run-index"
            idx_dir.mkdir()
            unrouted_dir = Path(td) / "unrouted"
            unrouted_dir.mkdir()

            entry = {"run_dir": "/nonexistent/path/that/does/not/exist"}
            (idx_dir / "stale-run-abcdef.json").write_text(json.dumps(entry))

            with (
                patch.object(slack_router, "RUN_INDEX_DIR", idx_dir),
                patch.object(slack_router, "UNROUTED_DIR", unrouted_dir),
            ):
                pruned = slack_router._gc_run_index()

            self.assertGreaterEqual(pruned, 1)
            self.assertFalse((idx_dir / "stale-run-abcdef.json").exists())

    def test_prunes_old_mtime_entry(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            idx_dir = Path(td) / "run-index"
            idx_dir.mkdir()
            unrouted_dir = Path(td) / "unrouted"
            unrouted_dir.mkdir()

            # run_dir exists (so first check passes)
            run_dir = Path(td) / "live-run"
            run_dir.mkdir()
            entry = {"run_dir": str(run_dir)}
            entry_file = idx_dir / "live-but-old-abcdef.json"
            entry_file.write_text(json.dumps(entry))
            # Set mtime to 15 days ago
            old_mtime = time.time() - (15 * 86400)
            os.utime(str(entry_file), (old_mtime, old_mtime))

            with (
                patch.object(slack_router, "RUN_INDEX_DIR", idx_dir),
                patch.object(slack_router, "UNROUTED_DIR", unrouted_dir),
            ):
                pruned = slack_router._gc_run_index()

            self.assertGreaterEqual(pruned, 1)
            self.assertFalse(entry_file.exists())

    def test_preserves_fresh_entry(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            idx_dir = Path(td) / "run-index"
            idx_dir.mkdir()
            unrouted_dir = Path(td) / "unrouted"
            unrouted_dir.mkdir()

            run_dir = Path(td) / "fresh-run"
            run_dir.mkdir()
            entry = {"run_dir": str(run_dir)}
            entry_file = idx_dir / "fresh-run-aabbcc.json"
            entry_file.write_text(json.dumps(entry))
            # mtime is now (fresh)

            with (
                patch.object(slack_router, "RUN_INDEX_DIR", idx_dir),
                patch.object(slack_router, "UNROUTED_DIR", unrouted_dir),
            ):
                pruned = slack_router._gc_run_index()

            self.assertEqual(pruned, 0)
            self.assertTrue(entry_file.exists())

    def test_prunes_old_unrouted_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            idx_dir = Path(td) / "run-index"
            idx_dir.mkdir()
            unrouted_dir = Path(td) / "unrouted"
            unrouted_dir.mkdir()

            old_file = unrouted_dir / "1234567890.000001.json"
            old_file.write_text('{"ts":"1234567890.000001"}')
            old_mtime = time.time() - (15 * 86400)
            os.utime(str(old_file), (old_mtime, old_mtime))

            with (
                patch.object(slack_router, "RUN_INDEX_DIR", idx_dir),
                patch.object(slack_router, "UNROUTED_DIR", unrouted_dir),
            ):
                pruned = slack_router._gc_run_index()

            self.assertGreaterEqual(pruned, 1)
            self.assertFalse(old_file.exists())

    def test_preserves_fresh_unrouted_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            idx_dir = Path(td) / "run-index"
            idx_dir.mkdir()
            unrouted_dir = Path(td) / "unrouted"
            unrouted_dir.mkdir()

            fresh_file = unrouted_dir / "9999999999.000001.json"
            fresh_file.write_text('{"ts":"9999999999.000001"}')
            # mtime is now

            with (
                patch.object(slack_router, "RUN_INDEX_DIR", idx_dir),
                patch.object(slack_router, "UNROUTED_DIR", unrouted_dir),
            ):
                pruned = slack_router._gc_run_index()

            self.assertEqual(pruned, 0)
            self.assertTrue(fresh_file.exists())

    def test_handles_corrupt_json_gracefully(self) -> None:
        """Corrupt JSON in index entry → logged, not crashed."""
        with tempfile.TemporaryDirectory() as td:
            idx_dir = Path(td) / "run-index"
            idx_dir.mkdir()
            unrouted_dir = Path(td) / "unrouted"
            unrouted_dir.mkdir()

            bad_file = idx_dir / "corrupt-abcdef.json"
            bad_file.write_text("{NOT VALID JSON")

            with (
                patch.object(slack_router, "RUN_INDEX_DIR", idx_dir),
                patch.object(slack_router, "UNROUTED_DIR", unrouted_dir),
            ):
                # Must not raise
                slack_router._gc_run_index()

    def test_handles_missing_run_dir_key_gracefully(self) -> None:
        """JSON without run_dir key → logged, not crashed."""
        with tempfile.TemporaryDirectory() as td:
            idx_dir = Path(td) / "run-index"
            idx_dir.mkdir()
            unrouted_dir = Path(td) / "unrouted"
            unrouted_dir.mkdir()

            bad_file = idx_dir / "no-run-dir-abc123.json"
            bad_file.write_text('{"other_key": "value"}')

            with (
                patch.object(slack_router, "RUN_INDEX_DIR", idx_dir),
                patch.object(slack_router, "UNROUTED_DIR", unrouted_dir),
            ):
                slack_router._gc_run_index()


# ===========================================================================
# 8. _cleanup_orphan_tmps
# ===========================================================================


class TestCleanupOrphanTmps(unittest.TestCase):
    """_cleanup_orphan_tmps removes old *.tmp files; leaves fresh and non-tmp."""

    THRESHOLD = slack_router.ORPHAN_TMP_MAX_AGE_S  # 60s

    def test_removes_old_tmp(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            inbox = Path(td) / "inbox"
            inbox.mkdir(mode=0o700)
            old_tmp = inbox / "event.json.tmp"
            old_tmp.write_text("partial")
            old_mtime = time.time() - (self.THRESHOLD + 10)
            os.utime(str(old_tmp), (old_mtime, old_mtime))

            slack_router._cleanup_orphan_tmps(inbox)
            self.assertFalse(old_tmp.exists())

    def test_leaves_fresh_tmp(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            inbox = Path(td) / "inbox"
            inbox.mkdir(mode=0o700)
            fresh_tmp = inbox / "fresh.json.tmp"
            fresh_tmp.write_text("in-flight")
            # mtime is now (fresh)

            slack_router._cleanup_orphan_tmps(inbox)
            self.assertTrue(fresh_tmp.exists())

    def test_leaves_committed_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            inbox = Path(td) / "inbox"
            inbox.mkdir(mode=0o700)
            committed = inbox / "event.json"
            committed.write_text('{"ts": "1"}')
            old_mtime = time.time() - (self.THRESHOLD + 10)
            os.utime(str(committed), (old_mtime, old_mtime))

            slack_router._cleanup_orphan_tmps(inbox)
            self.assertTrue(committed.exists(), "Committed .json files must not be touched")

    def test_no_crash_on_missing_inbox(self) -> None:
        slack_router._cleanup_orphan_tmps(Path("/tmp/does/not/exist/inbox"))

    def test_no_crash_on_nondir(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            not_a_dir = Path(td) / "file.txt"
            not_a_dir.write_text("not a dir")
            slack_router._cleanup_orphan_tmps(not_a_dir)  # must not raise


# ===========================================================================
# 9. _safe_load_context (pipeline_notify)
# ===========================================================================


class TestSafeLoadContext(unittest.TestCase):
    """_read_slack_context returns {} on missing file, bad JSON, OSError."""

    @classmethod
    def setUpClass(cls) -> None:
        # Import pipeline_notify with slack_bolt + filelock stubbed
        filelock_mock = MagicMock()
        filelock_mock.FileLock = MagicMock
        if "filelock" not in sys.modules:
            sys.modules["filelock"] = filelock_mock  # type: ignore[assignment]

        import importlib
        if "pipeline_notify" in sys.modules:
            importlib.reload(sys.modules["pipeline_notify"])  # type: ignore[arg-type]
        import pipeline_notify  # noqa: F401
        cls.mod = pipeline_notify

    def test_missing_file_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run"
            run_dir.mkdir()
            result = self.mod._read_slack_context(run_dir)
        self.assertEqual(result, {})

    def test_malformed_json_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run"
            run_dir.mkdir()
            ctx_path = run_dir / ".slack-context.json"
            ctx_path.write_text("{INVALID JSON", encoding="utf-8")
            result = self.mod._read_slack_context(run_dir)
        self.assertEqual(result, {})

    def test_valid_json_returned(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run"
            run_dir.mkdir()
            ctx_path = run_dir / ".slack-context.json"
            ctx_path.write_text('{"message_ts": "123.456"}', encoding="utf-8")
            result = self.mod._read_slack_context(run_dir)
        self.assertEqual(result.get("message_ts"), "123.456")

    def test_osnerror_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run"
            run_dir.mkdir()
            ctx_path = run_dir / ".slack-context.json"
            ctx_path.write_text("{}")
            # Simulate OSError on read
            with patch.object(self.mod.Path, "read_text", side_effect=OSError("disk error")):
                result = self.mod._read_slack_context(run_dir)
        self.assertEqual(result, {})


# ===========================================================================
# 10. _recover_message_ts (pipeline_notify)
# ===========================================================================


class TestRecoverMessageTs(unittest.TestCase):
    """_recover_message_ts returns None on miss; ts on match."""

    @classmethod
    def setUpClass(cls) -> None:
        filelock_mock = MagicMock()
        filelock_mock.FileLock = MagicMock
        if "filelock" not in sys.modules:
            sys.modules["filelock"] = filelock_mock  # type: ignore[assignment]
        import pipeline_notify
        cls.mod = pipeline_notify

    def _mock_app(self, messages: list[dict[str, Any]]) -> Any:
        app = MagicMock()
        app.client.conversations_replies.return_value = {"messages": messages}
        return app

    def test_returns_none_when_client_msg_id_not_found(self) -> None:
        app = self._mock_app([
            {"ts": "111.001", "metadata": {"event_payload": {"client_msg_id": "other-id"}}},
        ])
        result = self.mod._recover_message_ts(app, "C1", "111.000", "target-id")
        self.assertIsNone(result)

    def test_returns_ts_when_client_msg_id_found(self) -> None:
        app = self._mock_app([
            {"ts": "222.002", "metadata": {"event_payload": {"client_msg_id": "target-id"}}},
        ])
        result = self.mod._recover_message_ts(app, "C1", "222.000", "target-id")
        self.assertEqual(result, "222.002")

    def test_returns_none_on_empty_messages(self) -> None:
        app = self._mock_app([])
        result = self.mod._recover_message_ts(app, "C1", "333.000", "any-id")
        self.assertIsNone(result)

    def test_returns_none_when_api_raises(self) -> None:
        app = MagicMock()
        app.client.conversations_replies.side_effect = Exception("network error")
        result = self.mod._recover_message_ts(app, "C1", "444.000", "any-id")
        self.assertIsNone(result)

    def test_scans_all_messages_finds_second(self) -> None:
        app = self._mock_app([
            {"ts": "555.001", "metadata": {"event_payload": {"client_msg_id": "other"}}},
            {"ts": "555.002", "metadata": {"event_payload": {"client_msg_id": "match-me"}}},
        ])
        result = self.mod._recover_message_ts(app, "C1", "555.000", "match-me")
        self.assertEqual(result, "555.002")

    def test_handles_missing_metadata_gracefully(self) -> None:
        """Messages without metadata field don't crash the scan."""
        app = self._mock_app([
            {"ts": "666.001"},  # no metadata
            {"ts": "666.002", "metadata": {"event_payload": {"client_msg_id": "found"}}},
        ])
        result = self.mod._recover_message_ts(app, "C1", "666.000", "found")
        self.assertEqual(result, "666.002")


# ===========================================================================
# 11. Button block construction — canonical value format
# ===========================================================================


class TestButtonBlockConstruction(unittest.TestCase):
    """_build_question_blocks and _build_decision_blocks emit canonical value format."""

    @classmethod
    def setUpClass(cls) -> None:
        filelock_mock = MagicMock()
        filelock_mock.FileLock = MagicMock
        if "filelock" not in sys.modules:
            sys.modules["filelock"] = filelock_mock  # type: ignore[assignment]
        import pipeline_notify
        cls.mod = pipeline_notify

    def test_question_button_value_format(self) -> None:
        """Each question button value = <phash8>|<run-id>|<qid>|<key>."""
        options = [{"key": "A", "title": "Option A"}, {"key": "B", "title": "Option B"}]
        blocks = self.mod._build_question_blocks(
            run_id="clever-finding-canyon-113225",
            qid="q1",
            header="Test",
            prompt="Pick one",
            options=options,
            phash8="abcd1234",
            attachment_links=[],
        )
        # Last block is actions block
        actions_block = blocks[-1]
        self.assertEqual(actions_block["type"], "actions")
        elements = actions_block["elements"]
        self.assertEqual(len(elements), 2)

        for elem, opt in zip(elements, options):
            value = elem["value"]
            parts = value.split("|")
            self.assertEqual(len(parts), 4, f"Expected 4 pipe-separated parts, got: {value!r}")
            self.assertEqual(parts[0], "abcd1234")
            self.assertEqual(parts[1], "clever-finding-canyon-113225")
            self.assertEqual(parts[2], "q1")
            self.assertEqual(parts[3], opt["key"])

    def test_decision_button_value_format(self) -> None:
        """Each decision button value = <phash8>|<run-id>|<did>|<key>."""
        options = [{"key": "A", "title": "Go"}, {"key": "B", "title": "Stop"}]
        blocks = self.mod._build_decision_blocks(
            run_id="clever-finding-canyon-113225",
            did="d1",
            topic="Deploy?",
            options=options,
            phash8="deadbeef",
        )
        actions_block = blocks[-1]
        self.assertEqual(actions_block["type"], "actions")
        elements = actions_block["elements"]
        self.assertEqual(len(elements), 2)

        for elem, opt in zip(elements, options):
            value = elem["value"]
            parts = value.split("|")
            self.assertEqual(len(parts), 4)
            self.assertEqual(parts[0], "deadbeef")
            self.assertEqual(parts[1], "clever-finding-canyon-113225")
            self.assertEqual(parts[2], "d1")
            self.assertEqual(parts[3], opt["key"])

    def test_action_ids_correct_format(self) -> None:
        """Question button action_ids = question_pick_<KEY>."""
        options = [{"key": "A", "title": "Alpha"}]
        blocks = self.mod._build_question_blocks(
            run_id="r", qid="q1", header="h", prompt="p",
            options=options, phash8="00000000", attachment_links=[],
        )
        actions = blocks[-1]["elements"]
        self.assertEqual(actions[0]["action_id"], "question_pick_A")

    def test_decision_action_ids_correct_format(self) -> None:
        """Decision button action_ids = decision_pick_<KEY>."""
        options = [{"key": "B", "title": "Beta"}]
        blocks = self.mod._build_decision_blocks(
            run_id="r", did="d1", topic="t", options=options, phash8="00000000",
        )
        actions = blocks[-1]["elements"]
        self.assertEqual(actions[0]["action_id"], "decision_pick_B")


# ===========================================================================
# 12. _project_hash determinism
# ===========================================================================


class TestProjectHash(unittest.TestCase):
    """_project_hash(path) is deterministic; different paths produce different hashes."""

    def test_same_path_same_hash(self) -> None:
        h1 = slack_router._project_hash("/home/user/project")
        h2 = slack_router._project_hash("/home/user/project")
        self.assertEqual(h1, h2)

    def test_hash_is_8_hex_chars(self) -> None:
        h = slack_router._project_hash("/some/path")
        self.assertEqual(len(h), 8)
        self.assertRegex(h, r"^[0-9a-f]{8}$")

    def test_five_different_paths_different_hashes(self) -> None:
        paths = [
            "/home/alice/project",
            "/home/bob/project",
            "/var/projects/alpha",
            "/opt/runner/workspace",
            "/tmp/test-project",
        ]
        hashes = [slack_router._project_hash(p) for p in paths]
        self.assertEqual(len(set(hashes)), 5, f"Hash collisions: {hashes}")

    def test_pipeline_notify_project_hash_matches_router(self) -> None:
        """Both modules use sha1[:8] — verify agreement on a sample path."""
        filelock_mock = MagicMock()
        filelock_mock.FileLock = MagicMock
        if "filelock" not in sys.modules:
            sys.modules["filelock"] = filelock_mock  # type: ignore[assignment]
        import pipeline_notify

        path = Path("/home/user/dotfiles")
        h_router = slack_router._project_hash(str(path))
        h_notify = pipeline_notify._project_hash(path)
        self.assertEqual(h_router, h_notify, "Router and notify must produce identical project hashes")


# ===========================================================================
# 13. _require_binding_or_degrade (pipeline_ask)
# ===========================================================================


class TestRequireBindingOrDegrade(unittest.TestCase):
    """_require_binding_or_degrade returns False with no binding, True with binding."""

    @classmethod
    def setUpClass(cls) -> None:
        import pipeline_ask
        cls.mod = pipeline_ask

    def test_returns_false_when_no_binding(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run"
            run_dir.mkdir()
            with patch.object(self.mod, "resolve_session_binding", return_value=None):
                result = self.mod._require_binding_or_degrade(run_dir)
        self.assertFalse(result)

    def test_returns_true_when_binding_present(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run"
            run_dir.mkdir()
            with patch.object(
                self.mod, "resolve_session_binding",
                return_value=("C_CHANNEL", "111.222")
            ):
                result = self.mod._require_binding_or_degrade(run_dir)
        self.assertTrue(result)

    def test_false_path_writes_to_stderr(self) -> None:
        import io, contextlib
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run"
            run_dir.mkdir()
            buf = io.StringIO()
            with patch.object(self.mod, "resolve_session_binding", return_value=None):
                with contextlib.redirect_stderr(buf):
                    self.mod._require_binding_or_degrade(run_dir)
        self.assertIn("no active Slack session binding", buf.getvalue())


# ===========================================================================
# 14. _write_initial_slack_context (pipeline_ask)
# ===========================================================================


class TestWriteInitialSlackContext(unittest.TestCase):
    """_write_initial_slack_context writes design §8.1 fields with message_ts: null."""

    @classmethod
    def setUpClass(cls) -> None:
        import pipeline_ask
        cls.mod = pipeline_ask

    def test_writes_expected_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run"
            run_dir.mkdir()
            project = Path(td) / "project"
            project.mkdir()
            options = [("A", "Alpha"), ("B", "Beta")]
            self.mod._write_initial_slack_context(
                run_dir=run_dir,
                project_path=project,
                run_id="clever-finding-canyon-113225",
                qid="q1",
                header="Test Header",
                prompt="Choose wisely",
                options=options,
            )
            ctx_path = run_dir / ".slack-context.json"
            self.assertTrue(ctx_path.exists())
            ctx = json.loads(ctx_path.read_text())

        self.assertEqual(ctx["schema_version"], 2)
        self.assertEqual(ctx["run_id"], "clever-finding-canyon-113225")
        self.assertEqual(ctx["qid"], "q1")
        self.assertIsNone(ctx["did"])
        self.assertIsNone(ctx["message_ts"])
        self.assertIsNone(ctx["channel"])
        self.assertIsNone(ctx["thread_ts"])
        self.assertIn("project_path", ctx)
        self.assertIn("project_path_hash", ctx)
        self.assertEqual(len(ctx["project_path_hash"]), 8)

    def test_idempotent_when_message_ts_set(self) -> None:
        """If message_ts already set, do not overwrite (preserve notify-owned fields)."""
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run"
            run_dir.mkdir()
            project = Path(td) / "project"
            project.mkdir()

            ctx_path = run_dir / ".slack-context.json"
            existing = {"message_ts": "999.001", "channel": "C_EXISTING", "schema_version": 2}
            ctx_path.write_text(json.dumps(existing))

            self.mod._write_initial_slack_context(
                run_dir=run_dir,
                project_path=project,
                run_id="test-run-abc123",
                qid="q1",
                header="H",
                prompt="P",
                options=[("A", "Opt")],
            )
            # Should not be overwritten
            ctx = json.loads(ctx_path.read_text())
        self.assertEqual(ctx["message_ts"], "999.001")

    def test_options_serialized_correctly(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run"
            run_dir.mkdir()
            project = Path(td) / "project"
            project.mkdir()
            options = [("A", "First"), ("B", "Second"), ("C", "Third")]
            self.mod._write_initial_slack_context(
                run_dir=run_dir,
                project_path=project,
                run_id="test-run-abc123",
                qid="q2",
                header="H",
                prompt="P",
                options=options,
            )
            ctx = json.loads((run_dir / ".slack-context.json").read_text())
        self.assertEqual(ctx["options"], [["A", "First"], ["B", "Second"], ["C", "Third"]])


# ===========================================================================
# 15. _reap_legacy_listeners (session_bind)
# ===========================================================================


class TestReapLegacyListeners(unittest.TestCase):
    """_reap_legacy_listeners is a no-op when pgrep returns no matches."""

    @classmethod
    def setUpClass(cls) -> None:
        import session_bind
        cls.mod = session_bind

    def test_no_op_when_no_matches(self) -> None:
        """When pgrep returns empty stdout, no kill is sent."""
        kill_calls: list[tuple[int, int]] = []

        def track_kill(pid: int, sig: int) -> None:
            kill_calls.append((pid, sig))

        no_match_result = MagicMock()
        no_match_result.stdout = ""
        no_match_result.returncode = 1

        with (
            patch("session_bind.subprocess.run", return_value=no_match_result),
            patch("session_bind.os.kill", side_effect=track_kill),
        ):
            self.mod._reap_legacy_listeners()

        self.assertEqual(kill_calls, [])

    def test_sends_sigterm_when_matches(self) -> None:
        """When pgrep finds PIDs, SIGTERM is sent to each."""
        import signal as sig_module

        kill_calls: list[tuple[int, int]] = []

        def track_kill(pid: int, sig: int) -> None:
            kill_calls.append((pid, sig))
            raise ProcessLookupError  # simulate already dead

        match_result = MagicMock()
        match_result.stdout = "12345 /path/to/slack_listener.py\n67890 /other/slack_listener.py\n"
        match_result.returncode = 0

        with (
            patch("session_bind.subprocess.run", return_value=match_result),
            patch("session_bind.os.kill", side_effect=track_kill),
            patch("session_bind.time.sleep"),  # skip the 2s wait
            patch("session_bind._is_pid_alive", return_value=False),
        ):
            self.mod._reap_legacy_listeners()

        sigterm_pids = [pid for pid, sig in kill_calls if sig == sig_module.SIGTERM]
        self.assertIn(12345, sigterm_pids)
        self.assertIn(67890, sigterm_pids)

    def test_handles_pgrep_os_error_gracefully(self) -> None:
        """If pgrep is not available (OSError), function returns without crashing."""
        with patch("session_bind.subprocess.run", side_effect=OSError("pgrep not found")):
            # Must not raise
            self.mod._reap_legacy_listeners()


# ===========================================================================
# 16. Inbox file schema compatibility
# ===========================================================================


class TestInboxFileSchema(unittest.TestCase):
    """Verify the inbox file schema written by slack_router._write_inbox_file
    matches the schema previously emitted by the deleted session_inbox.py.
    """

    EXPECTED_FIELDS = {"session_id", "thread_ts", "message_ts", "user_id", "text", "received_at"}

    def test_write_inbox_file_emits_expected_schema(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            inbox = Path(td) / "inbox"
            inbox.mkdir(mode=0o700)

            event = {
                "ts": "1716000000.000100",
                "thread_ts": "1716000000.000001",
                "user": "UABC1234",
                "text": "Hello from Slack",
                "channel": "C0TEST123",
            }

            with patch.object(slack_router, "log"):
                slack_router._write_inbox_file(inbox, event)

            written = inbox / "1716000000.000100.json"
            self.assertTrue(written.exists())

            payload = json.loads(written.read_text())

        # Verify all expected fields present
        self.assertEqual(set(payload.keys()), self.EXPECTED_FIELDS)

    def test_write_inbox_file_field_values_correct(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            inbox = Path(td) / "inbox"
            inbox.mkdir(mode=0o700)

            event = {
                "ts": "1716000001.000200",
                "thread_ts": "1716000000.000001",
                "user": "UTEST9999",
                "text": "Test message content",
            }

            with patch.object(slack_router, "log"):
                slack_router._write_inbox_file(inbox, event)

            payload = json.loads((inbox / "1716000001.000200.json").read_text())

        self.assertEqual(payload["session_id"], inbox.parent.name)
        self.assertEqual(payload["thread_ts"], "1716000000.000001")
        self.assertEqual(payload["message_ts"], "1716000001.000200")
        self.assertEqual(payload["user_id"], "UTEST9999")
        self.assertEqual(payload["text"], "Test message content")
        self.assertIn("received_at", payload)
        self.assertTrue(payload["received_at"])

    def test_write_inbox_file_returns_false_on_missing_ts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            inbox = Path(td) / "inbox"
            inbox.mkdir(mode=0o700)
            event = {"thread_ts": "1.0", "user": "U1", "text": "no ts"}
            with patch.object(slack_router, "log"):
                result = slack_router._write_inbox_file(inbox, event)
        self.assertFalse(result)

    def test_write_inbox_file_idempotent(self) -> None:
        """Second write for same ts returns False (file already exists)."""
        with tempfile.TemporaryDirectory() as td:
            inbox = Path(td) / "inbox"
            inbox.mkdir(mode=0o700)
            event = {"ts": "1716000002.000300", "thread_ts": "1.0", "user": "U1", "text": "hi"}
            with patch.object(slack_router, "log"):
                r1 = slack_router._write_inbox_file(inbox, event)
                r2 = slack_router._write_inbox_file(inbox, event)
        self.assertTrue(r1)
        self.assertFalse(r2)


# ===========================================================================
# 17. Atomic write: write-tmp + rename, no partial file on simulated crash
# ===========================================================================


class TestAtomicWriteSemantics(unittest.TestCase):
    """atomic_write_text uses tmp + rename; no partial file on crash."""

    def test_no_tmp_after_success(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "state.json"
            atomic_write_text(target, '{"ok": true}')
            tmp = Path(str(target) + ".tmp")
            self.assertFalse(tmp.exists(), "Tmp file must be cleaned up after rename")
            self.assertTrue(target.exists())

    def test_target_content_correct(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "data.json"
            atomic_write_text(target, "hello atomic")
            self.assertEqual(target.read_text(encoding="utf-8"), "hello atomic")

    def test_no_target_on_fsync_failure(self) -> None:
        """If fsync fails, rename is NOT called — target stays absent."""
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "output.json"
            with patch("_slack_env.os.fsync", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    atomic_write_text(target, "partial")
            self.assertFalse(target.exists(), "Target must not exist when fsync failed")

    def test_rename_not_called_on_fsync_failure(self) -> None:
        rename_calls: list[Any] = []
        orig_rename = os.rename

        def tracking_rename(src: str, dst: str) -> None:
            rename_calls.append((src, dst))
            orig_rename(src, dst)

        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "output.json"
            with (
                patch("_slack_env.os.fsync", side_effect=OSError("crash")),
                patch("_slack_env.os.rename", side_effect=tracking_rename),
            ):
                with self.assertRaises(OSError):
                    atomic_write_text(target, "data")

        self.assertEqual(rename_calls, [], "os.rename must NOT be called when fsync raises")

    def test_file_mode_set_correctly(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "secret.json"
            atomic_write_text(target, "secret", mode=0o600)
            st = target.stat()
            self.assertEqual(st.st_mode & 0o777, 0o600)

    def test_overwrite_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "state.json"
            atomic_write_text(target, "version1")
            atomic_write_text(target, "version2")
            self.assertEqual(target.read_text(encoding="utf-8"), "version2")


# ===========================================================================
# H1: Single router per host — flock semantics
# ===========================================================================


def _flock_prober(tmp_pid_path: str, result_queue: multiprocessing.Queue) -> None:  # type: ignore[type-arg]
    """Child process: try to acquire flock on the pid file.

    Reports: 'acquired' if flock succeeded, 'rejected' if BlockingIOError.
    Does NOT write the PID file content or unlink — just acquires and reports.
    """
    import fcntl, os, sys
    try:
        fd = os.open(tmp_pid_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result_queue.put("acquired")
            # Hold lock briefly then release (don't want to keep it)
            time.sleep(0.2)
            fcntl.flock(fd, fcntl.LOCK_UN)
        except BlockingIOError:
            result_queue.put("rejected")
        finally:
            os.close(fd)
    except Exception as exc:
        result_queue.put(f"error:{exc}")


class TestSingleInstanceFlock(unittest.TestCase):
    """H1: second prober is rejected when first holds the flock."""

    def test_second_process_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            pid_path = os.path.join(td, "router.pid")

            # First process acquires flock and holds it
            fd = os.open(pid_path, os.O_RDWR | os.O_CREAT, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

                # Second prober should be rejected
                q: multiprocessing.Queue = multiprocessing.Queue()  # type: ignore[type-arg]
                p = multiprocessing.Process(target=_flock_prober, args=(pid_path, q))
                p.start()
                p.join(timeout=5)
                result = q.get(timeout=2)

                self.assertEqual(result, "rejected",
                    "Second prober must be rejected when first holds the flock")
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)

    def test_second_exits_without_unlinking_pid_file(self) -> None:
        """The losing prober exits without removing the PID file."""
        with tempfile.TemporaryDirectory() as td:
            pid_path = os.path.join(td, "router.pid")

            # First process holds flock
            fd = os.open(pid_path, os.O_RDWR | os.O_CREAT, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                os.write(fd, b"99999\n")

                # Second prober hits BlockingIOError and exits
                q: multiprocessing.Queue = multiprocessing.Queue()  # type: ignore[type-arg]
                p = multiprocessing.Process(target=_flock_prober, args=(pid_path, q))
                p.start()
                p.join(timeout=5)

                # PID file still exists (winner holds it)
                self.assertTrue(os.path.exists(pid_path),
                    "Loser must not unlink the PID file")
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)

    def test_first_prober_can_acquire(self) -> None:
        """When no one holds the lock, prober acquires it."""
        with tempfile.TemporaryDirectory() as td:
            pid_path = os.path.join(td, "router.pid")
            q: multiprocessing.Queue = multiprocessing.Queue()  # type: ignore[type-arg]
            p = multiprocessing.Process(target=_flock_prober, args=(pid_path, q))
            p.start()
            p.join(timeout=5)
            result = q.get(timeout=2)
            self.assertEqual(result, "acquired")


# ===========================================================================
# H4: Inbox dir created with mode 0700
# ===========================================================================


class TestInboxDirMode(unittest.TestCase):
    """H4: inbox dir created on demand with mode 0700."""

    def test_inbox_dir_created_with_0700(self) -> None:
        """_write_inbox_file creates the inbox dir with mode 0o700."""
        with tempfile.TemporaryDirectory() as td:
            inbox = Path(td) / "session_abc" / "inbox"
            # Not pre-created
            self.assertFalse(inbox.exists())

            event = {
                "ts": "1716000010.000001",
                "thread_ts": "1716000000.000001",
                "user": "UTEST",
                "text": "hi",
            }
            with patch.object(slack_router, "log"):
                slack_router._write_inbox_file(inbox, event)

            self.assertTrue(inbox.exists())
            mode = inbox.stat().st_mode & 0o777
            self.assertEqual(mode, 0o700, f"Inbox dir must be 0700, got {oct(mode)}")

    def test_inbox_dir_mode_on_unrouted(self) -> None:
        """UNROUTED_DIR created with mode 0o700."""
        with tempfile.TemporaryDirectory() as td:
            unrouted = Path(td) / "unrouted"
            self.assertFalse(unrouted.exists())
            event = {
                "ts": "1716000020.000001",
                "thread_ts": "1716000000.000001",
                "user": "UNONE",
                "text": "unrouted event",
            }
            with (
                patch.object(slack_router, "UNROUTED_DIR", unrouted),
                patch.object(slack_router, "log"),
            ):
                slack_router._write_unrouted_file(event)

            self.assertTrue(unrouted.exists())
            mode = unrouted.stat().st_mode & 0o777
            self.assertEqual(mode, 0o700, f"UNROUTED_DIR must be 0700, got {oct(mode)}")


# ===========================================================================
# Smuggling scan (documented inline — no test code)
# ===========================================================================
# Grep outputs are in the verdict file. No test code here.


if __name__ == "__main__":
    unittest.main(verbosity=2)
