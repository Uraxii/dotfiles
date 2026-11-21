"""Installers that more than one platform uses."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from .runner import Ctx, Step, StepFailed, has_bin, shell

NERD_FONT_URL = "https://github.com/ryanoasis/nerd-fonts/releases/latest/download/0xProto.zip"
GODOTS_URL = "https://github.com/MakovWait/godots/releases/latest/download/LinuxX11.zip"


def _download(ctx: Ctx, url: str, dest: Path) -> None:
    print(f"  + download {url}", flush=True)
    if ctx.dry_run:
        return
    try:
        with urllib.request.urlopen(url) as resp, open(dest, "wb") as out:
            shutil.copyfileobj(resp, out)
    except OSError as exc:
        raise StepFailed(f"download failed: {url}: {exc}") from exc


# --------------------------------------------------------------------------- #
# Package managers that need extra logic
# --------------------------------------------------------------------------- #

def aur(names: list[str], group: str = "desktop") -> Step:
    """Arch: install AUR (and repo) packages with paru or yay."""
    def action(ctx: Ctx) -> None:
        helper = next((h for h in ("paru", "yay") if has_bin(h)), None)
        if helper is None:
            ctx.note(f"AUR packages ({', '.join(names)}): install paru or yay, then run this task again")
            return
        ctx.run([helper, "-S", "--needed", "--noconfirm", *names])
    return Step("aur: " + " ".join(names), action, group)


def winget(package_id: str, group: str = "core") -> Step:
    """Windows: install one winget package if `winget list` does not show it."""
    def action(ctx: Ctx) -> None:
        argv = ["winget", "install", "--id", package_id, "--exact", "--silent",
                "--accept-package-agreements", "--accept-source-agreements"]
        if not has_bin("winget"):
            if ctx.dry_run:
                ctx.run(argv)
                return
            raise StepFailed("winget is not on PATH (install App Installer from the Microsoft Store)")
        listed = subprocess.run(
            ["winget", "list", "--id", package_id, "--exact", "--accept-source-agreements"],
            capture_output=True, check=False,
        )
        if listed.returncode == 0:
            print("  already installed")
            return
        ctx.run(argv)
    return Step(f"winget: {package_id}", action, group)


NIX_FLAGS = ["--extra-experimental-features", "nix-command flakes"]


def _nix_installed() -> set[str]:
    out = subprocess.run(["nix", *NIX_FLAGS, "profile", "list", "--json"],
                         capture_output=True, text=True, check=False)
    if out.returncode != 0:
        return set()
    elements = json.loads(out.stdout or "{}").get("elements", {})
    # Newer nix: dict keyed by name. Older nix: list with attrPath.
    if isinstance(elements, dict):
        return set(elements)
    return {e.get("attrPath", "").rsplit(".", 1)[-1] for e in elements}


def nix_profile(names: list[str], group: str = "core", unfree: bool = False) -> Step:
    """NixOS: `nix profile install nixpkgs#<name>` for each missing name."""
    def action(ctx: Ctx) -> None:
        have = _nix_installed() if has_bin("nix") else set()
        # Profile elements are named by the last attribute component:
        # nerd-fonts._0xproto is listed as _0xproto.
        missing = [n for n in names if n.rsplit(".", 1)[-1] not in have]
        if not missing:
            print("  already installed")
            return
        argv = ["nix", *NIX_FLAGS, "profile", "install"]
        env = None
        if unfree:
            argv.append("--impure")
            env = {"NIXPKGS_ALLOW_UNFREE": "1"}
        ctx.run(argv + [f"nixpkgs#{n}" for n in missing], env)
    return Step("nix: " + " ".join(names), action, group)


# --------------------------------------------------------------------------- #
# Upstream installers (no package in the platform's manager)
# --------------------------------------------------------------------------- #

def _font_dir(ctx: Ctx) -> Path:
    if ctx.platform == "windows":
        local = os.environ.get("LOCALAPPDATA") or str(ctx.home / "AppData" / "Local")
        return Path(local) / "Microsoft" / "Windows" / "Fonts"
    return ctx.home / ".local" / "share" / "fonts" / "0xProto"


def _register_windows_fonts(fonts: list[Path]) -> None:
    import winreg  # Windows only

    key_path = r"Software\Microsoft\Windows NT\CurrentVersion\Fonts"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
        for f in fonts:
            winreg.SetValueEx(key, f"{f.stem} (TrueType)", 0, winreg.REG_SZ, str(f))


def nerd_font(group: str = "desktop") -> Step:
    """0xProto Nerd Font, per-user install (Linux fontconfig or Windows HKCU)."""
    def action(ctx: Ctx) -> None:
        dest = _font_dir(ctx)
        if list(dest.glob("0xProto*.ttf")):
            print("  already installed")
            return
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "0xProto.zip"
            _download(ctx, NERD_FONT_URL, archive)
            print(f"  + extract *.ttf -> {dest}")
            if ctx.dry_run:
                return
            dest.mkdir(parents=True, exist_ok=True)
            fonts: list[Path] = []
            with zipfile.ZipFile(archive) as zf:
                for member in zf.namelist():
                    if member.endswith(".ttf") and "/" not in member:
                        target = dest / member
                        target.write_bytes(zf.read(member))
                        fonts.append(target)
        if ctx.platform == "windows":
            _register_windows_fonts(fonts)
        elif has_bin("fc-cache"):
            ctx.run(["fc-cache", "-f"])
    return Step("nerd font: 0xProto", action, group)


def godots_linux(group: str = "desktop") -> Step:
    """Godots (Godot version manager) from the upstream release zip (x86_64 only)."""
    def action(ctx: Ctx) -> None:
        if platform.machine() not in ("x86_64", "AMD64"):
            ctx.note(f"godots: the upstream release is x86_64 only; this CPU is {platform.machine()}")
            return
        app_dir = ctx.home / ".local" / "share" / "godots"
        link = ctx.home / ".local" / "bin" / "godots"
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "godots.zip"
            _download(ctx, GODOTS_URL, archive)
            print(f"  + extract -> {app_dir}; link {link}")
            if ctx.dry_run:
                return
            app_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(app_dir)
        binary = app_dir / "Godots.x86_64"
        binary.chmod(0o755)
        link.parent.mkdir(parents=True, exist_ok=True)
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(binary)
    return Step("godots", action, group, skip_if_bin=("godots",))


def networkmanager_dmenu(group: str = "desktop") -> Step:
    return shell(
        "networkmanager-dmenu",
        'tmp=$(mktemp -d) && git clone --depth 1 https://github.com/firecat53/networkmanager-dmenu "$tmp" '
        '&& sudo install -m 755 "$tmp/networkmanager_dmenu" /usr/local/bin/networkmanager_dmenu '
        '&& rm -rf "$tmp"',
        group,
        skip_if_bin=("networkmanager_dmenu",),
    )


def docker_script(group: str = "core") -> Step:
    return shell("docker", "curl -fsSL https://get.docker.com | sudo sh", group,
                 skip_if_bin=("docker",))


def hermes(group: str = "core") -> Step:
    def action(ctx: Ctx) -> None:
        ctx.sh("curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash")
        ctx.note("hermes: run `hermes setup` once (interactive)")
    return Step("hermes", action, group, skip_if_bin=("hermes",))


# --------------------------------------------------------------------------- #
# Login shell
# --------------------------------------------------------------------------- #

SHELL_ENV = "DOTFILES_SHELL"


def login_shell(default: str = "fish") -> Step:
    """Set the login shell (DOTFILES_SHELL, default fish; 'none' skips)."""
    def action(ctx: Ctx) -> None:
        name = os.environ.get(SHELL_ENV, default)
        if name == "none":
            print("  skip (DOTFILES_SHELL=none)")
            return
        path = shutil.which(name)
        if path is None:
            if ctx.dry_run:
                print(f"  {name} is not on PATH yet; it is set after the packages install")
                return
            raise StepFailed(f"{name} is not on PATH")
        if ctx.platform == "termux":
            ctx.run(["chsh", "-s", name])
            return
        import pwd  # POSIX only

        if pwd.getpwuid(os.getuid()).pw_shell == path:
            print(f"  already {path}")
            return
        shells = Path("/etc/shells")
        if not shells.exists() or path not in shells.read_text().split():
            ctx.run(["sudo", "sh", "-c", f"echo '{path}' >> /etc/shells"])
        ctx.run(["chsh", "-s", path])
    return Step("login shell", action, "core")
