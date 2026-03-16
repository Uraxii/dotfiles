# Reviewer — Memory

## Lessons

### Review test code for hardcoded structural assumptions (2026-03-12)
When reviewing test files, actively check for hardcoded counts, fixed lists of field names, specific orderings, and CSS class references. These are the most common source of silently stale tests. If a test asserts `toHaveCount(6)` or iterates over a fixed `['weapon', 'head', ...]` array, flag it — these should derive from the actual game/app state.

### Renaming requires a full-project grep (2026-03-12)
When reviewing a rename (e.g., "Glamour Guesser" → "Glamdle"), check: title tags, localStorage keys, share text, console messages, test assertions, test comments, design docs, bookmarklet pages, and URL paths in test configs. Also check for localStorage migration — changing a storage key without migrating silently drops all user data.
