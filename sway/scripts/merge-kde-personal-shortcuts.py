#!/usr/bin/env python3
"""In plain words: restores the rest of Nicole's personal KDE shortcuts after
a fresh install, everything the Polonium-only restore did not cover: closing
a window with Meta+Q, switching desktops with Meta+1..0, the accessibility
and activity chords, and KRunner's launch keys.

Reads her old machine's `kglobalshortcutsrc` (the source of truth) and,
for every action that had a real chord bound there, writes that chord into
the live file with kwriteconfig6, keeping the live file's own
DefaultShortcut and FriendlyName. `Polonium*` and `Krohnkite*` keys are
never touched (Polonium was restored separately and verified; Krohnkite
is not installed on this machine).

Two chord collisions exist and are resolved automatically instead of
being written in a colliding order:

1. `activate task manager entry 1..9` (plasmashell) currently hold
   Meta+1..Meta+9, which her old machine gave to `Switch to Desktop 1..9`
   (kwin) instead. Both sides are restored; the task-manager entries move
   to their old Meta+Ctrl+N chords first, freeing Meta+N for the desktop
   switches.
2. `manage activities` (plasmashell) currently holds Meta+Q, which her old
   machine gave to `Window Close` (kwin) instead. Her old file shows
   `manage activities` explicitly unbound (active "none") on that
   machine, so restoring Window Close's Meta+Q here also clears
   `manage activities` back to unbound, matching what she actually ran.
   This one is not named anywhere in the restore list; it falls out of
   requiring "her old active chord wins" and "no duplicate active chord"
   to both hold at once.

The `[services]` entries reference `.desktop` files by name, which can
differ machine to machine:

- `org.kde.krunner.desktop` exists here and is restored.
- `raxii-box-com.mitchellh.ghostty.desktop` was a distrobox-exported name
  from the old machine and does not apply here.
- `com.mitchellh.ghostty.desktop`, the native package's likely name, is
  bound to Meta+Return only if that `.desktop` file is actually present
  on this machine. Ghostty was being installed in parallel; if it was not
  done yet when this ran, the binding is skipped and reported rather than
  guessed.
- `wlr-which-key.desktop` is skipped outright; that tool was cut from the
  migration.

Idempotent: rerunning finds every key already at its target value and
writes nothing.

    ./merge-kde-personal-shortcuts.py            # apply
    ./merge-kde-personal-shortcuts.py --check    # report only, change nothing
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

LIVE_FILE = "kglobalshortcutsrc"  # bare name: kwriteconfig6 resolves it under ~/.config
DEFAULT_SOURCE = Path(__file__).with_name("kde-personal-shortcuts-old-machine.ini")

SKIPPED_PREFIXES = ("Polonium", "Krohnkite")
# Not a shortcut at all: KDE's own label for the whole group ("KWin",
# "plasmashell", ...), not an "Active,Default,FriendlyName" triple.
GROUP_LABEL_KEY = "_k_friendly_name"

# [services][<desktop-id>] entries: which ones may ever be restored, and
# under what desktop-id. Anything not listed here is left alone.
GHOSTTY_OLD_ID = "raxii-box-com.mitchellh.ghostty.desktop"  # distrobox export, old machine only
GHOSTTY_NATIVE_ID = "com.mitchellh.ghostty.desktop"          # native package, this machine
KRUNNER_ID = "org.kde.krunner.desktop"
WHICH_KEY_ID = "wlr-which-key.desktop"

GroupPath = tuple[str, ...]


def parse_groups(text: str) -> dict[GroupPath, dict[str, str]]:
    """{group_path: {action: raw_value}} for every `[group]` or
    `[group][subgroup]` section in a kglobalshortcutsrc-style file."""
    groups: dict[GroupPath, dict[str, str]] = {}
    group: GroupPath | None = None
    for line in text.splitlines():
        if line.startswith("["):
            group = tuple(re.findall(r"\[([^\]]+)\]", line))
            groups.setdefault(group, {})
            continue
        if group is not None and "=" in line:
            key, _, value = line.partition("=")
            groups[group][key] = value
    return groups


def active_tokens(raw_value: str, has_triple_format: bool) -> set[str]:
    """The chord(s) an action is currently bound to."""
    active_field = raw_value.split(",", 1)[0] if has_triple_format else raw_value
    return {t for t in active_field.split("\\t") if t and t.lower() != "none"}


def kwriteconfig(groups: GroupPath, key: str, value: str) -> None:
    args = ["kwriteconfig6", "--file", LIVE_FILE]
    for g in groups:
        args += ["--group", g]
    args += ["--key", key, value]
    subprocess.run(args, check=True)


def kreadconfig(file: str, groups: GroupPath, key: str) -> str:
    # kreadconfig6 does the KConfig backslash-escaping/unescaping for us.
    # Feed kwriteconfig6 only values that came back through kreadconfig6,
    # never a raw file read, or the escaping compounds (a prior agent hit
    # exactly this bug on a Polonium chord).
    args = ["kreadconfig6", "--file", file]
    for g in groups:
        args += ["--group", g]
    args += ["--key", key]
    result = subprocess.run(args, capture_output=True, text=True, check=True)
    return result.stdout.rstrip("\n")


class Candidate:
    """One action queued for restore: its target chord(s) plus the write
    that gets it there."""

    def __init__(self, groups: GroupPath, action: str, is_triple: bool,
                 target_active_tokens: set[str], write_value: str):
        self.groups = groups
        self.action = action
        self.is_triple = is_triple
        self.target_active_tokens = target_active_tokens
        self.write_value = write_value

    @property
    def key(self) -> tuple[GroupPath, str]:
        return (self.groups, self.action)


def allowed_services() -> set[str]:
    """[services][<id>] entries this run may ever touch, resolved against
    what is actually installed on this machine."""
    allowed = {KRUNNER_ID}
    search_dirs = [
        "/usr/share/applications",
        str(Path.home() / ".local/share/applications"),
    ]
    for d in search_dirs:
        matches = list(Path(d).glob("*[Gg]hostty*.desktop")) if Path(d).is_dir() else []
        if matches:
            allowed.add(GHOSTTY_NATIVE_ID)
            break
    return allowed


def build_triple_write(old_active: str, live_raw: str, old_raw: str) -> str:
    """New `Active,Default,FriendlyName` value: old's active chord, live's
    (or if absent, old's) default and friendly name."""
    default_field, friendly_field = "", ""
    source = live_raw if live_raw else old_raw
    fields = source.split(",", 2)
    if len(fields) >= 2:
        default_field = fields[1]
    if len(fields) >= 3:
        friendly_field = fields[2]
    return f"{old_active},{default_field},{friendly_field}"


def collect_candidates(
    old_groups: dict[GroupPath, dict[str, str]],
    live_groups: dict[GroupPath, dict[str, str]],
    services_allowed: set[str],
    source_path: Path,
) -> tuple[list[Candidate], list[str]]:
    """Every action worth restoring, plus report lines for anything
    deliberately left out."""
    candidates: list[Candidate] = []
    notes: list[str] = []

    for groups, actions in old_groups.items():
        is_services = groups[0] == "services"
        is_triple = not is_services
        for action, old_raw in actions.items():
            if action.startswith(SKIPPED_PREFIXES) or action == GROUP_LABEL_KEY:
                continue
            if is_services:
                desktop_id = groups[1] if len(groups) > 1 else ""
                if desktop_id in (WHICH_KEY_ID, GHOSTTY_OLD_ID):
                    continue
                if desktop_id not in services_allowed:
                    continue
            desired_tokens = active_tokens(old_raw, is_triple)
            if not desired_tokens:
                continue  # old machine had no real binding here

            old_value = kreadconfig(str(source_path), groups, action)
            live_raw = live_groups.get(groups, {}).get(action, "")
            live_value = kreadconfig(LIVE_FILE, groups, action) if live_raw else ""

            if is_triple:
                old_active = old_value.split(",", 1)[0]
                write_value = build_triple_write(old_active, live_value, old_value)
            else:
                write_value = old_value

            if write_value == live_value:
                continue  # already correct

            candidates.append(Candidate(groups, action, is_triple,
                                         desired_tokens, write_value))

    ghostty_native_in_old = old_groups.get(("services", GHOSTTY_NATIVE_ID), {})
    ghostty_native_bound = active_tokens(
        ghostty_native_in_old.get("_launch", ""), False)
    if GHOSTTY_NATIVE_ID not in services_allowed:
        notes.append(
            f"Ghostty ({GHOSTTY_NATIVE_ID}) not found on this machine yet - "
            "Meta+Return was not bound. Install Ghostty, then rerun this "
            "script."
        )
    elif not ghostty_native_bound:
        notes.append(
            f"Ghostty is installed, but the old machine's {GHOSTTY_NATIVE_ID} "
            "entry was itself unbound (the Meta+Return chord lived under "
            f"the old distrobox name {GHOSTTY_OLD_ID} instead). Bind "
            "Meta+Return to Ghostty by hand if you want it back."
        )

    return candidates, notes


def find_live_holder(
    live_groups: dict[GroupPath, dict[str, str]],
    chord: str,
    skip: tuple[GroupPath, str],
) -> tuple[GroupPath, str] | None:
    for groups, actions in live_groups.items():
        is_triple = groups[0] != "services"
        for action, raw_value in actions.items():
            if (groups, action) == skip or action == GROUP_LABEL_KEY:
                continue
            if chord in active_tokens(raw_value, is_triple):
                return groups, action
    return None


def add_collision_clearing_candidates(
    candidates: list[Candidate],
    old_groups: dict[GroupPath, dict[str, str]],
    live_groups: dict[GroupPath, dict[str, str]],
    source_path: Path,
) -> list[str]:
    """An action outside the restore set may still be squatting on a
    chord a candidate needs. If the old machine's file shows that squatter
    with a different (or no) chord there, restore the squatter too, so the
    candidate's chord is actually free instead of merely reassigned."""
    reports: list[str] = []
    already_queued = {c.key for c in candidates}
    seen_squatters = set()

    for candidate in list(candidates):
        for chord in candidate.target_active_tokens:
            holder = find_live_holder(live_groups, chord, skip=candidate.key)
            if holder is None or holder in already_queued or holder in seen_squatters:
                continue
            holder_groups, holder_action = holder
            old_holder_raw = old_groups.get(holder_groups, {}).get(holder_action)
            if old_holder_raw is None:
                reports.append(
                    f"UNRESOLVED COLLISION: {candidate.action} wants {chord}, "
                    f"held live by [{'/'.join(holder_groups)}] {holder_action!r}, "
                    "which the old machine's file does not mention. Leaving "
                    f"{holder_action!r} untouched and skipping {chord} for "
                    f"{candidate.action}."
                )
                continue
            is_triple = holder_groups[0] != "services"
            holder_old_tokens = active_tokens(old_holder_raw, is_triple)
            if chord in holder_old_tokens:
                reports.append(
                    f"UNRESOLVED COLLISION: {candidate.action} and "
                    f"[{'/'.join(holder_groups)}] {holder_action!r} both "
                    f"want {chord} on the old machine too. Leaving "
                    f"{holder_action!r} untouched and skipping {chord} for "
                    f"{candidate.action}."
                )
                continue
            old_value = kreadconfig(str(source_path), holder_groups, holder_action)
            live_raw = live_groups.get(holder_groups, {}).get(holder_action, "")
            live_value = kreadconfig(LIVE_FILE, holder_groups, holder_action) if live_raw else ""
            old_active = old_value.split(",", 1)[0] if is_triple else old_value
            write_value = (build_triple_write(old_active, live_value, old_value)
                           if is_triple else old_value)
            if write_value == live_value:
                continue
            reports.append(
                f"chord theft resolved: {holder_action!r} moves off {chord} "
                f"(old machine value {old_active!r}) so {candidate.action} "
                f"can have it back."
            )
            candidates.append(Candidate(holder_groups, holder_action, is_triple,
                                         holder_old_tokens, write_value))
            already_queued.add((holder_groups, holder_action))
            seen_squatters.add(holder)

    return reports


def order_writes(
    candidates: list[Candidate],
    live_groups: dict[GroupPath, dict[str, str]],
) -> tuple[list[Candidate], list[str]]:
    """Writes in an order where no chord is ever claimed while another
    queued action still holds it live."""
    live_state: dict[tuple[GroupPath, str], set[str]] = {}
    for groups, actions in live_groups.items():
        is_triple = groups[0] != "services"
        for action, raw in actions.items():
            live_state[(groups, action)] = active_tokens(raw, is_triple)

    pending = list(candidates)
    ordered: list[Candidate] = []
    errors: list[str] = []

    while pending:
        progressed = False
        still_pending = []
        pending_keys = {c.key for c in pending}
        for candidate in pending:
            blocked_by = None
            for chord in candidate.target_active_tokens:
                for other_key, other_tokens in live_state.items():
                    if other_key == candidate.key:
                        continue
                    if other_key in pending_keys and chord in other_tokens:
                        blocked_by = other_key
                        break
                if blocked_by:
                    break
            if blocked_by:
                still_pending.append(candidate)
                continue
            live_state[candidate.key] = candidate.target_active_tokens
            ordered.append(candidate)
            progressed = True
        if not progressed:
            for candidate in still_pending:
                errors.append(
                    f"CYCLE: could not find a safe write order for "
                    f"{candidate.action} without a mid-run duplicate chord. "
                    "Skipping it."
                )
            break
        pending = still_pending

    return ordered, errors


def check_no_duplicate_active_chords(text: str) -> list[str]:
    """Every active chord bound to exactly one action. Returns violations."""
    groups = parse_groups(text)
    holders: dict[str, list[str]] = {}
    for group_path, actions in groups.items():
        is_triple = group_path[0] != "services"
        for action, raw_value in actions.items():
            if action.startswith(SKIPPED_PREFIXES) or action == GROUP_LABEL_KEY:
                continue
            label = f"[{'/'.join(group_path)}] {action}"
            for chord in active_tokens(raw_value, is_triple):
                holders.setdefault(chord, []).append(label)
    return [f"{chord}: {', '.join(labels)}"
            for chord, labels in sorted(holders.items()) if len(labels) > 1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE,
                        help=f"old machine's snapshot (default: {DEFAULT_SOURCE})")
    parser.add_argument("--check", action="store_true",
                        help="report what would change; write nothing")
    args = parser.parse_args()

    live_path = Path.home() / ".config" / LIVE_FILE
    if not live_path.exists():
        print(f"FAILED: live file not found at {live_path}")
        return 1
    if not args.source.exists():
        print(f"FAILED: source snapshot not found at {args.source}")
        return 1

    old_groups = parse_groups(args.source.read_text())
    live_groups = parse_groups(live_path.read_text())

    services_allowed = allowed_services()
    candidates, notes = collect_candidates(old_groups, live_groups,
                                            services_allowed, args.source)
    collision_reports = add_collision_clearing_candidates(
        candidates, old_groups, live_groups, args.source)
    ordered, order_errors = order_writes(candidates, live_groups)

    for line in notes + collision_reports + order_errors:
        print(line)

    if not ordered:
        print("nothing to write; already merged")
        return 1 if order_errors else 0

    print(f"{len(ordered)} key(s) to write, in this order:")
    for c in ordered:
        print(f"  [{'/'.join(c.groups)}] {c.action} = {c.write_value}")

    if args.check:
        print("--check given, no changes written")
        return 1

    for c in ordered:
        kwriteconfig(c.groups, c.action, c.write_value)

    failed_readback = [c for c in ordered
                        if kreadconfig(LIVE_FILE, c.groups, c.action) != c.write_value]
    if failed_readback:
        print(f"FAILED readback on: {[c.action for c in failed_readback]}")
        return 1

    dupes = check_no_duplicate_active_chords(live_path.read_text())
    if dupes:
        print("DUPLICATE ACTIVE CHORDS after write:")
        for d in dupes:
            print(f"  {d}")
        return 1

    print("done.")
    return 1 if order_errors else 0


if __name__ == "__main__":
    sys.exit(main())
