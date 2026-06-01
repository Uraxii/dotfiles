#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:-0.5.1}"
APP_JS="${HERMES_DESKTOP_APP_JS:-$HOME/.local/share/hermes-desktop-patched/${VERSION}/squashfs-root/resources/app/out/main/index.js}"
PATCH_FILE="$(dirname "${BASH_SOURCE[0]}")/hermes-desktop-0.5.1-ssh-tunnel-sessions.patch"

if [[ ! -f "$APP_JS" ]]; then
  echo "Hermes Desktop main bundle not found: $APP_JS" >&2
  exit 1
fi
if [[ ! -f "$PATCH_FILE" ]]; then
  echo "Patch file not found: $PATCH_FILE" >&2
  exit 1
fi

backup="${APP_JS}.bak.ssh-tunnel-sessions.$(date +%Y%m%d-%H%M%S)"
cp "$APP_JS" "$backup"

if patch --dry-run "$APP_JS" < "$PATCH_FILE" >/tmp/hermes-desktop-patch-check.log 2>&1; then
  patch "$APP_JS" < "$PATCH_FILE"
  echo "Patched $APP_JS"
  echo "Backup: $backup"
else
  if grep -q 'HERMES_DESKTOP_STDIN_B64' "$APP_JS" && grep -q 'conn.ssh.localPort' "$APP_JS"; then
    echo "Patch already appears applied: $APP_JS"
    rm -f "$backup"
  else
    echo "Patch did not apply cleanly. Backup left at: $backup" >&2
    cat /tmp/hermes-desktop-patch-check.log >&2
    exit 1
  fi
fi
