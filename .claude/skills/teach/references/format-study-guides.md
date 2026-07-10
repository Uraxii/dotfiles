# Study Guide Format Reference

Study guide hold lesson-shape content — concept, theory, context, "why matter". Anything need more than sentence or two of explain → guide, not flashcard.

## When to use

- Concept explanation needing context to make sense
- Cultural/contextual literacy (honorific, convention, historiographical note)
- Comparison across multi dimension (compare-contrast table)
- Procedural sequence (how-to walkthrough)
- Reference student look up, not memorize
- "Why matter" framing that motivate downstream drill

## File format

Markdown (`.md`). Render well in Quizlet note feature, GitHub, Notion, Obsidian, plain text editor, printer. No HTML/PDF/proprietary unless user request.

## Structure

Guide should have:

1. **Title** — clear, descriptive, include scope
2. **Intro** — what cover, who for, how use (1-3 sentence)
3. **Section** — one per concept/topic, ordered logical
4. **Cross-reference** — link between section + to related flashcard deck if relevant
5. **"How to use" closing** — when applicable

## Section design

Each section:

- Clear heading
- One-sentence hook telling student why matter
- Prose for explain, not bullet/table (bullet for enumerable list only)
- Concrete example
- "So what" — how this change student understanding/behavior

### Good section example

```markdown
## Yakuza (ヤクザ) and debt

Japanese organized crime. Loan-sharking is a classic yakuza activity — Denji's father borrowed money before dying, leaving Denji with the debt. Yakuza debts are quasi-legal but enforced through fear and violence. This is why Denji can't just declare bankruptcy: refusing to pay can mean death. Selling his organs in chapter 1 is not metaphor — it's a real (illegal) thing desperate people do.
```

Why work:
- Hook ("Japanese organized crime") establish topic immediate
- Concrete example (Denji's debt) anchor abstract concept
- "So what" (selling organ real, not metaphor) connect back to manga

### Bad section example

```markdown
## Yakuza

The yakuza is a thing in Japan. Some characters in Chainsaw Man are involved with them. They lend money. It's bad to owe them money.
```

Why fail:
- No real explain, just fact
- No concrete example with detail
- No "so what" — student can't apply
- Tone flat + forgettable

## Length guidance

- **Short** (1-3 section, ~500 word): single focused topic
- **Medium** (4-10 section, 1500-3000 word): multi-faceted topic
- **Long** (10+ section, 3000+ word): full unit/subject overview. Consider split into multi guide linked.

Longer than ~3000 word → ask if student need this much at once or should split.

## List vs prose

Default prose. Use list when:

- Content genuinely enumerable (honorific: 〜さん, 〜ちゃん, 〜くん with brief explain)
- Student scan to find one item, not read sequential
- Relation between item parallel (each sibling, none more important)

Don't use list for:
- Sequential reasoning ("first this, then that, therefore...")
- Single concept with one main point
- Anywhere sentence would do

Guide all bullet = list with section heading. Student lose connective tissue that make explain cohere.

## Tables

Use for genuine comparison along multi dimension. Don't use to dress up info that should be prose.

### Good use

| Pronoun | Reading | Use |
|---|---|---|
| 私 | watashi | "I" — polite default |
| 僕 | boku | "I" — softer male |
| 俺 | ore | "I" — rough/boastful male |
| お前 | omae | "you" — rude unless very close |

Work because pronoun vary along genuine comparable dimension (form, reading, register).

### Bad use

| Topic | Description |
|---|---|
| Yakuza | Organized crime |
| Public Safety | Government agency |
| Senpai | Senior at work |

Glossary that should be paragraph series. Table add nothing when each row independent + no shared dimension.

## Citations and sourcing

Don't trust parametric knowledge for factual claim. Ground guide in trusted source: user's own notes (Notion), primary docs, high-reputation reference. Nontrivial factual claim → cite it (inline link or short source line). Citation raise trust + give student a primary source to go deeper.

Each guide should name **one primary source** — the single highest-quality resource on the topic — near the top, so student know where to read/watch beyond the guide.

Don't over-cite: common knowledge for the audience need no footnote. Cite what a skeptical student would question.

## Glossary

Topic with own nomenclature → glossary is essential reference material. Short guide (or appendix section): term, one-line definition, minimal example. Prose paragraph per term, not table (see Tables — bad use).

Once glossary exist, **adhere to it everywhere**: every card, guide, quiz use the glossary's term + spelling. Drift between material = student learn two names for one thing.

## Cross-references

Guide section pair with flashcard deck or exercise → say so:

```markdown
## Imperative forms

[explanation here]

For drilling: see **Commands** flashcard deck.
For grammar pattern practice: see **Command → Dictionary Form** deck.
```

Help student understand how material fit together. Learn concept here, drill there, practice elsewhere.

## "How to use" closing

Longer guide combining with other material → end with brief guidance:

```markdown
## How to use this guide

Read through once before starting Volume 1. When you hit a scene that involves any of these concepts (Aki giving Denji a polite scolding, someone calling someone お前 with hostility, a contract scene), come back and re-read the relevant section. The cultural understanding compounds over time.
```

Skip for very short or self-explanatory guide.

## NOT belong in study guide

- Vocabulary list (use flashcard or include as reference appendix only)
- Drillable fact student should memorize (use flashcard)
- Active practice content (use exercise)
- Anything student supposed to reference once + never look at again (just put inline where needed)

## Self-critique checklist

Before deliver:

- [ ] Title clear indicate scope
- [ ] Each section has hook + explain + example + "so what"
- [ ] Prose default; list/table only where add value
- [ ] No section exist just to pad
- [ ] Cross-reference to flashcard/exercise present where relevant
- [ ] Nontrivial claim cited; one primary source named
- [ ] Terminology match the subject glossary (if one exist)
- [ ] No section is bullet list that should be paragraph
- [ ] No truly drillable content buried in prose
- [ ] Student can use without need additional context not supplied
