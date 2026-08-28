#!/usr/bin/env bash
# Headless repro: open a markdown file with fenced code blocks under
# treesitter highlighting. Fails if Neovim prints any Error on stderr
# (notably "attempt to call method 'range'" from nvim-treesitter master).
# Usage: ts-md-repro.sh [file.md]
set -u

md="${1:-}"
if [ -z "$md" ]; then
  md="$(mktemp --suffix=.md)"
  trap 'rm -f "$md"' EXIT
  cat > "$md" <<'MD'
---
title: repro
---

# Heading

| a | b |
|---|---|
| 1 | 2 |

```lua
local x = 1
print(x)
```

```math
x^2 + y^2 = z^2
```
MD
fi

err="$(nvim --headless "$md" \
  +'lua vim.treesitter.start()' \
  +'lua vim.api.nvim__redraw({flush=true})' \
  +q 2>&1 >/dev/null)"

if printf '%s' "$err" | grep -qE "attempt to call method 'range'|Decoration provider|E5108"; then
  printf '%s\n' "$err"
  echo "FAIL: treesitter error on $md"
  exit 1
fi
echo "OK: no treesitter error on $md"
