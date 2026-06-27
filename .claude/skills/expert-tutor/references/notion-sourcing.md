# Notion Sourcing Reference

When the user wants material drawn from their own Notion ("quiz me on X", "pull from my notes"),
ground the questions and answer keys in their workspace instead of model memory. Read content
from Notion; never invent what their notes say.

## Find the source — auto-search, then confirm

1. **Search.** `notion-search` for the topic. Load Notion tools first via tool_search
   ("notion search", "notion fetch", "notion query data sources", "notion create pages",
   "notion update page").
2. **Confirm before building.** Search is semantic and imperfect — a wrong page yields a wrong
   quiz. State what you found and confirm: "Basing this on your V11 Cryptography notes — right
   pages?" Proceed once confirmed, or let the user point you at a specific page/DB.
3. **Fetch.** `notion-fetch` the confirmed page(s); for a structured database, query the data
   source. Use the real content as the basis for questions; put verbatim/cited text in the key.

If search returns nothing usable, say so and offer to fall back to the content ladder below.

## Structured KB vs loose notes (this decides adaptivity)

Notion supplies the *content*; mastery tracking needs *stable item ids*. Two cases:

- **Structured KB** — each page/row is an atomic item with a stable title (e.g. requirement
  notes titled `ASVS 5.3.2 ...`). Use those titles as item ids directly. Best case.
- **Loose notes** — unstructured pages. Derive a syllabus once (a tree of atomic items), confirm
  it with the user, and **freeze** it as the Mastery DB rows. Don't regenerate it casually or
  mastery history detaches from items. See `progress-tracking.md`.

## Content ladder (preference order)

The subject's registry row (`progress-tracking.md`) carries a `Source` field saying which
tier(s) apply for that subject. Per subject, prefer higher tiers for accuracy:
1. **Authoritative doc** in the user's project/uploads or Notion → extract verbatim → key.
2. **The user's own Notion notes** → quiz them on their material.
3. **Model knowledge** → fine for stable fundamentals; no invented specifics.
4. **Web search** → current/volatile/niche topics; cite; ground the key.

Anti-hallucination: prefer 1-2; web-ground tier 3 when the topic is volatile or you are unsure.
Never attribute a claim to the user's notes that isn't in them.
