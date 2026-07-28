#!/usr/bin/env python3
"""Pre-commit content linter for a PUBLIC dotfiles repo.

Purpose: no machine- or user-identifying expanded values, and no secrets,
ever land in a commit.

Scope: scans the STAGED content of each staged file (the git index blob),
i.e. exactly what would be committed. Never touches unstaged/untracked
files.

Replacement standard per file context (see README.md for the evidence
behind each choice):
    *.sh / files with a shebang -> $HOME   (expands correctly in shell use)
    *.md                        -> ~       (repo already standardized on ~
                                             with an explicit expansion note)
    *.json / everything else    -> $HOME   (safe default; a real env var,
                                             not shell-dependent ~ expansion)

Bare usernames are only rewritten in path-like contexts
(bounded by / or @), never in prose, never inside an email domain.

Values with no portable replacement (email, tailnet id, hostname) are
BLOCKED, not rewritten: rewriting them would break the thing that uses
them (e.g. a tailnet permission rule stops matching). Move those to the
untracked scripts/commit-linter/identity.local instead.

Secret-shaped strings are always a hard block, never auto-fixed.

Usage:
    scripts/commit-linter/lint_staged.py     # run from the repo root
"""
from __future__ import annotations

import difflib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

__all__ = ["main"]

USER_FORM = "$USER"
USER_NAME = Path.home().name
HOME_FORMS = tuple(
    dict.fromkeys(
        (
            str(Path.home()),
            str(Path.home()).replace("/var/home/", "/home/", 1),
        )
    )
)
IDENTITY_LOCAL = Path(__file__).resolve().parent / "identity.local"
DMG_SCAN = Path.home() / ".local/share/stepsecurity-dmg/dmg-scan.sh"
TRUFFLEHOG_HINT = "install: see scripts/commit-linter/README.md"

# The linter's own script contains the secret prefixes and _KEY/_TOKEN/_SECRET
# pattern literals, so it legitimately contains the regex's trigger text
# without containing a real secret. Exempt it from the regex pass (2) and the
# auto-fix pass (4) only; TruffleHog (pass 5) still scans it.
SELF_FILES = {
    "scripts/commit-linter/lint_staged.py",
}

SECRET_RE = re.compile(
    r"sk-ant-|sk-proj-|ghp_|github_pat_|gho_|xoxb-|xoxp-|"
    r"AKIA[0-9A-Z]{16}|"
    r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"
)
SECRETVAR_RE = re.compile(
    r"[A-Za-z_]*(_KEY|_TOKEN|_SECRET)[ \t]*[:=]"
    r"[ \t]*[\"']?[A-Za-z0-9+/_=-]{20,}"
)
# Storage/cache/cookie key NAME constants (e.g. `_THEME_STORAGE_KEY =
# "artifact-serve-theme"`) aren't secrets, but a 20+ char kebab/snake
# name trips SECRETVAR_RE's length check. Post-filter those specific
# suffixes out, but only when the assigned value itself has no entropy
# (plain lowercase, no uppercase/+//=): a real secret assigned to an
# oddly-named *_STORAGE_KEY var still fails this filter and stays
# blocked. A post-filter on the matched lines is simpler than one regex
# doing both jobs. Pass 5 (trufflehog) is the entropy-based backstop for
# anything this prefilter now lets through. A trailing `;` (JS/TS) is
# tolerated after the value; the entropy constraint on the value itself
# is unchanged.
KEYNAME_EXEMPT_RE = re.compile(
    r"(_STORAGE_KEY|_CACHE_KEY|_COOKIE_NAME|_PREFS_KEY)[ \t]*[:=]"
    r"[ \t]*[\"']?[a-z0-9_-]{20,}[\"']?[ \t]*;?[ \t]*$"
)


def git(args: list[str]) -> bytes:
    """Run git with args and return stdout; raise on a non-zero exit."""
    return subprocess.run(
        ["git", *args], check=True, stdout=subprocess.PIPE
    ).stdout


def nul_paths(out: bytes) -> list[str]:
    """Decode git's NUL-delimited path output into a path list."""
    return [p.decode() for p in out.rstrip(b"\0").split(b"\0") if p]


def staged_files() -> list[str]:
    """Return staged paths, excluding deletions."""
    return nul_paths(
        git(["diff", "--cached", "-z", "--name-only", "--diff-filter=ACMR"])
    )


def unstaged_files() -> set[str]:
    """Return paths whose worktree copy differs from the index."""
    return set(nul_paths(git(["diff", "-z", "--name-only"])))


