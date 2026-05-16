#!/usr/bin/env bash
# Display-format current directory path for the tmux status bar:
# replaces $HOME prefix with `~`. Full path otherwise (no truncation).
#
# Usage: pwd-display.sh /full/path/here
# Called by tmux via #(pwd-display.sh '#{pane_current_path}').

set -eu
path=${1:-$PWD}
# Tilde-substitution in ${x/.../~} re-expands the tilde back to $HOME in
# bash 4+. Use sed for a literal `~` replacement.
printf '%s' "$path" | sed "s|^${HOME//\//\\/}|~|"
