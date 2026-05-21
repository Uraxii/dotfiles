#!/usr/bin/env python3
"""install.py — install packages declared in deps.toml across distros.

Reads ./deps.toml, detects the host distro from /etc/os-release, resolves
per-distro overrides, and installs missing packages via the right native
package manager (pacman, apt, dnf, nix profile) or fallback source
(cargo, uv-tool, pip, npm, AUR helper, manual instructions).

Usage:
    install.py                      # install everything (idempotent)
    install.py --group desktop      # install one group
    install.py --only ghostty,tmux  # install specific packages
    install.py -n                   # dry run; print what would happen
    install.py --list-groups        # list group names
    install.py --show ghostty       # resolve one pkg's install spec for this distro
    install.py --distro arch        # override detection (testing)

Exit code: 0 if every requested pkg installed-or-already-present, 1 otherwise.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import shlex
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["main"]

REPO_ROOT = Path(__file__).resolve().parent
DEPS_TOML = REPO_ROOT / "deps.toml"
RESERVED_KEYS = {"version", "supported_distros", "defaults", "groups", "shell", "profiles"}

log = logging.getLogger("install")


# --------------------------------------------------------------------------- #
# Distro detection
# --------------------------------------------------------------------------- #

DISTRO_ALIASES: dict[str, str] = {
    "arch": "arch", "manjaro": "arch", "endeavouros": "arch", "garuda": "arch",
    "nixos": "nixos",
    "ubuntu": "ubuntu", "debian": "ubuntu", "linuxmint": "ubuntu", "pop": "ubuntu",
    "fedora": "fedora", "rhel": "fedora", "centos": "fedora", "rocky": "fedora",
    "termux": "termux",
}


def detect_distro() -> str:
    """Return a canonical distro id from /etc/os-release (or termux env)."""
    # Termux is Android — no /etc/os-release on the Android root; the termux
    # one lives at $PREFIX/etc/os-release. $TERMUX_VERSION is always exported
    # in a termux shell, so use it as the authoritative signal.
    if os.environ.get("TERMUX_VERSION"):
        return "termux"
    osr = Path("/etc/os-release")
    if not osr.exists():
        raise SystemExit("cannot detect distro: /etc/os-release missing")
    kv: dict[str, str] = {}
    for line in osr.read_text().splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        kv[k.strip()] = v.strip().strip('"')
    candidates: list[str] = []
    if "ID" in kv:
        candidates.append(kv["ID"].lower())
    if "ID_LIKE" in kv:
        candidates.extend(p.lower() for p in kv["ID_LIKE"].split())
    for c in candidates:
        if c in DISTRO_ALIASES:
            return DISTRO_ALIASES[c]
    raise SystemExit(f"unsupported distro: ID={kv.get('ID')!r} ID_LIKE={kv.get('ID_LIKE')!r}")


# --------------------------------------------------------------------------- #
# Resolved package model
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Resolved:
    pkg_id: str
    install_name: str
    source: str
    version: str | None
    description: str
    url: str | None
    post_install: str | None
    enabled: bool
    bins: tuple[str, ...] = ()
    reason: str | None = None  # populated when source = "unsupported"
    install_cmd: str | None = None  # populated when source = "script"
    sudo: bool = False  # informational: does install require root?

    def __str__(self) -> str:
        v = f" {self.version}" if self.version else ""
        u = f" ({self.url})" if self.url else ""
        s = " [sudo]" if self.sudo else ""
        return f"{self.pkg_id} → {self.source}:{self.install_name}{v}{u}{s}"


def _normalise_bins(raw: object) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        return (raw,)
    if isinstance(raw, list) and all(isinstance(x, str) for x in raw):
        return tuple(raw)
    raise ValueError(f"`bin` must be a string or list of strings, got {type(raw).__name__}")


def _default_sudo(source: str, distro: str) -> bool:
    """Derive default sudo requirement from (source, distro).

    Override via `sudo = true|false` on entry or per-distro table.
      - native pacman/apt/dnf wrap the install cmd in sudo → true.
      - termux `pkg` is single-user Android — never sudo.
      - AUR helpers escalate internally → true.
      - nix/nix-unstable use the user profile → false.
      - cargo/npm/uv-tool/pip install to user dirs → false.
      - script: author wraps sudo explicitly inside install_cmd → default false.
      - manual/skip/unsupported never install → false.
    """
    if source == "native":
        return distro != "termux"
    if source == "aur":
        return True
    return False


def resolve(pkg_id: str, entry: dict, distro: str, defaults: dict) -> Resolved:
    """Merge defaults + entry + per-distro override into a Resolved spec."""
    if "pkg" not in entry:
        raise ValueError(f"{pkg_id}: missing required `pkg` field")
    if "description" not in entry:
        raise ValueError(f"{pkg_id}: missing required `description` field")
    override = entry.get(distro, {})
    if not isinstance(override, dict):
        raise ValueError(f"{pkg_id}: per-distro override for {distro!r} is not a table")
    source = override.get("source", entry.get("source", defaults.get("source", "native")))
    sudo_raw = override.get("sudo", entry.get("sudo"))
    if sudo_raw is None:
        sudo = _default_sudo(source, distro)
    else:
        if not isinstance(sudo_raw, bool):
            raise ValueError(f"{pkg_id}: `sudo` must be a bool, got {type(sudo_raw).__name__}")
        sudo = sudo_raw
    return Resolved(
        pkg_id=pkg_id,
        install_name=override.get("pkg", entry["pkg"]),
        source=source,
        version=override.get("version", entry.get("version")),
        description=entry["description"],
        url=override.get("url", entry.get("url")),
        post_install=entry.get("post_install"),
        enabled=bool(override.get("enabled", entry.get("enabled", defaults.get("enabled", True)))),
        bins=_normalise_bins(override.get("bin", entry.get("bin"))),
        reason=override.get("reason", entry.get("reason")),
        install_cmd=override.get("install_cmd", entry.get("install_cmd")),
        sudo=sudo,
    )


# --------------------------------------------------------------------------- #
# Version constraint
# --------------------------------------------------------------------------- #

_OP_RE = re.compile(r"^\s*(>=|<=|==|=|>|<|~=)?\s*([0-9][0-9A-Za-z.\-_+]*)\s*$")
_VER_RE = re.compile(r"\b(\d+(?:\.\d+){1,3})\b")


def probe_bin_version(bin_name: str) -> str | None:
    """Run `<bin> --version` and parse first `N.N[.N[.N]]` sequence.

    Used by the driver when a declared binary is on PATH but the adapter's
    presence query returns None (e.g. binary installed outside the active
    package manager). Returns None on timeout, missing binary, or no parse.
    """
    try:
        r = subprocess.run(
            [bin_name, "--version"],
            check=False, text=True, capture_output=True, timeout=3,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    text = (r.stdout or "") + "\n" + (r.stderr or "")
    m = _VER_RE.search(text)
    return m.group(1) if m else None


def _parse_ver(s: str) -> tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", s)) or (0,)


def _cmp(a: tuple[int, ...], b: tuple[int, ...]) -> int:
    return (a > b) - (a < b)


def satisfies(installed_ver: str | None, constraint: str | None) -> bool:
    """Return True if installed_ver satisfies constraint string.

    Constraint = "" / None → True. Multi-clause = comma-separated AND.
    Operators: =, ==, >=, <=, >, <, ~= (compatible-release: same major).

    Sentinel `"external"` (set by the driver when a declared binary is on
    PATH but no version could be probed) is accepted as satisfying any
    constraint — presence beats unknown version.
    """
    if not constraint:
        return True
    if installed_ver is None:
        return False
    if installed_ver == "external":
        log.warning(
            "  ! version unknown for external install — accepting pin %r on trust",
            constraint,
        )
        return True
    inst = _parse_ver(installed_ver)
    for clause in constraint.split(","):
        m = _OP_RE.match(clause)
        if not m:
            log.warning("unparseable version clause %r — treating as satisfied", clause)
            continue
        op, want = m.group(1) or "=", m.group(2)
        wv = _parse_ver(want)
        c = _cmp(inst, wv)
        ok = (
            (op in ("=", "==") and c == 0)
            or (op == ">=" and c >= 0)
            or (op == "<=" and c <= 0)
            or (op == ">" and c > 0)
            or (op == "<" and c < 0)
            or (op == "~=" and c >= 0 and inst[: max(1, len(wv) - 1)] == wv[: max(1, len(wv) - 1)])
        )
        if not ok:
            return False
    return True


# --------------------------------------------------------------------------- #
# Pkg-manager adapters
# --------------------------------------------------------------------------- #

@dataclass
class RunResult:
    installed: bool
    already_present: bool
    skipped_reason: str | None = None
    error: str | None = None


class Adapter:
    """Subclass per package source. `dry_run` skips state changes."""

    name = "abstract"

    def __init__(self, distro: str, dry_run: bool) -> None:
        self.distro = distro
        self.dry_run = dry_run

    # --- query --------------------------------------------------------------

    def installed_version(self, name: str) -> str | None:
        raise NotImplementedError

    # --- install ------------------------------------------------------------

    def install(self, name: str, version: str | None) -> RunResult:
        raise NotImplementedError

    # --- helpers ------------------------------------------------------------

    def _run(
        self,
        argv: list[str],
        *,
        capture: bool = False,
        env_extra: dict[str, str] | None = None,
    ) -> tuple[int, str]:
        log.debug("exec: %s", shlex.join(argv))
        if self.dry_run and argv[0] not in ("pacman", "dpkg", "rpm", "nix-env", "nix", "cargo", "tldr", "fc-cache", "sh", "bash"):
            # always allow read-only queries to run in dry-run too — those use `capture=True`
            return 0, ""
        if self.dry_run and not capture:
            log.info("[dry-run] %s", shlex.join(argv))
            return 0, ""
        env = None
        if env_extra:
            env = {**os.environ, **env_extra}
        try:
            r = subprocess.run(
                argv,
                check=False,
                text=True,
                stdout=subprocess.PIPE if capture else None,
                stderr=subprocess.PIPE if capture else None,
                env=env,
            )
        except FileNotFoundError as e:
            return 127, str(e)
        return r.returncode, (r.stdout or "")


# --- pacman (arch family) -----------------------------------------------------

class PacmanAdapter(Adapter):
    name = "pacman"

    def installed_version(self, name: str) -> str | None:
        rc, out = self._run(["pacman", "-Qi", name], capture=True)
        if rc != 0:
            return None
        for line in out.splitlines():
            if line.startswith("Version"):
                return line.split(":", 1)[1].strip()
        return None

    def install(self, name: str, version: str | None) -> RunResult:
        # pacman doesn't support range versions; install latest and let satisfies() warn later
        rc, _ = self._run(["sudo", "pacman", "-S", "--needed", "--noconfirm", name])
        return RunResult(installed=rc == 0, already_present=False, error=None if rc == 0 else f"pacman exit {rc}")


# --- AUR helper ---------------------------------------------------------------

class AurAdapter(PacmanAdapter):
    name = "aur"

    def __init__(self, distro: str, dry_run: bool) -> None:
        super().__init__(distro, dry_run)
        self.helper = next((h for h in ("yay", "paru") if shutil.which(h)), None)

    def install(self, name: str, version: str | None) -> RunResult:
        if self.helper is None:
            return RunResult(installed=False, already_present=False, error="no AUR helper found (install yay or paru)")
        rc, _ = self._run([self.helper, "-S", "--needed", "--noconfirm", name])
        return RunResult(installed=rc == 0, already_present=False, error=None if rc == 0 else f"{self.helper} exit {rc}")


# --- apt (debian/ubuntu) ------------------------------------------------------

class AptAdapter(Adapter):
    name = "apt"

    def installed_version(self, name: str) -> str | None:
        rc, out = self._run(["dpkg-query", "-W", "-f=${Version}", name], capture=True)
        return out.strip() if rc == 0 and out.strip() else None

    def install(self, name: str, version: str | None) -> RunResult:
        target = f"{name}={version}" if version and version.replace(".", "").isdigit() else name
        rc, _ = self._run(["sudo", "apt-get", "install", "-y", target])
        return RunResult(installed=rc == 0, already_present=False, error=None if rc == 0 else f"apt-get exit {rc}")


# --- pkg (termux) -------------------------------------------------------------

class TermuxAdapter(Adapter):
    """termux `pkg` (apt wrapper). No sudo on Android (single-user)."""

    name = "pkg"

    def installed_version(self, name: str) -> str | None:
        rc, out = self._run(["dpkg-query", "-W", "-f=${Version}", name], capture=True)
        return out.strip() if rc == 0 and out.strip() else None

    def install(self, name: str, version: str | None) -> RunResult:
        target = f"{name}={version}" if version and version.replace(".", "").isdigit() else name
        rc, _ = self._run(["pkg", "install", "-y", target])
        return RunResult(installed=rc == 0, already_present=False, error=None if rc == 0 else f"pkg exit {rc}")


# --- dnf (fedora/rhel) --------------------------------------------------------

class DnfAdapter(Adapter):
    name = "dnf"

    def installed_version(self, name: str) -> str | None:
        rc, out = self._run(["rpm", "-q", "--queryformat", "%{VERSION}", name], capture=True)
        return out.strip() if rc == 0 and out.strip() and "not installed" not in out else None

    def install(self, name: str, version: str | None) -> RunResult:
        target = f"{name}-{version}" if version and version.replace(".", "").isdigit() else name
        rc, _ = self._run(["sudo", "dnf", "install", "-y", target])
        return RunResult(installed=rc == 0, already_present=False, error=None if rc == 0 else f"dnf exit {rc}")


# --- nix profile --------------------------------------------------------------

class NixAdapter(Adapter):
    """nix profile add against the configured channel.

    Requires experimental features `nix-command` + `flakes`. Passed inline via
    `--extra-experimental-features` so the system nix.conf doesn't need to opt
    in. Attribute path uses dot syntax (e.g. `nerd-fonts._0xproto`) — passed
    verbatim to nix.
    """

    name = "nix"
    channel = "nixpkgs"
    _FLAGS = ["--extra-experimental-features", "nix-command flakes"]

    def installed_version(self, name: str) -> str | None:
        # nix-env still works for declarative profiles; for the new profile
        # format, fall back to `nix profile list --json`.
        rc, out = self._run(["nix-env", "-q", name], capture=True)
        if rc == 0 and out.strip():
            m = re.match(rf"{re.escape(name)}-([0-9].*)$", out.strip().splitlines()[0])
            if m:
                return m.group(1)
            return "present"
        import json
        rc, out = self._run(
            ["nix", *self._FLAGS, "profile", "list", "--json"], capture=True,
        )
        if rc != 0 or not out.strip():
            return None
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            return None
        elems = data.get("elements") or {}
        # Newer nix returns dict {id: entry}; older returns list.
        iter_elems = elems.values() if isinstance(elems, dict) else elems
        for el in iter_elems:
            attr = el.get("attrPath") or ""
            if attr == name or attr.endswith(f".{name}"):
                return el.get("originalUrl") or "present"
        return None

    def install(self, name: str, version: str | None) -> RunResult:
        target = f"{self.channel}#{name}"
        # Priority 4 (< default 5) so the new pkg wins file-collision resolution
        # against an existing `home-manager-path` aggregate in the profile.
        # Without this, any file overlap (locales, man pages) aborts the add.
        argv = ["nix", *self._FLAGS, "profile", "add", "--priority", "4", target]
        rc, _ = self._run(argv)
        return RunResult(installed=rc == 0, already_present=False, error=None if rc == 0 else f"nix profile exit {rc}")


class NixUnstableAdapter(NixAdapter):
    name = "nix-unstable"
    channel = "github:NixOS/nixpkgs/nixos-unstable"


# --- cargo --------------------------------------------------------------------

class CargoAdapter(Adapter):
    name = "cargo"

    def installed_version(self, name: str) -> str | None:
        rc, out = self._run(["cargo", "install", "--list"], capture=True)
        if rc != 0:
            return None
        for line in out.splitlines():
            m = re.match(rf"{re.escape(name)} v([0-9].*?):", line)
            if m:
                return m.group(1)
        return None

    def install(self, name: str, version: str | None) -> RunResult:
        if not shutil.which("cargo"):
            return RunResult(installed=False, already_present=False, error="cargo not in PATH; install rustup")
        argv = ["cargo", "install", name]
        if version and version.replace(".", "").isdigit():
            argv += ["--version", version]
        rc, _ = self._run(argv)
        return RunResult(installed=rc == 0, already_present=False, error=None if rc == 0 else f"cargo exit {rc}")


# --- npm (global) -------------------------------------------------------------

class NpmAdapter(Adapter):
    """npm install -g <name>[@version]. Works for plain names, scoped packages
    (@scope/name), and tarball/URL specs (e.g. file:./pkg.tgz, https://...).

    Idempotency: queries `npm ls -g <name> --json`. Version pin honoured if
    parseable (numeric prefix); operator-style constraints (>=, ~=) handed to
    npm verbatim (npm supports semver ranges natively).
    """

    name = "npm"

    def installed_version(self, name: str) -> str | None:
        import json
        rc, out = self._run(["npm", "ls", "-g", name, "--depth=0", "--json"], capture=True)
        if rc != 0 or not out.strip():
            return None
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            return None
        deps = data.get("dependencies") or {}
        entry = deps.get(name)
        if not entry:
            return None
        return entry.get("version")

    def install(self, name: str, version: str | None) -> RunResult:
        if not shutil.which("npm"):
            return RunResult(
                installed=False, already_present=False,
                error="npm not in PATH; install nodejs (./install.py --only nodejs)",
            )
        # name may be `pkg`, `@scope/pkg`, a tarball path, or a URL — pass through.
        # Append @version only if version looks like a numeric spec (npm accepts
        # ranges directly: `pkg@^1.2`, `pkg@latest`, etc).
        spec = name
        if version:
            spec = f"{name}@{version}"

        # Nix-store-installed node has an immutable global prefix
        # (`/nix/store/...-nodejs-X/lib/node_modules`). `npm install -g` will
        # ENOENT trying to mkdir there. Redirect to a user-writable prefix.
        env_extra: dict[str, str] | None = None
        rc, prefix_out = self._run(
            ["npm", "config", "get", "prefix"], capture=True,
        )
        prefix = prefix_out.strip()
        if rc == 0 and prefix.startswith("/nix/store"):
            user_prefix = str(Path.home() / ".npm-global")
            (Path(user_prefix) / "bin").mkdir(parents=True, exist_ok=True)
            env_extra = {"NPM_CONFIG_PREFIX": user_prefix}
            log.info(
                "  • npm prefix in nix store (%s) — redirecting to %s "
                "(ensure %s/bin is on PATH)",
                prefix, user_prefix, user_prefix,
            )

        rc, _ = self._run(["npm", "install", "-g", spec], env_extra=env_extra)
        return RunResult(installed=rc == 0, already_present=False, error=None if rc == 0 else f"npm exit {rc}")


# --- uv tool (PEP 668-safe pip replacement) -----------------------------------

class UvToolAdapter(Adapter):
    """uv tool install — isolated per-tool venvs. PEP 668-safe.

    Preferred over plain pip on systems where the system Python is
    externally-managed (Arch, Fedora ≥39, Debian ≥12, Ubuntu ≥23.04). Each tool
    gets its own venv; binaries land in ~/.local/share/uv/tools/<tool>/bin and
    are symlinked into ~/.local/bin (set by uv's PATH-management one-shot).

    Supports pip-style extras syntax via brackets, e.g. `xonsh[full]`.
    """

    name = "uv-tool"
    _BARE_RE = re.compile(r"^([A-Za-z0-9._-]+)")

    def installed_version(self, name: str) -> str | None:
        rc, out = self._run(["uv", "tool", "list"], capture=True)
        if rc != 0:
            return None
        m = self._BARE_RE.match(name)
        bare = m.group(1) if m else name
        for line in out.splitlines():
            line = line.strip()
            # `uv tool list` lines: "<name> v<version>"
            m = re.match(rf"^{re.escape(bare)}\s+v([0-9][^\s]*)", line)
            if m:
                return m.group(1)
        return None

    def install(self, name: str, version: str | None) -> RunResult:
        if not shutil.which("uv"):
            return RunResult(
                installed=False, already_present=False,
                error="uv not in PATH; install: ./install.py --only uv",
            )
        spec = name
        if version:
            # uv tool accepts PEP 440 specifier syntax: pkg==X, pkg>=X, pkg~=X
            # If version is numeric-only, prepend ==; else pass operator verbatim.
            spec = f"{name}{version}" if version.lstrip()[:1] in "<>=~!" else f"{name}=={version}"
        rc, _ = self._run(["uv", "tool", "install", spec])
        return RunResult(installed=rc == 0, already_present=False, error=None if rc == 0 else f"uv tool exit {rc}")


# --- pip ----------------------------------------------------------------------

class PipAdapter(Adapter):
    """pip install --user. Auto-adds --break-system-packages on PEP 668
    externally-managed Pythons (Arch, Fedora ≥39, Debian ≥12, Ubuntu ≥23.04).

    Strip pip-style extras (`pkg[full]`) when querying `pip show` since pip
    records the base distribution name.
    """

    name = "pip"
    _BARE_RE = re.compile(r"^([A-Za-z0-9._-]+)")

    @staticmethod
    def _is_externally_managed() -> bool:
        rc = subprocess.run(
            [sys.executable, "-c",
             "import sys, pathlib;"
             "p = pathlib.Path(sys.prefix) / 'lib' /"
             " f'python{sys.version_info.major}.{sys.version_info.minor}' /"
             " 'EXTERNALLY-MANAGED';"
             "raise SystemExit(0 if p.exists() else 1)"],
            check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ).returncode
        return rc == 0

    def installed_version(self, name: str) -> str | None:
        m = self._BARE_RE.match(name)
        bare = m.group(1) if m else name
        rc, out = self._run([sys.executable, "-m", "pip", "show", bare], capture=True)
        if rc != 0:
            return None
        for line in out.splitlines():
            if line.startswith("Version:"):
                return line.split(":", 1)[1].strip()
        return None

    def install(self, name: str, version: str | None) -> RunResult:
        spec = name
        if version:
            spec = f"{name}{version}" if version.lstrip()[:1] in "<>=~!" else f"{name}=={version}"
        argv = [sys.executable, "-m", "pip", "install", "--user", spec]
        if self._is_externally_managed():
            argv.append("--break-system-packages")
        rc, _ = self._run(argv)
        return RunResult(installed=rc == 0, already_present=False, error=None if rc == 0 else f"pip exit {rc}")


# --- script (upstream curl|bash installer) -----------------------------------

class ScriptAdapter(Adapter):
    """Run an upstream-provided install command (e.g. `curl -fsSL ... | bash`).

    Presence detection is bin-only — there is no package-manager registry to
    query. The driver's `spec.bins` PATH probe handles already-installed
    state; this adapter just shells out to the declared `install_cmd`.

    `install_cmd` is REQUIRED in deps.toml; resolve-time validation rejects a
    `source = "script"` entry without it. The command is executed via
    `bash -c <cmd>` so pipelines and redirections work as-written upstream.
    """

    name = "script"

    def installed_version(self, name: str) -> str | None:
        return None  # bin-probe fallback in driver handles presence

    def install(self, name: str, version: str | None) -> RunResult:
        # `name` here is `spec.install_name`; the actual shell command was
        # passed in via spec.install_cmd and is looked up by process_one,
        # which stashes it on the adapter before calling install().
        cmd = getattr(self, "_cmd", None)
        if not cmd:
            return RunResult(
                installed=False, already_present=False,
                error="script adapter: install_cmd not set (deps.toml missing install_cmd)",
            )
        rc, _ = self._run(["bash", "-c", cmd])
        return RunResult(
            installed=rc == 0, already_present=False,
            error=None if rc == 0 else f"script exit {rc}",
        )


# --- manual / skip ------------------------------------------------------------

class ManualAdapter(Adapter):
    name = "manual"

    def installed_version(self, name: str) -> str | None:
        return None  # never auto-detect; user-driven

    def install(self, name: str, version: str | None) -> RunResult:
        return RunResult(installed=False, already_present=False, skipped_reason="manual")


class SkipAdapter(Adapter):
    name = "skip"

    def installed_version(self, name: str) -> str | None:
        return None

    def install(self, name: str, version: str | None) -> RunResult:
        return RunResult(installed=False, already_present=False, skipped_reason="declared skip")


class UnsupportedAdapter(Adapter):
    """Platform doesn't ship this package. Distinct from `skip` (user-deferred).

    Reason comes from spec.reason; process_one short-circuits to surface it
    in the report so this adapter is largely a marker. installed_version
    still probes via bins fallback so an externally-installed binary can
    satisfy the dep even on an unsupported platform.
    """

    name = "unsupported"

    def installed_version(self, name: str) -> str | None:
        return None

    def install(self, name: str, version: str | None) -> RunResult:
        return RunResult(installed=False, already_present=False, skipped_reason="unsupported on this platform")


# --- dispatch -----------------------------------------------------------------

NATIVE_BY_DISTRO: dict[str, type[Adapter]] = {
    "arch": PacmanAdapter,
    "ubuntu": AptAdapter,
    "fedora": DnfAdapter,
    "nixos": NixAdapter,
    "termux": TermuxAdapter,
}


def get_adapter(source: str, distro: str, dry_run: bool) -> Adapter:
    if source == "native":
        cls = NATIVE_BY_DISTRO.get(distro)
        if cls is None:
            raise SystemExit(f"no native adapter for distro {distro!r}")
        return cls(distro, dry_run)
    table: dict[str, type[Adapter]] = {
        "aur": AurAdapter, "nix": NixAdapter, "nix-unstable": NixUnstableAdapter,
        "cargo": CargoAdapter, "pip": PipAdapter, "uv-tool": UvToolAdapter, "npm": NpmAdapter,
        "script": ScriptAdapter,
        "manual": ManualAdapter, "skip": SkipAdapter, "unsupported": UnsupportedAdapter,
    }
    cls = table.get(source)
    if cls is None:
        raise SystemExit(f"unknown source {source!r} for distro {distro!r}")
    return cls(distro, dry_run)


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #

@dataclass
class Report:
    installed: list[str] = field(default_factory=list)
    already: list[str] = field(default_factory=list)
    disabled: list[str] = field(default_factory=list)
    manual: list[tuple[str, str | None]] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)

    def emit(self) -> None:
        log.info("=" * 50)
        log.info("install summary")
        log.info("=" * 50)
        for cat, items in (
            ("installed", self.installed), ("already present", self.already),
            ("disabled (enabled=false)", self.disabled),
            ("skipped (declared)", [f"{p}: {r}" for p, r in self.skipped]),
            ("manual (action required)", [f"{p} → {u or 'see deps.toml'}" for p, u in self.manual]),
            ("failed", [f"{p}: {e}" for p, e in self.failed]),
        ):
            if items:
                log.info("  %s (%d):", cat, len(items))
                for i in items:
                    log.info("    - %s", i)


# --------------------------------------------------------------------------- #
# Per-system defaults / interactive selector
# --------------------------------------------------------------------------- #

def is_headless() -> bool:
    """No graphical session detected (no $DISPLAY and no $WAYLAND_DISPLAY)."""
    return not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def default_profile_for(distro: str, config: dict) -> str | None:
    """Pick a sensible default profile for the running system.

    Returns profile name or None. Auto-preselection rules:
      - termux: None (per-pkg `unsupported` overrides already cover desktop gap).
      - headless + `[profiles.server]` declared: "server".
      - graphical session OR no server profile: None (install everything).
    """
    profiles = config.get("profiles", {})
    if distro == "termux":
        return None
    if "server" in profiles and is_headless():
        return "server"
    return None


def _initial_selection(
    config: dict,
    distro: str,
    defaults: dict,
    profile: str | None,
) -> set[str]:
    """Pkgs preselected in interactive mode: enabled + not profile-excluded
    + source not in {skip, unsupported, manual}.
    """
    excluded: set[str] = set()
    if profile:
        prof = config.get("profiles", {}).get(profile, {})
        groups = config.get("groups", {})
        for g in prof.get("exclude_groups", []) or []:
            excluded.update(groups.get(g, []))
        for pid in prof.get("exclude", []) or []:
            excluded.add(pid)

    selected: set[str] = set()
    for k, entry in config.items():
        if k in RESERVED_KEYS:
            continue
        try:
            spec = resolve(k, entry, distro, defaults)
        except ValueError:
            continue
        if not spec.enabled or spec.source in ("skip", "unsupported", "manual"):
            continue
        if k in excluded:
            continue
        selected.add(k)
    return selected


class _Row:
    __slots__ = ("kind", "pkg_id", "group")

    def __init__(self, kind: str, pkg_id: str | None = None, group: str | None = None) -> None:
        self.kind = kind  # "group" or "pkg"
        self.pkg_id = pkg_id
        self.group = group


def _build_rows(config: dict) -> list[_Row]:
    """Flat scrollable rows: group header line + pkg lines, declaration order.

    Pkgs not in any group go in trailing 'other' section. Group ordering
    follows [groups] declaration; pkg ordering inside a group follows the
    group's id list.
    """
    rows: list[_Row] = []
    groups = config.get("groups", {})
    all_pkg_ids = {k for k in config if k not in RESERVED_KEYS}
    assigned: set[str] = set()
    for gname, members in groups.items():
        rows.append(_Row("group", group=gname))
        for pid in members:
            if pid in all_pkg_ids:
                rows.append(_Row("pkg", pkg_id=pid, group=gname))
                assigned.add(pid)
    leftover = [k for k in config if k in all_pkg_ids and k not in assigned]
    if leftover:
        rows.append(_Row("group", group="other"))
        for pid in leftover:
            rows.append(_Row("pkg", pkg_id=pid, group="other"))
    return rows


def _curses_start_with_fallback(run_fn) -> None:
    """Call curses.wrapper(run_fn). If TERM has no terminfo entry on this host
    (e.g. SSH from a ghostty client onto a server w/o ghostty terminfo), retry
    with common fallbacks. Raises the last curses.error if all attempts fail.
    """
    import curses
    original = os.environ.get("TERM")
    try:
        curses.wrapper(run_fn)
        return
    except curses.error as e:
        last_err = e

    for fallback in ("xterm-256color", "xterm", "vt100", "ansi"):
        if fallback == original:
            continue
        os.environ["TERM"] = fallback
        try:
            curses.wrapper(run_fn)
            log.info(
                "curses ran with TERM=%s (host TERM=%r had no terminfo)",
                fallback, original,
            )
            return
        except curses.error as e:
            last_err = e
            continue
        finally:
            if original is not None:
                os.environ["TERM"] = original
            else:
                os.environ.pop("TERM", None)
    raise last_err


def interactive_select(
    config: dict,
    distro: str,
    defaults: dict,
    auto_profile: str | None,
) -> tuple[set[str] | None, bool]:
    """Curses multi-select. Returns (selected_ids, dry_run_requested).

    selected_ids = None  → user cancelled (q/esc).
    dry_run_requested True iff user pressed `d` to submit as dry-run.

    Raises RuntimeError if curses can't init under any TERM fallback (host
    has no usable terminfo). Caller should catch and degrade to non-interactive.
    """
    import curses

    selected: set[str] = _initial_selection(config, distro, defaults, auto_profile)
    rows = _build_rows(config)
    # Cache resolved spec per pkg for the session (description, source, sudo).
    cache: dict[str, Resolved | None] = {}
    for r in rows:
        if r.kind == "pkg" and r.pkg_id is not None:
            try:
                cache[r.pkg_id] = resolve(r.pkg_id, config[r.pkg_id], distro, defaults)
            except ValueError:
                cache[r.pkg_id] = None

    state = {"cursor": 0, "submit": False, "dry": False}

    def _group_pkg_ids(group: str) -> list[str]:
        return [
            r.pkg_id for r in rows
            if r.kind == "pkg" and r.group == group and r.pkg_id is not None
        ]

    def _run(stdscr: "curses._CursesWindow") -> None:
        curses.curs_set(0)
        stdscr.nodelay(False)
        while True:
            stdscr.erase()
            h, w = stdscr.getmaxyx()
            profile_label = auto_profile or "none"
            header = (
                f" install.py  distro={distro}  profile={profile_label}  "
                f"selected={len(selected)}/{sum(1 for r in rows if r.kind == 'pkg')}"
            )
            stdscr.addnstr(0, 0, header.ljust(w - 1), w - 1, curses.A_REVERSE)
            help_line = (
                " space=toggle  g=group-toggle  a=all  z=clear  "
                "enter=install  d=dry-run  q=quit"
            )
            stdscr.addnstr(h - 1, 0, help_line.ljust(w - 1), w - 1, curses.A_REVERSE)

            # Viewport: rows visible between line 2 and h-2.
            view_h = h - 3
            cursor = state["cursor"]
            top = max(0, cursor - view_h + 1) if cursor >= view_h else 0
            for i in range(top, min(len(rows), top + view_h)):
                r = rows[i]
                y = 2 + (i - top)
                is_cursor = i == cursor
                attr = curses.A_REVERSE if is_cursor else curses.A_NORMAL
                if r.kind == "group":
                    pids = _group_pkg_ids(r.group or "")
                    chk = sum(1 for p in pids if p in selected)
                    line = f"  [{r.group}]  ({chk}/{len(pids)})"
                    stdscr.addnstr(y, 0, line.ljust(w - 1), w - 1, attr | curses.A_BOLD)
                else:
                    spec = cache.get(r.pkg_id or "")
                    if spec is not None:
                        src = spec.source
                        sudo = " sudo" if spec.sudo else ""
                        desc = spec.description
                    else:
                        src, sudo, desc = "?", "", ""
                    mark = "[x]" if r.pkg_id in selected else "[ ]"
                    line = f"    {mark} {(r.pkg_id or ''):<22} [{src}{sudo}]  {desc}"
                    stdscr.addnstr(y, 0, line.ljust(w - 1), w - 1, attr)

            stdscr.refresh()
            k = stdscr.getch()
            if k in (ord("q"), 27):
                return
            if k in (curses.KEY_UP, ord("k")):
                state["cursor"] = max(0, cursor - 1)
            elif k in (curses.KEY_DOWN, ord("j")):
                state["cursor"] = min(len(rows) - 1, cursor + 1)
            elif k == curses.KEY_NPAGE:
                state["cursor"] = min(len(rows) - 1, cursor + view_h)
            elif k == curses.KEY_PPAGE:
                state["cursor"] = max(0, cursor - view_h)
            elif k == curses.KEY_HOME:
                state["cursor"] = 0
            elif k == curses.KEY_END:
                state["cursor"] = len(rows) - 1
            elif k == ord(" "):
                r = rows[cursor]
                if r.kind == "pkg" and r.pkg_id is not None:
                    if r.pkg_id in selected:
                        selected.discard(r.pkg_id)
                    else:
                        selected.add(r.pkg_id)
                elif r.kind == "group":
                    pids = _group_pkg_ids(r.group or "")
                    if all(p in selected for p in pids):
                        for p in pids:
                            selected.discard(p)
                    else:
                        for p in pids:
                            selected.add(p)
            elif k == ord("g"):
                r = rows[cursor]
                grp = r.group
                if grp:
                    pids = _group_pkg_ids(grp)
                    if all(p in selected for p in pids):
                        for p in pids:
                            selected.discard(p)
                    else:
                        for p in pids:
                            selected.add(p)
            elif k == ord("a"):
                for r in rows:
                    if r.kind == "pkg" and r.pkg_id is not None:
                        selected.add(r.pkg_id)
            elif k == ord("z"):
                selected.clear()
            elif k == ord("d"):
                state["dry"] = True
                state["submit"] = True
                return
            elif k in (curses.KEY_ENTER, 10, 13):
                state["submit"] = True
                return

    try:
        _curses_start_with_fallback(_run)
    except curses.error as e:
        raise RuntimeError(
            f"curses unavailable: {e} (TERM={os.environ.get('TERM')!r}; "
            "install terminfo for your terminal or use --no-interactive)"
        ) from e
    if not state["submit"]:
        return None, False
    return selected, state["dry"]


def select_packages(
    config: dict,
    distro: str,
    group: str | None,
    only: set[str] | None,
) -> list[tuple[str, dict]]:
    all_pkgs = {k: v for k, v in config.items() if k not in RESERVED_KEYS}
    if only:
        unknown = only - all_pkgs.keys()
        if unknown:
            raise SystemExit(f"unknown packages: {sorted(unknown)}")
        return [(k, all_pkgs[k]) for k in only]
    if group:
        groups = config.get("groups", {})
        if group not in groups:
            raise SystemExit(f"unknown group {group!r}; available: {sorted(groups)}")
        ids = groups[group]
        return [(k, all_pkgs[k]) for k in ids if k in all_pkgs]
    return list(all_pkgs.items())


def apply_profile(
    pkgs: list[tuple[str, dict]],
    profile_name: str,
    config: dict,
) -> tuple[list[tuple[str, dict]], list[str]]:
    """Filter pkgs through `[profiles.<name>]` exclude rules.

    Profile fields:
      - exclude_groups: list[str] — group names whose members are removed.
      - exclude: list[str] — individual pkg ids removed.

    Returns (kept_pkgs, excluded_pkg_ids). Excluded ids logged by caller.
    Unknown group or pkg id in profile is a hard error (no silent drift).
    """
    profiles = config.get("profiles", {})
    if profile_name not in profiles:
        raise SystemExit(
            f"unknown profile {profile_name!r}; available: {sorted(profiles)}"
        )
    prof = profiles[profile_name]
    if not isinstance(prof, dict):
        raise SystemExit(f"profile {profile_name!r} must be a table")

    excluded_ids: set[str] = set()
    groups = config.get("groups", {})
    for g in prof.get("exclude_groups", []) or []:
        if g not in groups:
            raise SystemExit(
                f"profile {profile_name!r}: unknown group {g!r}; "
                f"available: {sorted(groups)}"
            )
        excluded_ids.update(groups[g])
    for pid in prof.get("exclude", []) or []:
        all_pkg_ids = {k for k in config if k not in RESERVED_KEYS}
        if pid not in all_pkg_ids:
            raise SystemExit(
                f"profile {profile_name!r}: unknown package {pid!r}"
            )
        excluded_ids.add(pid)

    kept = [(k, v) for k, v in pkgs if k not in excluded_ids]
    dropped = sorted(k for k, _ in pkgs if k in excluded_ids)
    return kept, dropped


def process_one(
    pkg_id: str,
    entry: dict,
    distro: str,
    defaults: dict,
    dry_run: bool,
    report: Report,
) -> None:
    try:
        spec = resolve(pkg_id, entry, distro, defaults)
    except ValueError as e:
        log.error("%s: resolve error: %s", pkg_id, e)
        report.failed.append((pkg_id, str(e)))
        return

    if not spec.enabled:
        log.info("%s: disabled — skip", pkg_id)
        report.disabled.append(pkg_id)
        return

    if spec.source == "script" and not spec.install_cmd:
        log.error("%s: source=script but install_cmd not set in deps.toml", pkg_id)
        report.failed.append((pkg_id, "script source requires install_cmd"))
        return

    adapter = get_adapter(spec.source, distro, dry_run)
    if spec.source == "script":
        adapter._cmd = spec.install_cmd  # type: ignore[attr-defined]
    sudo_tag = " (sudo)" if spec.sudo else ""
    log.info("• %s [%s]%s %s", pkg_id, spec.source, sudo_tag, spec.description)

    # presence + pin check
    inst = adapter.installed_version(spec.install_name)
    if inst is None and spec.bins:
        # Fallback: any declared binary on PATH = treat as externally installed.
        # Probe `<bin> --version` to extract a real version when possible; if the
        # probe fails we drop to the "external" sentinel, which `satisfies()`
        # accepts as matching any pin (presence-on-trust).
        for b in spec.bins:
            path = shutil.which(b)
            if path:
                log.info("  ✓ detected external install: %s", path)
                probed = probe_bin_version(b)
                if probed:
                    log.info("    probed version: %s", probed)
                    inst = probed
                else:
                    inst = "external"
                break
    if inst is not None:
        if satisfies(inst, spec.version):
            log.info("  ✓ already present (v%s)", inst)
            report.already.append(pkg_id)
            return
        log.info("  ↻ installed v%s violates pin %r — reinstall", inst, spec.version)

    # install
    if spec.source == "manual":
        log.info("  ⚠ manual install required: %s", spec.url or "(see deps.toml)")
        report.manual.append((pkg_id, spec.url))
        return

    if spec.source == "unsupported":
        reason = spec.reason or "platform doesn't ship this package"
        log.info("  ⊘ unsupported on %s: %s", distro, reason)
        report.skipped.append((pkg_id, f"unsupported on {distro}: {reason}"))
        return

    if spec.source == "skip":
        log.info("  ⊘ declared skip")
        report.skipped.append((pkg_id, "declared skip"))
        return

    if dry_run:
        if spec.source == "script":
            log.info("  [dry-run] would run script: %s", spec.install_cmd)
        else:
            log.info("  [dry-run] would install %s via %s", spec.install_name, spec.source)
        report.installed.append(pkg_id)
        return

    result = adapter.install(spec.install_name, spec.version)
    if result.skipped_reason:
        # For `unsupported` source, prefer the per-pkg reason from deps.toml
        # over the generic adapter message ("unsupported on this platform").
        reason = result.skipped_reason
        if spec.source == "unsupported" and spec.reason:
            reason = f"unsupported on {distro}: {spec.reason}"
        report.skipped.append((pkg_id, reason))
        return
    if not result.installed:
        log.error("  ✗ install failed: %s", result.error)
        report.failed.append((pkg_id, result.error or "unknown"))
        return
    log.info("  ✓ installed")
    report.installed.append(pkg_id)

    if spec.post_install:
        log.info("  → post_install: %s", spec.post_install)
        rc = subprocess.run(spec.post_install, shell=True, check=False).returncode
        if rc != 0:
            log.warning("  post_install exit %d", rc)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _current_login_shell() -> str | None:
    """Return the user's login shell from getent passwd (authoritative).

    Falls back to $SHELL if getent missing. Returns None on probe failure.
    """
    user = os.environ.get("USER") or os.environ.get("LOGNAME")
    if user and shutil.which("getent"):
        r = subprocess.run(
            ["getent", "passwd", user], check=False, capture_output=True, text=True,
        )
        if r.returncode == 0 and r.stdout:
            fields = r.stdout.rstrip("\n").split(":")
            if len(fields) >= 7:
                return fields[6] or None
    env_shell = os.environ.get("SHELL")
    return env_shell or None


def apply_default_shell(
    config: dict,
    distro: str,
    defaults: dict,
    dry_run: bool,
    override_id: str | None = None,
) -> tuple[bool, str | None]:
    """Apply [shell].default from config, or override_id if passed.

    Returns (changed, error). `changed=False, error=None` means no-op (already set
    or no [shell] block).
    """
    shell_cfg = config.get("shell")
    if not shell_cfg and not override_id:
        return False, None
    target_id = override_id or (shell_cfg or {}).get("default")
    if not target_id:
        return False, None

    if target_id not in config or target_id in RESERVED_KEYS:
        return False, f"shell id {target_id!r} is not a declared package"

    try:
        spec = resolve(target_id, config[target_id], distro, defaults)
    except ValueError as e:
        return False, f"resolve error for shell {target_id!r}: {e}"

    # Find binary path on PATH.
    bin_path: str | None = None
    candidates = spec.bins or (target_id,)
    for b in candidates:
        p = shutil.which(b)
        if p:
            bin_path = p
            break
    if not bin_path:
        return False, f"shell binary not found on PATH (looked for {list(candidates)}); install it first"

    current = _current_login_shell()
    # Resolve symlinks so /bin/zsh vs /usr/bin/zsh (usrmerge) compare equal.
    def _real(p: str | None) -> str | None:
        if not p:
            return p
        try:
            return os.path.realpath(p)
        except OSError:
            return p

    if _real(current) == _real(bin_path):
        log.info("default shell: already %s", current)
        return False, None

    log.info("default shell: %s → %s", current or "<unknown>", bin_path)

    # Ensure registered in /etc/shells.
    etc_shells = Path("/etc/shells")
    listed = False
    if etc_shells.exists():
        listed = any(
            line.strip() == bin_path for line in etc_shells.read_text().splitlines()
        )
    if not listed:
        log.info("  • /etc/shells does not list %s — appending (sudo)", bin_path)
        if dry_run:
            log.info("  [dry-run] would: echo %s | sudo tee -a /etc/shells", bin_path)
        else:
            r = subprocess.run(
                ["sudo", "tee", "-a", "/etc/shells"],
                input=bin_path + "\n", text=True, check=False,
                stdout=subprocess.DEVNULL,
            )
            if r.returncode != 0:
                return False, f"failed to register {bin_path} in /etc/shells (sudo exit {r.returncode})"

    # chsh — operates on the current user, no sudo needed.
    if dry_run:
        log.info("  [dry-run] would: chsh -s %s", bin_path)
        return True, None
    r = subprocess.run(["chsh", "-s", bin_path], check=False)
    if r.returncode != 0:
        return False, f"chsh exit {r.returncode}"
    log.info("  ✓ login shell switched to %s (re-login to take effect)", bin_path)
    return True, None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--group", help="install one group from [groups]")
    p.add_argument("--only", help="comma-separated package ids")
    p.add_argument(
        "--profile",
        help="apply named profile from [profiles] (e.g. 'server' to drop desktop pkgs)",
    )
    p.add_argument("--list-profiles", action="store_true")
    p.add_argument(
        "--list-sudo", action="store_true",
        help="list selected packages that require sudo for the current distro",
    )
    p.add_argument("--distro", help="override detected distro (testing)")
    p.add_argument("-n", "--dry-run", action="store_true")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--list-groups", action="store_true")
    p.add_argument("--list-packages", action="store_true")
    p.add_argument("--show", metavar="PKG", help="resolve one pkg for this distro and exit")
    p.add_argument("--config", default=str(DEPS_TOML), help="path to deps.toml")
    p.add_argument("--shell", metavar="PKG_ID", help="override [shell].default; apply this shell")
    p.add_argument("--skip-shell", action="store_true", help="do not touch login shell even if [shell].default set")
    p.add_argument(
        "-i", "--interactive", action="store_true",
        help="force interactive curses selector (otherwise auto when tty + no --group/--only/--profile)",
    )
    p.add_argument(
        "--no-interactive", action="store_true",
        help="force-skip interactive selector even on tty (for scripted use in a terminal)",
    )
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )

    # Prepend user-local bin dirs so binaries dropped during this run
    # (astral `uv` → ~/.local/bin/uv, uv-tool venv symlinks → ~/.local/bin/<tool>,
    # cargo → ~/.cargo/bin, etc) are findable by subsequent shutil.which()
    # probes in the SAME process. Without this, e.g. `xonsh` (uv-tool) fails
    # with "uv not in PATH" even after uv just installed seconds earlier,
    # because uv's astral installer drops into ~/.local/bin which the user's
    # login shell rc hasn't been re-sourced to pick up yet.
    extra_path_dirs = [
        str(Path.home() / ".local" / "bin"),
        str(Path.home() / ".cargo" / "bin"),
    ]
    current_path = os.environ.get("PATH", "")
    current_parts = current_path.split(":")
    prepended = [d for d in extra_path_dirs if d not in current_parts]
    if prepended:
        os.environ["PATH"] = ":".join(prepended) + (":" + current_path if current_path else "")
        log.info("PATH: prepended %s", ", ".join(prepended))

    cfg_path = Path(args.config)
    if not cfg_path.exists():
        log.error("config not found: %s", cfg_path)
        return 2
    config = tomllib.loads(cfg_path.read_text())
    defaults = config.get("defaults", {})

    if args.list_groups:
        for g, members in sorted(config.get("groups", {}).items()):
            print(f"{g}: {', '.join(members)}")
        return 0

    if args.list_packages:
        for k in sorted(k for k in config if k not in RESERVED_KEYS):
            print(f"{k}: {config[k].get('description', '')}")
        return 0

    if args.list_profiles:
        for name, body in sorted(config.get("profiles", {}).items()):
            xg = body.get("exclude_groups", []) or []
            xp = body.get("exclude", []) or []
            print(f"{name}: exclude_groups={xg} exclude={xp}")
        return 0

    distro = args.distro or detect_distro()
    log.info("distro: %s", distro)

    if distro not in config.get("supported_distros", []):
        log.warning("distro %r not in supported_distros — continuing anyway", distro)

    if args.show:
        if args.show not in config or args.show in RESERVED_KEYS:
            log.error("unknown package: %s", args.show)
            return 2
        spec = resolve(args.show, config[args.show], distro, defaults)
        for f in ("pkg_id", "install_name", "source", "version", "description", "url", "post_install", "enabled", "sudo", "reason"):
            print(f"  {f}: {getattr(spec, f)}")
        return 0

    only = {s.strip() for s in args.only.split(",")} if args.only else None

    # Decide interactive mode.
    tty_ok = sys.stdin.isatty() and sys.stdout.isatty()
    list_modes_active = bool(
        args.list_groups or args.list_packages or args.list_profiles or args.list_sudo
    )
    auto_tui = (
        tty_ok
        and not args.no_interactive
        and not args.group
        and not only
        and not args.profile
        and not list_modes_active
    )
    use_tui = args.interactive or auto_tui

    if use_tui and not tty_ok:
        log.warning("interactive requested but stdin/stdout not a tty — falling back")
        use_tui = False

    fallback_profile: str | None = None  # set if TUI was attempted but failed
    if use_tui:
        auto_profile = default_profile_for(distro, config)
        if auto_profile:
            log.info("interactive: preselecting profile %r (headless detected)", auto_profile)
        try:
            result_ids, dry_from_tui = interactive_select(
                config, distro, defaults, auto_profile,
            )
        except RuntimeError as e:
            log.warning("%s", e)
            log.warning("falling back to non-interactive install")
            use_tui = False
            fallback_profile = auto_profile
        else:
            if result_ids is None:
                log.info("interactive: cancelled — nothing installed")
                return 0
            if not result_ids:
                log.info("interactive: no packages selected — nothing to do")
                return 0
            if dry_from_tui:
                args.dry_run = True
            # Preserve declaration order so install ordering (e.g. nodejs
            # before opencode, uv before xonsh) is respected.
            selected = [
                (k, v) for k, v in config.items()
                if k not in RESERVED_KEYS and k in result_ids
            ]

    if not use_tui:
        selected = select_packages(config, distro, args.group, only)
        effective_profile = args.profile or fallback_profile
        if effective_profile:
            if only:
                log.info("profile %r ignored: --only takes precedence", effective_profile)
            else:
                selected, dropped = apply_profile(selected, effective_profile, config)
                if dropped:
                    profile_src = "fallback" if effective_profile == fallback_profile and not args.profile else "explicit"
                    log.info(
                        "profile %r (%s) excludes %d pkg(s): %s",
                        effective_profile, profile_src, len(dropped), ", ".join(dropped),
                    )

    log.info("selected: %d package(s)", len(selected))

    if args.list_sudo:
        sudo_pkgs: list[tuple[str, str]] = []
        no_sudo_pkgs: list[str] = []
        for pkg_id, entry in selected:
            try:
                spec = resolve(pkg_id, entry, distro, defaults)
            except ValueError as e:
                log.error("%s: resolve error: %s", pkg_id, e)
                continue
            if spec.sudo:
                sudo_pkgs.append((pkg_id, spec.source))
            else:
                no_sudo_pkgs.append(pkg_id)
        print(f"requires sudo ({len(sudo_pkgs)}):")
        for pid, src in sudo_pkgs:
            print(f"  - {pid} [{src}]")
        print(f"no sudo ({len(no_sudo_pkgs)}):")
        for pid in no_sudo_pkgs:
            print(f"  - {pid}")
        return 0

    report = Report()
    for pkg_id, entry in selected:
        process_one(pkg_id, entry, distro, defaults, args.dry_run, report)

    report.emit()

    # Post-install: apply default login shell if declared.
    if not args.skip_shell:
        changed, err = apply_default_shell(
            config, distro, defaults, args.dry_run, override_id=args.shell,
        )
        if err:
            log.error("shell switch: %s", err)
            return 1 if not report.failed else 1
        if changed:
            log.info("default shell change recorded; log out + back in to activate.")

    return 0 if not report.failed else 1


if __name__ == "__main__":
    sys.exit(main())
