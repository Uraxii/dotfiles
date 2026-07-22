#!/usr/bin/env bash
# kb.sh -- personal machine-local knowledgebase vault (Obsidian-compatible).
#
# Mirrors the beads-hub.sh split: per-project SOURCE notes live under
# their own project dir, one GLOBAL derived INDEX is built over all of
# them. Unlike beads-hub, the vault itself is NOT a git repo and is
# NEVER committed -- personal notes + clipped web sources, machine-local.
#
#   $KB_HOME/.obsidian/           marks the dir as an Obsidian vault
#   $KB_HOME/index/kb.db          FTS5 index over every project (kb-index.py)
#   $KB_HOME/<project>/{decisions,notes,research,sources}/*.md
#
# Usage:
#   kb.sh init                    create the vault (idempotent)
#   kb.sh add PROJECT             create PROJECT's note dirs (idempotent)
#   kb.sh path PROJECT            print $KB_HOME/PROJECT
#   kb.sh index                   rebuild the global FTS5 index
#   kb.sh clip URL [--project P]  deterministic web-source capture
#   kb.sh status                  JSON: kb_home, initialized?, projects
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KB_HOME="${KB_HOME:-$HOME/.knowledgebase}"
NOTE_DIRS=(decisions notes research sources)

usage() {
  echo "usage: kb.sh {init|add|path|index|clip|status} [ARGS]" >&2
  exit 2
}

cmd_init() {
  mkdir -p "$KB_HOME/.obsidian" "$KB_HOME/index"
  echo "kb: vault ready at $KB_HOME"
}

cmd_add() {
  local project="${1:?usage: kb.sh add PROJECT}"
  cmd_init
  local dir
  for dir in "${NOTE_DIRS[@]}"; do
    mkdir -p "$KB_HOME/$project/$dir"
  done
  echo "kb: $project ready at $KB_HOME/$project"
}

cmd_path() {
  local project="${1:?usage: kb.sh path PROJECT}"
  echo "$KB_HOME/$project"
}

cmd_index() {
  KB_HOME="$KB_HOME" "$SCRIPT_DIR/kb-index.py" --kb-home "$KB_HOME" build
}

cmd_clip() {
  KB_HOME="$KB_HOME" "$SCRIPT_DIR/kb-clip.py" --kb-home "$KB_HOME" "$@"
}

cmd_status() {
  local initialized="false" projects_json="[]" name names=()
  if [ -d "$KB_HOME/.obsidian" ]; then
    initialized="true"
    while IFS= read -r name; do
      names+=("\"$name\"")
    done < <(find "$KB_HOME" -mindepth 1 -maxdepth 1 -type d \
      ! -name ".obsidian" ! -name "index" -printf '%f\n' | sort)
    [ "${#names[@]}" -gt 0 ] && projects_json="[$(IFS=,; echo "${names[*]}")]"
  fi
  printf '{"kb_home":"%s","initialized":%s,"projects":%s}\n' \
    "$KB_HOME" "$initialized" "$projects_json"
}

case "${1:-}" in
  init)   cmd_init ;;
  add)    shift; cmd_add "$@" ;;
  path)   shift; cmd_path "$@" ;;
  index)  cmd_index ;;
  clip)   shift; cmd_clip "$@" ;;
  status) cmd_status ;;
  *)      usage ;;
esac
