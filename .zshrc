# Useful Commands

# Reloads Z-Shell config witout opening a new shell.
# source ~/.zshrc


# Export Environment Variables

export CHROME_EXECUTABLE=google-chrome-stable
export PATH="$HOME/.local/bin:$PATH"
# npm global prefix redirect (nix-store node has read-only default prefix).
export PATH="$HOME/.npm-global/bin:$PATH"

# Command Line Prompt

# Use powerline
USE_POWERLINE="true"
# Has weird character width
# Example:
#    is not a diamond
HAS_WIDECHARS="false"


## Starship

eval "$(starship init zsh)"

## Oh My Posh

#eval "$(oh-my-posh init zsh --config ~/.config/omp/uraxii_atomic.omp.toml)"

# Key Bindings

bindkey "^[[H"    beginning-of-line   # Home
bindkey "^[[F"    end-of-line         # End
bindkey "^[[3~"   delete-char         # Del
bindkey "^[[1;5C" forward-word        # Ctrl+Right
bindkey "^[[1;5D" backward-word       # Ctrl+Left

# Aliases

# Allows the 'logout' keyword to work as expected in the Sway Window Manager.
[[ "$SWAYSOCK" ]] && alias logout='swaymsg exit'

# Suffix aliases — run files by name w/o shebang
alias -s py=python3

# tmux quick-attach / switch.
#   tm        → "main" session (default).
#   tm name   → named session.
#   tp        → session named after current dir basename (per-project).
# Outside tmux: attach if session exists, else create + attach.
# Inside tmux:  switch-client to the session (creating it detached if missing),
#               since tmux refuses to nest by default.
_tmux_go() {
  local name="$1"
  # Always ensure the session exists detached first. This split avoids the
  # nest-refusal that `tmux new -A` triggers when run from inside a pane.
  tmux has-session -t "$name" 2>/dev/null || tmux new-session -d -s "$name"
  if [[ -n "$TMUX" ]]; then
    tmux switch-client -t "$name"
  else
    tmux attach -t "$name"
  fi
}
tm() { _tmux_go "${1:-main}"; }
tp() { _tmux_go "$(basename "$PWD")"; }
# tr [name] → attach/switch to an existing session (default "main").
# Refuses to create. Fails loud if server or session missing.
tr() {
  emulate -L zsh
  local name="${1:-main}"
  local red='' dim='' bold='' rst=''
  if [[ -t 2 ]]; then
    red=$'\e[1;31m'; dim=$'\e[2m'; bold=$'\e[1m'; rst=$'\e[0m'
  fi
  local err() { print -u2 -- "${red}tr:${rst} ${bold}error:${rst} $1"; }
  local hint() { print -u2 -- "${dim}tr: hint: $1${rst}"; }
  if ! tmux has-session 2>/dev/null; then
    err "tmux not running"
    hint "use detach to exit a session without killing it"
    return 1
  fi
  if ! tmux has-session -t "=$name" 2>/dev/null; then
    local sessions
    sessions=$(tmux list-sessions -F '#S' 2>/dev/null | paste -sd, -)
    err "session '$name' does not exist"
    hint "available: ${sessions:-<none>}"
    return 1
  fi
  if [[ -n "$TMUX" ]]; then
    tmux switch-client -t "$name"
  else
    tmux attach -t "$name"
  fi
}

# Applications

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion

# opencode
export PATH=/home/nikki/.opencode/bin:$PATH

## tmux per-pane venv tracker
#
# Publishes the active Python virtualenv basename to a per-pane tmux user
# option (@venv) on each prompt. tmux.conf reads #{@venv} to render the venv
# pill; empty value collapses the pill. Only active inside a tmux pane.
if [ -n "$TMUX" ]; then
    _tmux_publish_venv() {
        if [ -n "$VIRTUAL_ENV" ]; then
            command tmux set-option -p -t "$TMUX_PANE" @venv "${VIRTUAL_ENV##*/}" >/dev/null 2>&1
        else
            command tmux set-option -p -t "$TMUX_PANE" -u @venv >/dev/null 2>&1
        fi
    }
    autoload -Uz add-zsh-hook
    add-zsh-hook precmd _tmux_publish_venv
fi

## Zoxide

# --cmd cd allows you to use cd instead of z/zi
# Initialized at the end of .zshrc (zoxide requires this)
export _ZO_DOCTOR=0
eval "$(zoxide init --cmd cd zsh)"


export PATH="$HOME/dev/flutter/bin:$PATH"
export PATH="$HOME/Android/Sdk/platform-tools:$HOME/Android/Sdk/emulator:$HOME/Android/Sdk/cmdline-tools/latest/bin:$PATH"
