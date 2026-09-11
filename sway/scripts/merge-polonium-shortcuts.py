#!/usr/bin/env python3
"""In plain words: restores Nicole's Polonium tiling-manager keyboard
shortcuts after a fresh KDE install, without touching anything else already
in her shortcut file.

Reads the 21 `Polonium*` chords from `polonium-shortcuts.ini`, a snapshot
taken from her old machine's live `kglobalshortcutsrc` (component `kwin`),
and writes each one into the live file with `kwriteconfig6`, one key at a
time. Everything else already in that file (Plasma and CachyOS defaults,
every non-Polonium action) is left exactly as it was.

One collision is known and pre-approved: `Lock Session` (component
`ksmserver`) defaults to Meta+L, and Polonium's `ActivateRight` wants the
same chord. Nicole decided on 2026-09-10 that Polonium keeps Meta+L, so her
hjkl focus row stays whole, and Lock Session should move to Meta+Ctrl+L
*if that chord is actually free once Polonium's own bindings are in place*.
Any OTHER collision, expected or not, is reported and that one key is left
untouched rather than silently overwritten.

Idempotent: rerunning finds every key already at its target value and
writes nothing.

    ./merge-polonium-shortcuts.py            # apply
    ./merge-polonium-shortcuts.py --check     # report only, change nothing
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

LIVE_FILE = "kglobalshortcutsrc"  # bare name: kwriteconfig6 resolves it under ~/.config
SOURCE_INI = Path(__file__).with_name("polonium-shortcuts.ini")

LOCK_ACTION = "Lock Session"
LOCK_GROUP = "ksmserver"
LOCK_CHORD = "Meta+L"
LOCK_RELOCATE_TO = "Meta+Ctrl+L"


def parse_groups(text: str) -> dict[str, dict[str, str]]:
    """{group_name: {action_id: raw_value}} for every `[group]` section."""
    groups: dict[str, dict[str, str]] = {}
    group = None
    for line in text.splitlines():
        if line.startswith("[") and line.endswith("]"):
            group = line[1:-1]
            groups.setdefault(group, {})
            continue
        if group is not None and "=" in line:
            key, _, value = line.partition("=")
            groups[group][key] = value
    return groups


def active_tokens(raw_value: str) -> set[str]:
    """The chord(s) an action is currently bound to (first CSV field)."""
    active_field = raw_value.split(",", 1)[0]
    return {t for t in active_field.split("\\t") if t and t.lower() != "none"}


def find_holder(groups: dict[str, dict[str, str]], chord: str,
                 skip: tuple[str, str] | None = None) -> tuple[str, str] | None:
    """First (group, action) other than `skip` whose active field holds `chord`."""
    for group, actions in groups.items():
        for action, raw_value in actions.items():
            if skip == (group, action):
                continue
            if chord in active_tokens(raw_value):
                return group, action
    return None


def kwriteconfig(group: str, key: str, value: str) -> None:
    subprocess.run(
        ["kwriteconfig6", "--file", LIVE_FILE, "--group", group, "--key", key, value],
        check=True,
    )


def kreadconfig(file: str, group: str, key: str) -> str:
    # kreadconfig6 does the KConfig backslash-escaping/unescaping for us. Two
    # values compared through it are the same logical shortcut even when their
    # raw on-disk byte forms differ (Polonium's "Meta+\" chord is stored with
    # doubled backslashes, and kwriteconfig6 doubles again on write - so the
    # value fed to kwriteconfig6 must always come from kreadconfig6, never
    # copied from a raw file read, or the escaping compounds).
    result = subprocess.run(
        ["kreadconfig6", "--file", file, "--group", group, "--key", key],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.rstrip("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, default=SOURCE_INI,
                        help=f"snapshot to read Polonium keys from (default: {SOURCE_INI})")
    parser.add_argument("--check", action="store_true",
                        help="report what would change; write nothing")
    args = parser.parse_args()

    source_groups = parse_groups(args.source.read_text())
    polonium = {k: v for k, v in source_groups.get("kwin", {}).items()
                if k.startswith("Polonium")}
    if len(polonium) != 21:
        print(f"FAILED: expected 21 Polonium* keys in {args.source}, found {len(polonium)}")
        return 1

    live_path = Path.home() / ".config" / LIVE_FILE
    if not live_path.exists():
        print(f"FAILED: live file not found at {live_path}")
        return 1
    live_groups = parse_groups(live_path.read_text())

    had_error = False
    to_write: list[tuple[str, str, str]] = []  # (group, key, value)

    for action, raw_value in sorted(polonium.items()):
        collided = False
        for chord in active_tokens(raw_value):
            holder = find_holder(live_groups, chord, skip=("kwin", action))
            if holder is None:
                continue
            holder_group, holder_action = holder
            if (holder_group, holder_action) == (LOCK_GROUP, LOCK_ACTION) and chord == LOCK_CHORD:
                continue  # the one pre-approved collision, handled below
            print(f"UNEXPECTED COLLISION: {action} wants {chord}, "
                  f"already held by [{holder_group}] {holder_action!r}. Skipping {action}.")
            had_error = True
            collided = True
            break
        if collided:
            continue
        desired = kreadconfig(str(args.source), "kwin", action)
        current = kreadconfig(LIVE_FILE, "kwin", action) if action in live_groups.get("kwin", {}) else None
        if current == desired:
            continue  # already correct, nothing to do
        to_write.append(("kwin", action, desired))

    # Lock Session relocation: only if the known collision is actually present.
    lock_raw = live_groups.get(LOCK_GROUP, {}).get(LOCK_ACTION, "")
    if LOCK_CHORD in active_tokens(lock_raw):
        # Free means free against the CURRENT live file *and* the 21 keys about
        # to be merged in - Polonium's own ResizeRight also wants Meta+Ctrl+L.
        merged_groups = {g: dict(a) for g, a in live_groups.items()}
        merged_groups.setdefault("kwin", {}).update(polonium)
        holder = find_holder(merged_groups, LOCK_RELOCATE_TO, skip=(LOCK_GROUP, LOCK_ACTION))
        if holder is not None:
            print(f"Lock Session NOT relocated: {LOCK_RELOCATE_TO} is claimed by "
                  f"[{holder[0]}] {holder[1]!r} (Polonium's own resize chord). "
                  f"Lock Session stays on {LOCK_CHORD}, alongside PoloniumActivateRight, "
                  "as Nicole's 2026-09-10 decision already accepts. Pick a different "
                  "chord for Lock Session if that ambiguity is unwanted.")
            had_error = True
        else:
            fields = lock_raw.split(",", 2)
            fields[0] = fields[0].replace(LOCK_CHORD, LOCK_RELOCATE_TO)
            new_value = ",".join(fields)
            to_write.append((LOCK_GROUP, LOCK_ACTION, new_value))

    if not to_write:
        print("nothing to write; already merged")
        return 1 if had_error else 0

    print(f"{len(to_write)} key(s) to write:")
    for group, key, value in to_write:
        print(f"  [{group}] {key} = {value}")

    if args.check:
        print("--check given, no changes written")
        return 1

    for group, key, value in to_write:
        kwriteconfig(group, key, value)

    failed_readback = [(g, k, v) for g, k, v in to_write if kreadconfig(LIVE_FILE, g, k) != v]
    if failed_readback:
        print(f"FAILED readback on: {failed_readback}")
        return 1

    print("done.")
    return 1 if had_error else 0


if __name__ == "__main__":
    sys.exit(main())
