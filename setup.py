#!/usr/bin/env python3
"""Dotfiles Setup TUI — manage dotfiles deployment and KDE keybinds.

Uses Textual for a terminal UI with selectable tasks.

Usage:
  ./setup.py

Tasks:
  - Install/update dotfiles via GNU Stow
  - Restore the KDE Plasma 6 keybinds: Polonium tiling plus personal chords
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import var
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Header,
    Label,
    ListItem,
    ListView,
    RichLog,
    Static,
)


DOTFILES_DIR = os.path.dirname(os.path.abspath(__file__))
STOW_PACKAGES = sorted(
    d
    for d in os.listdir(DOTFILES_DIR)
    if os.path.isdir(os.path.join(DOTFILES_DIR, d))
    and not d.startswith(".")
    and d
    not in (
        "docs",
        "graphify-out",
        "scripts",
        "tests",
    )
)

# Order matters: install the tiler and its settings, restore its shortcuts,
# then layer the personal chords on top.
KEYBIND_SCRIPTS = [
    os.path.expanduser(f"~/.config/sway/scripts/{name}")
    for name in (
        "apply-polonium-settings.py",
        "merge-polonium-shortcuts.py",
        "merge-kde-personal-shortcuts.py",
    )
]

TASKS = {
    "stow": {
        "label": "Install/Update dotfiles (stow)",
        "detail": f"GNU Stow — {len(STOW_PACKAGES)} packages",
        "default": True,
    },
    "keybinds": {
        "label": "Restore KDE keybinds (Polonium + personal)",
        "detail": f"{len(KEYBIND_SCRIPTS)} scripts — tiling settings, tiling"
        " shortcuts, personal chords",
        "default": False,
    },
}


class StowPackageList(ListView):
    """Collapsible list of stow packages."""

    BINDINGS = []

    def __init__(self) -> None:
        super().__init__(*[ListItem(Label(p)) for p in STOW_PACKAGES])
        self.can_focus = False

    def compose(self) -> ComposeResult:
        yield Static(f"Stow packages ({len(STOW_PACKAGES)}):", classes="section-label")
        for pkg in STOW_PACKAGES:
            yield ListItem(Label(pkg))


class SetupApp(App):
    """Dotfiles setup TUI."""

    TITLE = "Dotfiles Setup"

    CSS = """
    Screen {
        layout: vertical;
    }

    #task-list {
        margin: 1 1;
        padding: 0 1;
    }

    .task-row {
        height: 5;
        margin-bottom: 1;
    }

    Checkbox {
        padding: 0;
        min-height: 1;
    }

    .task-detail {
        color: $text-disabled;
        margin-left: 3;
    }

    #divider {
        height: 1;
        background: $foreground 10%;
        margin: 0 1;
    }

    #action-bar {
        height: 3;
        margin: 0 1;
        align: center middle;
    }

    #run-btn {
        width: 30;
    }

    #log-box {
        margin: 1 1;
        border: solid $border;
        height: 1fr;
    }

    #log {
        height: 100%;
    }

    .section-label {
        text-style: bold;
        color: $text;
        margin-bottom: 1;
    }
    """

    RUNNING = var(False)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Vertical(
            Static("Select tasks to run:", classes="section-label"),
            Vertical(
                Checkbox(
                    TASKS["stow"]["label"],
                    id="task-stow",
                    value=TASKS["stow"]["default"],
                ),
                Static(TASKS["stow"]["detail"], classes="task-detail"),
                Checkbox(
                    TASKS["keybinds"]["label"],
                    id="task-keybinds",
                    value=TASKS["keybinds"]["default"],
                ),
                Static(TASKS["keybinds"]["detail"], classes="task-detail"),
                id="task-list",
            ),
            Static(id="divider"),
            Horizontal(
                Button("  Run Selected  ", id="run", variant="primary"),
                Button("  Quit  ", id="quit", variant="default"),
                id="action-bar",
            ),
            Vertical(
                RichLog(id="log", highlight=True, markup=True, wrap=True),
                id="log-box",
            ),
        )
        yield Footer()

    def watch_RUNNING(self, running: bool) -> None:
        btn = self.query_one("#run", Button)
        btn.disabled = running
        btn.label = "Running..." if running else "  Run Selected  "

    @on(Button.Pressed, "#quit")
    def quit(self) -> None:
        self.exit()

    @on(Button.Pressed, "#run")
    def run_tasks(self) -> None:
        if self.RUNNING:
            return
        self.RUNNING = True
        self.run_async()

    @work(thread=True)
    def run_async(self) -> None:
        """Run selected tasks in a worker thread."""

        def log(msg: str) -> None:
            self.call_from_thread(self._log, msg)

        def run_stow() -> int:
            log("[yellow]→ Stowing dotfiles packages...[/]")

            # Match setup.sh: the repo root only. .stowrc sets --target=~/.config.
            cmds = [
                ["stow", "-d", DOTFILES_DIR, "."],
            ]

            errors = 0
            for cmd in cmds:
                pkg = cmd[-1]
                log(f"  stow {pkg}...")
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if proc.stdout:
                    for line in proc.stdout.strip().split("\n"):
                        if line and "WARNING: in simulation mode" not in line:
                            log(f"  {line}")
                if proc.stderr and "WARNING:" not in proc.stderr:
                    log(f"[red]  {proc.stderr.strip()}[/]")
                if proc.returncode != 0:
                    log(f"[red]  stow {pkg} failed (exit {proc.returncode})[/]")
                    errors += 1

            if errors == 0:
                log(f"[green]✓ Stow complete — {len(STOW_PACKAGES)} packages[/]")
            else:
                log(f"[red]✗ Stow had {errors} error(s)[/]")
            return errors

        def run_keybind_script(script: str) -> int:
            """Run one keybind script and log its output. 0 means clean."""
            name = os.path.basename(script)
            if not os.path.isfile(script):
                log(f"[red]✗ Script not found: {script}[/]")
                log("[dim]  Install dotfiles first or check the path.[/]")
                return 1
            log(f"  {name}...")
            proc = subprocess.run(
                [script],
                capture_output=True,
                text=True,
                timeout=30,
            )
            for stream in (proc.stdout, proc.stderr):
                for line in (stream or "").strip().split("\n"):
                    if line:
                        log(f"  {line}")
            if proc.returncode != 0:
                log(f"[red]  {name} exited {proc.returncode}[/]")
            return proc.returncode

        def run_keybinds() -> int:
            log("[yellow]→ Restoring KDE keybinds...[/]")
            errors = 0
            for script in KEYBIND_SCRIPTS:
                if run_keybind_script(script) != 0:
                    errors += 1
            if errors == 0:
                log("[green]✓ KDE keybinds restored[/]")
            else:
                log(f"[red]✗ {errors} keybind script(s) failed[/]")
            return errors

        errors = 0

        if self.query_one("#task-stow", Checkbox).value:
            errors += run_stow()

        if self.query_one("#task-keybinds", Checkbox).value:
            errors += run_keybinds()

        self.call_from_thread(self._finish, errors)

    def _log(self, msg: str) -> None:
        log = self.query_one("#log", RichLog)
        log.write(msg)
        log.scroll_end()

    def _finish(self, errors: int) -> None:
        log = self.query_one("#log", RichLog)
        if errors == 0:
            log.write("[bold green]── All tasks complete ──[/]")
        else:
            log.write(f"[bold red]── {errors} task(s) had errors ──[/]")
        self.RUNNING = False


def main() -> int:
    app = SetupApp()
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
