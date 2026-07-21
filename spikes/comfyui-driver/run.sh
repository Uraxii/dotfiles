#!/usr/bin/env bash
# Spike: drive ComfyUI headless via HTTP API. submit -> poll -> fetch image.
# Usage: ./run.sh "a prompt" [seed] [out.png]
set -euo pipefail

HOST="${COMFY_HOST:-http://127.0.0.1:8188}"
PROMPT="${1:-a red fox sitting in snow, photograph, golden hour}"
SEED="${2:-$RANDOM}"
OUT="${3:-$(dirname "$0")/out.png}"
TEMPLATE="$(dirname "$0")/workflow.json"

# 1. Inject prompt + seed into template (python handles JSON escaping).
BODY=$(python3 - "$TEMPLATE" "$PROMPT" "$SEED" <<'EOF'
import json, sys
g = json.load(open(sys.argv[1]))
g["6"]["inputs"]["text"] = sys.argv[2]
g["3"]["inputs"]["seed"] = int(sys.argv[3])
print(json.dumps({"prompt": g}))
EOF
)

# 2. Queue it.
PID=$(curl -sf -X POST "$HOST/prompt" -H 'Content-Type: application/json' \
      -d "$BODY" | python3 -c 'import json,sys; print(json.load(sys.stdin)["prompt_id"])')
echo "queued prompt_id=$PID seed=$SEED"

# 3. Poll history until outputs appear. ponytail: dumb 2s poll, no websocket.
for _ in $(seq 1 150); do
  IMG=$(curl -sf "$HOST/history/$PID" | python3 -c '
import json, sys
h = json.load(sys.stdin)
for entry in h.values():
    for out in entry.get("outputs", {}).values():
        for img in out.get("images", []):
            print("|".join([img["filename"], img["subfolder"], img["type"]])); sys.exit()
    # ponytail: identical graph = full cache hit = empty outputs. caller must vary seed.
    if entry.get("status", {}).get("completed"):
        print("CACHED"); sys.exit()
' || true)
  [ "$IMG" = "CACHED" ] && { echo "graph fully cached, no outputs; change seed or prompt" >&2; exit 1; }
  [ -n "$IMG" ] && break
  sleep 2
done
[ -n "${IMG:-}" ] || { echo "timed out waiting for $PID" >&2; exit 1; }

# 4. Fetch the image.
IFS='|' read -r FN SUB TYPE <<< "$IMG"
curl -sf -G "$HOST/view" --data-urlencode "filename=$FN" \
     --data-urlencode "subfolder=$SUB" --data-urlencode "type=$TYPE" -o "$OUT"
echo "saved $OUT ($FN)"
