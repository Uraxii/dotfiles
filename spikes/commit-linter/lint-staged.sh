#!/usr/bin/env bash
# Pre-commit content linter for a PUBLIC dotfiles repo.
#
# Purpose: no machine- or user-identifying expanded values, and no secrets,
# ever land in a commit.
#
# Scope: scans the STAGED content of each staged file (the git index blob),
# i.e. exactly what would be committed. Never touches unstaged/untracked
# files.
#
# Replacement standard per file context (see README.md for the evidence
# behind each choice):
#   *.sh / files with a shebang -> $HOME   (expands correctly in shell use)
#   *.md                        -> ~       (repo already standardized on ~
#                                            with an explicit expansion note)
#   *.json / everything else    -> $HOME   (safe default; a real env var,
#                                            not shell-dependent ~ expansion)
#
# Bare username ("nicole") is only rewritten in path-like contexts
# (bounded by / or @), never in prose, never inside an email domain.
#
# Values with no portable replacement (email, tailnet id, hostname) are
# BLOCKED, not rewritten: rewriting them would break the thing that uses
# them (e.g. a tailnet permission rule stops matching). Move those to an
# untracked local file instead (e.g. .claude/settings.local.json).
#
# Secret-shaped strings are always a hard block, never auto-fixed.

set -euo pipefail

USER_FORM='$USER'
FAIL=0

# ---- gather staged files (NUL-safe, excludes deletions) ----
mapfile -d '' -t STAGED_FILES < <(
  git diff --cached -z --name-only --diff-filter=ACMR
)

if [ "${#STAGED_FILES[@]}" -eq 0 ]; then
  exit 0
fi

mapfile -d '' -t UNSTAGED_FILES < <(git diff -z --name-only)

is_partial() {
  local f="$1" u
  for u in "${UNSTAGED_FILES[@]:-}"; do
    [ "$u" = "$f" ] && return 0
  done
  return 1
}

is_binary() {
  local f="$1"
  git diff --cached --numstat -- "$f" | awk '{print $1}' | grep -q '^-$'
}

# *.md gets ~ (repo's documented prose convention); everything else
# (*.sh, shebang scripts, *.json, unknown) gets $HOME, since $HOME is a
# real env var and works the same in every one of those contexts.
home_form_for() {
  case "$1" in
    *.md) printf '%s' '~' ;;
    *)    printf '%s' '$HOME' ;;
  esac
}

# ---- pass 1: partial staging guard ----
for f in "${STAGED_FILES[@]}"; do
  if is_partial "$f"; then
    echo "BLOCKED: $f is partially staged (working tree differs from" \
         "the index). Stage the whole file or none of it, then retry." >&2
    FAIL=1
  fi
done
[ "$FAIL" -eq 0 ] || exit 1

# ---- pass 2: secrets (hard block, never auto-fixed) ----
# The linter's own script and README document the secret prefixes and
# _KEY/_TOKEN/_SECRET pattern by name/example, so they legitimately
# contain the regex's trigger text without containing a real secret.
# They are exempt from THIS regex pass only; TruffleHog (pass 5) still
# scans them, so a real secret pasted into either file still blocks.
SELF_FILES=(
  "spikes/commit-linter/lint-staged.sh"
  "spikes/commit-linter/README.md"
)
is_self_file() {
  local f="$1" s
  for s in "${SELF_FILES[@]}"; do
    [ "$s" = "$f" ] && return 0
  done
  return 1
}

SECRET_RE='sk-ant-|sk-proj-|ghp_|github_pat_|gho_|xoxb-|xoxp-'
SECRET_RE="${SECRET_RE}|AKIA[0-9A-Z]{16}"
SECRET_RE="${SECRET_RE}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"
SECRETVAR_RE='[A-Za-z_]*(_KEY|_TOKEN|_SECRET)[[:space:]]*[:=]'
SECRETVAR_RE="${SECRETVAR_RE}[[:space:]]*[\"']?[A-Za-z0-9+/_=-]{20,}"

for f in "${STAGED_FILES[@]}"; do
  is_binary "$f" && continue
  is_self_file "$f" && continue
  hits="$(git show ":$f" | grep -nE "$SECRET_RE" || true)"
  more="$(git show ":$f" | grep -nE "$SECRETVAR_RE" || true)"
  if [ -n "$more" ]; then
    if [ -n "$hits" ]; then hits="$hits"$'\n'"$more"; else hits="$more"; fi
  fi
  if [ -n "$hits" ]; then
    hits="$(printf '%s\n' "$hits" | sort -t: -k1,1n -u)"
    echo "BLOCKED: secret-shaped content in $f:" >&2
    printf '%s\n' "$hits" | while IFS= read -r line; do
      echo "  $f:$line" >&2
    done
    FAIL=1
  fi
done
[ "$FAIL" -eq 0 ] || exit 1

