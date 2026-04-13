#!/bin/bash
# Claude Code statusline: usage bars + tokens per minute

input=$(cat)

# make_bar LABEL FILL_PCT [COLOR]
# Renders: LABEL [████░░░░░░] 42%
# COLOR is an optional ANSI escape; if provided, wraps the output
make_bar() {
  local label="$1"
  local fill_pct="$2"
  local color="${3:-}"
  local reset=$'\033[0m'
  local filled empty bar i pct_int
  filled=$(awk -v p="$fill_pct" 'BEGIN{f=int(p/10+0.5); if(f>10) f=10; print f}')
  empty=$((10 - filled))
  bar=""
  for ((i=0; i<filled; i++)); do bar="${bar}█"; done
  for ((i=0; i<empty;  i++)); do bar="${bar}░"; done
  pct_int=$(awk -v p="$fill_pct" 'BEGIN{printf "%.0f", p}')
  if [ -n "$color" ]; then
    printf '%b' "${color}${label} [${bar}] ${pct_int}%${reset}"
  else
    printf '%s [%s] %s%%' "$label" "$bar" "$pct_int"
  fi
}

warn=$'\033[33m'   # yellow

# --- (1) 5h usage limit ---
five_pct=$(jq -r '.rate_limits.five_hour.used_percentage // empty' <<<"$input")
limit_parts=""
if [ -n "$five_pct" ]; then
  five_int=$(awk -v p="$five_pct" 'BEGIN{printf "%.0f", p}')
  if [ "$five_int" -ge 80 ]; then
    limit_parts="$(make_bar "5h" "$five_int" "$warn")"
  else
    limit_parts="$(make_bar "5h" "$five_int")"
  fi
fi

# --- (2) 7d usage limit — only shown when >= 80% ---
week_pct=$(jq -r '.rate_limits.seven_day.used_percentage // empty' <<<"$input")
if [ -n "$week_pct" ]; then
  week_int=$(awk -v p="$week_pct" 'BEGIN{printf "%.0f", p}')
  if [ "$week_int" -ge 80 ]; then
    [ -n "$limit_parts" ] && limit_parts="${limit_parts}  "
    limit_parts="${limit_parts}$(make_bar "7d" "$week_int" "$warn")"
  fi
fi

# --- (3) Context window — always shown ---
ctx_pct=$(jq -r '.context_window.used_percentage // empty' <<<"$input")
ctx_part=""
if [ -n "$ctx_pct" ]; then
  ctx_int=$(awk -v p="$ctx_pct" 'BEGIN{printf "%.0f", p}')
  ctx_part="$(make_bar "ctx" "$ctx_int")"
fi

# --- (4) Tokens per minute (session total tokens / session duration) ---
tpm_part=""
in_tok=$(jq -r '.context_window.total_input_tokens // empty' <<<"$input")
out_tok=$(jq -r '.context_window.total_output_tokens // empty' <<<"$input")
dur_ms=$(jq -r '.cost.total_duration_ms // empty' <<<"$input")
ctx_size=$(jq -r '.context_window.context_window_size // empty' <<<"$input")
if [ -n "$in_tok" ] && [ -n "$out_tok" ] && [ -n "$dur_ms" ]; then
  tpm=$(awk -v i="$in_tok" -v o="$out_tok" -v d="$dur_ms" \
    'BEGIN{if(d>0) printf "%d", (i+o)*60000/d; else print "0"}')
  if [ "$tpm" -gt 0 ]; then
    # Warn if current rate will exhaust context window within 60 minutes
    tpm_color=""
    if [ -n "$ctx_size" ]; then
      minutes_left=$(awk -v s="$ctx_size" -v i="$in_tok" -v o="$out_tok" -v t="$tpm" \
        'BEGIN{r=s-i-o; if(t>0 && r>0) printf "%d", r/t; else print "9999"}')
      [ "$minutes_left" -lt 60 ] && tpm_color="$warn"
    fi
    if [ -n "$tpm_color" ]; then
      reset=$'\033[0m'
      tpm_part="${tpm_color}⚡${tpm} (⛃/min)${reset}"
    else
      tpm_part="${tpm} (⛃/min)"
    fi
  fi
fi

# --- Assemble ---
out=""
[ -n "$limit_parts" ] && out="$limit_parts"
if [ -n "$ctx_part" ]; then
  [ -n "$out" ] && out="${out}  "
  out="${out}${ctx_part}"
fi
if [ -n "$tpm_part" ]; then
  [ -n "$out" ] && out="${out}  "
  out="${out}${tpm_part}"
fi

printf '%s' "$out"
