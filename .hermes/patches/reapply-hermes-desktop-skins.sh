#!/usr/bin/env bash
set -euo pipefail

# Reapply Hermes Desktop: skins (synthwave-84, gruvbox, nord) + transparent bg
# Run after `hermes update` or re-extraction of the AppImage.
# Usage: ./reapply-hermes-desktop-skins.sh [version]
#   version defaults to 0.5.1

VERSION="${1:-0.5.1}"
PATCH_DIR="$(dirname "${BASH_SOURCE[0]}")"
BASE="${HOME}/.local/share/hermes-desktop-patched/${VERSION}/squashfs-root/resources/app"
MAIN_JS="${BASE}/out/main/index.js"
CSS_TARGET="$(ls "${BASE}/out/renderer/assets/index-"*.css 2>/dev/null | head -1)"
JS_TARGET="${BASE}/out/renderer/assets/index-CQogzKHB.js"

for f in "$MAIN_JS" "$CSS_TARGET" "$JS_TARGET"; do
  if [[ ! -f "$f" ]]; then
    echo "ERROR: $f not found" >&2
    exit 1
  fi
done

# ============================================================
# 0. Backup function
# ============================================================
backup() {
  local file="$1" tag="$2"
  local bak="${file}.bak.${tag}.$(date +%Y%m%d-%H%M%S)"
  cp "$file" "$bak"
  echo "Backup: $bak"
}

# ============================================================
# 1. Electron window: transparent + backgroundColor
# ============================================================
if grep -q 'transparent: true' "$MAIN_JS" 2>/dev/null; then
  echo "[SKIP] Already has transparent window"
else
  backup "$MAIN_JS" "transparent"
  sed -i 's/autoHideMenuBar: true,/autoHideMenuBar: true,\n    transparent: true,\n    backgroundColor: "#00000000",/' "$MAIN_JS"
  echo "[OK] Transparent window patched"
fi

# ============================================================
# 2. CSS: convert bg-* to rgba (transparency without blur)
# ============================================================
if grep -q 'rgba(33, 33, 33, 0.85)' "$CSS_TARGET" 2>/dev/null; then
  echo "[SKIP] Backgrounds already rgba"
else
  backup "$CSS_TARGET" "transparent-bg"

  # Dark theme
  sed -i 's/--bg-primary: #212121;/--bg-primary: rgba(33, 33, 33, 0.85);/' "$CSS_TARGET"
  sed -i 's/--bg-secondary: #171717;/--bg-secondary: rgba(23, 23, 23, 0.80);/' "$CSS_TARGET"
  sed -i 's/--bg-tertiary: #2f2f2f;/--bg-tertiary: rgba(47, 47, 47, 0.75);/' "$CSS_TARGET"
  sed -i 's/--bg-elevated: #303030;/--bg-elevated: rgba(48, 48, 48, 0.70);/' "$CSS_TARGET"
  sed -i 's/--bg-hover: #3a3a3a;/--bg-hover: rgba(58, 58, 58, 0.70);/' "$CSS_TARGET"
  sed -i 's/--bg-active: #424242;/--bg-active: rgba(66, 66, 66, 0.70);/' "$CSS_TARGET"
  sed -i 's/--agent-bubble: #2f2f2f;/--agent-bubble: rgba(47, 47, 47, 0.85);/' "$CSS_TARGET"
  sed -i 's/--code-bg: #1a1a1a;/--code-bg: rgba(26, 26, 26, 0.90);/' "$CSS_TARGET"
  sed -i 's/--scrollbar-thumb: #424242;/--scrollbar-thumb: rgba(66, 66, 66, 0.70);/' "$CSS_TARGET"
  sed -i 's/--scrollbar-hover: #555555;/--scrollbar-hover: rgba(85, 85, 85, 0.70);/' "$CSS_TARGET"

  # Light theme
  sed -i 's/--bg-primary: #ffffff;/--bg-primary: rgba(255, 255, 255, 0.85);/' "$CSS_TARGET"
  sed -i 's/--bg-secondary: #f8f8f8;/--bg-secondary: rgba(248, 248, 248, 0.80);/' "$CSS_TARGET"
  sed -i 's/--bg-tertiary: #f0f0f0;/--bg-tertiary: rgba(240, 240, 240, 0.75);/' "$CSS_TARGET"
  sed -i 's/--bg-elevated: #e8e8e8;/--bg-elevated: rgba(232, 232, 232, 0.70);/' "$CSS_TARGET"
  sed -i 's/--bg-hover: #ebebeb;/--bg-hover: rgba(235, 235, 235, 0.70);/' "$CSS_TARGET"
  sed -i 's/--bg-active: #e0e0e0;/--bg-active: rgba(224, 224, 224, 0.70);/' "$CSS_TARGET"
  sed -i 's/--agent-bubble: #f0f0f0;/--agent-bubble: rgba(240, 240, 240, 0.85);/' "$CSS_TARGET"
  sed -i 's/--code-bg: #f5f5f5;/--code-bg: rgba(245, 245, 245, 0.90);/' "$CSS_TARGET"
  sed -i 's/--scrollbar-thumb: #d4d4d4;/--scrollbar-thumb: rgba(212, 212, 212, 0.70);/' "$CSS_TARGET"
  sed -i 's/--scrollbar-hover: #bbbbbb;/--scrollbar-hover: rgba(187, 187, 187, 0.70);/' "$CSS_TARGET"

  echo "[OK] Backgrounds converted to rgba"
