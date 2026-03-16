# Researcher — Memory

## Lessons

### Always verify exact Unicode characters in API string matching (2026-03-12)
When an API query silently returns 0 results, check for Unicode lookalikes. XIVAPI category names used en-dashes (U+2013 `–`) where regular hyphens (U+002D `-`) were expected. The query didn't error — it just matched nothing. Visual inspection of the response data (not just the query) is the only way to catch this. Use `charCodeAt()` or hex dumps when debugging string mismatches.

### Check partial matches to diagnose missing data (2026-03-12)
When items are missing from a fetched dataset, search for partial name matches (e.g., search "Edenchoir" to find "Edenchoir Bastard Sword" exists but "Edenchoir Cane" doesn't). This quickly reveals which categories failed to fetch vs which items genuinely don't exist.
