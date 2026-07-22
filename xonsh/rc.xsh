# Xonsh config

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

$CHROME_EXECUTABLE = 'google-chrome-stable'

# zoxide doctor noise off; matches .zshrc.
$_ZO_DOCTOR = '0'

# PATH prepends — order matters (first wins). Mirror of .zshrc layout.
#   linuxbrew bin/sbin      Homebrew tools (starship, zoxide, xonsh itself)
#   ~/.local/bin            user-installed scripts + uv-tool shims
#   ~/.npm-global/bin       npm global redirect (nix node has RO store prefix)
#   ~/.opencode/bin         opencode CLI
#   ~/dev/flutter/bin       flutter SDK
#   Android SDK tools       platform-tools, emulator, cmdline-tools
# linuxbrew is listed first so it lands at the back of PATH (lowest priority);
# nothing else sources `brew shellenv`, so without this its bins are invisible.
import os as _os
for _p in (
    '/home/linuxbrew/.linuxbrew/sbin',
    '/home/linuxbrew/.linuxbrew/bin',
    _os.path.expanduser('~/Android/Sdk/cmdline-tools/latest/bin'),
    _os.path.expanduser('~/Android/Sdk/emulator'),
    _os.path.expanduser('~/Android/Sdk/platform-tools'),
    _os.path.expanduser('~/dev/flutter/bin'),
    _os.path.expanduser('~/.opencode/bin'),
    _os.path.expanduser('~/.npm-global/bin'),
    _os.path.expanduser('~/.local/bin'),
):
    if not _os.path.isdir(_p):
        continue
    if _p not in $PATH:
        $PATH.insert(0, _p)
del _p, _os

# ---------------------------------------------------------------------------
# Prompt + nav (starship, zoxide)
# ---------------------------------------------------------------------------

import shutil as _shutil
from pathlib import Path as _Path

# Bootstrap runtime starship config from repo on first shell start if missing.
# On sway systems set-theme.sh regenerates this from starship.toml.tmpl
# per theme; on non-sway systems the committed default is used as-is.
_runtime = _Path.home() / '.config' / 'starship.toml'
_source  = _Path.home() / 'dotfiles' / 'starship.toml'
if not _runtime.exists() and _source.exists():
    _runtime.parent.mkdir(parents=True, exist_ok=True)
    _shutil.copy(_source, _runtime)
del _runtime, _source, _Path

if _shutil.which('starship'):
    execx($(starship init xonsh))
if _shutil.which('zoxide'):
    execx($(zoxide init --cmd cd xonsh))
del _shutil

# ---------------------------------------------------------------------------
# Suffix-style alias: `foo.py` → `python3 foo.py`. Xonsh has no native suffix
# alias; emulate via a callable alias dispatching on extension.
# ---------------------------------------------------------------------------

# (skipped — xonsh runs python natively; just call `python3 foo.py`)

# ---------------------------------------------------------------------------
# Sway logout alias
# ---------------------------------------------------------------------------

if 'SWAYSOCK' in ${...}:
    aliases['logout'] = ['swaymsg', 'exit']

# ---------------------------------------------------------------------------
# tmux per-pane venv tracker — mirror of .zshrc precmd hook.
# Publishes active venv basename to tmux user option @venv; tmux.conf reads
# #{@venv} to render the venv pill. Only active inside a tmux pane.
# ---------------------------------------------------------------------------

if 'TMUX' in ${...}:
    from xonsh.built_ins import XSH as _XSH

    @_XSH.builtins.events.on_pre_prompt
    def _tmux_publish_venv():
        import subprocess
        pane = ${...}.get('TMUX_PANE', '')
        if not pane:
            return
        venv = ${...}.get('VIRTUAL_ENV', '')
        if venv:
            subprocess.run(
                ['tmux', 'set-option', '-p', '-t', pane, '@venv',
                 venv.rsplit('/', 1)[-1]],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        else:
            subprocess.run(
                ['tmux', 'set-option', '-p', '-t', pane, '-u', '@venv'],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
    del _XSH

# ---------------------------------------------------------------------------
# tmux helpers
# ---------------------------------------------------------------------------

# tmux quick-attach / switch.
#   tm        → "main" session (default).
#   tm name   → named session.
#   tp        → session named after current dir basename (per-project).
# Outside tmux: attach if session exists, else create + attach.
# Inside tmux:  switch-client to the session (creating it detached if missing),
#               since tmux refuses to nest by default.

def _tmux_go(name):
    import subprocess
    # Always ensure the session exists detached first. Splitting create from
    # attach avoids the nest-refusal that `tmux new -A` triggers from inside.
    has = subprocess.run(['tmux', 'has-session', '-t', name],
                         capture_output=True).returncode == 0
    if not has:
        $[tmux new-session -d -s @(name)]
    if 'TMUX' in ${...}:
        $[tmux switch-client -t @(name)]
    else:
        $[tmux attach -t @(name)]

def _tm(args, stdin=None):
    _tmux_go(args[0] if args else 'main')
aliases['tm'] = _tm

def _tp(args, stdin=None):
    import os
    _tmux_go(os.path.basename($PWD))
aliases['tp'] = _tp

# tr [name] → attach/switch to an existing session (default "main").
# Refuses to create. Fails loud if server or session missing.
def _tr(args, stdin=None):
    import sys, subprocess
    name = args[0] if args else 'main'
    tty = sys.stderr.isatty()
    red  = '\033[1;31m' if tty else ''
    dim  = '\033[2m'    if tty else ''
    bold = '\033[1m'    if tty else ''
    rst  = '\033[0m'    if tty else ''
    err  = lambda m: print(f'{red}tr:{rst} {bold}error:{rst} {m}', file=sys.stderr)
    hint = lambda m: print(f'{dim}tr: hint: {m}{rst}', file=sys.stderr)
    if subprocess.run(['tmux', 'has-session'], capture_output=True).returncode != 0:
        err('tmux not running')
        hint('use detach to exit a session without killing it')
        return 1
    if subprocess.run(['tmux', 'has-session', '-t', f'={name}'],
                      capture_output=True).returncode != 0:
        ls = subprocess.run(['tmux', 'list-sessions', '-F', '#S'],
                            capture_output=True, text=True)
        avail = ', '.join(l for l in ls.stdout.splitlines() if l) or '<none>'
        err(f"session '{name}' does not exist")
        hint(f'available: {avail}')
        return 1
    if 'TMUX' in ${...}:
        $[tmux switch-client -t @(name)]
    else:
        $[tmux attach -t @(name)]
aliases['tr'] = _tr