fi

# ============================================================
# 3. Skins: CSS variable blocks
# ============================================================
if grep -q 'Synthwave' "$CSS_TARGET" 2>/dev/null; then
  echo "[SKIP] Skins CSS already applied"
else
  linenum=$(grep -n '\/\* ----- Google Sans ----- \*\/' "$CSS_TARGET" | head -1 | cut -d: -f1)
  if [[ -z "$linenum" ]]; then
    echo "ERROR: Could not find insertion point in CSS" >&2
    exit 1
  fi
  head -n $((linenum - 1)) "$CSS_TARGET" > "${CSS_TARGET}.tmp"
  cat "${PATCH_DIR}/hermes-desktop-0.5.1-skins.patch.css" >> "${CSS_TARGET}.tmp"
  tail -n +"$linenum" "$CSS_TARGET" >> "${CSS_TARGET}.tmp"
  mv "${CSS_TARGET}.tmp" "$CSS_TARGET"
  echo "[OK] Skins CSS added"
fi

# ============================================================
# 4. JS: THEME_OPTIONS + ThemeProvider + labels
# ============================================================
if grep -q 'synthwave-84' "$JS_TARGET" 2>/dev/null; then
  echo "[SKIP] Skins JS already applied"
else
  backup "$JS_TARGET" "skins"

  sed -i 's/{ value: "dark", label: "constants.themeDark" }$/{ value: "dark", label: "constants.themeDark" },\n  { value: "synthwave-84", label: "Synthwave'"'"'84" },\n  { value: "gruvbox", label: "Gruvbox" },\n  { value: "nord", label: "Nord" }/' "$JS_TARGET"

  sed -i 's/stored === "light" || stored === "dark" || stored === "system"/stored === "light" || stored === "dark" || stored === "system" || stored === "synthwave-84" || stored === "gruvbox" || stored === "nord"/' "$JS_TARGET"

  sed -i 's/opt\.value === "system" ? t2("settings\.theme\.system") : opt\.value === "light" ? t2("settings\.theme\.light") : t2("settings\.theme\.dark")/opt.value === "system" ? t2("settings.theme.system") : opt.value === "light" ? t2("settings.theme.light") : opt.value === "dark" ? t2("settings.theme.dark") : opt.label/' "$JS_TARGET"

  echo "[OK] Skins JS patched"
fi

echo ""
echo "=== All patches applied ==="
echo "Transparent window + skins: System / Light / Dark / Synthwave '84 / Gruvbox / Nord"
echo "Settings → Appearance → Theme"