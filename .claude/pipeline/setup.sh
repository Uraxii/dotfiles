#!/usr/bin/env bash
# pipeline/setup.sh — portability bootstrap for the pipeline Slack toolchain.
#
# Run on a fresh machine after `stow -t ~ .`:
#
#   bash ~/.claude/pipeline/setup.sh
#
# Verifies every external dependency the router + pipeline_ask CLI rely on,
# walks through Slack token + manifest setup, and probes the bot's live
# OAuth scopes + channel membership. Does NOT install system packages
# (distro-dependent — script just tells you what's missing and how to get it).
#
# Exit codes: 0 = ready, 1 = needs action (see printed checklist).

set -euo pipefail

# ─── colors / helpers ────────────────────────────────────────────────────────
if [[ -t 1 ]]; then
  RED=$'\033[31m'; GRN=$'\033[32m'; YLW=$'\033[33m'; BLU=$'\033[34m'; DIM=$'\033[2m'; RST=$'\033[0m'
else
  RED=""; GRN=""; YLW=""; BLU=""; DIM=""; RST=""
fi

FAIL=0
ok()    { printf "  %s✓%s %s\n"  "$GRN" "$RST" "$1"; }
warn()  { printf "  %s!%s %s\n"  "$YLW" "$RST" "$1"; }
fail()  { printf "  %s✗%s %s\n"  "$RED" "$RST" "$1"; FAIL=1; }
note()  { printf "    %s%s%s\n"  "$DIM" "$1" "$RST"; }
header(){ printf "\n%s== %s ==%s\n" "$BLU" "$1" "$RST"; }

# ─── 1. CLI dependencies ─────────────────────────────────────────────────────
header "External commands"

check_cmd() {
  local cmd="$1" min_msg="$2"
  if command -v "$cmd" >/dev/null 2>&1; then
    ok "$cmd ($(command -v "$cmd"))"
  else
    fail "$cmd missing"
    note "$min_msg"
  fi
}

check_cmd python3 "Install Python 3.11+ (system package or pyenv). NixOS: in home.nix."
check_cmd uv      "Install: curl -LsSf https://astral.sh/uv/install.sh | sh   (NixOS: home.nix has uv)"
check_cmd stow    "Install via your distro package manager (e.g. pacman -S stow). NixOS: home.nix."
check_cmd jq      "Install via your distro package manager. NixOS: home.nix."
check_cmd curl    "Install via your distro package manager."
check_cmd git     "Install via your distro package manager."

if command -v python3 >/dev/null 2>&1; then
  py_ver=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
  py_major=$(printf '%s' "$py_ver" | cut -d. -f1)
  py_minor=$(printf '%s' "$py_ver" | cut -d. -f2)
  if [[ "$py_major" -ge 3 && "$py_minor" -ge 11 ]]; then
    ok "python $py_ver >= 3.11"
  else
    fail "python $py_ver too old (need >= 3.11)"
  fi
fi

# ─── 2. Repo install via stow ────────────────────────────────────────────────
header "Symlinks (stow)"

for path in \
  ~/.claude/pipeline/pipeline_ask.py \
  ~/.claude/pipeline/comms/router.py \
  ~/.claude/pipeline/session_bind.py \
  ~/.claude/hooks/cap_bash_timeout.py \
  ~/.claude/settings.json
do
  if [[ -L "$path" || -f "$path" ]]; then
    ok "$path"
  else
    fail "$path missing"
    note "Run: cd ~/dotfiles && stow -R -t ~ ."
  fi
done

# Confirm old listener is gone.
if [[ -f ~/.claude/pipeline/slack_listener.py ]]; then
  fail "slack_listener.py still present — remove manually or re-stow"
else
  ok "slack_listener.py absent (expected)"
fi

# ─── 3. Slack env file ───────────────────────────────────────────────────────
header "Slack tokens"

