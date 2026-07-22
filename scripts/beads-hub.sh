#!/usr/bin/env bash
# beads-hub.sh — global bd (beads) hub: ALL project boards live centrally
# under one hub root (no more <repo>/.beads), aggregated into one
# cross-project view via bd's multi-repo support.
#
#   $HUB_ROOT/hub/.beads       the aggregator board (prefix: hub)
#   $HUB_ROOT/<name>/.beads    one board per project (prefix: <name>, or
#                              an explicit override)
#
# The aggregator's config.yaml repos.additional list is what `bd repo sync`
# hydrates from; init-agent-workspace.sh calls `add` instead of running
# `bd init` itself, so a project repo never gets its own .beads again.
#
# Usage:
#   beads-hub.sh init                  create the aggregator (idempotent)
#   beads-hub.sh add NAME [PREFIX]     create+register $HUB_ROOT/NAME/.beads
#   beads-hub.sh sync                  hydrate the aggregator from all repos
#   beads-hub.sh list                  list repos registered in the aggregator
#   beads-hub.sh path NAME             print $HUB_ROOT/NAME/.beads
#   beads-hub.sh status                JSON: hub root, initialized?, repos
set -euo pipefail

# ponytail: default is NOT $HOME/.beads. bd 1.1.0 hard-refuses to init any
# board whose path has a ".beads"-named ancestor directory ("cannot
# initialize bd inside a .beads directory") -- and every subdir of
# $HOME/.beads matches that, aggregator included, so nesting hub/<name>
# boards under a dir literally called .beads is a dead end. BEADS_HUB_DIR
# still overrides if a caller wants a different location.
HUB_ROOT="${BEADS_HUB_DIR:-$HOME/.beads-hub}"
AGGREGATOR_DIR="$HUB_ROOT/hub"
AGGREGATOR_BEADS="$AGGREGATOR_DIR/.beads"

die() {
  echo "beads-hub: $*" >&2
  exit 1
}

usage() {
  echo "usage: beads-hub.sh {init|add|sync|list|path|status} [ARGS]" >&2
  exit 2
}

# A board dir is "initialized" once its Dolt db exists, not merely once the
# dir exists — a dir can pre-date its board (e.g. HUB_ROOT already holding
# an unrelated eventsData/ subdir before the aggregator is ever created).
board_exists() {
  local beads_dir="$1"
  [ -d "$beads_dir/embeddeddolt" ] || compgen -G "$beads_dir"'/*.db' > /dev/null 2>&1
}

# Run `bd init` for a board at DIR/.beads, then undo the incidental git
# repo bd's --stealth creates in DIR when DIR isn't already a git repo
# (stealth mode wants a repo to write its exclude rule into; with nothing
# else tracked there, the exclude rule serves no purpose and the bare repo
# is just litter).
init_board() {
  local dir="$1" prefix="$2" git_preexisted=1
  mkdir -p "$dir"
  [ -d "$dir/.git" ] && git_preexisted=0

  # --skip-agents/--skip-hooks: only want the board, not bd's own
  # CLAUDE.md/AGENTS.md scaffolding or its git hooksPath takeover.
  # --stealth: keep beads files untracked.
  ( cd "$dir" && bd init --non-interactive --skip-agents \
      --skip-hooks --stealth --prefix "$prefix" )

  if [ "$git_preexisted" -eq 1 ] && [ -d "$dir/.git" ]; then
    rm -rf "$dir/.git"
    echo "beads-hub: removed incidental git repo bd init created at $dir"
  fi
}

cmd_init() {
  if board_exists "$AGGREGATOR_BEADS"; then
    echo "beads-hub: aggregator already initialized at $AGGREGATOR_BEADS"
    return 0
  fi
  init_board "$AGGREGATOR_DIR" "hub"
  echo "beads-hub: aggregator initialized at $AGGREGATOR_BEADS"
}

cmd_add() {
  local name="${1:?usage: beads-hub.sh add NAME [PREFIX]}" prefix="${2:-}"
  prefix="${prefix:-$name}"
  local project_dir="$HUB_ROOT/$name" project_beads="$HUB_ROOT/$name/.beads"

  board_exists "$AGGREGATOR_BEADS" || cmd_init

  if board_exists "$project_beads"; then
    echo "beads-hub: $name already has a board at $project_beads"
  else
    init_board "$project_dir" "$prefix"
    echo "beads-hub: created board for $name at $project_beads"
  fi

  if registered_repos | grep -qxF "$project_dir"; then
    echo "beads-hub: $name already registered in aggregator"
    return 0
  fi
  BEADS_DIR="$AGGREGATOR_BEADS" bd repo add "$project_dir"
  echo "beads-hub: registered $name in aggregator"
}

# One registered repo path per line.
# ponytail: `bd repo list --json` silently ignores --json and always
# prints the human text form (verified against bd 1.1.0), so parse that
# text's stable "  - <path>" line prefix instead of pulling in jq.
registered_repos() {
  BEADS_DIR="$AGGREGATOR_BEADS" bd repo list 2>/dev/null | sed -n 's/^  - //p'
}

cmd_sync() {
  BEADS_DIR="$AGGREGATOR_BEADS" bd repo sync
}

cmd_list() {
  BEADS_DIR="$AGGREGATOR_BEADS" bd repo list
}

cmd_path() {
  local name="${1:?usage: beads-hub.sh path NAME}"
  local project_beads="$HUB_ROOT/$name/.beads"
  board_exists "$project_beads" || die "no board for $name at $project_beads"
  echo "$project_beads"
}

cmd_status() {
  local initialized="false" repos_json="[]" repo repos=()
  if board_exists "$AGGREGATOR_BEADS"; then
    initialized="true"
    while IFS= read -r repo; do
      repos+=("\"$repo\"")
    done < <(registered_repos)
    [ "${#repos[@]}" -gt 0 ] && repos_json="[$(IFS=,; echo "${repos[*]}")]"
  fi
  printf '{"hub_root":"%s","initialized":%s,"repos":%s}\n' \
    "$HUB_ROOT" "$initialized" "$repos_json"
}

case "${1:-}" in
  init)   cmd_init ;;
  add)    shift; cmd_add "$@" ;;
  sync)   cmd_sync ;;
  list)   cmd_list ;;
  path)   shift; cmd_path "$@" ;;
  status) cmd_status ;;
  *)      usage ;;
esac