def is_binary(path: str) -> bool:
    """Return whether git numstat reports a binary staged diff ("-")."""
    fields = git(["diff", "--cached", "--numstat", "--", path]).split()
    return bool(fields) and fields[0] == b"-"


def staged_text(path: str) -> str:
    """Return the staged blob as text, trailing newlines stripped."""
    return git(["show", f":{path}"]).decode(errors="replace").rstrip("\n")


def numbered_hits(content: str, pattern: re.Pattern[str] | str) -> list[str]:
    """Return grep -n style "<lineno>:<line>" hits for a regex or substring."""
    hits: list[str] = []
    for number, line in enumerate(content.splitlines(), start=1):
        found = pattern in line if isinstance(pattern, str) else pattern.search(line)
        if found:
            hits.append(f"{number}:{line}")
    return hits


def report(path: str, header: str, hits: list[str]) -> None:
    """Print a BLOCKED header plus its file-prefixed hit lines to stderr."""
    print(header, file=sys.stderr)
    for hit in hits:
        print(f"  {path}:{hit}", file=sys.stderr)


def fail_partial(files: list[str]) -> bool:
    """Pass 1: block a staged file that is also dirty in the worktree."""
    failed = False
    unstaged = unstaged_files()
    for path in files:
        if path not in unstaged:
            continue
        print(
            f"BLOCKED: {path} is partially staged (working tree differs from "
            "the index). Stage the whole file or none of it, then retry.",
            file=sys.stderr,
        )
        failed = True
    return failed


def secret_hits(content: str) -> list[str]:
    """Return secret-shaped hits, minus the key-name-constant exemptions."""
    hits = numbered_hits(content, SECRET_RE)
    hits += [
        hit
        for hit in numbered_hits(content, SECRETVAR_RE)
        if not KEYNAME_EXEMPT_RE.search(hit.split(":", 1)[1])
    ]
    deduped = list(dict.fromkeys(hits))
    return sorted(deduped, key=lambda hit: int(hit.split(":", 1)[0]))


def fail_secrets(files: list[str]) -> bool:
    """Pass 2: block secret-shaped staged content (never auto-fixed)."""
    failed = False
    for path in files:
        if is_binary(path) or path in SELF_FILES:
            continue
        hits = secret_hits(staged_text(path))
        if not hits:
            continue
        report(path, f"BLOCKED: secret-shaped content in {path}:", hits)
        failed = True
    return failed


def identity_needles() -> list[str]:
    """Return the email, tailnet, and live hostname needles for pass 3."""
    values = {"EMAIL": "", "TAILNET": ""}
    if IDENTITY_LOCAL.exists():
        for number, raw in enumerate(IDENTITY_LOCAL.read_text().splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].strip()
            if "=" not in line or "$" in line:
                print(
                    f"BLOCKED: unparseable {IDENTITY_LOCAL} line {number}.",
                    file=sys.stderr,
                )
                raise ValueError
            key, value = line.split("=", 1)
            if key.strip() in values:
                values[key.strip()] = value.strip().strip("\"'")
    else:
        print(
            f"NOTE: no {IDENTITY_LOCAL}; skipping email/tailnet checks "
            "(hostname check still runs).",
            file=sys.stderr,
        )
    return [v for v in (values["EMAIL"], values["TAILNET"], socket.gethostname()) if v]


def fail_identity(files: list[str]) -> bool:
    """Pass 3: block identity values that have no portable replacement."""
    failed = False
    needles = identity_needles()
    for path in files:
        if is_binary(path):
            continue
        content = staged_text(path)
        for needle in needles:
            hits = numbered_hits(content, needle)
            if not hits:
                continue
            report(
                path,
                f'BLOCKED: identifying value "{needle}" in {path} (no portable '
                "replacement exists). Move this to "
                "scripts/commit-linter/identity.local instead:",
                hits,
            )
            failed = True
    return failed


def fixed_text(path: str, content: str) -> str:
    """Return content with expanded home paths and bare username made portable."""
    home_form = "~" if path.endswith(".md") else "$HOME"
    fixed = content
    for expanded_home in HOME_FORMS:
        fixed = fixed.replace(expanded_home, home_form)
    # Line-anchored (MULTILINE) to match sed's per-line ^ and $.
    fixed = re.sub(
        rf"(^|/){re.escape(USER_NAME)}(/|$)",
        rf"\1{USER_FORM}\2",
        fixed,
        flags=re.MULTILINE,
    )
    return fixed.replace(f"{USER_NAME}@", f"{USER_FORM}@")