ENV_FILE="${SLACK_ENV_FILE:-$HOME/.claude/pipeline/slack.env.local}"
EXAMPLE_FILE="$HOME/.claude/pipeline/slack.env.example"

if [[ -f "$ENV_FILE" ]]; then
  perms=$(stat -c '%a' "$ENV_FILE" 2>/dev/null || stat -f '%A' "$ENV_FILE" 2>/dev/null)
  if [[ "$perms" == "600" ]]; then
    ok "$ENV_FILE (mode 600)"
  else
    warn "$ENV_FILE exists but mode is $perms; tighten with: chmod 600 $ENV_FILE"
  fi
elif [[ -f "$EXAMPLE_FILE" ]]; then
  fail "$ENV_FILE missing"
  note "Copy template + fill in tokens:"
  note "  cp $EXAMPLE_FILE $ENV_FILE && chmod 600 $ENV_FILE"
  note "  See $EXAMPLE_FILE header for token-creation walkthrough."
else
  fail "$ENV_FILE and template both missing — repo not stowed?"
fi

# ─── 4. Live Slack scope probe ───────────────────────────────────────────────
if [[ -f "$ENV_FILE" ]]; then
  header "Slack live probe"
  # shellcheck disable=SC1090
  set -o allexport; source "$ENV_FILE"; set +o allexport

  if [[ -z "${SLACK_BOT_TOKEN:-}" || "$SLACK_BOT_TOKEN" == "xoxb-replace-me" ]]; then
    fail "SLACK_BOT_TOKEN unset / placeholder"
  else
    headers=$(mktemp); body=$(mktemp)
    if curl -sS -H "Authorization: Bearer $SLACK_BOT_TOKEN" \
         "https://slack.com/api/auth.test" -D "$headers" -o "$body"; then
      if jq -e '.ok' "$body" >/dev/null 2>&1; then
        team=$(jq -r '.team'    "$body")
        bot=$(jq  -r '.user'    "$body")
        ok "auth ok: team=$team bot=$bot"
        scopes=$(grep -i '^x-oauth-scopes:' "$headers" | sed 's/^[^:]*: *//' | tr -d '\r')
        for need in chat:write chat:write.public files:read files:write; do
          if [[ ",$scopes," == *",$need,"* ]]; then
            ok "scope: $need"
          else
            fail "scope missing: $need"
            note "Add in OAuth & Permissions; click 'Reinstall to Workspace'."
          fi
        done
      else
        fail "auth.test failed: $(jq -r '.error // "unknown"' "$body")"
      fi
    else
      fail "curl to Slack failed (network or DNS)"
    fi
    rm -f "$headers" "$body"
  fi

  if [[ -z "${SLACK_APP_TOKEN:-}" || "$SLACK_APP_TOKEN" == "xapp-replace-me" ]]; then
    fail "SLACK_APP_TOKEN unset / placeholder"
  else
    ok "SLACK_APP_TOKEN set"
  fi

  if [[ -z "${SLACK_CHANNEL:-}" ]]; then
    warn "SLACK_CHANNEL unset (can be overridden per project in pipeline.toml)"
  else
    ok "SLACK_CHANNEL=$SLACK_CHANNEL"
    note "Bot must be invited: /invite @<bot-name> in that channel."
  fi
fi

# ─── 5. Router state dir ─────────────────────────────────────────────────────
header "Router state"

ROUTER_DIR="$HOME/.claude/comms-router"
if [[ -d "$ROUTER_DIR" ]]; then
  r_perms=$(stat -c '%a' "$ROUTER_DIR" 2>/dev/null || stat -f '%A' "$ROUTER_DIR" 2>/dev/null)
  if [[ "$r_perms" == "700" ]]; then
    ok "$ROUTER_DIR (mode 700)"
  else
    warn "$ROUTER_DIR exists but mode is $r_perms; tighten: chmod 700 $ROUTER_DIR"
  fi
  if [[ -f "$ROUTER_DIR/router.pid" ]]; then
    r_pid=$(cat "$ROUTER_DIR/router.pid" 2>/dev/null || echo "")
    if [[ -n "$r_pid" ]] && kill -0 "$r_pid" 2>/dev/null; then
      ok "router alive: pid=$r_pid"
    else
      note "router.pid present but process not alive (OK if not yet started)"
    fi
  else
    note "router not running (started on first slack-bind activate)"
  fi