# ---- pass 3: identity values with no portable form (hard block) ----
# Same self-exemption as pass 2, same reason: these two files name the
# email/tailnet id as documented examples, not as leaked identity data.
EMAIL='accounts@nicolepaul.net'
TAILNET='taild402ad'
HOST="$(hostname)"

for f in "${STAGED_FILES[@]}"; do
  is_binary "$f" && continue
  is_self_file "$f" && continue
  content="$(git show ":$f")"
  for needle in "$EMAIL" "$TAILNET" "$HOST"; do
    hits="$(printf '%s\n' "$content" | grep -nF -- "$needle" || true)"
    if [ -n "$hits" ]; then
      echo "BLOCKED: identifying value \"$needle\" in $f (no portable" \
           "replacement exists). Move this to an untracked local file" \
           "(e.g. .claude/settings.local.json) instead:" >&2
      printf '%s\n' "$hits" | while IFS= read -r line; do
        echo "  $f:$line" >&2
      done
      FAIL=1
    fi
  done
done
[ "$FAIL" -eq 0 ] || exit 1

# ---- pass 4: auto-fix expanded $HOME / bare username, re-stage ----
# Same self-exemption: these two files reference /var/home/nicole,
# /home/nicole and bare "nicole" as pattern text describing what the
# tool matches (including inside the sed patterns below). Auto-fixing
# them here would silently corrupt the linter's own detection regex.
for f in "${STAGED_FILES[@]}"; do
  is_binary "$f" && continue
  is_self_file "$f" && continue
  home_form="$(home_form_for "$f")"
  orig="$(git show ":$f")"
  fixed="$(printf '%s\n' "$orig" \
    | sed -E "s#/var/home/nicole#${home_form}#g; s#/home/nicole#${home_form}#g" \
    | sed -E "s#(^|/)nicole(/|\$)#\1${USER_FORM}\2#g" \
    | sed -E "s#nicole@#${USER_FORM}@#g")"
  if [ "$fixed" != "$orig" ]; then
    diff_out="$(diff <(printf '%s\n' "$orig") <(printf '%s\n' "$fixed") || true)"
    echo "FIXED: $f"
    printf '%s\n' "$diff_out"
    printf '%s\n' "$fixed" > "$f"
    git add -- "$f"
  fi
done

# ---- pass 5: trufflehog secret scan (staged content only, hard block) ----
# Fail-closed: a missing trufflehog binary blocks the commit, it never
# silently skips the scan.
TRUFFLEHOG_INSTALL_HINT="install: see spikes/commit-linter/README.md"
if ! command -v trufflehog >/dev/null 2>&1; then
  echo "BLOCKED: trufflehog not found on PATH ($TRUFFLEHOG_INSTALL_HINT)." >&2
  exit 1
fi

# Re-read the staged list: pass 4 may have re-staged fixed files, but the
# set of files being committed is unchanged.
mapfile -d '' -t STAGED_FILES < <(
  git diff --cached -z --name-only --diff-filter=ACMR
)

# Materialize staged blobs into a scratch dir so trufflehog scans exactly
# what would be committed (the index), not the working tree and not repo
# history. This is what makes the scan staged-content-only.
SCRATCH="$(mktemp -d)"
trap 'rm -rf "$SCRATCH"' EXIT

for f in "${STAGED_FILES[@]}"; do
  is_binary "$f" && continue
  mkdir -p "$SCRATCH/$(dirname -- "$f")"
  git show ":$f" > "$SCRATCH/$f"
done

th_out="$(trufflehog filesystem "$SCRATCH" --no-update \
  --results=verified,unverified,unknown --json 2>/dev/null || true)"
findings="$(printf '%s\n' "$th_out" | grep '"SourceMetadata"' || true)"

if [ -n "$findings" ]; then
  echo "BLOCKED: trufflehog found secret(s) in staged content:" >&2
  printf '%s\n' "$findings" | while IFS= read -r j; do
    det="$(printf '%s' "$j" | grep -o '"DetectorName":"[^"]*"' \
      | head -1 | cut -d'"' -f4)"
    file="$(printf '%s' "$j" | grep -o '"file":"[^"]*"' \
      | head -1 | cut -d'"' -f4)"
    line="$(printf '%s' "$j" | grep -o '"line":[0-9]*' \
      | head -1 | cut -d: -f2)"
    echo "  detector=$det file=${file#"$SCRATCH"/} line=$line" >&2
  done
  exit 1
fi

# ---- pass 6: StepSecurity Dev Machine Guard (supply-chain scan) ----
# Optional: machines without DMG installed skip silently, never blocked.
DMG_SCAN="$HOME/.local/share/stepsecurity-dmg/dmg-scan.sh"
if [ -x "$DMG_SCAN" ]; then
  "$DMG_SCAN"
fi

exit 0
