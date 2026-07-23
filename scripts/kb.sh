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
#   kb.sh init                       create the vault (idempotent)
#   kb.sh add PROJECT                create PROJECT's note dirs (idempotent)
#   kb.sh path PROJECT               print $KB_HOME/PROJECT
#   kb.sh index                      rebuild the global FTS5 index
#   kb.sh clip URL [--project P]     deterministic web-source capture
#   kb.sh put PROJECT TITLE [--type T] [--source S]
#                                    write a note (body on stdin)
#   kb.sh query Q [--project P] [--type T] [--all]
#                                    FTS5 search
#   kb.sh atomize FILE               deterministic split into atomic notes
#   kb.sh status                     JSON: kb_home, initialized?, projects
#
# put/query/clip prefer the running kb-serve.py HTTP service (see
# scripts/kb-serve.py, scripts/kb-container/) when it answers /health on
# KB_SERVE_PORT (default 9100): that path also atomizes + reindexes.
# Falls back to a local, in-process call of the same kb-serve.py functions
# when the service is down -- same behavior either way, no service
# required for personal/offline use.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KB_HOME="${KB_HOME:-$HOME/.knowledgebase}"
KB_SERVE_URL="http://127.0.0.1:${KB_SERVE_PORT:-9100}"
NOTE_DIRS=(decisions notes research sources)

usage() {
  echo "usage: kb.sh {init|add|path|index|clip|put|query|atomize|status} [ARGS]" >&2
  exit 2
}

service_up() {
  curl -sf -m 1 "$KB_SERVE_URL/health" >/dev/null 2>&1
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
  local url="${1:?usage: kb.sh clip URL [--project P]}"
  shift
  local project="inbox"
  while [ $# -gt 0 ]; do
    case "$1" in
      --project) project="$2"; shift 2 ;;
      *) usage ;;
    esac
  done
  if service_up; then
    # via the service: also atomizes + reindexes, unlike the bare
    # kb-clip.py call below.
    python3 -c 'import json,sys; print(json.dumps({"url":sys.argv[1],"project":sys.argv[2]}))' \
        "$url" "$project" \
      | curl -sf -X POST -H "Content-Type: application/json" -d @- "$KB_SERVE_URL/clip"
  else
    "$SCRIPT_DIR/kb-serve.py" clip "$url" --project "$project" --kb-home "$KB_HOME"
  fi
}

cmd_put() {
  local project="${1:?usage: kb.sh put PROJECT TITLE [--type T] [--source S] (body on stdin)}"
  local title="${2:?usage: kb.sh put PROJECT TITLE [--type T] [--source S] (body on stdin)}"
  shift 2
  local note_type="note" source=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --type) note_type="$2"; shift 2 ;;
      --source) source="$2"; shift 2 ;;
      *) usage ;;
    esac
  done
  local content
  content="$(cat)"
  if service_up; then
    python3 -c 'import json,sys
print(json.dumps({"project":sys.argv[1],"title":sys.argv[2],"type":sys.argv[3],
                   "source":sys.argv[4],"content":sys.argv[5]}))' \
        "$project" "$title" "$note_type" "$source" "$content" \
      | curl -sf -X POST -H "Content-Type: application/json" -d @- "$KB_SERVE_URL/put"
  else
    printf '%s' "$content" \
      | "$SCRIPT_DIR/kb-serve.py" put "$project" "$title" \
          --type "$note_type" --source "$source" --kb-home "$KB_HOME"
  fi
}

cmd_query() {
  local q="${1:?usage: kb.sh query QUERY [--project P] [--type T] [--all]}"
  shift
  local project="" note_type="" all_flag=0
  while [ $# -gt 0 ]; do
    case "$1" in
      --project) project="$2"; shift 2 ;;
      --type) note_type="$2"; shift 2 ;;
      --all) all_flag=1; shift ;;
      *) usage ;;
    esac
  done
  if service_up; then
    local encoded_q
    encoded_q="$(python3 -c 'import sys,urllib.parse; print(urllib.parse.quote(sys.argv[1]))' "$q")"
    local url="$KB_SERVE_URL/query?q=$encoded_q"
    [ -n "$project" ] && url="$url&project=$project"
    [ -n "$note_type" ] && url="$url&type=$note_type"
    [ "$all_flag" = 1 ] && url="$url&all=1"
    curl -sf "$url"
  else
    local args=("$q")
    [ -n "$project" ] && args+=(--project "$project")
    [ -n "$note_type" ] && args+=(--type "$note_type")
    [ "$all_flag" = 1 ] && args+=(--all)
    "$SCRIPT_DIR/kb-serve.py" query "${args[@]}" --kb-home "$KB_HOME"
  fi
}

cmd_atomize() {
  local file="${1:?usage: kb.sh atomize FILE}"
  "$SCRIPT_DIR/kb-atomize.py" --kb-home "$KB_HOME" "$file"
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
  init)    cmd_init ;;
  add)     shift; cmd_add "$@" ;;
  path)    shift; cmd_path "$@" ;;
  index)   cmd_index ;;
  clip)    shift; cmd_clip "$@" ;;
  put)     shift; cmd_put "$@" ;;
  query)   shift; cmd_query "$@" ;;
  atomize) shift; cmd_atomize "$@" ;;
  status)  cmd_status ;;
  *)       usage ;;
esac
