"""Pass 3 (identity block) of the commit linter, and its hostname opt-out.

Every value here is synthetic: a fake hostname, a fake email, a fake
tailnet. The test never reads the machine's real identity.local.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

FAKE_HOSTNAME = "example-distro"
FAKE_CONTENT = f'supported_distros = ["arch", "{FAKE_HOSTNAME}", "termux"]'
LINTER = (
    Path(__file__).parent.parent / "scripts" / "commit-linter" / "lint_staged.py"
)


@pytest.fixture()
def linter(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """The linter module, with git and the live hostname stubbed out."""
    spec = importlib.util.spec_from_file_location("lint_staged", LINTER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["lint_staged"] = module
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.socket, "gethostname", lambda: FAKE_HOSTNAME)
    monkeypatch.setattr(module, "is_binary", lambda path: False)
    monkeypatch.setattr(module, "staged_text", lambda path: FAKE_CONTENT)
    return module


def write_identity(module: ModuleType, tmp_path: Path, extra: str) -> None:
    """Point the linter at a synthetic identity.local under tmp_path."""
    path = tmp_path / "identity.local"
    path.write_text(
        "EMAIL=nobody@example.invalid\nTAILNET=example-tailnet\n" + extra
    )
    module.IDENTITY_LOCAL = path


def test_hostname_blocks_without_opt_out(
    linter: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_identity(linter, tmp_path, "")

    assert linter.fail_identity(["deps.toml"]) is True
    err = capsys.readouterr().err
    assert "BLOCKED: identifying value in deps.toml on line(s) 1" in err
    assert "HOSTNAME_CHECK" not in err


def test_hostname_opt_out_passes_and_announces_itself(
    linter: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_identity(linter, tmp_path, "HOSTNAME_CHECK=off\n")

    assert linter.fail_identity(["deps.toml"]) is False
    err = capsys.readouterr().err
    assert "NOTICE: HOSTNAME_CHECK=off" in err
    assert "DISABLED" in err
    assert "BLOCKED" not in err


def test_opt_out_leaves_email_and_tailnet_needles_alone(
    linter: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_identity(linter, tmp_path, "HOSTNAME_CHECK=off\n")
    linter.staged_text = lambda path: "contact: nobody@example.invalid"

    assert linter.fail_identity(["docs/contact.md"]) is True
    assert "BLOCKED: identifying value in docs/contact.md" in capsys.readouterr().err


def test_typoed_opt_out_value_leaves_the_check_on(
    linter: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_identity(linter, tmp_path, "HOSTNAME_CHECK=of\n")

    assert linter.fail_identity(["deps.toml"]) is True
    assert "NOTICE" not in capsys.readouterr().err
