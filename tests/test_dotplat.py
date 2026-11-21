"""Tests for the mise platform switchboard (mise/lib/dotplat)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mise" / "lib"))

from dotplat import detect
from dotplat.platforms import steps_for
from dotplat.runner import Ctx, run_steps


@pytest.mark.parametrize(
    ("os_release", "expected"),
    [
        ('ID=arch\n', "arch"),
        ('ID=endeavouros\nID_LIKE=arch\n', "arch"),
        ('ID=ubuntu\nID_LIKE=debian\n', "ubuntu"),
        ('ID=linuxmint\nID_LIKE="ubuntu debian"\n', "ubuntu"),
        ('ID=fedora\n', "fedora"),
        ('ID=bazzite\nID_LIKE="fedora"\n', "bazzite"),
        ('ID=nixos\n', "nixos"),
        ('ID=somethingnew\nID_LIKE="rhel fedora"\n', "fedora"),
    ],
)
def test_detect_from_os_release(tmp_path, os_release, expected):
    f = tmp_path / "os-release"
    f.write_text(os_release)
    assert detect.detect(environ={}, sys_platform="linux", os_release=f) == expected


def test_detect_windows_and_termux(tmp_path):
    missing = tmp_path / "none"
    assert detect.detect(environ={}, sys_platform="win32", os_release=missing) == "windows"
    assert detect.detect(environ={"TERMUX_VERSION": "0.118"}, sys_platform="linux",
                         os_release=missing) == "termux"


def test_detect_unknown_distro(tmp_path):
    f = tmp_path / "os-release"
    f.write_text("ID=gentoo\n")
    with pytest.raises(detect.UnsupportedPlatform):
        detect.detect(environ={}, sys_platform="linux", os_release=f)


def test_current_exports_and_honours_override():
    env = {detect.ENV_VAR: "Fedora"}
    assert detect.current(env) == "fedora"
    assert env[detect.ENV_VAR] == "fedora"
    with pytest.raises(detect.UnsupportedPlatform):
        detect.current({detect.ENV_VAR: "macos"})


@pytest.mark.parametrize("platform", detect.PLATFORMS)
def test_every_platform_has_rules(platform):
    steps = steps_for(platform)
    assert steps, platform
    assert {s.group for s in steps} <= {"core", "desktop"}


@pytest.mark.parametrize("platform", detect.PLATFORMS)
def test_dry_run_runs_no_commands(platform, monkeypatch, capsys):
    def boom(*a, **k):
        raise AssertionError(f"subprocess.run called in dry run: {a}")

    # winget and nix probe what is installed; those probes are read-only,
    # so let them see "nothing installed" instead of failing.
    monkeypatch.setattr("dotplat.runner.subprocess.run", boom)
    monkeypatch.setattr("dotplat.common.has_bin", lambda *n: False)
    monkeypatch.setattr("dotplat.runner.has_bin", lambda *n: False)
    ctx = Ctx(platform=platform, dry_run=True)
    assert run_steps(ctx, steps_for(platform)) == 0
    assert f"platform={platform}" in capsys.readouterr().out


def test_server_profile_skips_desktop(monkeypatch, capsys):
    monkeypatch.setattr("dotplat.runner.has_bin", lambda *n: False)
    ctx = Ctx(platform="arch", profile="server", dry_run=True)
    run_steps(ctx, steps_for("arch"))
    out = capsys.readouterr().out
    assert "sway" not in out.split("pacman: desktop")[0]
    assert "pacman: desktop: skip" in out


def test_platform_task_prints_override():
    task = Path(__file__).resolve().parent.parent / "mise" / "tasks" / "platform"
    out = subprocess.run([sys.executable, str(task)], capture_output=True, text=True,
                         env={"DOTFILES_PLATFORM": "nixos", "PATH": ""}, check=True)
    assert out.stdout.strip() == "nixos"
