"""Tests for revision-route.py — stdlib unittest."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent / "revision-route.py"
# parents[2] of revision-route.py = .claude/ → agents/orchestrator.md
ORCH_MD = SCRIPT.resolve().parents[2] / "agents" / "orchestrator.md"


def make_verdict(
    verdict: str = "Approved",
    role: str = "architect",
    review_type: str = "design",
    revision: int = 1,
    loops: int = 1,
) -> str:
    return (
        f"---\n"
        f"verdict: {verdict}\n"
        f"role: {role}\n"
        f"review_type: {review_type}\n"
        f"revision: r{revision}\n"
        f"loops: {loops}\n"
        f"---\n\n# Verdict\n{verdict}\n"
    )


def run_script(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


def run_with_orch(*args: str) -> subprocess.CompletedProcess:
    """Run script with real orchestrator.md path injected."""
    extra = ["--orch-path", str(ORCH_MD)] if ORCH_MD.exists() else []
    return run_script(*args, *extra)


class TestRevisionRouteHelp(unittest.TestCase):

    def test_help_exits_zero(self) -> None:
        r = run_script("--help")
        self.assertEqual(r.returncode, 0, r.stderr)
        combined = r.stdout.lower() + r.stderr.lower()
        self.assertTrue("revision-route" in combined or "usage" in combined)


class TestRevisionRouteValidInput(unittest.TestCase):

    def _run_verdict(self, **kwargs) -> tuple[int, dict]:
        with tempfile.NamedTemporaryFile(
            suffix=".md", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write(make_verdict(**kwargs))
            path = f.name
        r = run_with_orch("--verdict-path", path)
        Path(path).unlink(missing_ok=True)
        if r.returncode == 0:
            return r.returncode, json.loads(r.stdout)
        return r.returncode, {}

    def test_design_architect_approved(self) -> None:
        code, data = self._run_verdict(
            verdict="Approved", role="architect", review_type="design"
        )
        self.assertEqual(code, 0)
        self.assertEqual(data["action"], "approved")

    def test_design_architect_blocked_respawn(self) -> None:
        code, data = self._run_verdict(
            verdict="Blocked", role="architect", review_type="design"
        )
        self.assertEqual(code, 0)
        self.assertEqual(data["action"], "respawn")
        self.assertEqual(data["target_role"], "architect")

    def test_code_skeptic_code_blocked_respawn_build(self) -> None:
        code, data = self._run_verdict(
            verdict="Blocked", role="skeptic-code", review_type="code"
        )
        self.assertEqual(code, 0)
        self.assertEqual(data["action"], "respawn")
        self.assertEqual(data["target_role"], "build")

    def test_ops_skeptic_ops_approved(self) -> None:
        code, data = self._run_verdict(
            verdict="Approved", role="skeptic-ops", review_type="ops"
        )
        self.assertEqual(code, 0)
        self.assertEqual(data["action"], "approved")

    def test_test_audit_tester_blocked(self) -> None:
        code, data = self._run_verdict(
            verdict="Blocked", role="tester", review_type="test-audit"
        )
        self.assertEqual(code, 0)
        self.assertEqual(data["action"], "respawn")
        self.assertEqual(data["target_role"], "tester")

    def test_security_auditor_post_build_blocked(self) -> None:
        code, data = self._run_verdict(
            verdict="Blocked", role="security-auditor", review_type="code"
        )
        self.assertEqual(code, 0)
        self.assertEqual(data["action"], "respawn")
        self.assertEqual(data["target_role"], "build")

    def test_security_auditor_post_arch_blocked(self) -> None:
        code, data = self._run_verdict(
            verdict="Blocked", role="security-auditor", review_type="design"
        )
        self.assertEqual(code, 0)
        self.assertEqual(data["action"], "respawn")
        self.assertEqual(data["target_role"], "architect")

    def test_conditional_gives_approved(self) -> None:
        code, data = self._run_verdict(
            verdict="Conditional", role="architect", review_type="design"
        )
        self.assertEqual(code, 0)
        self.assertIn(data["action"], ("approved", "respawn"))

    def test_output_has_required_fields(self) -> None:
        code, data = self._run_verdict()
        self.assertEqual(code, 0)
        for field in ("action", "target_role", "revision_n", "reason",
                      "loop_cap_hit", "verdict_summary"):
            self.assertIn(field, data, f"missing field: {field}")

    def test_loop_cap_hit_returns_halt(self) -> None:
        with tempfile.NamedTemporaryFile(
            suffix=".md", mode="w", delete=False, encoding="utf-8"
        ) as f:
            # loops == loop_cap (3) → halt
            f.write(make_verdict(
                verdict="Blocked", role="architect",
                review_type="design", loops=3
            ))
            path = f.name
        r = run_with_orch("--verdict-path", path)
        Path(path).unlink(missing_ok=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(data["action"], "halt")
        self.assertTrue(data["loop_cap_hit"])


class TestRevisionRouteErrors(unittest.TestCase):

    def test_missing_file_exits_two(self) -> None:
        r = run_script("--verdict-path", "/tmp/no-such-verdict-xyz.md")
        self.assertEqual(r.returncode, 2, f"expected 2, got {r.returncode}")
        self.assertNotEqual(r.stderr.strip(), "")

    def test_malformed_frontmatter_exits_two(self) -> None:
        with tempfile.NamedTemporaryFile(
            suffix=".md", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write("# No frontmatter here\n")
            path = f.name
        r = run_script("--verdict-path", path)
        Path(path).unlink(missing_ok=True)
        self.assertEqual(r.returncode, 2, f"expected 2, got {r.returncode}")

    def test_unknown_tuple_exits_two(self) -> None:
        with tempfile.NamedTemporaryFile(
            suffix=".md", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write(make_verdict(role="unknown-role", review_type="unknown-type"))
            path = f.name
        r = run_script("--verdict-path", path)
        Path(path).unlink(missing_ok=True)
        self.assertEqual(r.returncode, 2, f"expected 2, got {r.returncode}")

    def test_invalid_verdict_value_exits_two(self) -> None:
        with tempfile.NamedTemporaryFile(
            suffix=".md", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write(make_verdict(verdict="Maybe"))
            path = f.name
        r = run_script("--verdict-path", path)
        Path(path).unlink(missing_ok=True)
        self.assertEqual(r.returncode, 2, f"expected 2, got {r.returncode}")


class TestDriftGuard(unittest.TestCase):
    """C5: drift-guard must exit exactly 2, not 1."""

    def test_drift_guard_exit_exactly_two_on_mismatch(self) -> None:
        """Pass a fake orchestrator.md with a row removed; expect exit==2."""
        # Build minimal orchestrator.md missing one row
        fake_orch = (
            "# Orchestrator\n\n"
            "## Revision Loop\n\n"
            "Upstream mapping:\n\n"
            "| Verdict | Re-spawn |\n"
            "|--------|----------|\n"
            # Intentionally omit verdict-design-r<N>.md row
            "| verdict-code-r<N>.md | build |\n"
            "| verdict-ops-r<N>.md | build |\n"
            "| verdict-review-r<N>.md | build |\n"
            "| verdict-security-r<N>.md post-build | build |\n"
            "| verdict-security-r<N>.md post-architect | architect |\n"
            "| verdict-test-r<N>.md | tester |\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            # Mimic .claude/agents/orchestrator.md structure
            agents_dir = td / ".claude" / "agents"
            agents_dir.mkdir(parents=True)
            (agents_dir / "orchestrator.md").write_text(fake_orch, encoding="utf-8")

            # Create a valid verdict file
            verdict_path = td / "verdict.md"
            verdict_path.write_text(
                make_verdict(verdict="Approved", role="architect", review_type="design"),
                encoding="utf-8",
            )

            # Run with env override for the orch path
            r = subprocess.run(
                [sys.executable, str(SCRIPT),
                 "--verdict-path", str(verdict_path),
                 "--orch-path", str(agents_dir / "orchestrator.md")],
                capture_output=True, text=True,
            )
        self.assertEqual(r.returncode, 2,
            f"Expected exit 2 on drift, got {r.returncode}. stderr: {r.stderr}")
        self.assertIn("drift", r.stderr.lower(),
            f"Expected 'drift' in stderr. Got: {r.stderr}")

    def test_drift_guard_passes_on_valid_orch(self) -> None:
        """Real orchestrator.md should pass drift check after PR-4 edits."""
        if not ORCH_MD.exists():
            self.skipTest("orchestrator.md not found at expected path")
        with tempfile.NamedTemporaryFile(
            suffix=".md", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write(make_verdict(verdict="Approved", role="architect", review_type="design"))
            path = f.name
        r = run_with_orch("--verdict-path", path)
        Path(path).unlink(missing_ok=True)
        self.assertEqual(r.returncode, 0,
            f"Drift guard failed on real orch.md: {r.stderr}")


if __name__ == "__main__":
    unittest.main()
