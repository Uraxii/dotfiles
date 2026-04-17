# Useful Commands

# Reloads Z-Shell config witout opening a new shell.
# source ~/.zshrc


# Export Environment Variables

export PATH="$HOME/.local/bin:$PATH"

# Command Line Prompt

# Use powerline
USE_POWERLINE="true"
# Has weird character width
# Example:
#    is not a diamond
HAS_WIDECHARS="false"


## Starship

#eval "$(starship init zsh)"

## Oh My Posh

eval "$(oh-my-posh init zsh --config ~/.config/omp/uraxii_atomic.omp.toml)"

# Key Bindings

bindkey "^[[H"    beginning-of-line   # Home
bindkey "^[[F"    end-of-line         # End
bindkey "^[[3~"   delete-char         # Del
bindkey "^[[1;5C" forward-word        # Ctrl+Right
bindkey "^[[1;5D" backward-word       # Ctrl+Left

# Aliases

# Allows the 'logout' keyword to work as expected in the Sway Window Manager.
[[ "$SWAYSOCK" ]] && alias logout='swaymsg exit'

# Applications

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion

# opencode
export PATH=/home/nikki/.opencode/bin:$PATH

## Zoxide

# --cmd cd allows you to use cd instead of z/zi
# Initialized at the end of .zshrc (zoxide requires this)
export _ZO_DOCTOR=0
eval "$(zoxide init --cmd cd zsh)"


