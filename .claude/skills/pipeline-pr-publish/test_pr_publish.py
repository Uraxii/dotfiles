"""Tests for pr-publish.py — stdlib unittest."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent / "pr-publish.py"


def make_pipeline_md(
    run_id: str = "test-run-abc123",
    base_ref: str = "main",
    base_sha: str = "abc123def456",
    github_delivery: str = "pr",
    shards: dict | None = None,
) -> str:
    if shards is None:
        shards = {
            "s1": {
                "status": "passed",
                "branch": f"pipeline/{run_id}/s1",
                "worktree": f"/tmp/{run_id}/worktrees/s1",
                "evidence": f"build-evidence-r1-s1.md",
                "depends_on": [],
            }
        }
    shards_yaml = ""
    for sid, s in shards.items():
        deps = json.dumps(s.get("depends_on", []))
        shards_yaml += (
            f"  {sid}: {{status: {s['status']}, "
            f"branch: {s['branch']}, "
            f"worktree: {s['worktree']}, "
            f"evidence: {s.get('evidence', 'null')}, "
            f"depends_on: {deps}}}\n"
        )
    return (
        f"---\n"
        f"run_id: {run_id}\n"
        f"plan_id: {run_id}\n"
        f"brief: test pipeline\n"
        f"roles_included: [build]\n"
        f"base_ref: {base_ref}\n"
        f"base_sha: {base_sha}\n"
        f"github_delivery: {github_delivery}\n"
        f"shards:\n{shards_yaml}"
        f"---\n\n## Stages\n- build: complete\n"
    )


def run_script(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


class TestPrPublishHelp(unittest.TestCase):

    def test_help_exits_zero(self) -> None:
        r = run_script("--help")
        self.assertEqual(r.returncode, 0, r.stderr)
        combined = r.stdout.lower() + r.stderr.lower()
        self.assertTrue("pr-publish" in combined or "usage" in combined)


class TestPrPublishValidInput(unittest.TestCase):

    def _write_pipeline_md(self, content: str) -> str:
        with tempfile.NamedTemporaryFile(
            suffix=".md", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            return f.name

    def test_valid_k1_exits_zero_with_json(self) -> None:
        path = self._write_pipeline_md(make_pipeline_md())
        r = run_script("--pipeline-md", path, "--no-git-probe")
        Path(path).unlink(missing_ok=True)
        self.assertEqual(r.returncode, 0, f"exit {r.returncode}: {r.stderr}")
        data = json.loads(r.stdout)
        self.assertIn("mode", data)
        self.assertIn("shards", data)
        self.assertIn("merge_order", data)
        self.assertIsInstance(data["shards"], list)

    def test_no_merge_order_rank_in_shard(self) -> None:
        """C4: per-shard block must NOT have merge_order_rank."""
        path = self._write_pipeline_md(make_pipeline_md())
        r = run_script("--pipeline-md", path, "--no-git-probe")
        Path(path).unlink(missing_ok=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        for shard in data["shards"]:
            self.assertNotIn("merge_order_rank", shard,
                f"shard {shard.get('shard_id')} has forbidden merge_order_rank field")

    def test_merge_order_top_level_array(self) -> None:
        path = self._write_pipeline_md(make_pipeline_md())
        r = run_script("--pipeline-md", path, "--no-git-probe")
        Path(path).unlink(missing_ok=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertIsInstance(data["merge_order"], list)
        self.assertEqual(len(data["merge_order"]), 1)
        self.assertEqual(data["merge_order"][0], "s1")

    def test_k2_with_dependency_merge_order(self) -> None:
        shards = {
            "s1": {
                "status": "passed",
                "branch": "pipeline/x/s1",
                "worktree": "/tmp/x/s1",
                "depends_on": [],
            },
            "s2": {
                "status": "passed",
                "branch": "pipeline/x/s2",
                "worktree": "/tmp/x/s2",
                "depends_on": ["s1"],
            },
        }
        path = self._write_pipeline_md(make_pipeline_md(shards=shards))
        r = run_script("--pipeline-md", path, "--no-git-probe")
        Path(path).unlink(missing_ok=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        order = data["merge_order"]
        self.assertIn("s1", order)
        self.assertIn("s2", order)
        # s1 must come before s2
        self.assertLess(order.index("s1"), order.index("s2"))

    def test_gh_absent_branches_only_exit_zero(self) -> None:
        """gh missing → mode=branches-only, exit 0."""
        path = self._write_pipeline_md(make_pipeline_md())
        # Pass empty PATH so gh is not found, skip git probe
        r = subprocess.run(
            [sys.executable, str(SCRIPT), "--pipeline-md", path, "--no-git-probe",
             "--no-gh-probe"],
            capture_output=True, text=True,
            env={"PATH": "", "HOME": "/tmp"},
        )
        Path(path).unlink(missing_ok=True)
        # Should exit 0 (gh absence is not hard error)
        self.assertEqual(r.returncode, 0, f"exit {r.returncode}: {r.stderr}")
        data = json.loads(r.stdout)
        self.assertEqual(data["mode"], "branches-only")
        self.assertFalse(data["gh_available"])
        self.assertIsNotNone(data["gh_reason"])

    def test_output_has_required_top_level_fields(self) -> None:
        path = self._write_pipeline_md(make_pipeline_md())
        r = run_script("--pipeline-md", path, "--no-git-probe")
        Path(path).unlink(missing_ok=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        for field in ("mode", "gh_available", "gh_reason", "base_sha",
                      "base_ref", "shards", "merge_order", "warnings"):
            self.assertIn(field, data, f"missing top-level field: {field}")

    def test_shard_has_commands_block(self) -> None:
        path = self._write_pipeline_md(make_pipeline_md())
        r = run_script("--pipeline-md", path, "--no-git-probe")
        Path(path).unlink(missing_ok=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        shard = data["shards"][0]
        self.assertIn("commands", shard)
        cmds = shard["commands"]
        self.assertIn("push", cmds)


class TestPrPublishErrors(unittest.TestCase):

    def test_missing_pipeline_md_exits_two(self) -> None:
        r = run_script("--pipeline-md", "/tmp/no-such-pipeline-xyz.md")
        self.assertEqual(r.returncode, 2, f"expected 2, got {r.returncode}")
        self.assertNotEqual(r.stderr.strip(), "")

    def test_cyclic_depends_on_exits_two(self) -> None:
        shards = {
            "s1": {
                "status": "passed",
                "branch": "pipeline/x/s1",
                "worktree": "/tmp/x/s1",
                "depends_on": ["s2"],
            },
            "s2": {
                "status": "passed",
                "branch": "pipeline/x/s2",
                "worktree": "/tmp/x/s2",
                "depends_on": ["s1"],
            },
        }
        with tempfile.NamedTemporaryFile(
            suffix=".md", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write(make_pipeline_md(shards=shards))
            path = f.name
        r = run_script("--pipeline-md", path, "--no-git-probe")
        Path(path).unlink(missing_ok=True)
        self.assertEqual(r.returncode, 2, f"expected 2, got {r.returncode}")
        self.assertIn("cycl", r.stderr.lower())


class TestApplyMode(unittest.TestCase):
    """Smoke-test --apply mode with mocked subprocess behavior."""

    def test_apply_help_visible(self) -> None:
        r = run_script("--help")
        self.assertEqual(r.returncode, 0)
        self.assertIn("apply", r.stdout.lower())


# ── B1 regression: digit-leading SHA in shard frontmatter ────────────────────

class TestDigitLeadingSha(unittest.TestCase):
    """B1: pipeline.md with commit_sha starting with digit must parse to dict."""

    def _make_pipeline_with_sha(self, commit_sha: str) -> str:
        """Build pipeline.md with commit_sha field in shard block."""
        return (
            "---\n"
            "run_id: vivid-juggling-rivest-840dcd\n"
            "plan_id: vivid-juggling-rivest-840dcd\n"
            "brief: PR-4 decompose orchestrator into 3 composable skills\n"
            "roles_included: [build]\n"
            "base_ref: main\n"
            "base_sha: 3dacf87274d0be571d022387e2ddc9bef1fb5cdd\n"
            "github_delivery: pr\n"
            "shards:\n"
            f"  s1: {{status: passed, branch: pipeline/vivid-juggling-rivest-840dcd/s1,"
            f" commit_sha: {commit_sha}, depends_on: []}}\n"
            "pr_urls: {}\n"
            "merge_shas: {}\n"
            "---\n\n## Stages\n- build: complete\n"
        )

    def _write_tmp(self, content: str) -> Path:
        import tempfile
        with tempfile.NamedTemporaryFile(
            suffix=".md", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            return Path(f.name)

    def test_digit_leading_sha_parses_to_dict(self) -> None:
        """Real pipeline.md commit_sha 0855bbb... must not exit 2."""
        real_sha = "0855bbb2422725a841b94c4c0bfe4ee3c3605e67"
        path = self._write_tmp(self._make_pipeline_with_sha(real_sha))
        r = run_script("--pipeline-md", str(path), "--no-git-probe", "--no-gh-probe")
        path.unlink(missing_ok=True)
        self.assertEqual(
            r.returncode, 0,
            f"exit {r.returncode} — digit-leading SHA broke parser: {r.stderr}",
        )
        data = json.loads(r.stdout)
        self.assertIn("shards", data)
        self.assertIsInstance(data["shards"], list)
        self.assertEqual(len(data["shards"]), 1)

    def test_all_digit_leading_sha_prefix(self) -> None:
        """SHA starting with 0-9 (≈63% of real SHAs) all parse correctly."""
        for digit in "0123456789":
            sha = f"{digit}855bbb2422725a841b94c4c0bfe4ee3c3605e67"
            path = self._write_tmp(self._make_pipeline_with_sha(sha))
            r = run_script(
                "--pipeline-md", str(path), "--no-git-probe", "--no-gh-probe"
            )
            path.unlink(missing_ok=True)
            self.assertEqual(
                r.returncode, 0,
                f"digit '{digit}'-leading SHA failed: {r.stderr}",
            )

    def test_empty_flow_map_pr_urls(self) -> None:
        """pr_urls: {} must parse as empty dict, not string '{}'."""
        # pipeline.md already has pr_urls: {} in the real file
        real_sha = "0855bbb2422725a841b94c4c0bfe4ee3c3605e67"
        path = self._write_tmp(self._make_pipeline_with_sha(real_sha))
        r = run_script("--pipeline-md", str(path), "--no-git-probe", "--no-gh-probe")
        path.unlink(missing_ok=True)
        # Reaching exit 0 proves frontmatter parsed w/o blowing up on pr_urls: {}
        self.assertEqual(r.returncode, 0, r.stderr)


# ── B2: _apply() functional tests via subprocess mock ─────────────────────────

import importlib.util
import io
from unittest.mock import MagicMock, patch

def _load_prpub():
    """Import pr-publish module directly (hyphen in name → spec load)."""
    spec = importlib.util.spec_from_file_location(
        "prpub", Path(__file__).parent / "pr-publish.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_PRPUB = _load_prpub()


def _make_shard_plans(
    shard_ids: list[str],
    *,
    include_gh: bool = True,
) -> tuple[list[str], dict[str, dict]]:
    """Build minimal merge_order + shard_plans_map for _apply() tests."""
    plans: dict[str, dict] = {}
    for sid in shard_ids:
        plans[sid] = {
            "shard_id": sid,
            "branch": f"pipeline/test/{sid}",
            "depends_on": [],
            "commands": {
                "recommit": ["git", "reset", "--soft", "abc123"],
                "push": ["git", "push", "origin", f"pipeline/test/{sid}"],
                "pr_create": (
                    ["gh", "pr", "create", "--base", "main", "--head",
                     f"pipeline/test/{sid}", "--title", f"[test] {sid}"]
                    if include_gh else None
                ),
                "pr_merge": (
                    ["gh", "pr", "merge", "--merge", f"pipeline/test/{sid}"]
                    if include_gh else None
                ),
            },
            "title": f"[test] {sid}",
            "body_path": None,
        }
    return shard_ids, plans


def _ok_result(stdout: str = "", stderr: str = "") -> MagicMock:
    r = MagicMock()
    r.returncode = 0
    r.stdout = stdout
    r.stderr = stderr
    return r


def _fail_result(stdout: str = "", stderr: str = "error") -> MagicMock:
    r = MagicMock()
    r.returncode = 1
    r.stdout = stdout
    r.stderr = stderr
    return r


class TestApplyFunctional(unittest.TestCase):
    """B2: _apply() subprocess mock tests."""

    def _capture_apply(
        self,
        mock_run: MagicMock,
        merge_order: list[str],
        shard_plans: dict[str, dict],
    ) -> tuple[int, list[dict]]:
        """Run _apply(), capture printed JSONL lines."""
        printed: list[str] = []
        with patch("builtins.print", side_effect=lambda s: printed.append(s)):
            exit_code = _PRPUB._apply({}, merge_order, shard_plans)
        lines = [json.loads(l) for l in printed]
        return exit_code, lines

    def test_all_success_exits_zero(self) -> None:
        """All git/gh succeed → exit 0, summary.failed empty."""
        merge_order, plans = _make_shard_plans(["s1"])
        with patch("subprocess.run", return_value=_ok_result()) as mock_run:
            code, lines = self._capture_apply(mock_run, merge_order, plans)
        self.assertEqual(code, 0)
        summary_lines = [l for l in lines if "summary" in l]
        self.assertEqual(len(summary_lines), 1)
        self.assertEqual(summary_lines[0]["summary"]["failed"], [])
        self.assertEqual(summary_lines[0]["summary"]["pushed"], 1)

    def test_push_fail_records_failed_exits_one(self) -> None:
        """git push fails → summary.failed=['s1/push'], exit 1."""
        merge_order, plans = _make_shard_plans(["s1"])

        def side_effect(cmd, **kw):
            if "push" in cmd:
                return _fail_result(stderr="push rejected")
            return _ok_result()

        with patch("subprocess.run", side_effect=side_effect):
            code, lines = self._capture_apply(MagicMock(), merge_order, plans)

        self.assertEqual(code, 1)
        summary = next(l["summary"] for l in lines if "summary" in l)
        self.assertIn("s1/push", summary["failed"])

    def test_pr_create_fail_records_failed_exits_one(self) -> None:
        """gh pr create fails → summary.failed=['s1/pr_create'], exit 1."""
        merge_order, plans = _make_shard_plans(["s1"])

        def side_effect(cmd, **kw):
            if "pr" in cmd and "create" in cmd:
                return _fail_result(stderr="gh pr create failed")
            return _ok_result()

        with patch("subprocess.run", side_effect=side_effect):
            code, lines = self._capture_apply(MagicMock(), merge_order, plans)

        self.assertEqual(code, 1)
        summary = next(l["summary"] for l in lines if "summary" in l)
        self.assertIn("s1/pr_create", summary["failed"])

    def test_jsonl_shape_per_shard_action(self) -> None:
        """Each action emits JSONL with shard/action/exit/stdout/stderr fields."""
        merge_order, plans = _make_shard_plans(["s1"])
        with patch("subprocess.run", return_value=_ok_result("ok-out")):
            code, lines = self._capture_apply(MagicMock(), merge_order, plans)

        action_lines = [l for l in lines if "action" in l]
        self.assertGreater(len(action_lines), 0)
        for line in action_lines:
            for field in ("shard", "action", "exit", "stdout", "stderr"):
                self.assertIn(field, line, f"JSONL line missing '{field}': {line}")

    def test_multi_shard_any_fail_exits_one(self) -> None:
        """K=2, s2 push fails → exit 1; s1/push in passed counts."""
        merge_order, plans = _make_shard_plans(["s1", "s2"])

        def side_effect(cmd, **kw):
            # s2 push fails
            if "push" in cmd and "s2" in " ".join(cmd):
                return _fail_result(stderr="s2 push rejected")
            return _ok_result()

        with patch("subprocess.run", side_effect=side_effect):
            code, lines = self._capture_apply(MagicMock(), merge_order, plans)

        self.assertEqual(code, 1)
        summary = next(l["summary"] for l in lines if "summary" in l)
        self.assertIn("s2/push", summary["failed"])
        self.assertEqual(summary["total_shards"], 2)

    def test_all_success_k2_exit_zero(self) -> None:
        """K=2 all pass → exit 0, pushed=2."""
        merge_order, plans = _make_shard_plans(["s1", "s2"])
        with patch("subprocess.run", return_value=_ok_result()):
            code, lines = self._capture_apply(MagicMock(), merge_order, plans)

        self.assertEqual(code, 0)
        summary = next(l["summary"] for l in lines if "summary" in l)
        self.assertEqual(summary["failed"], [])
        self.assertEqual(summary["pushed"], 2)


if __name__ == "__main__":
    unittest.main()
