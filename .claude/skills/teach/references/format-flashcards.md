# Flashcard Format Reference

Flashcard = atomic, drillable content. Each card test exactly one thing. Student recall in 2-3 sec when know. Fail either criterion → not a card.

## Atomic card design

Two side:
- **term** (front): prompt
- **definition** (back): answer

Back = shortest text that fully answer prompt. Not less. Not more.

### Anti-pattern

Turn flashcard into not-flashcard:

| Anti-pattern | Example | Fix |
|---|---|---|
| Multi answer one card | term: 悪魔 / def: あくま, devil, demon, used in CSM | Split: 悪魔→あくま + あくま→devil |
| Definition = paragraph | term: 公安 / def: "Public Safety Bureau. NOT regular police — Japan's domestic intelligence agency, similar to FBI..." | Move to guide. If card needed, one-liner |
| Embedded note | term: 殺せ / def: "Kill! (from 殺す/korosu)" | Just "Kill!" — dict form in metadata or separate deck |
| Multi meaning packed | term: やばい / def: "bad/dangerous; awesome (slang, both meanings)" | "dangerous; awesome" |
| Backstory on card | term: ザクッ / def: "slicing, stabbing (sharp cut) — Chainsaw Devil's signature attack" | "sharp slice" — context in metadata |

### Good pattern

- **One concept, one card.** 悪魔 → あくま. あくま → devil.
- **Two-line back OK when serve one concept.** Contraction with standard form:
  - term: やっぱ
  - definition: as I thought; after all\n(= やっぱり)
- **One-liner cultural card OK if truly compact.** "Public Safety — Japanese FBI-like agency, not police."
- **Metadata for grouping, not card face.** Level (N5, N4), category (verb, noun), source (chapter 1) → field student filter on, not card itself.

## Multi card per concept

Concept has multi recall direction or level → multi card.

**Japanese kanji word:**
1. kanji → reading (悪魔 → あくま)
2. reading → meaning (あくま → devil)

Different cognitive task. Student might know one, not other. Drill separate = more efficient.

**Formula:**
1. name → formula (quadratic formula → x = (-b ± √(b²-4ac))/2a)
2. when apply → formula (solving ax² + bx + c = 0 → quadratic formula)
3. derivation → guide, not card

**Imperative verb (Japanese):**
1. imperative → meaning (殺せ → Kill!)
2. imperative → dict form (殺せ → 殺す) — separate deck for grammar drill

Pattern: one card per recall direction student need.

## Quizlet JSON format

Quizlet AI smart-assist accept JSON. Flat array of `{term, definition}`:

```json
[
  {"term": "悪魔", "definition": "あくま"},
  {"term": "あくま", "definition": "devil; demon"},
  {"term": "ザクッ", "definition": "sharp slice; stab"}
]
```

Richer metadata for AI assist or downstream tool — not appear on card face but allow filter/group:

```json
[
  {"term": "悪魔", "definition": "あくま", "level": "N3", "category": "vocab"},
  {"term": "ザクッ", "definition": "sharp slice; stab", "category": "onomatopoeia"}
]
```

## Anki TSV format

For Anki, tab-separated values direct with import dialog. "Field separator: Tab", map field to Front / Back:

```
悪魔	あくま
あくま	devil; demon
ザクッ	sharp slice; stab
```

Multi-field Anki note (Front, Back, Tags) → add column:

```
悪魔	あくま	N3 vocab chapter1
あくま	devil; demon	N3 vocab chapter1
```

## File organization

Multi deck pack → one JSON per deck + master:

```
quizlet_kanji_to_reading.json
quizlet_reading_to_english.json
quizlet_onomatopoeia.json
quizlet_commands.json
quizlet_speech.json
quizlet_culture.json
quizlet_all.json          ← combined
master.json               ← deck nest with metadata
```

Per-deck file → student import as separate Quizlet set (recommend). Combined = convenience. Master = AI smart-assist or downstream tool.

## Card count guidance

No hard rule, rough heuristic for single-import deck:

- **20-50 card** — comfortable session, easy onboard
- **50-150 card** — solid topical (one chapter, one grammar pattern)
- **150-400 card** — large; consider split if natural split exist
- **400+ card** — usually too big to start; split by topic, level, chapter

Bigger ≠ better. Focused 80 well-chosen card beat sprawling 400 mixed-quality.

## NOT belong in flashcard

Move to study guide:
- Conceptual explanation longer than ~20 word
- Background context, history, "why matter"
- Procedural sequence with multi step ("how to factor polynomial")
- Comparison table across many dimension
- Cultural/contextual material requiring elaboration

User ask "flashcard" but content fit guide better → say so. Propose guide, optional with short companion deck of one-liner card for actually drillable item.

## Self-critique checklist

Before deliver flashcard deck:

- [ ] Every card = one clear question + one short answer
- [ ] No card has definition longer than ~15 word (cultural one-liner can stretch bit)
- [ ] No card bundle multi concept on back
- [ ] Multi-direction concept has multi card
- [ ] Level/category metadata consistent across deck
- [ ] No content that should be guide is in card
- [ ] No card trivially easy for audience (cut)
- [ ] No card depend on context student doesn't have (move to guide first)
