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
- `raxii-box-com.mitchellh.ghostty.desktop` carried the real Meta+Return
  chord on the old machine (a distrobox-exported Ghostty). Nicole's
  instruction on the new machine: bind that chord to whatever terminal she
  is actually using, not Ghostty specifically ("point at my current
  terminal, not just ghostty"). Her current terminal is Alacritty
  (confirmed from her live shell's process ancestry). The chord is written
  to `Alacritty.desktop` only if that `.desktop` file is actually present
  on this machine, never guessed.
- `wlr-which-key.desktop` is skipped outright; that tool was cut from the
  migration.

Writing the file is not enough on its own. The running desktop keeps its
own copy of every shortcut in memory and writes that copy back over the
file when Nicole logs out, so a file-only edit is wiped before it ever
takes effect (this is exactly why Meta+Q went on doing nothing after a
logout). So every chord is also pushed straight into the running shortcut
daemon over D-Bus with `setForeignShortcut`. That makes the chord live the
moment it is applied, and the daemon saves it to the file itself, so file
and memory agree and a logout has nothing left to clobber.

Idempotent: rerunning finds every key already at its target value, and the
running desktop already holding every chord, and does nothing.

    ./merge-kde-personal-shortcuts.py            # apply
    ./merge-kde-personal-shortcuts.py --check    # report only, change nothing
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

LIVE_FILE = "kglobalshortcutsrc"  # bare name: kwriteconfig6 resolves it under ~/.config
DEFAULT_SOURCE = Path(__file__).with_name("kde-personal-shortcuts-old-machine.ini")

SKIPPED_PREFIXES = ("Polonium", "Krohnkite")
# Not a shortcut at all: KDE's own label for the whole group ("KWin",
# "plasmashell", ...), not an "Active,Default,FriendlyName" triple.
GROUP_LABEL_KEY = "_k_friendly_name"

# [services][<desktop-id>] entries: which ones may ever be restored, and
# under what desktop-id. Anything not listed here is left alone.
TERMINAL_CHORD_SOURCE_ID = "raxii-box-com.mitchellh.ghostty.desktop"  # old machine: distrobox-exported Ghostty, holds the real Meta+Return chord
GHOSTTY_NATIVE_ID = "com.mitchellh.ghostty.desktop"  # not used for the write target; Nicole's terminal is Alacritty, not Ghostty
TERMINAL_ID = "Alacritty.desktop"  # her current terminal, confirmed 2026-09-10 from live shell process ancestry
KRUNNER_ID = "org.kde.krunner.desktop"
WHICH_KEY_ID = "wlr-which-key.desktop"

# The running shortcut daemon. A chord set here is live at once, and the
# daemon writes it to the file itself, which is the half a file edit misses.
KGLOBALACCEL_SERVICE = "org.kde.kglobalaccel"
KGLOBALACCEL_PATH = "/kglobalaccel"
KGLOBALACCEL_INTERFACE = "org.kde.KGlobalAccel"
COMPONENT_INTERFACE = "org.kde.kglobalaccel.Component"

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


@lru_cache(maxsize=None)
def read_source(source_path: str, groups: GroupPath, key: str) -> str:
    """One line of the old machine's snapshot, unescaped by kreadconfig6.
    Cached because both passes below ask for the same lines, and each ask
    costs a process."""
    return kreadconfig(source_path, groups, key)


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
        if (Path(d) / TERMINAL_ID).exists():
            allowed.add(TERMINAL_ID)
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


def restorable_actions(
    old_groups: dict[GroupPath, dict[str, str]],
    services_allowed: set[str],
):
    """Every row of the old machine's snapshot this run is allowed to touch,
    as (snapshot groups, groups to write, action, raw value, is_triple).
    The rows that are never touched - Polonium, Krohnkite, the group labels,
    and the launcher entries for tools that are not installed here - never
    come out of this."""
    for groups, actions in old_groups.items():
        is_services = groups[0] == "services"
        is_triple = not is_services
        for action, old_raw in actions.items():
            if action.startswith(SKIPPED_PREFIXES) or action == GROUP_LABEL_KEY:
                continue
            write_groups = groups
            if is_services:
                desktop_id = groups[1] if len(groups) > 1 else ""
                if desktop_id in (WHICH_KEY_ID, GHOSTTY_NATIVE_ID):
                    continue  # no real chord in this row on the old machine either way
                if desktop_id == TERMINAL_CHORD_SOURCE_ID:
                    if TERMINAL_ID not in services_allowed:
                        continue  # the caller's notes block explains this one
                    write_groups = ("services", TERMINAL_ID)
                elif desktop_id not in services_allowed:
                    continue
            yield groups, write_groups, action, old_raw, is_triple


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

    for groups, write_groups, action, old_raw, is_triple in restorable_actions(
            old_groups, services_allowed):
        desired_tokens = active_tokens(old_raw, is_triple)
        if not desired_tokens:
            continue  # old machine had no real binding here

        old_value = read_source(str(source_path), groups, action)
        live_raw = live_groups.get(write_groups, {}).get(action, "")
        live_value = kreadconfig(LIVE_FILE, write_groups, action) if live_raw else ""

        if is_triple:
            old_active = old_value.split(",", 1)[0]
            write_value = build_triple_write(old_active, live_value, old_value)
        else:
            write_value = old_value

        if write_value == live_value:
            continue  # already correct

        candidates.append(Candidate(write_groups, action, is_triple,
                                     desired_tokens, write_value))

    if TERMINAL_ID not in services_allowed:
        notes.append(
            f"{TERMINAL_ID} not found on this machine yet - Meta+Return "
            "was not bound. Install Alacritty, then rerun this script."
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


def qt_key_sequence_class():
    """Qt's own reader of chord strings, from whichever Python Qt binding is
    installed here. None when there is none, which switches the live push off
    and leaves the file-only behaviour untouched."""
    for module_name in ("PyQt6.QtGui", "PySide6.QtGui", "PyQt5.QtGui"):
        try:
            return __import__(module_name, fromlist=["QKeySequence"]).QKeySequence
        except ImportError:
            continue
    return None


def qt_keycodes(chord: str, key_sequence_class) -> list[int]:
    """The numbers the desktop speaks for one chord such as "Meta+Q". Qt does
    the reading, so there is no list of key names in this file to fall out of
    step with the one the desktop itself uses."""
    sequence = key_sequence_class(chord)
    codes = []
    for index in range(sequence.count()):
        combination = sequence[index]
        codes.append(int(combination.toCombined()
                         if hasattr(combination, "toCombined") else combination))
    return codes


def wanted_keycodes(value: str, is_triple: bool, key_sequence_class) -> list[int]:
    """Every chord one snapshot line asks for, as numbers. "none" asks for
    nothing, which is how the snapshot says "this key should do nothing"."""
    active = value.split(",", 1)[0] if is_triple else value
    codes: list[int] = []
    for chord in active.split("\t"):
        if chord and chord.lower() != "none":
            codes += qt_keycodes(chord, key_sequence_class)
    return sorted(codes)


def component_path(unique_name: str) -> str:
    """Where the daemon keeps one app's shortcuts. Anything that is not a
    letter or digit becomes an underscore, so "Alacritty.desktop" lives at
    "/component/Alacritty_desktop"."""
    return "/component/" + "".join(c if c.isalnum() else "_" for c in unique_name)


def live_shortcuts(bus, unique_name: str):
    """What the running desktop holds right now for one app:
    {action: (action label, app name, app label, key numbers)}. None when the
    desktop has never heard of that app."""
    import dbus
    try:
        obj = bus.get_object(KGLOBALACCEL_SERVICE, component_path(unique_name))
        infos = dbus.Interface(obj, COMPONENT_INTERFACE).allShortcutInfos()
    except dbus.DBusException:
        return None
    return {str(info[0]): (str(info[1]), str(info[2]), str(info[3]),
                           sorted(int(key) for key in info[6]))
            for info in infos}


class LivePush:
    """One action's chords on their way into the running desktop."""

    def __init__(self, action_id: list[str], wanted: list[int], live: list[int]):
        # [app name, action name, app label, action label] - the daemon wants
        # all four, and all four are read back off the daemon, never guessed.
        self.action_id = action_id
        self.wanted = wanted
        self.live = live

    @property
    def label(self) -> str:
        return f"[{self.action_id[0]}] {self.action_id[1]}"

    @property
    def claims(self) -> set[int]:
        """Chords this action is taking that it does not already hold."""
        return set(self.wanted) - set(self.live)

    @property
    def releases(self) -> set[int]:
        """Chords this action is giving up."""
        return set(self.live) - set(self.wanted)


def collect_live_pushes(bus, old_groups, services_allowed, source_path,
                        key_sequence_class):
    """Every action the running desktop holds differently from the snapshot,
    plain-English notes for the ones nothing can be done about, and the apps
    that were looked at, as (pushes, notes, {app: what it holds})."""
    pushes: list[LivePush] = []
    notes: list[str] = []
    components: dict[str, dict | None] = {}

    for groups, write_groups, action, _old_raw, is_triple in restorable_actions(
            old_groups, services_allowed):
        app = write_groups[1] if write_groups[0] == "services" else write_groups[0]
        if app not in components:
            components[app] = live_shortcuts(bus, app)
        registry = components[app]
        wanted = wanted_keycodes(read_source(str(source_path), groups, action),
                                 is_triple, key_sequence_class)
        if registry is None:
            if wanted:
                notes.append(f"live: [{app}] is not running, so {action!r} was "
                             "written to the file only.")
            continue
        entry = registry.get(action)
        if entry is None:
            if wanted:
                notes.append(f"live: the desktop does not know [{app}] {action!r}, "
                             "so it was written to the file only.")
            continue
        action_label, app_name, app_label, live = entry
        if wanted == live:
            continue
        pushes.append(LivePush([app_name, action, app_label, action_label],
                               wanted, live))
    return pushes, notes, components


def order_live_pushes(pushes: list[LivePush]) -> tuple[list[LivePush], list[str]]:
    """Give-ups before take-overs. An action losing a chord goes first, so the
    chord is free by the time the action that wants it asks for it."""
    remaining = list(pushes)
    ordered: list[LivePush] = []
    errors: list[str] = []
    while remaining:
        ready = [push for push in remaining
                 if not any(push.claims & other.releases
                            for other in remaining if other is not push)]
        if not ready:
            errors.append(
                "CYCLE: " + ", ".join(push.label for push in remaining)
                + " each want a chord another one still holds. Pushing them in "
                  "snapshot order and reporting whatever the desktop ends up with.")
            ordered += remaining
            break
        ordered += ready
        remaining = [push for push in remaining if push not in ready]
    return ordered, errors


def apply_live_pushes(bus, pushes: list[LivePush]) -> list[str]:
    """Set each action's chords in the running desktop, then ask the desktop
    what it ended up with. One line back per action that did not take."""
    import dbus
    accel = dbus.Interface(bus.get_object(KGLOBALACCEL_SERVICE, KGLOBALACCEL_PATH),
                           KGLOBALACCEL_INTERFACE)
    failures: list[str] = []
    for push in pushes:
        accel.setForeignShortcut(dbus.Array(push.action_id, signature="s"),
                                 dbus.Array(push.wanted, signature="i"))
        entry = (live_shortcuts(bus, push.action_id[0]) or {}).get(push.action_id[1])
        got = entry[3] if entry else None
        if got != push.wanted:
            failures.append(f"NOT LIVE: {push.label} was asked for "
                            f"{push.wanted or 'nothing'}, the desktop reports "
                            f"{got if got is not None else 'no such action'}")
    return failures


def live_duplicate_chords(bus, apps: list[str]) -> list[str]:
    """Chords the running desktop has handed to two actions at once, which is
    how a key ends up doing nothing, or the wrong thing. Polonium and
    Krohnkite actions are left out: a different script owns those."""
    holders: dict[int, list[str]] = {}
    for app in apps:
        for action, entry in (live_shortcuts(bus, app) or {}).items():
            if action.startswith(SKIPPED_PREFIXES):
                continue
            for key in entry[3]:
                holders.setdefault(key, []).append(f"[{app}] {action}")
    return [f"TWO ACTIONS SHARE ONE CHORD in the running desktop: key {key} "
            f"is held by {', '.join(names)}"
            for key, names in sorted(holders.items()) if len(names) > 1]


def sync_live_desktop(old_groups, services_allowed, source_path,
                      check_only: bool):
    """Make the running desktop agree with the snapshot. Returns how many
    chords still needed pushing and a line per one that would not take, or
    None when the running desktop could not be reached at all."""
    key_sequence_class = qt_key_sequence_class()
    if key_sequence_class is None:
        print("live: no Python Qt binding here (python-pyqt5, python-pyqt6 or "
              "pyside6), so chords went to the file only and will not survive a "
              "logout. Install one and rerun.")
        return None
    try:
        import dbus
    except ImportError:
        print("live: python-dbus is not installed, so chords went to the file "
              "only and will not survive a logout. Install it and rerun.")
        return None
    try:
        bus = dbus.SessionBus()
    except dbus.DBusException as error:
        print(f"live: no session to talk to ({error}); file written only.")
        return None

    pushes, notes, components = collect_live_pushes(
        bus, old_groups, services_allowed, source_path, key_sequence_class)
    ordered, errors = order_live_pushes(pushes)
    for line in notes:
        print(line)
    if ordered:
        print(f"live: {len(ordered)} shortcut(s) to push into the running "
              "desktop, in this order:")
        for push in ordered:
            print(f"  {push.label} -> {push.wanted or 'nothing'} "
                  f"(desktop had {push.live or 'nothing'})")
        if not check_only:
            errors += apply_live_pushes(bus, ordered)
    else:
        print("live: the running desktop already matches; nothing to push")
    if not check_only:
        errors += live_duplicate_chords(bus, list(components))
    return len(ordered), errors


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

    if ordered:
        print(f"file: {len(ordered)} key(s) to write, in this order:")
        for c in ordered:
            print(f"  [{'/'.join(c.groups)}] {c.action} = {c.write_value}")
    else:
        print("file: nothing to write; already merged")

    failures = list(order_errors)

    if not args.check:
        for c in ordered:
            kwriteconfig(c.groups, c.action, c.write_value)
        failed_readback = [c for c in ordered
                           if kreadconfig(LIVE_FILE, c.groups, c.action) != c.write_value]
        if failed_readback:
            failures.append(f"FAILED readback on: {[c.action for c in failed_readback]}")

    live_result = sync_live_desktop(old_groups, services_allowed, args.source,
                                    check_only=args.check)
    if live_result is None:
        # The running desktop was out of reach, so the file is all there is to
        # check - and it is the copy a logout overwrites.
        pending_live = 0
        if not args.check:
            failures += [f"DUPLICATE ACTIVE CHORD in the file: {d}"
                         for d in check_no_duplicate_active_chords(
                             live_path.read_text())]
    else:
        pending_live, live_failures = live_result
        failures += live_failures

    if args.check:
        print("--check given, nothing was changed")
        for line in failures:
            print(line)
        return 1 if (ordered or pending_live or failures) else 0

    if failures:
        for line in failures:
            print(line)
        return 1

    print("done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