def autofix(files: list[str]) -> None:
    """Pass 4: rewrite expanded $HOME / bare username on disk, then re-stage."""
    for path in files:
        if is_binary(path) or path in SELF_FILES:
            continue
        original = staged_text(path)
        fixed = fixed_text(path, original)
        if fixed == original:
            continue
        print(f"FIXED: {path}")
        print(
            "".join(
                difflib.unified_diff(
                    original.splitlines(keepends=True),
                    fixed.splitlines(keepends=True),
                    fromfile=f"a/{path}",
                    tofile=f"b/{path}",
                    lineterm="\n",
                )
            ),
            end="",
        )
        Path(path).write_text(fixed + "\n")
        git(["add", "--", path])


def copy_staged_blobs(files: list[str], scratch: Path) -> None:
    """Materialize each staged text blob under scratch, preserving its path."""
    for path in files:
        if is_binary(path):
            continue
        target = scratch / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(git(["show", f":{path}"]))


def trufflehog_findings(scratch: Path) -> list[dict[str, object]] | None:
    """Run TruffleHog over scratch and return one dict per JSON finding.

    --results includes `unverified` on purpose: most fake-but-real-shaped
    test secrets come back Verified: false, and the docs' typical
    `--results=verified,unknown` would silently let those through.
    """
    result = subprocess.run(
        [
            "trufflehog",
            "filesystem",
            str(scratch),
            "--no-update",
            "--results=verified,unverified,unknown",
            "--json",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    findings: list[dict[str, object]] = []
    for line in result.stdout.splitlines():
        if b'"SourceMetadata"' not in line:
            continue
        try:
            findings.append(json.loads(line))
        except json.JSONDecodeError:
            findings.append({})
    if result.returncode:
        print("BLOCKED: trufflehog scanner failed.", file=sys.stderr)
        return None
    return findings


def finding_location(finding: dict[str, object], scratch: Path) -> str:
    """Return a "detector=.. file=.. line=.." summary of one finding."""
    source = finding.get("SourceMetadata")
    data = source.get("Data", {}) if isinstance(source, dict) else {}
    fs = data.get("Filesystem", {}) if isinstance(data, dict) else {}
    path = str(fs.get("file", "")) if isinstance(fs, dict) else ""
    line = str(fs.get("line", "")) if isinstance(fs, dict) else ""
    try:
        path = str(Path(path).relative_to(scratch))
    except ValueError:
        pass
    detector = str(finding.get("DetectorName", ""))
    return f"  detector={detector} file={path} line={line}"


def fail_trufflehog(files: list[str]) -> bool:
    """Pass 5: TruffleHog scan of staged content, fail-closed.

    A missing trufflehog binary blocks the commit; it never silently
    skips the scan. A missing scanner must not look like a clean scan.
    """
    if shutil.which("trufflehog") is None:
        print(
            f"BLOCKED: trufflehog not found on PATH ({TRUFFLEHOG_HINT}).",
            file=sys.stderr,
        )
        return True
    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp)
        copy_staged_blobs(files, scratch)
        findings = trufflehog_findings(scratch)
        if findings is None:
            return True
        if not findings:
            return False
        print(
            "BLOCKED: trufflehog found secret(s) in staged content:",
            file=sys.stderr,
        )
        for finding in findings:
            print(finding_location(finding, scratch), file=sys.stderr)
        return True


def run_dmg_scan() -> int:
    """Pass 6: StepSecurity Dev Machine Guard supply-chain scan.

    Optional: machines without DMG installed skip silently, never blocked.
    """
    if DMG_SCAN.exists() and os.access(DMG_SCAN, os.X_OK):
        result = subprocess.run([str(DMG_SCAN)], check=False)
        if result.returncode:
            print("BLOCKED: dev-machine-guard scan failed.", file=sys.stderr)
            return 1
    return 0


def main() -> int:
    """Run every staged-content lint pass; return the process exit code."""
    repo_root = git(["rev-parse", "--show-toplevel"]).decode().strip()
    os.chdir(repo_root)
    files = staged_files()
    if not files:
        return 0
    if fail_partial(files):
        return 1
    if fail_secrets(files):
        return 1
    try:
        identity_failed = fail_identity(files)
    except ValueError:
        identity_failed = True
    if identity_failed:
        return 1
    autofix(files)
    # Re-read the staged list: pass 4 may have re-staged fixed files, but
    # the set of files being committed is unchanged.
    if fail_trufflehog(staged_files()):
        return 1
    return run_dmg_scan()


if __name__ == "__main__":
    raise SystemExit(main())
