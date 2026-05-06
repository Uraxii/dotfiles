#!/bin/bash
# Generate ~/.config/opencode/opencode.json from opencode.json.tmpl.
# Loads models.defaults, then models.local (if present) for overrides.
set -eu

CONFIG_DIR="$HOME/.config/opencode"
TMPL="$CONFIG_DIR/opencode.json.tmpl"
DEFAULTS="$CONFIG_DIR/models.defaults"
LOCAL="$CONFIG_DIR/models.local"
OUT="$CONFIG_DIR/opencode.json"

[ -f "$TMPL" ] || { echo "missing: $TMPL" >&2; exit 1; }
[ -f "$DEFAULTS" ] || { echo "missing: $DEFAULTS" >&2; exit 1; }

# shellcheck disable=SC1090
. "$DEFAULTS"
# shellcheck disable=SC1090
[ -f "$LOCAL" ] && . "$LOCAL"

VARS="MODEL_ORCHESTRATOR MODEL_PLAN MODEL_BUILD MODEL_RESEARCHER MODEL_ARCHITECT \
MODEL_SKEPTIC MODEL_REVIEWER MODEL_SECURITY_AUDITOR MODEL_TESTER \
MODEL_FRICTION_REVIEWER MODEL_MONITOR MODEL_PROGENITOR MODEL_CODE_REVIEWER"

tmp="$(mktemp)"
cp "$TMPL" "$tmp"
for v in $VARS; do
    val="$(eval "printf '%s' \"\${$v}\"")"
    # escape sed delimiters in value
    esc="$(printf '%s' "$val" | sed -e 's/[\/&|]/\\&/g')"
    sed -i "s|##${v}##|${esc}|g" "$tmp"
done

if grep -q '##MODEL_' "$tmp"; then
    echo "unsubstituted placeholders remain:" >&2
    grep -o '##MODEL_[A-Z_]*##' "$tmp" | sort -u >&2
    rm -f "$tmp"
    exit 1
fi

mv "$tmp" "$OUT"
echo "wrote $OUT"
