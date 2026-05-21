"""Tests for dep-graph-compose.py — stdlib unittest."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent / "dep-graph-compose.py"

VALID_PAYLOAD_K1 = json.dumps({
    "brief_path": "/tmp/brief.md",
    "plan_path": None,
    "roles_declared": ["architect", "build", "skeptic-design"],
    "roles_skipped": {},
    "decision_points": {},
    "design_handoff": "required",
    "ui_scope": False,
    "ops_scope": False,
    "code_change": True,
    "K": 1,
})

VALID_PAYLOAD_K3 = json.dumps({
    "brief_path": "/tmp/brief.md",
    "plan_path": None,
    "roles_declared": ["architect", "build", "skeptic-code"],
    "roles_skipped": {},
    "decision_points": {},
    "design_handoff": "n/a",
    "ui_scope": False,
    "ops_scope": False,
    "code_change": True,
    "K": 3,
})

VALID_PAYLOAD_K8 = json.dumps({
    "brief_path": "/tmp/brief.md",
    "plan_path": None,
    "roles_declared": ["build"],
    "roles_skipped": {},
    "decision_points": {},
    "design_handoff": "n/a",
    "ui_scope": False,
    "ops_scope": False,
    "code_change": True,
    "K": 8,
})


def run_script(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


class TestDepGraphCompose(unittest.TestCase):

    def test_help_exits_zero(self) -> None:
        r = run_script("--help")
        self.assertEqual(r.returncode, 0, f"--help nonzero: {r.stderr}")
        combined = r.stdout.lower() + r.stderr.lower()
        self.assertTrue("dep-graph-compose" in combined or "usage" in combined)

    def test_valid_k1_exits_zero_with_json(self) -> None:
        r = run_script("--payload", VALID_PAYLOAD_K1)
        self.assertEqual(r.returncode, 0, f"exit {r.returncode}: {r.stderr}")
        data = json.loads(r.stdout)
        self.assertIn("ordered_roles", data)
        self.assertIn("K", data)
        self.assertEqual(data["K"], 1)
        self.assertIn("warnings", data)

    def test_valid_k3_passes_k_through(self) -> None:
        r = run_script("--payload", VALID_PAYLOAD_K3)
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(data["K"], 3)

    def test_valid_k8_passes_k_through(self) -> None:
        r = run_script("--payload", VALID_PAYLOAD_K8)
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertEqual(data["K"], 8)

    def test_invalid_json_exits_two(self) -> None:
        r = run_script("--payload", "not-json")
        self.assertEqual(r.returncode, 2, f"expected exit 2, got {r.returncode}")
        self.assertNotEqual(r.stderr.strip(), "")

    def test_missing_required_key_exits_two(self) -> None:
        payload = json.dumps({"brief_path": "/tmp/x.md"})
        r = run_script("--payload", payload)
        self.assertEqual(r.returncode, 2, f"expected exit 2, got {r.returncode}")

    def test_k_zero_exits_two(self) -> None:
        payload_dict = json.loads(VALID_PAYLOAD_K1)
        payload_dict["K"] = 0
        r = run_script("--payload", json.dumps(payload_dict))
        self.assertEqual(r.returncode, 2, f"expected exit 2, got {r.returncode}")

    def test_no_hardcoded_k_cap(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        forbidden = re.search(r"\bK\s*[<>]=?\s*[48]\b", source)
        self.assertIsNone(forbidden,
            f"Hardcoded K cap found: {forbidden.group() if forbidden else ''}")

    def test_output_has_decision_inject_points(self) -> None:
        r = run_script("--payload", VALID_PAYLOAD_K1)
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertIn("decision_inject_points", data)


if __name__ == "__main__":
    unittest.main()
