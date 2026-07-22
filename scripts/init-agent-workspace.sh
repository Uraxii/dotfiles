#!/usr/bin/env bash
# init-agent-workspace.sh — scaffold the standard per-project agent
# workspace shape into a target repo:
#
#   .beads/       bd board (machine coordination: statuses, deps, claims)
#   docs/kb/      distilled markdown knowledge-base entries (tracked)
#   workstreams/  per-workstream status.md + artifacts
#   kb.db         FTS5 index over docs/kb/, kept current by build-kb-index.py
#
# See .claude/rules/orchestration.md ("Per-project standard shape") for why
# this shape exists. Idempotent: safe to run twice, second run is
# non-destructive and reports "already initialized" per component.
#
# Usage: scripts/init-agent-workspace.sh [TARGET_DIR] [--prefix PREFIX]
#   TARGET_DIR   repo to scaffold (default: current directory)
#   --prefix     bd issue prefix override (default: TARGET_DIR basename)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INDEXER="$SCRIPT_DIR/build-kb-index.py"

target_dir="."
prefix=""
while [ $# -gt 0 ]; do
  case "$1" in
    --prefix)
      [ $# -ge 2 ] || { echo "init-agent-workspace: --prefix requires a value" >&2; exit 1; }
      prefix="$2"; shift 2 ;;
    *)        target_dir="$1"; shift ;;
  esac
done

target_dir="$(cd "$target_dir" && pwd)"
cd "$target_dir"

# ---- bd board ----
if [ -d .beads ]; then
  echo "init-agent-workspace: .beads already initialized, skipping"
else
  prefix="${prefix:-$(basename "$target_dir")}"
  # --skip-agents/--skip-hooks: we only want the board, not bd's own
  # CLAUDE.md/AGENTS.md scaffolding or its git hooksPath takeover.
  # --stealth: keeps .beads/ out of git (via .git/info/exclude) instead of
  # bd's default of auto-committing .beads/ files itself; this repo's own
  # .gitignore (added below/by hand) is what actually tracks the ignore
  # rule across clones.
  bd init --non-interactive --prefix "$prefix" \
    --skip-agents --skip-hooks --stealth
  echo "init-agent-workspace: bd board initialized (prefix: $prefix)"
fi

# ---- docs/kb/ and workstreams/ ----
for dir in docs/kb workstreams; do
  if [ -d "$dir" ]; then
    echo "init-agent-workspace: $dir already exists, skipping"
  else
    mkdir -p "$dir"
    echo "init-agent-workspace: created $dir"
  fi
done

# ---- kb.db FTS5 index ----
# Always safe to re-run: build-kb-index.py does a full rebuild from
# docs/kb/*.md, so this both creates the db on first run and refreshes it
# on later runs without any separate "does it exist" branch.
"$INDEXER" --root "$target_dir"

# ---- post-commit KB reindex hook ----
hook="$target_dir/.git/hooks/post-commit"
if [ -f "$hook" ]; then
  echo "init-agent-workspace: WARNING $hook already exists, not overwriting."
  echo "  Add this line to it manually to keep the KB index current:"
  echo "  git diff-tree --no-commit-id --name-only -r --root HEAD | grep -q '^docs/kb/' && \"$INDEXER\" --root \"\$(git rev-parse --show-toplevel)\""
else
  cat > "$hook" <<HOOK_EOF
#!/usr/bin/env bash
# Post-commit KB reindex hook (untracked, installed by
# scripts/init-agent-workspace.sh). Reindexes docs/kb/ into kb.db only when
# this commit touched docs/kb/; no-op otherwise.
set -euo pipefail
repo_root="\$(git rev-parse --show-toplevel)"
if git diff-tree --no-commit-id --name-only -r --root HEAD | grep -q '^docs/kb/'; then
  "$INDEXER" --root "\$repo_root"
fi
HOOK_EOF
  chmod +x "$hook"
  echo "init-agent-workspace: installed post-commit KB reindex hook"
fi

echo "init-agent-workspace: done ($target_dir)"
