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
  ];
}
