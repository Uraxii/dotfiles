#!/usr/bin/env bash
# board-ui.sh — per-project lifecycle helper for bdui (bd's web front end).
#
# bdui auto-discovers the .beads board in its launch directory (cwd) and, by
# default, tracks a single global PID file — so two `bdui start` calls from
# different repos collide instead of running side by side. This wrapper
# gives each repo its own isolated bdui daemon by pointing BDUI_RUNTIME_DIR
# (bdui's own override for where it keeps its PID/log files) at a per-repo
# runtime dir, so `up`/`down`/`status` never step on a different project's
# instance.
#
# Usage:
#   board-ui.sh up [REPO_DIR]      start (or reuse) the board UI for REPO_DIR
#   board-ui.sh down [REPO_DIR]    stop the board UI for REPO_DIR
#   board-ui.sh status             list running board UIs
#
# REPO_DIR defaults to the current directory. `up` prints the UI URL.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BDUI_BIN="$SCRIPT_DIR/../spikes/beads-board/node_modules/.bin/bdui"
RUNTIME_ROOT="${XDG_RUNTIME_DIR:-/tmp}/board-ui"
PORT_START=3000
PORT_TRIES=100

# ponytail: linuxbrew's node isn't guaranteed on PATH for every caller of
# this script (e.g. a subagent shell); prepend it, same as the verified
# manual launch command.
export PATH="/home/linuxbrew/.linuxbrew/bin:$PATH"

die() {
  echo "board-ui: $*" >&2
  exit 1
}

require_bdui() {
  [ -x "$BDUI_BIN" ] || die "bdui not found at $BDUI_BIN"
}

is_alive() {
  local pid="$1"
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

# Runtime dir for REPO_DIR. Also passed to bdui as BDUI_RUNTIME_DIR, so
# bdui's own server.pid/daemon.log land here scoped to this one repo.
repo_runtime_dir() {
  local repo_dir="$1" slug
  slug="$(basename "$repo_dir")-$(printf '%s' "$repo_dir" | sha1sum | cut -c1-8)"
  echo "$RUNTIME_ROOT/$slug"
}

# Resolve REPO_DIR to an absolute path and confirm it holds a .beads board.
resolve_repo() {
  local raw="${1:-.}" repo_dir
  [ -d "$raw" ] || die "no such directory: $raw"
  repo_dir="$(cd "$raw" && pwd)"
  [ -d "$repo_dir/.beads" ] || die "no .beads board in $repo_dir"
  echo "$repo_dir"
}

# Ascending bind-test from PORT_START; first port nothing answers on wins.
# ponytail: /dev/tcp connect-probe, no nc/python dependency.
find_free_port() {
  local port
  for ((port = PORT_START; port < PORT_START + PORT_TRIES; port++)); do
    if ! { exec 3<>"/dev/tcp/127.0.0.1/$port"; } 2>/dev/null; then
      echo "$port"
      return 0
    fi
    exec 3<&- 3>&-
  done
  die "no free port in $PORT_START-$((PORT_START + PORT_TRIES - 1))"
}

cmd_up() {
  require_bdui
  local repo_dir run_dir pid port
  repo_dir="$(resolve_repo "${1:-.}")"
  run_dir="$(repo_runtime_dir "$repo_dir")"
  mkdir -p "$run_dir"

  if [ -f "$run_dir/server.pid" ]; then
    pid="$(cat "$run_dir/server.pid")"
    if is_alive "$pid" && [ -f "$run_dir/port" ]; then
      echo "http://127.0.0.1:$(cat "$run_dir/port")"
      return 0
    fi
    rm -f "$run_dir/server.pid" "$run_dir/port"  # stale entry, prune it
  fi

  port="$(find_free_port)"
  (cd "$repo_dir" && BDUI_RUNTIME_DIR="$run_dir" "$BDUI_BIN" start --host 127.0.0.1 --port "$port") \
    || die "bdui start failed for $repo_dir"

  echo "$port" > "$run_dir/port"
  echo "$repo_dir" > "$run_dir/repo"
  echo "http://127.0.0.1:$port"
}

cmd_down() {
  require_bdui
  local repo_dir run_dir
  repo_dir="$(resolve_repo "${1:-.}")"
  run_dir="$(repo_runtime_dir "$repo_dir")"

  if [ ! -f "$run_dir/server.pid" ]; then
    echo "board-ui: no board UI running for $repo_dir" >&2
    return 0
  fi

  BDUI_RUNTIME_DIR="$run_dir" "$BDUI_BIN" stop || true
  rm -rf "$run_dir"
  echo "board-ui: stopped $repo_dir"
}

cmd_status() {
  [ -d "$RUNTIME_ROOT" ] || return 0
  local run_dir pid port repo
  for run_dir in "$RUNTIME_ROOT"/*/; do
    [ -f "$run_dir/server.pid" ] || continue
    pid="$(cat "$run_dir/server.pid")"
    if ! is_alive "$pid"; then
      rm -rf "$run_dir"  # prune stale entry
      continue
    fi
    port="$(cat "$run_dir/port" 2>/dev/null || echo '?')"
    repo="$(cat "$run_dir/repo" 2>/dev/null || echo '?')"
    echo "$repo -> http://127.0.0.1:$port ($pid)"
  done
}

case "${1:-}" in
  up)     shift; cmd_up "${1:-.}" ;;
  down)   shift; cmd_down "${1:-.}" ;;
  status) cmd_status ;;
  *)      die "usage: board-ui.sh {up|down|status} [REPO_DIR]" ;;
esac
