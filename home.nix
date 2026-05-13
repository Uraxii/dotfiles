{ config, pkgs, ... }:

# This file manages package presence only.
# It does NOT manage any configuration files — all configs live in
# .config/ and are symlinked manually, as with the rest of this dotfiles repo.

{
  # Do not change this after the first activation.
  home.username = "nikki";
  home.homeDirectory = "/home/nikki";
  home.stateVersion = "24.11";

  programs.home-manager.enable = true;

  # Allow unfree pkgs (claude-code etc.)
  nixpkgs.config.allowUnfree = true;

  # Overlay: pull claude-code from nixos-unstable (faster than stable channel).
  # Anthropic ships ~weekly; 25.11 stable lags days/weeks.
  nixpkgs.overlays = [
    (final: prev: {
      claude-code = (import (builtins.fetchTarball {
        url = "https://nixos.org/channels/nixos-unstable/nixexprs.tar.xz";
      }) { config.allowUnfree = true; }).claude-code;
    })
  ];

  home.packages = with pkgs; [
    # Wayland / Sway ecosystem
    sway
    swayidle
    swaybg
    swaylock-effects

    # Status bar & launcher
    waybar
    wofi
    networkmanager_dmenu
    pavucontrol

    # Applications
    ghostty
    neovim
    gcc               # treesitter compile + native LSPs
    gnumake           # plugin builds (telescope-fzf-native etc.)
    unzip             # Mason package extraction
    ripgrep           # telescope live_grep
    fd                # telescope find_files
    wl-clipboard      # Wayland clipboard bridge for nvim
    nodejs_22         # Mason-installed JS/TS LSPs (tsserver, vtsls)

    # Fonts
    nerd-fonts._0xproto

    # Dotfiles tooling
    zsh
    oh-my-posh

    zoxide            # smart cd (used by .zshrc)
    stow              # symlink dotfiles into $HOME
    git               # base VCS (required by lazy.nvim)
    gh                # GitHub CLI (PR/issue/repo ops)
    claude-code       # Anthropic Claude Code CLI
    jq                # JSON parsing in scripts + setup.sh

    # Pipeline (Slack listener + pipeline_ask CLI + setup.sh)
    uv                # `uv run --script` runs slack_listener.py w/ inline deps;
                      # `uvx weasyprint` powers --attach HTML→PDF auto-convert.
    python313         # >= 3.11 required; stdlib used by pipeline_ask + hooks

    # weasyprint runtime system libs (needed by uvx --from weasyprint).
    # Without these, HTML→PDF conversion fails and pipeline_ask falls back to
    # uploading raw HTML (Slack shows it as text source, not rendered).
    pango
    cairo
    gdk-pixbuf
    libffi
  ];
}
