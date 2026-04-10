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

# Applications

## Zoxide

# --cmd cd allows you to use cd instead of z/zi
# Initialized at the end of .zshrc (zoxide requires this)
export _ZO_DOCTOR=0
eval "$(zoxide init --cmd cd zsh)"
