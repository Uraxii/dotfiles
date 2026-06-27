# Quiz Format Reference

Quiz = diagnostic practice that feeds a progress tracker. Unlike a plain exercise set, every
quiz here is **tracked**: each question targets one atomic item, results update a Mastery DB,
and the next quiz is weighted toward weak/unknown items. No untracked one-shot quizzes — if the
user wants questions, they get a tracked quiz.

Quiz extends the exercise format with four rules:
1. **Hide the target.** The visible question must not name the item it tests. Recognition from a
   scenario is the skill. The reveal lives in the answer key only.
2. **Mark confidence with "Not Sure."** Every question carries a "Not Sure"
   checkbox the user ticks *alongside* an answer (it does not replace answering). The answer is
   still scored on its merits, but a Not Sure tick flags low confidence: it sets `Review soon` and
   never lets the item reach `solid` on that attempt (Not Sure-correct → `learning`, not `solid`;
   Not Sure-wrong → `weak`). A blank answer is the only true gap → `weak` / `dontknow`. See
   `progress-tracking.md`.
3. **Difficulty rides mastery.** weak/unseen item → recall-level. solid item → re-test a level
   harder (edge case, why a partial answer fails). See `progress-tracking.md` for state.
4. **Point-weighted rubrics on free-text/code.** Every free-text question (short, code-review,
   diagram, and the non-code exercise types) carries a rubric worth a whole-number point total,
   broken into discrete checkpoints. Pick the total by depth, not a fixed value:
   - **1 pt** — a single recall/recognition answer with one checkpoint, where appropriate.
   - **3 pts** — single concept; name-the-flaw / one-fix (most L1 items).
   - **5 pts** — two-part reasoning, or flaw + fix + why-the-partial-fails.
   - **10 pts** — multi-step design, threat-model, or several independent checkpoints.
   A 1-pt question is all-or-nothing; 3/5/10 split the total into weighted checkpoints (e.g.
   10 = 4 identify + 4 fix + 2 idiomatic detail) and state them. mcq/multi are NOT point-weighted
   — score by correct option / partial-for-multi.
   **Scoring bands → mastery** (scale to the question's total): full = correct, mid = partial,
   low/zero = missed; a blank answer is a gap, not a miss, and a ticked "Not Sure" keeps the scored
   result but flags it for review (never `solid` that attempt). These bands drive the state
   transition in `progress-tracking.md`. Write bands as fractions of the total, e.g. for 5 pts:
   "5 = correct, 2.5–4 = partial, ≤2 = missed." A 1-pt question is simply "1 = correct, 0 =
   missed."

## Question types

Mix across a quiz — never all one type. Each maps to exactly one item.

- **mcq** — scenario + 4-5 options, one correct. Distractors plausible: adjacent concept, right
  idea wrong layer, real-but-insufficient.
- **multi** — select all that apply. Separates necessary from decoy. Partial credit.
- **code-review** — short snippet (JS/TS/C#/Python, or the subject's language) with the flaw.
  Student names the flaw + fix. Rubric = discrete checkpoints. Code subjects only.
- **short** — open "how/why/implement X". Rubric of required points + model answer.
- **diagram** — reason over a Mermaid figure with a gap or a choice between two designs.
- Non-code subjects swap code-review/diagram for the exercise types (translation, problem set,
  derivation, cloze) under the same hide-the-target + tracked rules.

## Notion page layout

Build the quiz as a page under the subject's sub-page (inside the workspace-root "Practice
Quizzes" hub; see `progress-tracking.md` for the layout). Match the structure the user already
has (see an existing quiz page for the pattern):

- Title `Quiz — YYYY-MM-DD`, icon a Notion line-icon URL (no emoji).
- Short intro: practice not a test, no timer, take a guess and tick "Not Sure" if not confident,
  open the key or say "grade today's quiz".
- Per question: `### Q<n> — <type label>`, the scenario, code in fenced blocks with a language,
  diagrams in ```mermaid, options plus a `- [ ] Not Sure` to-do, a
  `**Your answer:**` label for free-text. `---` between questions.
- A collapsed `<details>` answer-key toggle at the end: per question, reveal item id + short
  name + level, model answer / correct option(s), the point-weighted rubric with its checkpoint
  breakdown and scoring bands (rule 4), common mistake, idiomatic fix in the relevant
  language(s), and a `Covered:` line listing the item ids. Prefer inline `code` inside the toggle.

6-8 questions per quiz. Verbatim source text (if any) goes in the key, not the visible question.

## Self-critique before delivering

- [ ] Each question discriminates real understanding — a guess can't pass
- [ ] Distractors plausible; no give-away phrasing leaks the item
- [ ] Styles varied; at least one applied/code/diagram question where the subject allows
- [ ] Difficulty matches each item's level and current mastery
- [ ] Answer key correct, with the item reveal and idiomatic fixes
- [ ] Every free-text/code question has a point-weighted rubric (1/3/5/10 by depth) with bands
- [ ] Every covered item exists in the Mastery DB (see `progress-tracking.md`)