else
  note "$ROUTER_DIR absent — created lazily by router on first activate"
fi

# ─── 6. Migration: reap orphan listeners ─────────────────────────────────────
header "Migration (orphan listener reap)"

orphan_count=$(pgrep -fc "slack_listener.py" 2>/dev/null || echo "0")
if [[ "$orphan_count" -gt 0 ]]; then
  warn "$orphan_count orphan slack_listener.py process(es) found"
  note "Reaping: pgrep -f slack_listener.py | xargs -r kill -TERM"
  pgrep -f "slack_listener.py" | xargs -r kill -TERM 2>/dev/null || true
  sleep 2
  remaining=$(pgrep -fc "slack_listener.py" 2>/dev/null || echo "0")
  if [[ "$remaining" -gt 0 ]]; then
    warn "$remaining still alive; sending SIGKILL"
    pgrep -f "slack_listener.py" | xargs -r kill -KILL 2>/dev/null || true
  else
    ok "all orphan listeners reaped"
  fi
else
  ok "no orphan slack_listener.py processes"
fi

# ─── 7. Optional: HTML→PDF converter probe ───────────────────────────────────
header "HTML→PDF (optional; only for pipeline_ask.py --attach foo.html)"

if command -v uvx >/dev/null 2>&1; then
  ok "uvx ($(command -v uvx)) — weasyprint will be fetched on first --attach .html"
  note "Linux system libs may be required by weasyprint: pango cairo gdk-pixbuf."
  note "  Arch:    sudo pacman -S pango"
  note "  NixOS:   home.nix lists pango + cairo + gdk-pixbuf + libffi"
else
  warn "uvx missing — HTML auto-PDF disabled. Install: ships with uv."
fi

# ─── 8. Claude Code env (timeout cap) ────────────────────────────────────────
header "Claude Code settings"

if [[ -f ~/.claude/settings.json ]]; then
  max=$(jq -r '.env.BASH_MAX_TIMEOUT_MS // empty' ~/.claude/settings.json)
  if [[ -n "$max" && "$max" -ge 3600000 ]]; then
    ok "BASH_MAX_TIMEOUT_MS=$max ms"
  else
    warn "BASH_MAX_TIMEOUT_MS missing or low; long blocking pipeline_ask may be capped at default 10min."
  fi
  if jq -e '.hooks.PreToolUse[]? | select(.matcher == "Bash")' ~/.claude/settings.json >/dev/null 2>&1; then
    ok "PreToolUse Bash hook wired"
  else
    warn "PreToolUse Bash hook missing — no per-command timeout gate."
  fi
fi

# ─── Verdict ─────────────────────────────────────────────────────────────────
printf "\n"
if [[ "$FAIL" -eq 0 ]]; then
  printf "%sAll checks passed.%s Smoke test:\n" "$GRN" "$RST"
  printf "  uv run --script ~/.claude/pipeline/session_bind.py activate\n"
  printf "  mkdir -p ~/dotfiles/.pipeline/runs/smoke-aaaaaa\n"
  printf "  python3 ~/.claude/pipeline/pipeline_ask.py \\\\\n"
  printf "    --run smoke-aaaaaa --project ~/dotfiles \\\\\n"
  printf "    --header Smoke --prompt 'Hello?' \\\\\n"
  printf "    --opt A:yes --opt B:no --hard-timeout 60\n"
  exit 0
else
  printf "%sFailed checks above. Address them, re-run this script.%s\n" "$RED" "$RST"
  exit 1
fi
