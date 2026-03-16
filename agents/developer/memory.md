# Developer — Memory

## Decisions & Notes

### 2026-03-12 — Practice projects implementation
Implemented all 4 games following the state/update/render pattern from conventions. Key observations:
- The pattern scaled well from RPS (trivial) through Chess (complex)
- Chess's clone-and-check move legality is correct but creates many board clones — acceptable for browser 2P
- Single-file HTML/JS works fine for these sizes but Chess is pushing the limit (~300 lines of JS)
- Consistent dark theme UI across all games with shared color palette

### 2026-03-12 — Tic Tac Toe rewrite and Chess visual fix
- **TTT rewrite:** Replaced dynamic DOM rebuild (innerHTML + createElement loop) with static HTML cells and inline onclick handlers. Simpler, more debuggable, eliminates event re-binding on each render. Used simple global variables instead of a state object to avoid shadowing issues.
- **Chess visual fix:** Unicode chess symbols (outline ♔ vs filled ♚) render identically on many systems. Fix: use filled symbols for both sides, differentiate with CSS `color` + `text-shadow`. White = `#fff` with dark shadow, black = `#222` with light shadow.
- **Lesson:** Always verify HTML files can be opened in a browser before considering implementation done. Code that looks correct in source can fail at runtime due to encoding, browser quirks, or rendering issues.
