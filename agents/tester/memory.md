# Tester — Memory

## Lessons

### Never hardcode structural assumptions in tests (2026-03-12)
Tests that hardcode slot counts (`toHaveCount(6)`), fixed slot names (`['weapon', 'head', ...]`), specific slot orderings (`toHaveText('Weapon')`), or CSS class names that may not exist (`.glamour-meta`) go silently stale when the game structure changes. Derive from game state instead: read the actual slot count from progress dots, use the state's `slots` array, iterate dynamically. A test that passes on stale assumptions is worse than no test.

### Script extraction regex breaks when new script tags are added (2026-03-12)
`html.match(/<script>([\s\S]*)<\/script>/)` with greedy `*` will span across multiple `<script>` tags, capturing closing/opening tag boundaries as JavaScript. When an external `<script src="..."></script>` was added, this broke the test.js file silently. Use `matchAll` with a guard like `[^<]` to skip empty script tags and take the last match.

### DOM shims must cover dev tools initialization (2026-03-12)
Unit tests using `vm.createContext` need DOM stubs for `document.createElement`, `document.body.appendChild`, and `addEventListener` — not just `getElementById` and `querySelectorAll`. The dev tools IIFE runs at load time and calls these methods.
