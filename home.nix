{ config, pkgs, ... }:

# This file manages package presence only.
# It does NOT manage any configuration files — all configs live in
# .config/ and are symlinked manually, as with the rest of this dotfiles repo.

{
  # Do not change this after the first activation.
  home.stateVersion = "24.11";

  programs.home-manager.enable = true;

  home.packages = with pkgs; [
    # Wayland / Sway ecosystem
    sway
    swayidle
    swaybg
    swaylock-effects

    # Status bar & launcher
    waybar
    wofi
    networkmanager-dmenu
    pavucontrol

    # Applications
    ghostty

    # Fonts
    nerd-fonts._0xproto

    # Dotfiles tooling
    stow              # symlink dotfiles into $HOME
    gh                # GitHub CLI (PR/issue/repo ops)
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
