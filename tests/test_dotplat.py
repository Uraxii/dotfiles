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
        ('ID=somethingnew\nID_LIKE="fedora"\n', "fedora"),
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


@pytest.mark.parametrize("os_release", [
    "ID=gentoo\n",
    'ID=rocky\nID_LIKE="rhel centos fedora"\n',
    'ID=almalinux\nID_LIKE="rhel centos fedora"\n',
])
def test_detect_unsupported_distro(tmp_path, os_release):
    f = tmp_path / "os-release"
    f.write_text(os_release)
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


def test_tasks_pin_the_config_python():
    """Each task asks mise for the same python that config.toml installs."""
    import re
    import tomllib

    mise_dir = Path(__file__).resolve().parent.parent / "mise"
    want = tomllib.loads((mise_dir / "config.toml").read_text())["tools"]["python"]
    for task in sorted((mise_dir / "tasks").iterdir()):
        text = task.read_text()
        assert text.startswith("#!/usr/bin/env python\n"), task.name
        m = re.search(r'^#MISE tools=\{python="([^"]+)"\}$', text, re.MULTILINE)
        assert m and m.group(1) == want, task.name


def test_system_runtimes_only_on_termux_and_nixos():
    for platform in detect.PLATFORMS:
        env: dict[str, str] = {}
        detect.use_system_runtimes(platform, env)
        if platform in ("termux", "nixos"):
            assert env == {"MISE_DISABLE_TOOLS": "python,node"}
        else:
            assert env == {}
    env = {"MISE_DISABLE_TOOLS": "python,node,gh"}
    detect.use_system_runtimes("termux", env)
    assert env["MISE_DISABLE_TOOLS"] == "python,node,gh"  # a user value wins


def test_nix_matches_nested_attr_names(monkeypatch, capsys):
    from dotplat import common

    monkeypatch.setattr(common, "has_bin", lambda *n: True)
    monkeypatch.setattr(common, "_nix_installed", lambda: {"_0xproto", "sway"})
    step = common.nix_profile(["sway", "nerd-fonts._0xproto"])
    step.action(Ctx(platform="nixos", dry_run=True))
    assert "already installed" in capsys.readouterr().out


def test_unexpected_exception_fails_only_that_step(capsys):
    from dotplat.runner import Step

    ran = []

    def boom(ctx):
        import zipfile
        raise zipfile.BadZipFile("truncated download")

    steps = [Step("bad", boom), Step("good", lambda ctx: ran.append("good"))]
    assert run_steps(Ctx(platform="arch"), steps) == 1
    assert ran == ["good"]
    assert "Failed steps: bad" in capsys.readouterr().out


def test_godots_is_a_note_off_x86_64(monkeypatch):
    from dotplat import common

    monkeypatch.setattr(common.platform, "machine", lambda: "aarch64")
    ctx = Ctx(platform="ubuntu", dry_run=True)
    common.godots_linux().action(ctx)
    assert any("x86_64 only" in n for n in ctx.notes)


def test_setup_continues_when_mise_install_fails(tmp_path):
    """A failing `mise install` must not stop the system and stow steps."""
    task = Path(__file__).resolve().parent.parent / "mise" / "tasks" / "setup"
    fake = tmp_path / "bin"
    fake.mkdir()
    for name in ("mise", "bash"):
        script = fake / name
        script.write_text(f"#!/bin/sh\necho ran-{name}\nexit {1 if name == 'mise' else 0}\n")
        script.chmod(0o755)
    env = {"PATH": str(fake), "DOTFILES_PLATFORM": "arch", "DOTFILES_PROFILE": "server",
           "DOTFILES_SHELL": "none", "HOME": str(tmp_path)}
    # The system step would run real package managers, so stub its steps out.
    code = (
        "import sys, runpy; sys.path.insert(0, {!r});"
        "import dotplat.platforms as p; p.steps_for = lambda name: [];"
        "import dotplat.cli as c; c.steps_for = p.steps_for;"
        "sys.argv = [{!r}]; runpy.run_path({!r}, run_name='__main__')"
    ).format(str(task.parent.parent / "lib"), str(task), str(task))
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         env=env, check=False)
    assert "ran-mise" in out.stdout
    assert "ran-bash" in out.stdout  # stow still ran
    assert "these parts failed: mise install" in out.stdout
    assert out.returncode == 1
