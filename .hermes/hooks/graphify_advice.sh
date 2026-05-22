#!/usr/bin/env bash
# graphify_advice — Hermes pre_tool_call shell hook.
#
# Suggests `graphify query` for codebase grep/find operations when a
# graphify knowledge graph is present at the agent's working dir.
#
# Wired in ~/.hermes/config.yaml under hooks.pre_tool_call w/ matcher "terminal".
#
# Hermes shell hook wire protocol:
# - stdin: JSON envelope (hook_event_name, tool_name, tool_input.command, cwd, ...)
# - stdout: optional JSON `{"context":"..."}` to inject context-additive guidance
# - exit 0 = success
#
# Rewritten from inline-case in .claude/settings.json PreToolUse to standalone
# script form per Hermes shell-hook protocol.

set -eu

# Parse JSON stdin via python3 (no jq dep assumption).
PAYLOAD="$(cat)"
[ -z "$PAYLOAD" ] && exit 0

CMD="$(printf '%s' "$PAYLOAD" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print((d.get('tool_input') or {}).get('command') or '')
except Exception:
    pass
" 2>/dev/null || true)"

CWD="$(printf '%s' "$PAYLOAD" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get('cwd') or '')
except Exception:
    pass
" 2>/dev/null || true)"

# Match grep/find variants in the command.
case "$CMD" in
    *grep*|*"rg "*|*ripgrep*|*"find "*|*"fd "*|*"ack "*|*"ag "*)
        # Resolve graph file relative to cwd (fallback PWD).
        GRAPH_FILE="${CWD:-$PWD}/graphify-out/graph.json"
        if [ -f "$GRAPH_FILE" ]; then
            cat <<EOF
{"context":"graphify: knowledge graph at graphify-out/. For focused questions, run \`graphify query \"<question>\"\` (scoped subgraph, usually much smaller than GRAPH_REPORT.md) instead of grepping raw files. Read GRAPH_REPORT.md only for broad architecture context."}
EOF
        fi
        ;;
esac

exit 0
