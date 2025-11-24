export PATH="$HOME/.local/bin:$PATH"

# Use powerline
USE_POWERLINE="true"
# Has weird character width
# Example:
#    is not a diamond
HAS_WIDECHARS="false"

# Use Starship Prompt
#eval "$(starship init zsh)"

# Use Oh My Posh prompt
eval "$(oh-my-posh init zsh --config ~/.config/omp/uraxii_atomic.omp.toml)"
# Applications

## Zoxide

# --cmd cd allows you to use cd instead of z/zi
eval "$(zoxide init --cmd cd zsh)"

