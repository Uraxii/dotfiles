source /usr/share/cachyos-fish-config/cachyos-config.fish

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

set -gx CHROME_EXECUTABLE google-chrome-stable

# zoxide doctor noise off; matches the old xonsh and zsh configs.
set -gx _ZO_DOCTOR 0

# PATH prepends, highest priority first. Mirrors the old xonsh/zsh layout,
# minus the linuxbrew entries: those were a Bazzite (atomic /usr, no pacman)
# workaround, and on Arch these tools come from pacman instead.
# fish_add_path silently skips any path that doesn't exist.
fish_add_path ~/.local/bin ~/.npm-global/bin ~/.opencode/bin ~/dev/flutter/bin \
    ~/Android/Sdk/platform-tools ~/Android/Sdk/emulator \
    ~/Android/Sdk/cmdline-tools/latest/bin

# ---------------------------------------------------------------------------
# Prompt + nav (starship, zoxide)
# ---------------------------------------------------------------------------

# Bootstrap runtime starship config from the repo on first shell start if
# missing. On sway systems set-theme.sh regenerates this from
# starship.toml.tmpl per theme; elsewhere the committed default is used as-is.
if not test -f ~/.config/starship.toml; and test -f ~/dotfiles/starship.toml
    cp ~/dotfiles/starship.toml ~/.config/starship.toml
end

if type -q starship
    starship init fish | source
end
if type -q zoxide
    zoxide init fish --cmd cd | source
end

# ---------------------------------------------------------------------------
# tmux per-pane venv tracker
# ---------------------------------------------------------------------------
# Publishes the active Python virtualenv basename to a per-pane tmux user
# option (@venv) right before each prompt draws. tmux.conf reads #{@venv} to
# render the venv pill; an empty value collapses the pill. Only active inside
# a tmux pane. fish has no precmd hook, so this uses the fish_prompt event,
# the same mechanism fish-pure-prompt's own hooks use.

if set -q TMUX
    function _tmux_publish_venv --on-event fish_prompt
        if test -z "$TMUX_PANE"
            return
        end
        if set -q VIRTUAL_ENV
            tmux set-option -p -t $TMUX_PANE @venv (basename $VIRTUAL_ENV) >/dev/null 2>&1
        else
            tmux set-option -p -t $TMUX_PANE -u @venv >/dev/null 2>&1
        end
    end
end
